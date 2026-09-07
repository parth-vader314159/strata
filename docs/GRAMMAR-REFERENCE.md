# Grammar reference

**Generated from `grammars/*.yaml` by `tools/gen_reference.py` — do not edit.**
A hand-written mapping document drifts from the code within a week. This one
cannot, because it is derived from the files the engine loads. CI fails if the
committed copy is stale.

Target schema **OCSF 1.8.0** · 10 grammars · 7 structural families

## Coverage by structural family

Coverage is argued by structural family, not product count. A new source in a
family already handled is a configuration change, not a development task.

| Family | Grammars | What makes it distinct |
|---|---|---|
| `cef` | `generic.cef` | pipe header + key=value extension; covers any CEF-speaking vendor |
| `csv` | `panos.traffic`, `pfsense.filterlog` | positional columns, no names on the wire; one shifted column is a silent failure |
| `delimited` | `squid.access` | whitespace-positional, no quoting, last column absorbs the rest |
| `freeform` | `cisco.asa` | values embedded in an English sentence written for a human |
| `json` | `suricata.alert`, `zeek.conn` | already structured — all the work is in the mapping |
| `kv` | `checkpoint.firewall`, `fortigate.traffic` | self-describing `key=value`; the pair separator varies by vendor |
| `leef` | `generic.leef` | pipe header + tab-separated pairs; covers any LEEF-speaking vendor |

## `checkpoint.firewall` — Check Point Security Gateway

- **Version** `2.0.0` · **Family** `kv` · **OCSF class** `4001` (category `4`)
- **Compiled pipeline** `syslog?` → `kv`
- **Signature** must contain `|origin=`, any of ['product=VPN-1', '|s_port=', '|service='] (weight 0.95)

**Timestamp** — `time`, formats `epoch`, zone `UTC`.

| OCSF field | Vendor field | Type |
|---|---|---|
| `actor.user.name` | `user` | str |
| `app_name` | `appi_name` | str |
| `connection_info.protocol_name` | `proto` | str |
| `device.hostname` | `origin` | str |
| `dst_endpoint.ip` | `dst` | str |
| `dst_endpoint.port` | `service` | int |
| `firewall_rule.name` | `rule_name` | str |
| `src_endpoint.ip` | `src` | str |
| `src_endpoint.port` | `s_port` | int |
| `traffic.bytes` | `bytes` | int |
| `activity_id` | *(constant)* | `6` |
| `severity_id` | *(constant)* | `1` |

**Enum collapse** — the vendor's own word is always retained.

- `disposition_id` ← `action`: `accept`→1, `allow`→1, `drop`→3, `reject`→2, `block`→2, `encrypt`→1, `decrypt`→1 (default `99`), original in `disposition_orig`

---

## `cisco.asa` — Cisco ASA

- **Version** `2.0.0` · **Family** `freeform` · **OCSF class** `4001` (category `4`)
- **Compiled pipeline** `syslog?` → `regex` → `regex?` → `regex?` → `regex?`
- **Signature** matches `%ASA-\d-\d{6}` (weight 0.96)

**Timestamp** — `log_time`, formats `bsd`, zone `UTC`.

| OCSF field | Vendor field | Type |
|---|---|---|
| `connection_info.protocol_name` | `protocol` | str |
| `connection_info.session_uid` | `session_id` | str |
| `device.hostname` | `log_host` | str |
| `dst_endpoint.ip` | `destination_address` | str |
| `dst_endpoint.port` | `destination_port` | int |
| `dst_endpoint.zone` | `destination_zone` | str |
| `metadata.event_code` | `asa_code` | str |
| `src_endpoint.ip` | `source_address` | str |
| `src_endpoint.port` | `source_port` | int |
| `src_endpoint.zone` | `source_zone` | str |
| `activity_id` | *(constant)* | `6` |

**Enum collapse** — the vendor's own word is always retained.

- `disposition_id` ← `action`: `built`→1, `teardown`→1, `deny`→2, `denied`→2, `dropped`→3 (default `99`), original in `disposition_orig`
- `severity_id` ← `asa_severity`: `0`→6, `1`→6, `2`→5, `3`→4, `4`→3, `5`→2, `6`→1, `7`→1 (default `1`), original in `severity_orig`

