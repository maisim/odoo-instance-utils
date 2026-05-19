"""
Render an :class:`AddonSpec` to git-aggregator / doodba configuration files.

The output format is dictated by doodba's conventions:

- ``repos.yaml``: consumed by git-aggregator at build/runtime.
- ``addons.yaml``: consumed by doodba to build Odoo's ``addons_path``.
"""

from __future__ import annotations

import io

import yaml
from yaml.nodes import Node

from odoo_instance_utils.spec import AddonSpec


def _represent_tuple(dumper: yaml.Dumper, data: tuple) -> Node:
    """Serialize Python tuples as YAML sequences (flow style for compactness)."""
    return dumper.represent_sequence("tag:yaml.org,2002:seq", list(data), flow_style=True)


_yaml_dumper = yaml.Dumper
_yaml_dumper.add_representer(tuple, _represent_tuple)


def _yaml_str(data: object) -> str:
    """Dump *data* to a YAML string (no ``---`` document marker)."""
    buf = io.StringIO()
    yaml.dump(data, buf, Dumper=_yaml_dumper, default_flow_style=False, sort_keys=False)
    return buf.getvalue()


def render_repos_yaml(spec: AddonSpec) -> str:
    """Generate the git-aggregator repo entries for *spec*.

    Returns only the per-addon-repo stanzas (``./<repo>: ...``).
    The OCB entry is the caller's responsibility.
    """
    parts: list[str] = []
    for repo in spec.repos:
        entry = {
            f"./{repo.name}": {
                "defaults": {"depth": repo.depth},
                "remotes": {repo.remote: repo.url},
                "target": repo.target,
                "merges": list(repo.merges),
            }
        }
        parts.append(_yaml_str(entry))
    return "\n".join(parts)


def render_addons_yaml(spec: AddonSpec) -> str:
    """Generate the doodba addons manifest for *spec*.

    Maps each repo to its active module list.
    """
    parts: list[str] = []
    for sel in spec.selections:
        # When modules=("*",), emit the YAML list item "*" "as-is" —
        # doodba treats this as "every module in the repo".
        modules: list[str] = list(sel.modules)
        entry = {sel.repo: modules}
        parts.append(_yaml_str(entry))
    return "\n".join(parts)
