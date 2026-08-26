"""
strata.learn.forge
==================
THE FORGE -- turning sample lines into a working grammar.
Requirements (e) and (i), and the part of the demo people remember.

Onboarding a new log source conventionally takes two to five engineer-days:
read the vendor's field reference, hand-write regex, test, discover the edge
cases, rewrite. The Forge turns that into: paste samples, read the proposal,
correct a couple of names, publish. Minutes, no code, no restart.

HOW A MAPPING IS PROPOSED

Two independent signals, combined:

  BY NAME   `srcip`, `src_ip`, `source-address`, `client_addr` all clearly mean
            the same thing. A pattern table covers the spellings vendors
            actually use.

  BY VALUE  A column named `col_08` tells you nothing -- but if every value in
            it is an IPv4 address, and the column two later is always an
            integer under 65536, you are looking at an endpoint and its port.

The second is the one that matters. Name matching only works on sources
considerate enough to label their fields; value inference works on positional
CSV, where there are no names at all. Together they get most of the way, and
the human supplies the meaning a machine cannot infer -- which is the right
division of labour.

WE PROPOSE. WE NEVER AUTO-PUBLISH.

A grammar that silently starts mis-mapping a field is precisely the failure
this project exists to eliminate, so shipping one without a human reading it
would be self-defeating. The proposal is an ordinary grammar file, validated
by exactly the same schema as a hand-written one -- there is no special case
and no privileged path.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from ..parse.grammar import Grammar
from ..parse.shapes import Shape
from ..parse.timeparse import sniff as sniff_time
from .induction import Induction, Profile, induce

# ---------------------------------------------------------------------------
# Name-based hints
# ---------------------------------------------------------------------------
# Ordered: first match wins, so specific patterns precede general ones.
NAME_HINTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^(src|source|client|orig|local|initiator)[_.\-]?(ip|addr|address|host)$", re.I),
     "src_endpoint.ip"),
    (re.compile(r"^(dst|dest|destination|server|remote|target|resp|responder)[_.\-]?(ip|addr|address|host)$", re.I),
     "dst_endpoint.ip"),
    (re.compile(r"^(src|source|client|local|orig)[_.\-]?port$", re.I), "src_endpoint.port"),
    (re.compile(r"^(dst|dest|destination|server|remote|resp)[_.\-]?port$", re.I), "dst_endpoint.port"),
    (re.compile(r"^(src|source|client)[_.\-]?(user|username|user_name)$", re.I), "actor.user.name"),
    (re.compile(r"^(user|username|usr|usrname|account)$", re.I), "actor.user.name"),
    (re.compile(r"^(src|source)[_.\-]?zone$", re.I), "src_endpoint.zone"),
    (re.compile(r"^(dst|dest|destination)[_.\-]?zone$", re.I), "dst_endpoint.zone"),
    (re.compile(r"^(proto|protocol|ipproto)$", re.I), "connection_info.protocol_name"),
    (re.compile(r"^(app|application|app_name|appi_name|service|app_proto)$", re.I), "app_name"),
    (re.compile(r"^(sent|out|tx|egress|upload)[_.\-]?(bytes?|octets?)$|^(bytes?|octets?)[_.\-]?(sent|out|tx)$", re.I),
     "traffic.bytes_out"),
    (re.compile(r"^(rcvd|recv|received|in|rx|ingress|download)[_.\-]?(bytes?|octets?)$|^(bytes?|octets?)[_.\-]?(rcvd|recv|received|in|rx)$", re.I),
     "traffic.bytes_in"),
    (re.compile(r"^(bytes?|octets?|size|length|len)$|^total[_.\-]?(bytes?|octets?)$", re.I),
     "traffic.bytes"),
    (re.compile(r"^(packets?|pkts?)$", re.I), "traffic.packets"),
    (re.compile(r"^(session|sess|conn|connection|flow)[_.\-]?(id|uid)?$", re.I),
     "connection_info.session_uid"),
    (re.compile(r"^(rule|policy|acl)[_.\-]?(name|id)?$", re.I), "firewall_rule.name"),
    (re.compile(r"^(url|uri|request|request_url)$", re.I), "http_request.url.text"),
    (re.compile(r"^(method|http_method|verb)$", re.I), "http_request.http_method"),
    (re.compile(r"^(host|hostname|device|devname|dvchost|origin|sensor)$", re.I),
     "device.hostname"),
    (re.compile(r"^(iface|interface|intf|in_iface|port_name)$", re.I),
     "src_endpoint.interface_name"),
    (re.compile(r"^(sig|signature)[_.\-]?(id|name)?$|^(msg|message|alert|title)$", re.I),
     "finding_info.title"),
    (re.compile(r"^(duration|elapsed|dur|took)[_.\-]?(ms|s|sec)?$", re.I), "duration"),
]

DISPOSITION_FIELD = re.compile(
    r"^(action|disposition|verdict|result|status|conn_state|outcome)$", re.I)

DISPOSITION_TABLE: dict[str, int] = {
    "allow": 1, "allowed": 1, "accept": 1, "accepted": 1, "permit": 1,
    "permitted": 1, "pass": 1, "ok": 1, "success": 1, "built": 1,
    "deny": 2, "denied": 2, "block": 2, "blocked": 2, "reject": 2,
    "rejected": 2, "refuse": 2, "refused": 2,
    "drop": 3, "dropped": 3, "discard": 3,
    "reset": 8, "rst": 8, "teardown": 1, "close": 8, "closed": 8,
}

SEVERITY_FIELD = re.compile(r"^(severity|level|sev|priority|prio)$", re.I)


def by_name(field_name: str) -> str | None:
    leaf = field_name.rsplit(".", 1)[-1]
    for pattern, path in NAME_HINTS:
        if pattern.match(field_name) or pattern.match(leaf):
            return path
    return None


# ---------------------------------------------------------------------------
# Value-based inference -- the part that works on unnamed columns
# ---------------------------------------------------------------------------

def by_value(profiles: list[Profile]) -> dict[str, str]:
    """Infer endpoints and ports from value shapes and adjacency.

    The rules are the ones a human uses reading an unfamiliar log:

      * The first two high-cardinality IPv4 fields are source and destination,
        in that order. Vendors overwhelmingly write source first.
      * A small integer immediately after an IPv4 field is that endpoint's
        port. Adjacency is the signal; the value range alone is far too weak,
        since half of everything is a small integer.
      * A field that is always a timestamp is the clock, and the earliest such
        field is the event time rather than a later processing time.

    Every one of these is a heuristic and can be wrong, which is exactly why
    the proposal is reviewed rather than published.
    """
    mapping: dict[str, str] = {}
    ordered = sorted(profiles, key=lambda p: (p.position if p.position >= 0 else 1 << 30))

    ip_fields = [p for p in ordered
                 if p.kind == "ipv4" and p.purity > 0.85 and p.distinct > 1]

    if ip_fields:
        mapping[ip_fields[0].key] = "src_endpoint.ip"
        if len(ip_fields) > 1:
            mapping[ip_fields[1].key] = "dst_endpoint.ip"

    # Ports by adjacency, only for positional sources where adjacency is real.
    index = {p.key: i for i, p in enumerate(ordered)}
    for ip_profile, path in ((ip_fields[0] if ip_fields else None, "src_endpoint.port"),
                             (ip_fields[1] if len(ip_fields) > 1 else None, "dst_endpoint.port")):
        if ip_profile is None or ip_profile.position < 0:
            continue
        start = index[ip_profile.key]
        for candidate in ordered[start + 1: start + 3]:
            if (candidate.kind == "port_or_int" and candidate.purity > 0.8
                    and candidate.key not in mapping):
                mapping[candidate.key] = path
                break

    return mapping


def pick_clock(profiles: list[Profile]) -> tuple[str, list[str]] | None:
    """Which field carries the event's own time, and in what format."""
    best: tuple[str, list[str]] | None = None
    for p in profiles:
        if not p.samples:
            continue
        named_time = re.search(r"time|date|ts$|^ts|stamp", p.key, re.I)
        if p.kind not in ("timestamp", "epoch_or_int") and not named_time:
            continue
        fmt = sniff_time(p.samples[0])
        if fmt is None:
            continue
        candidate = (p.key, [fmt])
        # Prefer an explicitly time-named field over a numeric lookalike: a
        # session id of the right magnitude is indistinguishable from an epoch.
        if named_time:
            return candidate
        if best is None:
            best = candidate
    return best


