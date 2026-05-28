from __future__ import annotations

import os
import subprocess
import sys
from ast import literal_eval
from typing import TYPE_CHECKING

import yaml

from .exceptions import ConflictError
from .hashing import fingerprint_module

if TYPE_CHECKING:
    from .spec import AddonRepo as AddonRepoType

if sys.version_info < (3, 8):
    import importlib_metadata
else:
    from importlib import metadata as importlib_metadata


class Addon:
    def __init__(self, name="", path="", git_repo=""):
        self.name = name
        self._path = path
        self.git_repo = git_repo
        self.dependencies = []
        self.is_installed = False
        self.needs_upgrade = False
        self.is_dependency_of = []
        self.manifest = {}
        self.db_version: str = ""  # installed_version from ir.module.module
        self.db_state: str = ""  # state from ir.module.module
        self.repo_ref: AddonRepoType | None = None  # link to declarative AddonRepo
        self.conflicting_path: str = ""  # set when same addon name found at another path

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Addon {self.name}>"

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, value):
        if self._path and self._path != value:
            raise ConflictError(f"An addon {self.name} already exists with a different path")
        self._path = value

    @property
    def repo_name(self):
        return self.git_repo.split("/")[-1].split(".")[0] if self.git_repo else ""

    @property
    def git_head(self):
        if self.git_repo:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.path,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        return ""

    @property
    def git_branch(self) -> str | None:
        """Current branch name, or None if detached HEAD or no git repo."""
        if self.git_repo:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.path,
                capture_output=True,
                text=True,
            )
            branch = result.stdout.strip()
            if branch == "HEAD":
                return None  # detached HEAD
            return branch
        return None

    @property
    def remote(self):
        return self.git_repo.split("/")[-2] if self.git_repo else ""

    @property
    def fs_version(self):
        """Version string from the manifest on disk, or ``None``."""
        return self.manifest.get("version", None)

    @property
    def target_version(self):
        version = self.fs_version
        if version:
            return ".".join(version.split(".")[0:2])

    @property
    def missing_from_filesystem(self) -> bool:
        """``True`` when the module is installed in DB but absent from disk."""
        return self.is_installed and not self.path

    @property
    def version_mismatch(self) -> bool:
        """``True`` when fs_version and db_version are both set and differ."""
        return bool(self.db_version and self.fs_version and self.db_version != self.fs_version)

    @property
    def mismatch_detected(self) -> bool:
        """``True`` when any discrepancy exists between filesystem and DB state.

        Covers: needs_upgrade, missing_from_filesystem, version_mismatch,
        db_state="to remove" while still on disk, and duplicate path conflicts.
        """
        if self.needs_upgrade:
            return True
        if self.missing_from_filesystem:
            return True
        if self.version_mismatch:
            return True
        if self.db_state == "to remove" and self.path:
            return True
        if self.conflicting_path:
            return True
        return False

    @property
    def python_dependencies(self):
        return self.manifest.get("external_dependencies", {}).get("python", [])

    @property
    def apt_dependencies(self) -> list[str]:
        """System packages from the manifest's ``external_dependencies.deb``."""
        return self.manifest.get("external_dependencies", {}).get("deb", [])

    @property
    def npm_dependencies(self) -> list[str]:
        """Node packages from the manifest's ``external_dependencies.npm``."""
        deps = self.manifest.get("external_dependencies", {}).get("npm", {})
        if isinstance(deps, dict):
            return [f"{pkg}@{ver}" for pkg, ver in deps.items()]
        return deps

    @property
    def gem_dependencies(self) -> list[str]:
        """Ruby gems from the manifest's ``external_dependencies.gem``."""
        return self.manifest.get("external_dependencies", {}).get("gem", [])

    @property
    def auto_install(self):
        return self.manifest.get("auto_install", False)

    @property
    def fingerprint(self) -> str:
        """SHA256 hex digest of the module's source files, or ``""``."""
        return fingerprint_module(self.path) if self._path else ""

    def to_dict(self):
        return {
            "name": self.name,
            "path": self.path,
            "git_repo": self.git_repo,
            "dependencies": [a.name for a in self.dependencies],
            "is_installed": self.is_installed,
            "is_dependency_of": [a.name for a in self.is_dependency_of],
            "repo_name": self.repo_name,
            "git_head": self.git_head,
            "git_branch": self.git_branch,
            "remote": self.remote,
            "fs_version": self.fs_version,
            "target_version": self.target_version,
            "auto_install": self.auto_install,
            "db_version": self.db_version,
            "db_state": self.db_state,
            "fingerprint": self.fingerprint,
            "conflicting_path": self.conflicting_path,
            "missing_from_filesystem": self.missing_from_filesystem,
            "version_mismatch": self.version_mismatch,
            "mismatch_detected": self.mismatch_detected,
            "python_dependencies": self.python_dependencies,
            "apt_dependencies": self.apt_dependencies,
            "npm_dependencies": self.npm_dependencies,
            "gem_dependencies": self.gem_dependencies,
        }


