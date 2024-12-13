import os
import sys

from ast import literal_eval

from .exceptions import ConflictError, IntegrityError
import yaml

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
        self.is_dependency_of = []
        self.manifest = {}

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
            raise ConflictError(
                f"An addon {self.name} already exists with a different path"
            )
        self._path = value

    @property
    def repo_name(self):
        return self.git_repo.split("/")[-1].split(".")[0] if self.git_repo else ""

    @property
    def git_head(self):
        if self.git_repo:
            return os.popen(f"cd {self.path} && git rev-parse HEAD").read().strip()
        return ""

    @property
    def git_branch(self):
        if self.git_repo:
            branch = (
                os.popen(f"cd {self.path} && git rev-parse --abbrev-ref HEAD")
                .read()
                .strip()
            )
            if branch == "HEAD":
                raise IntegrityError(
                    f"Repo {self.repo_name} is in detached HEAD state ({self._path})"
                )
            return branch
        return ""

    @property
    def remote(self):
        return self.git_repo.split("/")[-2] if self.git_repo else ""

    @property
    def version(self):
        return self.manifest.get("version", None)

    @property
    def target_version(self):
        version = self.manifest.get("version", None)
        if version:
            return ".".join(version.split(".")[0:2])

    @property
    def python_dependencies(self):
        return self.manifest.get("external_dependencies", {}).get("python", [])

    @property
    def auto_install(self):
        return self.manifest.get("auto_install", False)

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
            "remote": self.remote,
            "version": self.version,
            "target_version": self.target_version,
            "auto_install": self.auto_install,
        }


class Addons:

    # Filters
    installed = None
    minimize_list = False
    include_auto_installed_addons = True

    def __init__(self, addons_paths: list = [], addons: list = []):
        self._addons = addons
        self.addons_paths = addons_paths
        if addons_paths:
            self.fill_from_addons_paths()

    def __call__(
        self,
        installed=None,
        minimize_list=False,
        include_auto_installed_addons=True,
        remotes=None,
    ):
        """Filter the addons list"""
        self.installed = installed
        self.minimize_list = minimize_list
        self.include_auto_installed_addons = include_auto_installed_addons
        self.remotes = remotes
        return self

    def __str__(self):
        return "\n".join([a.name for a in self.addons])

    def __len__(self):
        return len(self.addons)

    def __iter__(self):
        return iter(self.addons)

    def __getitem__(self, addon_name):
        return next(
            (a for a in self.addons if a.name == addon_name), Addon(name=addon_name)
        )

    @property
    def addons(self):
        if self.installed is True:
            return [a for a in self._addons if a.is_installed]
        elif self.installed is False:
            return [a for a in self._addons if not a.is_installed]

        if self.include_auto_installed_addons is False:
            return [a for a in self._addons if not a.auto_install]

        if self.minimize_list:
            current_addons_names = [a.name for a in self._addons]
            addons = [a for a in self._addons if a.name not in current_addons_names]
            return addons

        return self._addons

    @property
    def python_dependencies(self):
        dependencies = []
        for addon in self.addons:
            dependencies.extend(addon.python_dependencies)

        return list(set(dependencies))

    def fill_from_addons_paths(self):
        """Fill the addons list from the addons paths defined in self.addons_paths"""
        for addons_path in self.addons_paths.split(","):
            if os.path.isdir(addons_path):
                git_repo = ""
                if os.path.isdir(os.path.join(addons_path, ".git")):
                    git_repo = (
                        os.popen(
                            f"cd {addons_path} && git config --get remote.origin.url"
                        )
                        .read()
                        .strip()
                    )

                for item in os.listdir(addons_path):
                    item_path = os.path.join(addons_path, item)
                    if os.path.isdir(item_path) and "__manifest__.py" in os.listdir(
                        item_path
                    ):
                        addon = Addon(name=item, path=item_path, git_repo=git_repo)
                        with open(os.path.join(item_path, "__manifest__.py"), "r") as f:
                            addon.manifest = literal_eval(f.read())
                        self.addons.append(addon)

    def to_dict(self):
        yield from (a.to_dict() for a in self.addons)

    def build_sources_list(self):
        sources = {}
        for addon in self.addons:
            if addon.git_repo:
                sources[addon.repo_name] = {
                    "repo": addon.git_repo,
                    "remote": addon.remote,
                    "head": addon.git_head,
                    "branch": addon.git_branch,
                }
        return sources

    def generate_requirements_txt(self):
        dependencies = []
        for dep in self.python_dependencies():
            try:
                dependencies.append(
                    f"{dep}=={importlib_metadata.version(dep).split('+')[0]}"
                )
            except importlib_metadata.PackageNotFoundError:
                dependencies.append(dep)
        return "\n".join(dependencies)

    def generate_repos_yaml(self):
        """Generate the content of the repos.yaml file for the addons part"""

        for repo_name, infos in self.build_sources_list().items():
            target = (
                infos["remote"] + " " + infos["branch"]
                if infos["branch"]
                else infos["head"]
            )

        repos = {}
        for repo_name, infos in self.build_sources_list().items():
            target = (
                infos["remote"] + " " + infos["branch"]
                if infos["branch"]
                else infos["head"]
            )
            repos[repo_name] = {
                "defaults": {"depth": 1},
                "remotes": {infos["remote"]: infos["repo"]},
                "merges": [target],
                "target": target,
            }

        return yaml.dump(repos, default_flow_style=False)

    def generate_addons_yaml(self):
        addons_dict = {}
        for addon in self.addons:
            if not addon.repo_name:
                continue
            if addon.repo_name not in addons_dict:
                addons_dict[addon.repo_name] = []
            addons_dict[addon.repo_name].append(addon.name)

        return yaml.dump(addons_dict, default_flow_style=False)

    def generate_modules_csv_content_for_oow(self):
        return "\n".join(
            f"{addon.name},{addon.manifest.get('name', '')}" for addon in self.addons
        )