---

## `fortigate.traffic` — Fortinet FortiGate

- **Version** `2.0.0` · **Family** `kv` · **OCSF class** `4001` (category `4`)
- **Compiled pipeline** `syslog?` → `kv`
- **Signature** must contain `devname=`, any of ['type="traffic"', 'type=traffic'] (weight 0.96)

**Timestamp** — `eventtime`, formats `epoch`, `epoch_ms`, zone `UTC`.

| OCSF field | Vendor field | Type |
|---|---|---|
| `actor.user.name` | `srcuser` | str |
| `app_name` | `app` | str |
| `connection_info.session_uid` | `sessionid` | str |
| `device.hostname` | `devname` | str |
| `device.uid` | `devid` | str |
| `dst_endpoint.interface_name` | `dstintf` | str |
| `dst_endpoint.ip` | `dstip` | str |
| `dst_endpoint.port` | `dstport` | int |
| `dst_endpoint.zone` | `dstintfrole` | str |
| `duration` | `duration` | int |
| `firewall_rule.name` | `policyname` | str |
| `src_endpoint.interface_name` | `srcintf` | str |
| `src_endpoint.ip` | `srcip` | str |
| `src_endpoint.port` | `srcport` | int |
| `src_endpoint.zone` | `srcintfrole` | str |
| `traffic.bytes_in` | `rcvdbyte` | int |
| `traffic.bytes_out` | `sentbyte` | int |
| `activity_id` | *(constant)* | `6` |
| `severity_id` | *(constant)* | `1` |

**Enum collapse** — the vendor's own word is always retained.

- `disposition_id` ← `action`: `accept`→1, `allow`→1, `deny`→2, `block`→2, `drop`→3, `close`→8, `timeout`→99 (default `99`), original in `disposition_orig`

---

## `generic.cef` — Generic CEF

- **Version** `2.0.0` · **Family** `cef` · **OCSF class** `4001` (category `4`)
- **Compiled pipeline** `syslog?` → `cef`
- **Signature** matches `CEF:\d\|` (weight 0.93)

**Timestamp** — `log_time`, formats `bsd`, zone `UTC`.

| OCSF field | Vendor field | Type |
|---|---|---|
| `actor.user.name` | `suser` | str |
| `app_name` | `app` | str |
| `connection_info.protocol_name` | `proto` | str |
| `device.hostname` | `dvchost` | str |
| `dst_endpoint.ip` | `dst` | str |
| `dst_endpoint.port` | `dpt` | int |
| `finding_info.title` | `cef_name` | str |
| `finding_info.uid` | `cef_signature_id` | str |
| `metadata.product.name` | `cef_product` | str |
| `metadata.product.vendor_name` | `cef_vendor` | str |
| `metadata.product.version` | `cef_device_version` | str |
| `src_endpoint.ip` | `src` | str |
| `src_endpoint.port` | `spt` | int |
| `traffic.bytes_in` | `in` | int |
| `traffic.bytes_out` | `out` | int |
| `activity_id` | *(constant)* | `6` |

**Enum collapse** — the vendor's own word is always retained.

- `disposition_id` ← `act`: `allow`→1, `permit`→1, `accept`→1, `deny`→2, `block`→2, `drop`→3, `reset`→8 (default `99`), original in `disposition_orig`
- `severity_id` ← `cef_severity`: `0`→1, `1`→1, `2`→2, `3`→2, `4`→3, `5`→3, `6`→4, `7`→4, `8`→5, `9`→5, `10`→6 (default `1`), original in `severity_orig`

---

## `generic.leef` — Generic LEEF

- **Version** `2.0.0` · **Family** `leef` · **OCSF class** `4001` (category `4`)
- **Compiled pipeline** `syslog?` → `leef`
- **Signature** matches `LEEF:\d(\.\d)?\|` (weight 0.93)

**Timestamp** — `devTime`, formats `iso8601`, `epoch_ms`, `epoch`, zone `UTC`.