# ---------------------------------------------------------------------------
# The Forge
# ---------------------------------------------------------------------------

class Proposal:
    """A generated grammar plus everything a reviewer needs to judge it."""

    __slots__ = ("document", "yaml", "valid", "error", "induction",
                 "mapped", "discovered", "unmapped_fields", "confidence_notes")

    def __init__(self, document: dict, induction: Induction) -> None:
        self.document = document
        self.induction = induction
        self.yaml = yaml.safe_dump(document, sort_keys=False, allow_unicode=True,
                                   default_flow_style=False, width=100)
        emit = document.get("emit", {})
        self.mapped = len(emit.get("fields", {})) + len(emit.get("enums", {}))
        self.discovered = len(induction.profiles)
        claimed = set(emit.get("fields", {}).values()) | {
            m["source"] for m in emit.get("enums", {}).values()}
        self.unmapped_fields = [p.key for p in induction.profiles
                                if p.key not in claimed][:40]
        self.confidence_notes: list[str] = list(induction.notes)

        try:
            Grammar.model_validate(document)
            self.valid, self.error = True, None
        except Exception as exc:
            self.valid, self.error = False, str(exc)[:400]

    @property
    def coverage(self) -> float:
        return self.mapped / self.discovered if self.discovered else 0.0

    def report(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "error": self.error,
            "yaml": self.yaml,
            "grammar": self.document,
            "fields_discovered": self.discovered,
            "fields_mapped": self.mapped,
            "coverage": round(self.coverage, 3),
            "unmapped": self.unmapped_fields,
            "notes": self.confidence_notes,
            "induction": self.induction.report(),
        }


