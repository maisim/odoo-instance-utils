"""
Native doodba ``addons.yaml`` parsing and rendering.

``addons.yaml`` maps each addon repository path to the list of modules
doodba should add to Odoo's ``addons_path``. A single ``"*"`` entry means
"every module found in that repository".

Example::

    server-tools:
        - auditlog
        - base_technical_features
    web: "*"
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import yaml


def parse_addons_yaml(text: str) -> "OrderedDict[str, list[str]]":
    """Parse ``addons.yaml`` *text* into an ordered ``{repo: [modules]}`` map.

    A scalar ``"*"`` value is normalised to ``["*"]``.
    """
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError("addons.yaml must be a mapping of repos to module lists")
    result: "OrderedDict[str, list[str]]" = OrderedDict()
    for repo, modules in data.items():
        if modules is None:
            result[repo] = []
        elif isinstance(modules, str):
            result[repo] = [modules]
        elif isinstance(modules, list):
            result[repo] = [str(m) for m in modules]
        else:
            raise ValueError(f"{repo}: module list must be a list or '*'")
    return result


def load_addons_yaml(path: str | Path) -> "OrderedDict[str, list[str]]":
    """Read and parse an ``addons.yaml`` file."""
    return parse_addons_yaml(Path(path).read_text())


def dump_addons_yaml(addons: dict[str, list[str]]) -> str:
    """Render an ``{repo: [modules]}`` mapping to ``addons.yaml`` text.

    A ``["*"]`` value is emitted as the scalar ``"*"`` to match doodba's
    "all modules" convention.
    """
    plain: "OrderedDict[str, object]" = OrderedDict()
    for repo, modules in addons.items():
        if list(modules) == ["*"]:
            plain[repo] = "*"
        else:
            plain[repo] = list(modules)
    return yaml.dump(dict(plain), default_flow_style=False, sort_keys=False)


def write_addons_yaml(addons: dict[str, list[str]], path: str | Path) -> None:
    """Write an ``{repo: [modules]}`` mapping to an ``addons.yaml`` file."""
    Path(path).write_text(dump_addons_yaml(addons))