| OCSF field | Vendor field | Type |
|---|---|---|
| `actor.user.name` | `usrName` | str |
| `connection_info.protocol_name` | `proto` | str |
| `dst_endpoint.ip` | `dst` | str |
| `dst_endpoint.port` | `dstPort` | int |
| `finding_info.uid` | `leef_event_id` | str |
| `metadata.product.name` | `leef_product` | str |
| `metadata.product.vendor_name` | `leef_vendor` | str |
| `metadata.product.version` | `leef_device_version` | str |
| `src_endpoint.ip` | `src` | str |
| `src_endpoint.port` | `srcPort` | int |
| `traffic.bytes` | `totalBytes` | int |
| `activity_id` | *(constant)* | `6` |

**Enum collapse** — the vendor's own word is always retained.

- `disposition_id` ← `action`: `accept`→1, `allow`→1, `permit`→1, `deny`→2, `block`→2, `drop`→3, `reject`→2 (default `99`), original in `disposition_orig`

---

## `panos.traffic` — Palo Alto Networks PAN-OS

- **Version** `2.0.0` · **Family** `csv` · **OCSF class** `4001` (category `4`)
- **Compiled pipeline** `syslog?` → `columns`
- **Signature** must contain `,TRAFFIC,`, any of [',end,', ',start,', ',drop,', ',deny,'] (weight 0.97)

**Timestamp** — `generated_time`, formats `slashed`, zone `UTC`.

| OCSF field | Vendor field | Type |
|---|---|---|
| `actor.user.name` | `source_user` | str |
| `app_name` | `application` | str |
| `connection_info.protocol_name` | `protocol` | str |
| `connection_info.session_uid` | `session_id` | str |
| `device.hostname` | `log_host` | str |
| `device.uid` | `serial` | str |
| `dst_endpoint.ip` | `destination_address` | str |
| `dst_endpoint.port` | `destination_port` | int |
| `dst_endpoint.zone` | `destination_zone` | str |
| `duration` | `elapsed_seconds` | int |
| `firewall_rule.name` | `rule_name` | str |
| `src_endpoint.interface_name` | `inbound_interface` | str |
| `src_endpoint.ip` | `source_address` | str |
| `src_endpoint.port` | `source_port` | int |
| `src_endpoint.zone` | `source_zone` | str |
| `traffic.bytes` | `bytes_total` | int |
| `traffic.bytes_in` | `bytes_received` | int |
| `traffic.bytes_out` | `bytes_sent` | int |
| `traffic.packets` | `packets` | int |
| `activity_id` | *(constant)* | `6` |
| `severity_id` | *(constant)* | `1` |

**Enum collapse** — the vendor's own word is always retained.

- `disposition_id` ← `action`: `allow`→1, `deny`→2, `drop`→3, `drop-icmp`→3, `reset-both`→8, `reset-client`→8, `reset-server`→8 (default `99`), original in `disposition_orig`

---

## `pfsense.filterlog` — Netgate pfSense

- **Version** `2.0.0` · **Family** `csv` · **OCSF class** `4001` (category `4`)
- **Compiled pipeline** `syslog?` → `prefix` → `columns`
- **Signature** must contain `filterlog` (weight 0.95)

**Timestamp** — `log_time`, formats `bsd`, zone `UTC`.

| OCSF field | Vendor field | Type |
|---|---|---|
| `connection_info.protocol_name` | `protocol` | str |
| `device.hostname` | `log_host` | str |
| `dst_endpoint.ip` | `destination_address` | str |
| `dst_endpoint.port` | `destination_port` | int |
| `firewall_rule.uid` | `rule_number` | str |
| `src_endpoint.interface_name` | `interface` | str |
| `src_endpoint.ip` | `source_address` | str |
| `src_endpoint.port` | `source_port` | int |
| `traffic.bytes` | `length` | int |
| `activity_id` | *(constant)* | `6` |

**Enum collapse** — the vendor's own word is always retained.

- `disposition_id` ← `action`: `pass`→1, `block`→2, `reject`→2, `rdr`→1, `nat`→1 (default `99`), original in `disposition_orig`
- `connection_info.direction_id` ← `direction`: `in`→1, `out`→2 (default `0`), original in `direction_orig`

---

## `squid.access` — Squid Squid Proxy

- **Version** `2.0.0` · **Family** `delimited` · **OCSF class** `4002` (category `4`)
- **Compiled pipeline** `whitespace`
- **Signature** matches `TCP_(MISS|HIT|DENIED|TUNNEL|REFRESH|MEM)` (weight 0.94)