class Forge:
    """Sample lines in, reviewable grammar out."""

    def study(self, lines: list[str]) -> dict[str, Any]:
        """Step one of the UI: what IS this?"""
        return induce(lines).report()

    def propose(self, lines: list[str], grammar_id: str, vendor: str = "Unknown",
                product: str = "Unknown", names: list[str] | None = None,
                ocsf_class: int = 4001, category: int = 4) -> Proposal:
        """Step two: generate a complete, validated grammar."""
        result = induce(lines)

        if names:
            for i, p in enumerate(result.profiles):
                if i < len(names) and names[i]:
                    p.key = names[i]

        pipeline = self._pipeline(result)
        emit, coerce = self._emit(result, ocsf_class, category)
        clock = pick_clock(result.profiles)

        doc: dict[str, Any] = {
            "id": grammar_id,
            "version": "0.1.0",
            "vendor": vendor,
            "product": product,
            "title": f"{vendor} {product} (proposed by the Forge)",
            "family": result.shape.label,
            "signature": self._signature(result),
            "pipeline": pipeline,
        }
        if coerce:
            doc["coerce"] = coerce
        if clock:
            doc["clock"] = {"field": clock[0], "formats": clock[1], "zone": "UTC"}
        elif result.syslog_wrapped:
            # No timestamp in the payload, but the syslog envelope has one and
            # the pipeline already extracts it. Using it beats falling back to
            # receipt time.
            doc["clock"] = {"field": "log_time", "formats": ["bsd"], "zone": "UTC"}
        doc["emit"] = emit

        return Proposal(doc, result)

    # ------------------------------------------------------------- internals

    def _signature(self, r: Induction) -> dict[str, Any]:
        sig: dict[str, Any] = {}
        if r.signature_literals:
            sig["must"] = r.signature_literals[:2]
            sig["weight"] = 0.9
        else:
            sig["pattern"] = _shape_pattern(r.shape)
            sig["weight"] = 0.6          # weak on purpose; a reviewer should tighten it
        return sig

    def _pipeline(self, r: Induction) -> list[dict[str, Any]]:
        steps: list[dict[str, Any]] = []
        if r.syslog_wrapped:
            steps.append({"syslog": "auto", "optional": True})

        if r.shape is Shape.JSON:
            steps.append({"json": True, "flatten_sep": "."})
        elif r.shape is Shape.CEF:
            steps.append({"cef": True})
        elif r.shape is Shape.LEEF:
            steps.append({"leef": True})
        elif r.shape is Shape.KV:
            pair_sep = "|" if _pipe_separated(r) else None
            step: dict[str, Any] = {"kv": True}
            if pair_sep:
                step["pair_sep"] = pair_sep
            steps.append(step)
        elif r.shape is Shape.CSV:
            steps.append({"columns": [p.key for p in r.profiles], "sep": ","})
        elif r.shape is Shape.DELIMITED:
            steps.append({"whitespace": [p.key for p in r.profiles]})
        else:
            pattern = _template_regex(r)
            if pattern:
                steps.append({"regex": pattern, "optional": True, "keep_body": True})

        if not steps:
            steps.append({"regex": "(?P<raw_message>.+)", "optional": True})
        return steps

    def _emit(self, r: Induction, cls: int, category: int
              ) -> tuple[dict[str, Any], dict[str, str]]:
        fields: dict[str, str] = {}
        enums: dict[str, Any] = {}
        coerce: dict[str, str] = {}

        value_map = by_value(r.profiles)

        for p in r.profiles:
            if p.kind == "empty":
                continue
            cast = p.coerce_type()
            if cast:
                coerce[p.key] = cast

            path = by_name(p.key) or value_map.get(p.key)
            if path and path not in fields:
                fields[path] = p.key

            leaf = p.key.rsplit(".", 1)[-1]
            if DISPOSITION_FIELD.match(leaf) and "disposition_id" not in enums:
                observed = {s.lower() for s in p.samples}
                table = {k: v for k, v in DISPOSITION_TABLE.items() if k in observed}
                enums["disposition_id"] = {
                    "source": p.key,
                    "table": table or DISPOSITION_TABLE,
                    "default": 99,
                    "keep": "disposition_orig",
                }
            elif SEVERITY_FIELD.match(leaf) and "severity_id" not in enums:
                if p.kind in ("int", "port_or_int"):
                    enums["severity_id"] = {
                        "source": p.key,
                        "table": {"0": 1, "1": 1, "2": 2, "3": 2,
                                  "4": 3, "5": 3, "6": 4, "7": 5},
                        "default": 1,
                        "keep": "severity_orig",
                    }

        emit: dict[str, Any] = {"class": cls, "category": category,
                                "const": {"activity_id": 6}}
        if fields:
            emit["fields"] = fields
        if enums:
            emit["enums"] = enums
        return emit, coerce


