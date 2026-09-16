"""Config loader with provenance tracking.

Every numeric leaf in config/*.yaml is a record {value, unit, source, confidence}. The loader exposes
plain values for ergonomic access (cfg.band.carrier.fc_ghz -> 3.9) while recording a flat registry of
(path, value, unit, source, confidence) so that:

* `docs/assumptions.md` is GENERATED from the registry (one row per assumption — brief §9), and
* the CLI can fail in --strict mode if any 'unverified' value survives (brief §10.2).

A leaf is recognised as a Param record if it is a dict containing both 'value' and 'source'.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import yaml

CONFIDENCE_LEVELS = ("verified", "secondary", "unverified", "design")
CONFIG_FILES = ("band", "ues", "services", "qos", "scenario_best", "latency")


class UnverifiedValueWarning(UserWarning):
    """Emitted when an [UNVERIFIED] config value is read."""


@dataclass(frozen=True)
class Param:
    path: str
    value: Any
    unit: str
    source: str
    confidence: str

    @property
    def unverified(self) -> bool:
        return self.confidence == "unverified"


class Section:
    """Attribute/item access wrapper around a nested dict of plain values."""

    def __init__(self, data: dict[str, Any], path: str = ""):
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "_path", path)

    def __getattr__(self, key: str) -> Any:
        d = self._data
        if key not in d:                      # YAML may have parsed numeric keys (e.g. 5QI 82) as int
            try:
                key = int(key) if int(key) in d else key
            except (TypeError, ValueError):
                pass
        try:
            v = d[key]
        except KeyError as e:
            raise AttributeError(f"{self._path}.{key} not in config") from e
        return Section(v, f"{self._path}.{key}") if isinstance(v, dict) else v

    def __getitem__(self, key) -> Any:
        return self.__getattr__(str(key))

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def items(self) -> Iterator[tuple[str, Any]]:
        for k, v in self._data.items():
            yield k, (Section(v, f"{self._path}.{k}") if isinstance(v, dict) else v)

    def raw(self) -> dict[str, Any]:
        return self._data

    def __repr__(self) -> str:
        return f"Section({self._path or '<root>'}: {list(self._data)})"


def _is_param(node: Any) -> bool:
    return isinstance(node, dict) and "value" in node and "source" in node


def _strip(node: Any, path: str, registry: list[Param]) -> Any:
    """Recursively replace Param records by their value, appending each record to registry."""
    if _is_param(node):
        conf = node.get("confidence", "unverified")
        if conf not in CONFIDENCE_LEVELS:
            raise ValueError(f"{path}: bad confidence '{conf}' (allowed: {CONFIDENCE_LEVELS})")
        registry.append(Param(path, node["value"], str(node.get("unit", "")), node["source"], conf))
        return node["value"]
    if isinstance(node, dict):
        return {k: _strip(v, f"{path}.{k}" if path else k, registry) for k, v in node.items()}
    if isinstance(node, list):
        return [_strip(v, f"{path}[{i}]", registry) for i, v in enumerate(node)]
    return node


@dataclass
class Config:
    root: Path
    data: dict[str, Any]
    registry: list[Param] = field(default_factory=list)

    def __getattr__(self, key: str) -> Any:
        if key in ("root", "data", "registry"):
            raise AttributeError(key)
        if key not in self.data:
            raise AttributeError(f"no config file '{key}' (have {list(self.data)})")
        return Section(self.data[key], key)

    # --- provenance helpers -------------------------------------------------------------------
    def unverified(self) -> list[Param]:
        return [p for p in self.registry if p.unverified]

    def by_confidence(self) -> dict[str, int]:
        out = {c: 0 for c in CONFIDENCE_LEVELS}
        for p in self.registry:
            out[p.confidence] += 1
        return out

    def warn_unverified(self) -> None:
        n = len(self.unverified())
        if n:
            warnings.warn(
                f"{n} config values are [UNVERIFIED]; run `make assumptions` to list them. "
                "None of them may appear in the report without a source.",
                UnverifiedValueWarning,
                stacklevel=2,
            )


def find_root(start: Path | None = None) -> Path:
    """Walk up from `start` (or this file) until a directory containing config/band.yaml is found."""
    p = (start or Path(__file__)).resolve()
    for cand in [p, *p.parents]:
        if (cand / "config" / "band.yaml").exists():
            return cand
    raise FileNotFoundError("could not locate the port5g repo root (config/band.yaml)")


def load_config(root: Path | None = None, warn: bool = True) -> Config:
    root = Path(root) if root else find_root()
    registry: list[Param] = []
    data: dict[str, Any] = {}
    for name in CONFIG_FILES:
        path = root / "config" / f"{name}.yaml"
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        data[name] = _strip(raw, name, registry)
    cfg = Config(root=root, data=data, registry=registry)
    if warn:
        cfg.warn_unverified()
    return cfg
