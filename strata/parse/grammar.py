"""
strata.parse.grammar
====================
THE GRAMMAR FORMAT -- how STRATA learns to read a log source.

A grammar is a YAML document loaded at runtime. Adding a log source means
dropping a file in `grammars/` or publishing one from the Forge: no rebuild,
no restart, no deploy. Requirements (e) and (i) rest entirely on this.

This module defines and VALIDATES the format. It is the trust boundary, so
validation here is strict and total -- an unknown key is an error, not a
shrug, because a silently ignored key means a mapping the author believes is
in effect and is not.

    id: panos.traffic
    version: 1.0.0
    vendor: Palo Alto Networks
    product: PAN-OS
    family: csv                     # structural family; gates triage

    signature:                      # how do we recognise this source?
      must: [",TRAFFIC,"]           # every literal must be present
      any: ["end", "drop"]          # at least one, if given
      pattern: '...'                # optional regex confirmation
      weight: 0.95                  # confidence when it matches

    pipeline:                       # ordered extraction steps
      - syslog: auto
        optional: true
      - columns: [a, b, c]
        sep: ","

    coerce: {a: int}

    clock:                          # where the event's own time lives
      field: generated_time
      formats: [slashed]
      zone: UTC

    emit:                           # vendor vocabulary -> OCSF
      class: 4001
      category: 4
      const: {activity_id: 6}
      fields: {"src_endpoint.ip": source_address}
      enums: {...}
      ignore: [padding_1]
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .shapes import SHAPE_BY_NAME, Shape

STEP_KEYS = {"syslog", "columns", "whitespace", "kv", "json", "cef", "leef",
             "regex", "prefix"}

# YAML key -> python attribute, where they differ.
_ATTR = {"json": "as_json"}


class Strict(BaseModel):
    """Base for every grammar node: unknown keys are rejected.

    Pydantic's default is to ignore extra keys. For a config format edited by
    humans that is the wrong default -- a typo'd `fileds:` would be silently
    dropped and the author would believe a mapping was live when it was not.
    """
    model_config = ConfigDict(extra="forbid")


class Signature(Strict):
    """How triage recognises this source."""

    must: list[str] = Field(default_factory=list)
    any: list[str] = Field(default_factory=list)
    pattern: str | None = None
    weight: float = Field(default=0.9, gt=0.0, le=1.0)

    @model_validator(mode="after")
    def _has_a_test(self) -> "Signature":
        if not (self.must or self.any or self.pattern):
            raise ValueError(
                "signature needs at least one of: must, any, pattern. "
                "A grammar with no signature can never be selected.")
        return self


class Step(Strict):
    """One extraction step. Exactly one primitive key must be present."""

    syslog: Literal["auto", "rfc3164", "rfc5424"] | None = None
    columns: list[str] | None = None
    whitespace: list[str] | None = None
    kv: bool | None = None
    # `json` is a deprecated method name on BaseModel, so the attribute is
    # `as_json` and the YAML key stays `json` via the alias. Cosmetic, but a
    # library warning on every import erodes trust in everything else we print.
    as_json: bool | None = Field(default=None, alias="json")
    cef: bool | None = None
    leef: bool | None = None
    regex: str | None = None
    prefix: str | None = None

    # arguments
    sep: str = ","
    quote: str = '"'
    pair_sep: str | None = None      # kv: what separates PAIRS (default whitespace)
    lower_keys: bool = False
    maxsplit: int = 0
    source: str = "__body__"
    keep_body: bool = False
    depth: int = 6
    flatten_sep: str = "."
    optional: bool = False

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _exactly_one(self) -> "Step":
        present = [k for k in STEP_KEYS
                   if getattr(self, _ATTR.get(k, k), None) not in (None, False)]
        if len(present) != 1:
            raise ValueError(
                f"a step must name exactly one of {sorted(STEP_KEYS)}; got {present or 'none'}")
        self._kind = present[0]      # type: ignore[attr-defined]
        return self

    @property
    def kind(self) -> str:
        return getattr(self, "_kind", "")


class EnumMap(Strict):
    """Collapse a vendor's vocabulary into an OCSF enum, keeping the original.

    `keep` is not optional in spirit. Normalizing "reset-both" to 8 is the
    point; losing the fact that it was specifically a bidirectional reset is
    not. Every shipped grammar sets it.
    """

    source: str
    table: dict[str, int | str]
    default: int | str = 99
    keep: str | None = None


class Emit(Strict):
    """Vendor field names -> OCSF paths."""

    cls: int = Field(alias="class")
    category: int
    const: dict[str, Any] = Field(default_factory=dict)
    fields: dict[str, str] = Field(default_factory=dict)
    enums: dict[str, EnumMap] = Field(default_factory=dict)
    ignore: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Clock(Strict):
    field: str
    formats: list[str] = Field(min_length=1)
    zone: str = "UTC"


class Grammar(Strict):
    """A complete, self-contained description of how to read one log source."""

    id: str = Field(pattern=r"^[a-z0-9]+(?:\.[a-z0-9_]+)+$", max_length=64)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    vendor: str = Field(max_length=64)
    product: str = Field(max_length=64)
    title: str = ""
    family: str = "freeform"
    signature: Signature
    pipeline: list[Step] = Field(min_length=1)
    coerce: dict[str, Literal["int", "float", "bool", "str"]] = Field(default_factory=dict)
    clock: Clock | None = None
    emit: Emit

    @model_validator(mode="after")
    def _known_family(self) -> "Grammar":
        if self.family not in SHAPE_BY_NAME:
            raise ValueError(
                f"unknown family {self.family!r}; known: {sorted(SHAPE_BY_NAME)}")
        return self

    @property
    def shape(self) -> Shape:
        return SHAPE_BY_NAME[self.family]


class Library:
    """Loads, validates and hot-reloads grammars from a directory.

    `reload()` is the entire runtime implementation of requirement (e): the
    Forge writes a file, calls reload, and the new source starts parsing. No
    process restart -- which is what "plug and play" has to mean to mean
    anything.

    A broken grammar is skipped and reported, never fatal. Users write these,
    and one bad file must not take the pipeline down.
    """

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.grammars: dict[str, Grammar] = {}
        self.errors: dict[str, str] = {}
        self.generation = 0
        self.reload()

    def reload(self) -> dict[str, str]:
        found: dict[str, Grammar] = {}
        errors: dict[str, str] = {}

        for path in sorted(self.directory.glob("*.y*ml")):
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    raise ValueError("grammar file must be a YAML mapping")
                g = Grammar.model_validate(raw)
                if g.id in found:
                    raise ValueError(f"duplicate grammar id {g.id!r}")
                found[g.id] = g
            except ValidationError as exc:
                errors[path.name] = _tidy(exc)
            except (ValueError, yaml.YAMLError) as exc:
                errors[path.name] = str(exc)

        self.grammars, self.errors = found, errors
        self.generation += 1
        return errors

    def get(self, gid: str) -> Grammar | None:
        return self.grammars.get(gid)

    def all(self) -> list[Grammar]:
        return list(self.grammars.values())

    def by_family(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for g in self.grammars.values():
            out.setdefault(g.family, []).append(g.id)
        return {k: sorted(v) for k, v in sorted(out.items())}

    def __len__(self) -> int:
        return len(self.grammars)


def _tidy(exc: ValidationError) -> str:
    """Pydantic errors are verbose and repetitive. A grammar author needs to
    know which key and what was wrong, on one line."""
    parts = []
    for err in exc.errors()[:4]:
        loc = ".".join(str(p) for p in err["loc"]) or "(root)"
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts)
