"""
Native git-aggregator ``repos.yaml`` parsing and rendering.

``repos.yaml`` is doodba's git-aggregator configuration: a mapping of
destination paths (``./odoo``, ``./web`` ...) to stanzas describing the
remotes, target ref and merges used to assemble each addon repository.

This module models that file natively (preserving order and any unknown
keys) so it can be read, manipulated and written back without loss. It is
deliberately decoupled from ``git_aggregator`` to keep this package light
and Python 3.7+ compatible; :func:`validate_repos_yaml` optionally delegates
to ``git_aggregator.config.get_repos`` when that package is importable.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_KNOWN_KEYS = ("defaults", "remotes", "target", "merges")


@dataclass
class RepoStanza:
    """A single ``repos.yaml`` entry (one addon repository).

    + path: destination path key (e.g. ``"./web"``).
    + remotes: mapping of remote name to clone URL.
    + target: git-aggregator target ref (e.g. ``"OCA 16.0"``).
    + merges: list of merge refs (``"remote ref"`` strings).
    + defaults: git-aggregator ``defaults`` block (e.g. ``{"depth": 1}``).
    + extra: any other keys present in the stanza, preserved verbatim.
    """

    path: str
    remotes: dict[str, str] = field(default_factory=dict)
    target: str = ""
    merges: list[str] = field(default_factory=list)
    defaults: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)

    def to_mapping(self) -> "OrderedDict[str, object]":
        """Render this stanza as an ordered mapping for YAML dumping."""
        body: "OrderedDict[str, object]" = OrderedDict()
        if self.defaults:
            body["defaults"] = dict(self.defaults)
        if self.remotes:
            body["remotes"] = dict(self.remotes)
        if self.target:
            body["target"] = self.target
        if self.merges:
            body["merges"] = list(self.merges)
        for key, value in self.extra.items():
            body[key] = value
        return body


def _stanza_from_mapping(path: str, body: dict) -> RepoStanza:
    body = body or {}
    extra = {k: v for k, v in body.items() if k not in _KNOWN_KEYS}
    return RepoStanza(
        path=path,
        remotes=dict(body.get("remotes") or {}),
        target=str(body.get("target") or ""),
        merges=[str(m) for m in (body.get("merges") or [])],
        defaults=dict(body.get("defaults") or {}),
        extra=extra,
    )


def parse_repos_yaml(text: str) -> list[RepoStanza]:
    """Parse ``repos.yaml`` *text* into an ordered list of stanzas."""
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError("repos.yaml must be a mapping of paths to stanzas")
    return [_stanza_from_mapping(path, body) for path, body in data.items()]


def load_repos_yaml(path: str | Path) -> list[RepoStanza]:
    """Read and parse a ``repos.yaml`` file."""
    return parse_repos_yaml(Path(path).read_text())


def dump_repos_yaml(stanzas: list[RepoStanza]) -> str:
    """Render *stanzas* back to ``repos.yaml`` text (order preserved)."""
    mapping: "OrderedDict[str, object]" = OrderedDict(
        (stanza.path, stanza.to_mapping()) for stanza in stanzas
    )
    return yaml.dump(
        _to_plain(mapping),
        default_flow_style=False,
        sort_keys=False,
    )


def write_repos_yaml(stanzas: list[RepoStanza], path: str | Path) -> None:
    """Write *stanzas* to a ``repos.yaml`` file."""
    Path(path).write_text(dump_repos_yaml(stanzas))


def _to_plain(value: object) -> object:
    """Recursively convert OrderedDict to plain dict for clean YAML output."""
    if isinstance(value, dict):
        return {k: _to_plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_plain(v) for v in value]
    return value


def validate_repos_yaml(stanzas: list[RepoStanza]) -> None:
    """Validate *stanzas*, delegating to git-aggregator when available.

    Raises :class:`ValueError` on structural problems. When
    ``git_aggregator`` is importable, its stricter ``get_repos`` validation
    is reused; otherwise a minimal local check is performed.
    """
    try:
        from git_aggregator.config import get_repos  # type: ignore
    except ImportError:
        _validate_local(stanzas)
        return
    config = {s.path: s.to_mapping() for s in stanzas}
    get_repos(config)


def _validate_local(stanzas: list[RepoStanza]) -> None:
    seen: set[str] = set()
    for stanza in stanzas:
        if stanza.path in seen:
            raise ValueError(f"duplicate repos.yaml path: {stanza.path}")
        seen.add(stanza.path)
        if not stanza.remotes:
            raise ValueError(f"{stanza.path}: at least one remote is required")
        for merge in stanza.merges:
            parts = merge.split(" ")
            if len(parts) != 2:
                raise ValueError(f'{stanza.path}: merge must be "remote ref", got {merge!r}')
            if parts[0] not in stanza.remotes:
                raise ValueError(f"{stanza.path}: merge remote {parts[0]!r} not in remotes")
