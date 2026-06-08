"""
Verify a live Odoo instance against a declared ``addons.yaml``.

Reframed from the old ``AddonSpec.diff``: instead of an ``AddonSpec`` object
it reads the native ``{repo: [modules]}`` mapping (as produced by
:mod:`odoo_instance_utils.addons_yaml`) and reports modules that are
declared but missing on disk, or present on disk but not declared.

Per-module version drift between filesystem and database remains the
responsibility of :attr:`odoo_instance_utils.addons.Addon.version_mismatch`
and is independent of this declared-vs-disk check.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from odoo_instance_utils.addons import Addons


def diff_addons_yaml(
    declared: dict[str, list[str]],
    addons: "Addons",
) -> list[str]:
    """Compare a declared ``{repo: [modules]}`` map against live *addons*.

    + declared: mapping of repo path/name to declared module names. A
      ``["*"]`` value means "every module in the repo".
    + addons: an :class:`Addons` collection scanned from disk.

    Returns a list of human-readable discrepancies (empty = match).
    """
    runtime_modules: dict[str, set[str]] = {}
    for addon in addons.addons:
        runtime_modules.setdefault(addon.repo_name, set()).add(addon.name)

    issues: list[str] = []
    all_repos = set(runtime_modules) | set(declared)

    for repo in sorted(all_repos):
        declared_mods = tuple(declared.get(repo, ()))
        runtime = runtime_modules.get(repo, set())

        if "*" in declared_mods:
            if not runtime:
                issues.append(f"{repo}: declared but not found on disk")
            continue

        declared_set = set(declared_mods)
        for module in sorted(declared_set - runtime):
            issues.append(f"{repo}/{module}: declared but not found on disk")
        for module in sorted(runtime - declared_set):
            issues.append(f"{repo}/{module}: on disk but not declared")

    return issues