def _pipe_separated(r: Induction) -> bool:
    """Does this KV source use '|' between pairs rather than whitespace?"""
    for tpl in r.templates[:1]:
        return "|" in "".join(tpl.get("template", []))
    for p in r.profiles[:6]:
        for s in p.samples[:3]:
            if "|" in s:
                return True
    return False


def _shape_pattern(shape: Shape) -> str:
    return {
        Shape.JSON: r"^\s*\{.*\}\s*$",
        Shape.KV: r"\w+=\S+\s+\w+=\S+",
        Shape.CSV: r"(?:[^,]*,){8,}",
        Shape.CEF: r"CEF:\d\|",
        Shape.LEEF: r"LEEF:\d",
        Shape.DELIMITED: r"^\S+(?:\s+\S+){4,}$",
    }.get(shape, r".{16,}")


def _template_regex(r: Induction) -> str | None:
    """Mined template -> named-capture regex.

    Constants are escaped literally; each variable slot becomes a named group.
    The names are placeholders until a human renames them, which is exactly
    the split: the machine finds the structure, the human supplies the meaning.
    """
    if not r.templates:
        return None
    template = r.templates[0]["template"]
    parts: list[str] = []
    slot = 0
    for token in template:
        if token == "<*>" or (token.startswith("<") and token.endswith(">")):
            parts.append(f"(?P<var_{slot:02d}>\\S+)")
            slot += 1
        else:
            parts.append(re.escape(token))
    return r"\s*".join(parts) if slot else None
