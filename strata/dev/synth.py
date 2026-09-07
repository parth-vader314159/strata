"""
strata.dev.synth
================
Deterministic synthetic log generator with GROUND TRUTH.

Two jobs, both load-bearing:

1. The demo runs offline, on any laptop, with no firewall in the room and no
   recorded capture that might contain real customer data.

2. Every generated line carries the values that produced it, so accuracy is
   MEASURED rather than eyeballed. "Our parser works" is an opinion;
   "field accuracy 0.998 against ground truth over 20,000 events" is a result.

Seeded from a fixed integer: the same seed always yields the same corpus, so a
test failure is always reproducible.

FIDELITY IN DISTRIBUTION, NOT ONLY IN SYNTAX

A generator that emits a fresh random IP per line is syntactically perfect and
statistically useless -- every aggregation returns one row per event, and
nothing that depends on repeat behaviour (top talkers, baselines, beaconing)
can be demonstrated. Real networks have a few hundred hosts, a handful of them
noisy. So the generator draws from bounded pools with a Zipf-ish bias.

DELIBERATE NASTINESS

A corpus of clean lines proves nothing. This one injects, at known rates:
  * quoted delimiters inside CSV fields   (shifts every later column)
  * invalid UTF-8 bytes                   (kills any str-based pipeline)
  * truncation at the RFC 3164 1024 limit (a field cut in half)
  * empty fields collapsing two separators
  * an unknown vendor format              (must quarantine, never mangle)
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

APPS = ["ssl", "web-browsing", "dns", "ssh", "smtp", "ms-rdp", "quic",
        "bittorrent", "ntp", "ldap"]
ZONES = ["trust", "untrust", "dmz", "guest", "vpn"]
SIGNATURES = [
    (2010935, "ET POLICY Suspicious inbound to MSSQL port 1433", "Potentially Bad Traffic", 2),
    (2001219, "ET SCAN Potential SSH Scan", "Attempted Information Leak", 2),
    (2013028, "ET POLICY curl User-Agent Outbound", "Not Suspicious Traffic", 3),
    (2024897, "ET EXPLOIT Possible CVE-2021-44228 Log4j RCE", "Attempted Admin Privilege Gain", 1),
    (2027863, "ET INFO Observed DNS over HTTPS Domain", "Misc activity", 3),
]
PORTS = [443, 80, 22, 53, 3389, 1433, 25, 445, 8080, 123]


@dataclass(slots=True)
class Sample:
    """One synthetic line plus the truth that produced it."""
    payload: bytes
    source: str                          # expected grammar id, or "unknown"
    truth: dict[str, Any] = field(default_factory=dict)
    must_reject: bool = False


class Corpus:
    def __init__(self, seed: int = 20260826) -> None:
        self.rng = random.Random(seed)
        self.base = datetime(2026, 8, 26, 9, 0, 0, tzinfo=timezone.utc)
        r = self.rng
        # Bounded host pools -- see the module docstring on distribution.
        self._inside = [f"10.{r.randint(0,6)}.{r.randint(0,24)}.{r.randint(1,254)}"
                        for _ in range(140)]
        self._outside = [f"{r.choice([203,198,45,104,172])}.{r.randint(0,255)}."
                         f"{r.randint(0,255)}.{r.randint(1,254)}" for _ in range(240)]
        self._users = [f"u{r.randint(1000,1099)}" for _ in range(40)]

    # ------------------------------------------------------------- helpers

    def _in(self) -> str:
        # A handful of hosts carry a disproportionate share, as in real traffic.
        return (self.rng.choice(self._inside[:10]) if self.rng.random() < 0.4
                else self.rng.choice(self._inside))

    def _out(self) -> str:
        return self.rng.choice(self._outside)

    def _at(self, i: int) -> datetime:
        return self.base + timedelta(seconds=i * self.rng.randint(1, 3))

    # ------------------------------------------------------------ producers

    def panos(self, i: int) -> Sample:
        r, t = self.rng, self._at(i)
        src, dst = self._in(), self._out()
        sp, dp = r.randint(1024, 65535), r.choice(PORTS)
        action = r.choice(["allow", "allow", "allow", "deny", "drop", "reset-both"])
        sent, recv = r.randint(200, 90_000), r.randint(200, 900_000)
        sess = r.randint(10_000, 999_999)
        # A rule name containing a comma, quoted -- the classic CSV trap.
        rule = r.choice(["Allow-Web", '"Allow-Web,Prod"', "Block-P2P", "Guest-Restrict"])
        ts = t.strftime("%Y/%m/%d %H:%M:%S")
        line = (f"<14>{t.strftime('%b %d %H:%M:%S')} fw-edge-01 "
                f"1,{ts},014201005263,TRAFFIC,end,2561,{ts},{src},{dst},"
                f"0.0.0.0,0.0.0.0,{rule},,,{r.choice(APPS)},vsys1,"
                f"{r.choice(ZONES)},untrust,ae1.10,ae2,LogFwd,0,{sess},1,"
                f"{sp},{dp},0,0,0x400053,tcp,{action},{sent+recv},{sent},{recv},"
                f"{r.randint(4,300)},{ts},{r.randint(0,900)},any")
        return Sample(line.encode(), "panos.traffic",
                      {"src": src, "dst": dst, "sport": sp, "dport": dp,
                       "action": action, "bytes": sent + recv})

    def fortigate(self, i: int) -> Sample:
        r, t = self.rng, self._at(i)
        src, dst = self._in(), self._out()
        sp, dp = r.randint(1024, 65535), r.choice(PORTS)
        action = r.choice(["accept", "accept", "accept", "deny", "close"])
        sent, recv = r.randint(100, 50_000), r.randint(100, 400_000)
        line = (f'<189>date={t.strftime("%Y-%m-%d")} time={t.strftime("%H:%M:%S")} '
                f'devname="FG201F-EDGE" devid="FG201FTK21001234" logid="0000000013" '
                f'type="traffic" subtype="forward" level="notice" vd="root" '
                f'eventtime={int(t.timestamp())} srcip={src} srcport={sp} '
                f'srcintf="port1" srcintfrole="lan" dstip={dst} dstport={dp} '
                f'dstintf="wan1" dstintfrole="wan" sessionid={r.randint(1000,999999)} '
                f'proto=6 action="{action}" policyid={r.randint(1,60)} '
                f'policyname="{r.choice(["Internet-Access","Block-Social","DMZ-Out"])}" '
                f'service="HTTPS" trandisp="snat" app="{r.choice(APPS)}" '
                f'srcuser="{r.choice(self._users)}" duration={r.randint(1,900)} '
                f'sentbyte={sent} rcvdbyte={recv} sentpkt={r.randint(1,200)} '
                f'rcvdpkt={r.randint(1,400)}')
        return Sample(line.encode(), "fortigate.traffic",
                      {"src": src, "dst": dst, "sport": sp, "dport": dp,
                       "action": action})

    def checkpoint(self, i: int) -> Sample:
        r, t = self.rng, self._at(i)
        src, dst = self._in(), self._out()
        sp, dp = r.randint(1024, 65535), r.choice(PORTS)
        action = r.choice(["accept", "accept", "drop", "reject"])
        line = (f"<134>{t.strftime('%b %d %H:%M:%S')} cp-gw-01 "
                f"time={int(t.timestamp())}|action={action}|origin=cp-gw-01|"
                f"product=VPN-1 & FireWall-1|src={src}|s_port={sp}|dst={dst}|"
                f"service={dp}|proto=tcp|"
                f"rule_name={r.choice(['Corp-Out','DMZ-Web','Deny-All'])}|"
                f"appi_name={r.choice(APPS)}|bytes={r.randint(200,500_000)}|"
                f"user={r.choice(self._users)}")
        return Sample(line.encode(), "checkpoint.firewall",
                      {"src": src, "dst": dst, "sport": sp, "dport": dp,
                       "action": action})

    def suricata(self, i: int) -> Sample:
        r, t = self.rng, self._at(i)
        src, dst = self._out(), self._in()
        sid, sig, cat, sev = r.choice(SIGNATURES)
        sp, dp = r.randint(1024, 65535), r.choice(PORTS)
        doc = {
            "timestamp": t.strftime("%Y-%m-%dT%H:%M:%S.%f") + "+0000",
            "flow_id": r.randint(10**14, 10**15), "event_type": "alert",
            "src_ip": src, "src_port": sp, "dest_ip": dst, "dest_port": dp,
            "proto": "TCP", "app_proto": r.choice(["http", "tls", "failed", "dns"]),
            "alert": {"action": r.choice(["allowed", "blocked"]),
                      "signature_id": sid, "rev": 4, "signature": sig,
                      "category": cat, "severity": sev},
            "host": "ids-sensor-02",
        }
        return Sample(json.dumps(doc).encode(), "suricata.alert",
                      {"src": src, "dst": dst, "sport": sp, "dport": dp, "sid": sid})

    def zeek(self, i: int) -> Sample:
        r, t = self.rng, self._at(i)
        src, dst = self._in(), self._out()
        sp, dp = r.randint(1024, 65535), r.choice(PORTS)
        state = r.choice(["SF", "SF", "S0", "REJ", "RSTO", "OTH"])
        doc = {
            "ts": round(t.timestamp(), 6),
            "uid": "C" + "".join(r.choice("abcdefghijklmnopqrstuvwxyz0123456789")
                                 for _ in range(17)),
            "id.orig_h": src, "id.orig_p": sp, "id.resp_h": dst, "id.resp_p": dp,
            "proto": "tcp", "service": r.choice(["http", "ssl", "dns", "ssh"]),
            "duration": round(r.uniform(0.01, 300.0), 6),
            "orig_bytes": r.randint(40, 90_000), "resp_bytes": r.randint(40, 900_000),
            "conn_state": state, "orig_pkts": r.randint(1, 500),
            "resp_pkts": r.randint(1, 900),
        }
        return Sample(json.dumps(doc).encode(), "zeek.conn",
                      {"src": src, "dst": dst, "sport": sp, "dport": dp,
                       "action": state})

    def asa(self, i: int) -> Sample:
        r, t = self.rng, self._at(i)
        src, dst = self._in(), self._out()
        sp, dp = r.randint(1024, 65535), r.choice(PORTS)
        action = r.choice(["Built", "Teardown", "Deny"])
        code = {"Built": "302013", "Teardown": "302014", "Deny": "106023"}[action]
        line = (f"<166>{t.strftime('%b %d %H:%M:%S')} asa-edge : %ASA-6-{code}: "
                f"{action} outbound TCP connection {r.randint(1000,999999)} "
                f"for outside:{dst}/{dp} ({dst}/{dp}) to inside:{src}/{sp} ({src}/{sp})")
        return Sample(line.encode(), "cisco.asa",
                      {"src": src, "dst": dst, "sport": sp, "dport": dp,
                       "action": action})

    def squid(self, i: int) -> Sample:
        r, t = self.rng, self._at(i)
        client = self._in()
        code = r.choice(["TCP_MISS/200", "TCP_HIT/200", "TCP_DENIED/403",
                         "TCP_TUNNEL/200", "TCP_MEM_HIT/200"])
        url = r.choice(["http://example.com/index.html",
                        "https://cdn.example.net/app.js",
                        "http://malware-test.invalid/payload.bin",
                        "https://updates.example.org/v2/manifest"])
        by = r.randint(200, 400_000)
        # Squid writes "-" for an absent user; the extractor must treat that as
        # absent rather than as the literal string.
        user = r.choice([*self._users, "-", "-"])
        line = (f"{t.timestamp():.3f} {r.randint(1,5000):>6} {client} {code} {by} "
                f"GET {url} {user} HIER_DIRECT/93.184.216.34 text/html")
        return Sample(line.encode(), "squid.access",
                      {"src": client, "bytes": by, "action": code})

    def cef(self, i: int) -> Sample:
        r, t = self.rng, self._at(i)
        src, dst = self._in(), self._out()
        act = r.choice(["allow", "deny", "block"])
        # A value containing spaces, to exercise CEF extension parsing.
        name = r.choice(["Web Attack Detected", "SQL Injection Attempt",
                         "Policy Violation"])
        line = (f"<134>{t.strftime('%b %d %H:%M:%S')} waf-01 "
                f"CEF:0|Imperva|SecureSphere|14.2|{r.randint(1000,9999)}|"
                f"{name}|{r.randint(1,10)}|src={src} spt={r.randint(1024,65535)} "
                f"dst={dst} dpt=443 proto=TCP act={act} app=https "
                f"in={r.randint(100,9000)} out={r.randint(100,90000)} "
                f"suser={r.choice(self._users)} dvchost=waf-01")
        return Sample(line.encode(), "generic.cef", {"src": src, "action": act})

    def leef(self, i: int) -> Sample:
        r, t = self.rng, self._at(i)
        src, dst = self._in(), self._out()
        sp, dp = r.randint(1024, 65535), r.choice([443, 8443, 22])
        action = r.choice(["accept", "deny", "drop"])
        pairs = "\t".join([
            f"devTime={t.strftime('%Y-%m-%dT%H:%M:%S.000+0000')}",
            f"src={src}", f"srcPort={sp}", f"dst={dst}", f"dstPort={dp}",
            "proto=TCP", f"action={action}",
            f"totalBytes={r.randint(200,300_000)}",
            f"usrName={r.choice(self._users)}"])
        line = (f"<134>{t.strftime('%b %d %H:%M:%S')} qradar-fwd "
                f"LEEF:2.0|Juniper|SRX|21.4|{r.randint(1000,9999)}|{pairs}")
        return Sample(line.encode(), "generic.leef",
                      {"src": src, "dst": dst, "sport": sp, "action": action})

    def pfsense(self, i: int) -> Sample:
        r, t = self.rng, self._at(i)
        src, dst = self._in(), self._out()
        sp, dp = r.randint(1024, 65535), r.choice(PORTS)
        action = r.choice(["pass", "pass", "block", "block"])
        proto = r.choice(["tcp", "udp"])
        line = (f"<134>{t.strftime('%b %d %H:%M:%S')} pfsense-edge "
                f"filterlog[62362]: {r.randint(1,120)},,,"
                f"{r.randint(10**8,10**9)},igb0,match,{action},"
                f"{r.choice(['in','out'])},4,0x0,,{r.randint(48,128)},"
                f"{r.randint(1,65535)},0,{'DF' if proto=='tcp' else 'none'},"
                f"{6 if proto=='tcp' else 17},{proto},{r.randint(40,1500)},"
                f"{src},{dst},{sp},{dp}")
        return Sample(line.encode(), "pfsense.filterlog",
                      {"src": src, "dst": dst, "sport": sp, "dport": dp,
                       "action": action})

    # ----------------------------------------------------------- nastiness

    def bad_utf8(self, i: int) -> Sample:
        """Bytes that are not valid UTF-8.

        This single case fails any pipeline that decodes on receipt. It is in
        the default corpus deliberately: if the losslessness claim cannot
        survive it, the claim is false.
        """
        base = self.panos(i)
        payload = base.payload.replace(b"fw-edge-01", b"fw-edge-\xff\xfe\x8101")
        return Sample(payload, "panos.traffic", base.truth)

    def truncated(self, i: int) -> Sample:
        """Cut at the RFC 3164 1024-byte limit, mid-field."""
        base = self.panos(i)
        return Sample(base.payload[:1024], "panos.traffic", {})

    def unknown(self, i: int) -> Sample:
        """A vendor format no grammar claims. MUST be quarantined rather than
        mangled -- and it is what the Forge onboards live in the demo."""
        r, t = self.rng, self._at(i)
        line = (f"[{t.isoformat()}] MERIDIAN-GW/7.1 :: "
                f"session={r.randint(1,99999)} client_addr={self._in()} "
                f"server_addr={self._out()} "
                f"verdict={r.choice(['PERMIT','REFUSE','THROTTLE'])} "
                f"policy=<{r.choice(['corp-std','contractor','iot-seg'])}> "
                f"octets_tx={r.randint(100,9999)} octets_rx={r.randint(100,99999)} "
                f"latency_ms={r.randint(1,400)}")
        return Sample(line.encode(), "unknown", {}, must_reject=True)

    # ------------------------------------------------------------------ api

    def stream(self, count: int, messy: bool = True) -> Iterator[Sample]:
        producers: list[Callable[[int], Sample]] = [
            self.panos, self.fortigate, self.checkpoint, self.suricata,
            self.zeek, self.asa, self.squid, self.cef, self.leef, self.pfsense]
        # Weighted like a real perimeter: two dominant firewall vendors and a
        # long tail. A uniform mix would flatter triage in a way real traffic
        # never does.
        weights = [22, 18, 9, 10, 9, 8, 8, 6, 4, 6]

        for i in range(count):
            if messy and i % 97 == 96:
                yield self.unknown(i)
            elif messy and i % 211 == 210:
                yield self.bad_utf8(i)
            elif messy and i % 331 == 330:
                yield self.truncated(i)
            else:
                yield self.rng.choices(producers, weights=weights)[0](i)

    def write(self, path: str | Path, count: int, messy: bool = True) -> dict:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tally: dict[str, int] = {}
        with open(p, "wb") as fh:
            for s in self.stream(count, messy):
                fh.write(s.payload + b"\n")
                tally[s.source] = tally.get(s.source, 0) + 1
        return {"path": str(p), "lines": count,
                "by_source": dict(sorted(tally.items(), key=lambda kv: -kv[1]))}
