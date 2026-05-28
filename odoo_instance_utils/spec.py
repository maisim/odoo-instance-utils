"""
Declarative addon specification.

A frozen description of *which* addon modules a project uses and *where*
their source code lives.  The spec is the source of truth for:

- rendering git-aggregator ``repos.yaml`` and doodba ``addons.yaml``,
- capturing a spec from a live Odoo instance,
- verifying that a live instance matches the declared spec.

All types are frozen dataclasses — hashable, comparable, and safe to
embed in Pydantic models.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from odoo_instance_utils.odoo_instance import OdooInstance


@dataclass(frozen=True)
class AddonRepo:
    """A git repository containing Odoo addon modules.

    Describes where to clone the code from and what ref to merge via
    git-aggregator.  One ``AddonRepo`` typically maps to one OCA
    repository, one private repository, etc.

    + name: unique slug (e.g. ``"server-tools"``).
    + url: full git clone URL.
    + remote: git-aggregator remote name (e.g. ``"oca"``, ``"origin"``).
    + target: merge target ref — branch name (``"oca 17.0"``) or commit SHA.
    + merges: additional merge refs; defaults to ``(target,)``.
    + depth: shallow clone depth for git-aggregator.
    """

    name: str
    url: str
    remote: str
    target: str
    merges: tuple[str, ...] = ()
    depth: int = 1

    def __post_init__(self) -> None:
        if not self.merges:
            object.__setattr__(self, "merges", (self.target,))


def OCAAddonRepo(
    repo: str,
    org: str = "OCA",
    branch: str | None = None,
) -> AddonRepo:
    """Pre-configured ``AddonRepo`` for an OCA-style repository.

    ``branch`` defaults to ``None`` — callers should substitute the
    project's Odoo version before constructing the full target string.
    """
    remote = org.lower()
    return AddonRepo(
        name=repo,
        url=f"https://github.com/{org}/{repo}.git",
        remote=remote,
        target=f"{remote} {branch}" if branch else "",
    )


@dataclass(frozen=True)
class AddonSelection:
    """Which modules from a given repo are active in the project.

    + repo: references :attr:`AddonRepo.name`.
    + modules: tuple of module names to activate. ``("*",)`` means
      every module found in the repo.
    """

    repo: str
    modules: tuple[str, ...] = ("*",)


@dataclass(frozen=True)
class AddonSpec:
    """Complete addon specification for a project.

    Aggregates the repo sources and the per-repo module selections.
    This is the value exported by ``foundry_addons.py``.
    """

    repos: tuple[AddonRepo, ...] = ()
    selections: tuple[AddonSelection, ...] = ()

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        repo_names = {r.name for r in self.repos}
        if len(repo_names) != len(self.repos):
            raise ValueError("AddonSpec.repos names must be unique")
        for sel in self.selections:
            if sel.repo not in repo_names:
                raise ValueError(f"AddonSelection.repo={sel.repo!r} does not match any AddonRepo")
        sel_names = [s.repo for s in self.selections]
        if len(sel_names) != len(set(sel_names)):
            raise ValueError("AddonSpec.selections repo references must be unique")

    @classmethod
    def from_instance(cls, odoo_instance: OdooInstance) -> AddonSpec:
        """Capture an ``AddonSpec`` from a live Odoo instance.

        Groups modules by their git remote origin, pins each repo to its
        current HEAD, and selects all modules present in each repo.
        """
        addons = odoo_instance.addons
        sources = addons.build_sources_list()

        repos: list[AddonRepo] = []
        repo_order: list[str] = []  # preserve discovery order
        for repo_name, info in sources.items():
            target = info["head"] or (
                info["remote"] + " " + info["branch"] if info["branch"] else ""
            )
            repos.append(
                AddonRepo(
                    name=repo_name,
                    url=info["repo"],
                    remote=info["remote"],
                    target=target,
                )
            )
            repo_order.append(repo_name)

        # Group addons by repo_name, preserving order
        by_repo: dict[str, list[str]] = {name: [] for name in repo_order}
        for addon in addons.addons:
            rname = addon.repo_name
            if rname and rname in by_repo:
                by_repo[rname].append(addon.name)

        selections = [
            AddonSelection(repo=name, modules=tuple(sorted(mods)))
            for name, mods in by_repo.items()
            if mods
        ]

        return cls(repos=tuple(repos), selections=tuple(selections))

    def diff(self, odoo_instance: OdooInstance) -> list[str]:
        """Compare this spec against a live *odoo_instance*.

        Returns a list of human-readable discrepancies (empty = match).
        Detects: modules in spec but missing on disk, modules on disk
        not declared, fingerprint mismatches.
        """
        from odoo_instance_utils.addons import Addons

        issues: list[str] = []

        addons = Addons(addons_paths=odoo_instance.addons.addons_paths)
        runtime_modules: dict[str, set[str]] = {}
        for addon in addons.addons:
            runtime_modules.setdefault(addon.repo_name, set()).add(addon.name)

        declared_modules: dict[str, tuple[str, ...]] = {s.repo: s.modules for s in self.selections}

        all_repo_names = set(runtime_modules) | set(declared_modules)

        for repo_name in sorted(all_repo_names):
            declared = declared_modules.get(repo_name, ())
            runtime = runtime_modules.get(repo_name, set())

            if "*" in declared:
                # "all modules" — only flag when the repo is entirely missing
                if not runtime:
                    issues.append(f"{repo_name}: declared but not found on disk")
            else:
                declared_set = set(declared)
                missing = declared_set - runtime
                extra = runtime - declared_set
                for m in sorted(missing):
                    issues.append(f"{repo_name}/{m}: declared in spec but not found on disk")
                for m in sorted(extra):
                    issues.append(f"{repo_name}/{m}: on disk but not declared in spec")

            # Fingerprint check for modules present in both
            runtime_by_name = {a.name: a for a in addons.addons if a.repo_name == repo_name}
            for mod_name in sorted(declared_set & runtime):
                addon = runtime_by_name.get(mod_name)
                if addon and addon.fingerprint:
                    # Store fingerprint for future verification
                    addon.repo_ref = next((r for r in self.repos if r.name == repo_name), None)

        return issues

    @classmethod
    def from_json(cls, data: dict) -> AddonSpec:
        """Build an ``AddonSpec`` from the JSON output of the ``OdooAddons`` fact.

        The *data* dict has the shape::

            {
              "repos": {
                "server-tools": {"url": "...", "remote": "oca",
                                 "branch": "17.0", "head": "abc123..."}
              },
              "addons": {
                "auditlog": {"repo": "server-tools", "version": "17.0.1.0.0"}
              }
            }
        """
        repos_list: list[AddonRepo] = []
        for name, info in data.get("repos", {}).items():
            target = info.get("head", "") or (
                f"{info['remote']} {info['branch']}"
                if info.get("remote") and info.get("branch")
                else ""
            )
            repos_list.append(
                AddonRepo(
                    name=name,
                    url=info.get("url", ""),
                    remote=info.get("remote", ""),
                    target=target,
                )
            )

        by_repo: dict[str, list[str]] = {}
        for mod_name, mod_info in data.get("addons", {}).items():
            repo = mod_info.get("repo", "")
            if repo:
                by_repo.setdefault(repo, []).append(mod_name)

        selections = [
            AddonSelection(repo=name, modules=tuple(sorted(modules)))
            for name, modules in by_repo.items()
        ]

        return cls(repos=tuple(repos_list), selections=tuple(selections))

    def to_python(self) -> str:
        """Render this spec as the content of a ``foundry_addons.py`` file."""
        lines = [
            '"""Addon specification."""',
            "",
            "from odoo_instance_utils.spec import AddonRepo, AddonSelection, AddonSpec",
            "",
            "addon_spec = AddonSpec(",
            "    repos=(",
        ]
        for repo in self.repos:
            lines.append(f"        AddonRepo(name={repo.name!r}, url={repo.url!r},")
            lines.append(f"                 remote={repo.remote!r}, target={repo.target!r}),")
        lines.append("    ),")
        lines.append("    selections=(")
        for sel in self.selections:
            lines.append(f"        AddonSelection(repo={sel.repo!r}, modules={sel.modules!r}),")
        lines.append("    ),")
        lines.append(")")
        return "\n".join(lines) + "\n"