class Addons:
    # Filters
    installed = None
    minimize_list = False
    include_auto_installed_addons = True
    needs_upgrade = None

    def __init__(self, addons_paths: str = "", addons: list | None = None):
        self._addons = list(addons) if addons is not None else []
        self.addons_paths = addons_paths
        if addons_paths:
            self.fill_from_addons_paths()

    def __call__(
        self,
        installed=None,
        minimize_list=False,
        include_auto_installed_addons=True,
        remotes=None,
        needs_upgrade=None,
    ):
        """Filter the addons list"""
        self.installed = installed
        self.minimize_list = minimize_list
        self.include_auto_installed_addons = include_auto_installed_addons
        self.remotes = remotes
        self.needs_upgrade = needs_upgrade
        return self

    def __str__(self):
        return "\n".join([a.name for a in self.addons])

    def __len__(self):
        return len(self.addons)

    def __iter__(self):
        return iter(self.addons)

    def __getitem__(self, addon_name):
        addon = next((a for a in self._addons if a.name == addon_name), None)
        if addon is None:
            addon = Addon(name=addon_name)
            self._addons.append(addon)
        return addon

    @property
    def addons(self):
        if self.needs_upgrade is True:
            return [a for a in self._addons if a.needs_upgrade]

        if self.installed is True:
            return [a for a in self._addons if a.is_installed]
        elif self.installed is False:
            return [a for a in self._addons if not a.is_installed]

        if self.include_auto_installed_addons is False:
            return [a for a in self._addons if not a.auto_install]

        if self.minimize_list:
            # Keep only addons not already covered as a dependency of another included addon
            addons = [
                a
                for a in self._addons
                if a.is_installed
                and not any(
                    a.name in [d.name for d in other.dependencies]
                    for other in self._addons
                    if other.is_installed
                )
            ]
            return addons

        return self._addons

    @property
    def python_dependencies(self):
        dependencies = []
        for addon in self.addons:
            dependencies.extend(addon.python_dependencies)
        return list(set(dependencies))

    @property
    def apt_dependencies(self) -> list[str]:
        deps: list[str] = []
        for addon in self.addons:
            deps.extend(addon.apt_dependencies)
        return sorted(set(deps))

    @property
    def npm_dependencies(self) -> list[str]:
        deps: list[str] = []
        for addon in self.addons:
            deps.extend(addon.npm_dependencies)
        return sorted(set(deps))

    @property
    def gem_dependencies(self) -> list[str]:
        deps: list[str] = []
        for addon in self.addons:
            deps.extend(addon.gem_dependencies)
        return sorted(set(deps))

    @staticmethod
    def _find_git_repo(path: str) -> str:
        """Walk up from *path* to find ``.git``, return ``remote.origin.url`` or ``""``.

        An addon may not live in a git repo at all — in that case the empty
        string is returned and the addon is simply not associated with any repo.
        """
        search_dir = path
        while search_dir != os.path.dirname(search_dir):
            if os.path.isdir(os.path.join(search_dir, ".git")):
                result = subprocess.run(
                    ["git", "config", "--get", "remote.origin.url"],
                    cwd=search_dir,
                    capture_output=True,
                    text=True,
                )
                return result.stdout.strip()
            search_dir = os.path.dirname(search_dir)
        return ""

    @staticmethod
    def _resolve_git_state(cwd: str) -> dict:
        """Extract the complete git state of a repo for lock file generation.

        Returns a dict with ``remotes``, ``merges``, and ``target`` keys.
        Each merge and the target have ``remote``, ``sha``, and ``ref``
        (branch name if resolvable, else ``None``).
        """
        remotes: dict[str, str] = {}
        merges: list[dict[str, str | None]] = []
        target: dict[str, str | None] = {}

        # --- remotes (excluding origin partial clone) ---
        remotes_raw = subprocess.run(
            ["git", "remote", "-v"],
            cwd=cwd,
            capture_output=True,
            text=True,
        ).stdout
        seen: set[str] = set()
        origin_is_partial = any(
            "origin" in line and "[blob:none]" in line for line in remotes_raw.strip().split("\n")
        )
        for line in remotes_raw.strip().split("\n"):
            parts = line.split()
            if len(parts) < 2:
                continue
            name, url = parts[0], parts[1]
            # Skip origin when it uses a partial clone — it's a git-aggregator artifact
            if name == "origin" and origin_is_partial:
                continue
            if name in seen:
                continue
            seen.add(name)
            remotes[name] = url.rstrip(".git")

        # Fallback: if we filtered everything, keep origin
        if not remotes:
            for line in remotes_raw.strip().split("\n"):
                parts = line.split()
                if len(parts) < 2:
                    continue
                name, url = parts[0], parts[1]
                if name not in seen:
                    seen.add(name)
                    remotes[name] = url.rstrip(".git")

        def _tracking_branch(sha: str) -> tuple[str | None, str | None]:
            """Return (remote, branch) for a SHA, or (None, None)."""
            result = subprocess.run(
                ["git", "branch", "-r", "--contains", sha],
                cwd=cwd,
                capture_output=True,
                text=True,
            )
            matches = [
                line.strip().split("/", 1)
                for line in result.stdout.strip().split("\n")
                if line.strip() and "/" in line.strip()
            ]
            if not matches:
                return None, None
            # Prefer non-origin remotes
            non_origin = [(r, b) for r, b in matches if r != "origin"]
            pick = non_origin[0] if non_origin else matches[0]
            return pick[0], pick[1]

        def _best_remote() -> str | None:
            """Return the best remote name for this repo, or None."""
            remotes_list = list(remotes.keys())
            if not remotes_list:
                return None
            # Prefer non-origin
            non_origin = [r for r in remotes_list if r != "origin"]
            return non_origin[0] if non_origin else remotes_list[0]

        # --- target ---
        head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
        ).stdout.strip()
        local_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
        ).stdout.strip()
        target_remote, target_ref = _tracking_branch(head_sha)
        if not target_ref and local_branch != "HEAD":
            target_ref = local_branch
        if not target_remote:
            target_remote = _best_remote()
        target = {
            "sha": head_sha,
            "ref": target_ref or local_branch if local_branch != "HEAD" else None,
            "remote": target_remote,
        }

        # --- merges (parent SHAs) ---
        parents_raw = subprocess.run(
            ["git", "rev-list", "--parents", "-n", "1", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
        ).stdout.strip()
        parent_shas = parents_raw.split()[1:]  # first token is HEAD itself
        for sha in parent_shas:
            remote, ref = _tracking_branch(sha)
            if not remote:
                remote = _best_remote()
            merges.append(
                {
                    "sha": sha,
                    "remote": remote,
                    "ref": ref,
                }
            )

        # Shallow clones (depth=1) may have no parent history.
        # Fall back to the target SHA as the single merge.
        if not merges:
            merges.append(
                {
                    "sha": head_sha,
                    "remote": target_remote,
                    "ref": target_ref,
                }
            )

        return {"remotes": remotes, "merges": merges, "target": target}

    def fill_from_addons_paths(self):
        """Populate path / git_repo / manifest from the filesystem.

        Uses ``self[item]`` so it enriches addons already created by
        ``fill_from_odoo_db`` rather than creating duplicates.  If an addon
        with the same name already has a different path, the conflict is
        recorded via ``conflicting_path`` instead of raising.
        """
        for addons_path in self.addons_paths.split(","):
            if not os.path.isdir(addons_path):
                continue
            for item in os.listdir(addons_path):
                item_path = os.path.join(addons_path, item)
                if not os.path.isdir(item_path):
                    continue
                if "__manifest__.py" not in os.listdir(item_path):
                    continue

                addon = self[item]  # existing or new

                try:
                    addon.path = item_path
                except ConflictError:
                    # Same addon name found at a different path — record the conflict
                    addon.conflicting_path = item_path
                    continue

                real_path = os.path.realpath(item_path)
                git_repo = self._find_git_repo(real_path)
                if git_repo:
                    addon.git_repo = git_repo

                manifest_path = os.path.join(item_path, "__manifest__.py")
                with open(manifest_path) as f:
                    addon.manifest = literal_eval(f.read())

    def fill_from_odoo_db(self, env) -> None:
        """Populate addons from the Odoo database (``ir.module.module``).

        The DB is the authoritative source for *what* is installed. Sets
        ``db_version``, ``db_state``, ``is_installed``, ``needs_upgrade``,
        and dependency relationships. Tries to find each module on the
        filesystem to populate ``path``, ``git_repo``, and ``manifest``.
        """
        Module = env["ir.module.module"]
        for module in Module.search(
            [("state", "in", ["installed", "to upgrade", "to remove", "uninstalled"])]
        ):
            addon = self[module.name]

            addon.db_version = module.installed_version or ""
            addon.db_state = module.state
            if module.state in ("installed", "to upgrade"):
                addon.is_installed = True
            if module.state == "to upgrade":
                addon.needs_upgrade = True

            for dep in module.dependencies_id:
                dep_addon = self[dep.name]
                dep_addon.is_dependency_of.append(addon)
                addon.dependencies.append(dep_addon)

            if not addon.path:
                for addons_path in self.addons_paths.split(","):
                    candidate = os.path.join(addons_path, module.name)
                    if not os.path.isdir(candidate):
                        continue
                    if "__manifest__.py" not in os.listdir(candidate):
                        continue
                    addon.path = candidate
                    real_path = os.path.realpath(candidate)
                    git_repo = self._find_git_repo(real_path)
                    if git_repo:
                        addon.git_repo = git_repo
                    with open(os.path.join(candidate, "__manifest__.py")) as f:
                        addon.manifest = literal_eval(f.read())
                    break

    def to_dict(self):
        yield from (a.to_dict() for a in self.addons)

    def build_sources_list(self):
        sources = {}
        for addon in self.addons:
            if addon.git_repo and addon.repo_name not in sources:
                sources[addon.repo_name] = {
                    "repo": addon.git_repo,
                    "remote": addon.remote,
                    "head": addon.git_head,
                    "branch": addon.git_branch,  # None if detached HEAD
                    "lock": Addons._resolve_git_state(addon.path),
                }
        return sources

    def generate_requirements_txt(self):
        dependencies = []
        for dep in self.python_dependencies:
            try:
                dependencies.append(f"{dep}=={importlib_metadata.version(dep).split('+')[0]}")
            except importlib_metadata.PackageNotFoundError:
                dependencies.append(dep)
        return "\n".join(dependencies)

    def generate_repos_yaml(self, use_head: bool = False) -> str:
        """Generate the content of the repos.yaml file for the addons part.

        use_head: pin to current HEAD commit instead of branch name.
        """
        repos = {}
        for repo_name, infos in self.build_sources_list().items():
            if use_head or not infos["branch"]:
                target = infos["head"] or ""
            else:
                target = infos["remote"] + " " + infos["branch"]
            repos[repo_name] = {
                "defaults": {"depth": 1},
                "remotes": {infos["remote"]: infos["repo"]},
                "merges": [target],
                "target": target,
            }

        return yaml.dump(repos, default_flow_style=False)

    def generate_repos_lock(self) -> str:
        """Generate ``repos.lock.yaml`` content with pinned SHAs.

        Uses the same ``remote ref`` string format as ``repos.yaml``,
        but with commit SHAs instead of branch names.  Resolved branch
        names are included as inline YAML comments for human readability.
        """
        lines: list[str] = []
        for repo_name, infos in self.build_sources_list().items():
            lock = infos["lock"]
            lines.append(f"{repo_name}:")
            # remotes
            lines.append("  remotes:")
            for remote_name, remote_url in lock["remotes"].items():
                lines.append(f"    {remote_name}: {remote_url}")
            # merges
            lines.append("  merges:")
            for m in lock["merges"]:
                merge_line = f"    - {m['remote']} {m['sha']}"
                if m.get("ref"):
                    merge_line += f"  # {m['ref']}"
                lines.append(merge_line)
            # target
            target_line = f"  target: {lock['target']['remote']} {lock['target']['sha']}"
            if lock["target"].get("ref"):
                target_line += f"  # {lock['target']['ref']}"
            lines.append(target_line)
            lines.append("")
        return "\n".join(lines)

    def generate_addons_yaml(self):
        addons_dict: dict[str, list[str]] = {}
        for addon in self.addons:
            if not addon.repo_name:
                continue
            if addon.repo_name not in addons_dict:
                addons_dict[addon.repo_name] = []
            addons_dict[addon.repo_name].append(addon.name)

        return yaml.dump(addons_dict, default_flow_style=False)

    def generate_modules_csv_content_for_oow(self):
        return "\n".join(f"{addon.name},{addon.manifest.get('name', '')}" for addon in self.addons)