**Timestamp** — `epoch_time`, formats `epoch`, zone `UTC`.

| OCSF field | Vendor field | Type |
|---|---|---|
| `actor.user.name` | `user` | str |
| `duration` | `duration_ms` | int |
| `http_request.http_method` | `method` | str |
| `http_request.url.text` | `url` | str |
| `metadata.event_code` | `result_code` | str |
| `src_endpoint.ip` | `client_address` | str |
| `traffic.bytes` | `bytes` | int |
| `activity_id` | *(constant)* | `1` |

**Enum collapse** — the vendor's own word is always retained.

- `disposition_id` ← `result_code`: `TCP_DENIED/403`→2, `TCP_DENIED/407`→2, `TCP_MISS/200`→1, `TCP_HIT/200`→1, `TCP_TUNNEL/200`→1, `TCP_MEM_HIT/200`→1, `TCP_REFRESH_HIT/200`→1 (default `99`), original in `disposition_orig`

---

## `suricata.alert` — OISF Suricata

- **Version** `2.0.0` · **Family** `json` · **OCSF class** `2004` (category `2`)
- **Compiled pipeline** `json`
- **Signature** matches `"event_type"\s*:\s*"alert"` (weight 0.98)

**Timestamp** — `timestamp`, formats `iso8601`, zone `UTC`.

| OCSF field | Vendor field | Type |
|---|---|---|
| `app_name` | `app_proto` | str |
| `connection_info.protocol_name` | `proto` | str |
| `connection_info.uid` | `flow_id` | str |
| `device.hostname` | `host` | str |
| `dst_endpoint.ip` | `dest_ip` | str |
| `dst_endpoint.port` | `dest_port` | int |
| `finding_info.title` | `alert.signature` | str |
| `finding_info.types` | `alert.category` | str |
| `finding_info.uid` | `alert.signature_id` | int |
| `src_endpoint.ip` | `src_ip` | str |
| `src_endpoint.port` | `src_port` | int |
| `activity_id` | *(constant)* | `1` |

**Enum collapse** — the vendor's own word is always retained.

- `severity_id` ← `alert.severity`: `1`→5, `2`→4, `3`→2, `4`→1 (default `1`), original in `severity_orig`
- `disposition_id` ← `alert.action`: `allowed`→1, `blocked`→2, `drop`→3 (default `99`), original in `disposition_orig`

---

## `zeek.conn` — Zeek Zeek

- **Version** `2.0.0` · **Family** `json` · **OCSF class** `4001` (category `4`)
- **Compiled pipeline** `json`
- **Signature** must contain `"id.orig_h"`, any of ['"conn_state"', '"orig_bytes"'] (weight 0.96)

**Timestamp** — `ts`, formats `epoch`, `iso8601`, zone `UTC`.

| OCSF field | Vendor field | Type |
|---|---|---|
| `app_name` | `service` | str |
| `connection_info.protocol_name` | `proto` | str |
| `connection_info.uid` | `uid` | str |
| `dst_endpoint.ip` | `id.resp_h` | str |
| `dst_endpoint.port` | `id.resp_p` | int |
| `duration` | `duration` | float |
| `src_endpoint.ip` | `id.orig_h` | str |
| `src_endpoint.port` | `id.orig_p` | int |
| `traffic.bytes_in` | `resp_bytes` | int |
| `traffic.bytes_out` | `orig_bytes` | int |
| `traffic.packets` | `orig_pkts` | int |
| `activity_id` | *(constant)* | `6` |
| `severity_id` | *(constant)* | `1` |

**Enum collapse** — the vendor's own word is always retained.

- `disposition_id` ← `conn_state`: `SF`→1, `S1`→1, `S0`→3, `REJ`→2, `RSTO`→8, `RSTR`→8, `OTH`→99 (default `99`), original in `disposition_orig`

---

## Everything else

Any field the pipeline extracted that no row above claims is placed in the
event's `unmapped` object. The mapper computes that as a set difference, so a
forgotten mapping is *visible in the output* rather than silently missing. And
regardless of mapping, the original bytes are in the ledger, addressable by
`record_id` and provable by Merkle inclusion.
