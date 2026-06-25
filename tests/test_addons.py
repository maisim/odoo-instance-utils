from unittest.mock import MagicMock, patch

from odoo_instance_utils.addons import Addon, Addons


def make_addon(
    name, is_installed=False, auto_install=False, git_repo="", python_deps=None, manifest=None
):
    addon = Addon(name=name, path=f"/fake/{name}", git_repo=git_repo)
    addon.is_installed = is_installed
    addon.manifest = manifest or {
        "auto_install": auto_install,
        "external_dependencies": {"python": python_deps or []},
    }
    return addon


def make_addons(*addons):
    return Addons(addons=list(addons))


class TestAddonsFiltering:
    def test_all_addons_by_default(self):
        sale = make_addon("sale")
        account = make_addon("account")
        addons = make_addons(sale, account)
        assert list(addons) == [sale, account]

    def test_filter_installed_true(self):
        sale = make_addon("sale", is_installed=True)
        account = make_addon("account", is_installed=False)
        addons = make_addons(sale, account)(installed=True)
        assert list(addons) == [sale]

    def test_filter_installed_false(self):
        sale = make_addon("sale", is_installed=True)
        account = make_addon("account", is_installed=False)
        addons = make_addons(sale, account)(installed=False)
        assert list(addons) == [account]

    def test_exclude_auto_installed(self):
        crm = make_addon("crm", auto_install=True)
        sale = make_addon("sale", auto_install=False)
        addons = make_addons(crm, sale)(include_auto_installed_addons=False)
        assert list(addons) == [sale]

    def test_filter_needs_upgrade(self):
        sale = make_addon("sale", is_installed=True)
        sale.needs_upgrade = True
        account = make_addon("account", is_installed=True)
        addons = make_addons(sale, account)(needs_upgrade=True)
        assert list(addons) == [sale]

    def test_filter_needs_upgrade_empty(self):
        sale = make_addon("sale", is_installed=True)
        addons = make_addons(sale)(needs_upgrade=True)
        assert list(addons) == []

    def test_minimize_list_removes_covered_deps(self):
        account = make_addon("account", is_installed=True)
        sale = make_addon("sale", is_installed=True)
        sale.dependencies = [account]  # sale dépend de account
        addons = make_addons(sale, account)(minimize_list=True)
        # account est une dep de sale → doit être exclu de la liste minimale
        result_names = [a.name for a in addons]
        assert "sale" in result_names
        assert "account" not in result_names

    def test_minimize_list_keeps_root_addons(self):
        sale = make_addon("sale", is_installed=True)
        crm = make_addon("crm", is_installed=True)
        addons = make_addons(sale, crm)(minimize_list=True)
        result_names = [a.name for a in addons]
        assert "sale" in result_names
        assert "crm" in result_names

    def test_getitem_existing(self):
        sale = make_addon("sale")
        addons = make_addons(sale)
        assert addons["sale"] is sale

    def test_getitem_missing_returns_empty_addon(self):
        addons = make_addons()
        result = addons["unknown"]
        assert result.name == "unknown"

    def test_len(self):
        addons = make_addons(make_addon("sale"), make_addon("account"))
        assert len(addons) == 2

    def test_str(self):
        addons = make_addons(make_addon("sale"), make_addon("account"))
        assert str(addons) == "sale\naccount"


class TestAddonsPythonDependencies:
    def test_aggregates_deps(self):
        sale = make_addon("sale", python_deps=["babel"])
        account = make_addon("account", python_deps=["babel", "num2words"])
        addons = make_addons(sale, account)
        deps = addons.python_dependencies
        assert set(deps) == {"babel", "num2words"}

    def test_no_deps(self):
        addons = make_addons(make_addon("sale"))
        assert addons.python_dependencies == []


class TestAddonsDependenciesAggregation:
    def test_aggregates_apt_deps(self):
        sale = make_addon("sale", manifest={"external_dependencies": {"deb": ["libssl-dev"]}})
        account = make_addon(
            "account",
            manifest={"external_dependencies": {"deb": ["libssl-dev", "postgresql-client"]}},
        )
        addons = make_addons(sale, account)
        assert addons.apt_dependencies == ["libssl-dev", "postgresql-client"]

    def test_no_apt_deps(self):
        addons = make_addons(make_addon("sale"))
        assert addons.apt_dependencies == []

    def test_aggregates_npm_deps(self):
        sale = make_addon("sale", manifest={"external_dependencies": {"npm": {"sass": "1.0"}}})
        crm = make_addon("crm", manifest={"external_dependencies": {"npm": {"less": "2.0"}}})
        addons = make_addons(sale, crm)
        assert sorted(addons.npm_dependencies) == ["less@2.0", "sass@1.0"]

    def test_aggregates_gem_deps(self):
        sale = make_addon("sale", manifest={"external_dependencies": {"gem": ["sassc"]}})
        account = make_addon("account", manifest={"external_dependencies": {"gem": ["bootstrap"]}})
        addons = make_addons(sale, account)
        assert addons.gem_dependencies == ["bootstrap", "sassc"]


class TestAddonsGenerateYaml:
    def test_generate_addons_yaml(self):
        sale = make_addon("sale", git_repo="https://github.com/OCA/sale-workflow.git")
        account = make_addon(
            "account", git_repo="https://github.com/OCA/account-financial-tools.git"
        )
        addons = make_addons(sale, account)
        content = addons.generate_addons_yaml()
        assert "sale-workflow" in content
        assert "account-financial-tools" in content
        assert "sale" in content
        assert "account" in content

    def test_generate_addons_yaml_skips_no_repo(self):
        sale = make_addon("sale")  # no git_repo
        addons = make_addons(sale)
        content = addons.generate_addons_yaml()
        assert content.strip() == "{}"

    def test_generate_repos_yaml(self):
        sale = make_addon("sale", git_repo="https://github.com/OCA/sale-workflow.git")
        sha = "abc1234\n"
        branch = "16.0\n"
        remotes_out = "OCA\thttps://github.com/OCA/sale-workflow.git (fetch)\n"
        tracking_out = "OCA/16.0\n"
        parents_out = "abc1234 abc1234\n"
        with patch(
            "odoo_instance_utils.addons.subprocess.run",
            side_effect=[
                # 1. addon.git_head: git rev-parse HEAD
                MagicMock(stdout=sha),
                # 2. addon.git_branch: git rev-parse --abbrev-ref HEAD
                MagicMock(stdout=branch),
                # 3. _resolve_git_state: git remote -v
                MagicMock(stdout=remotes_out),
                # 4. _resolve_git_state: git rev-parse HEAD
                MagicMock(stdout=sha),
                # 5. _resolve_git_state: git rev-parse --abbrev-ref HEAD
                MagicMock(stdout=branch),
                # 6. _resolve_git_state: git branch -r --contains HEAD (target)
                MagicMock(stdout=tracking_out),
                # 7. _resolve_git_state: git rev-list --parents -n 1 HEAD
                MagicMock(stdout=parents_out),
                # 8. _resolve_git_state: git branch -r --contains <parent1>
                MagicMock(stdout=tracking_out),
            ],
        ):
            addons = make_addons(sale)
            content = addons.generate_repos_yaml()
        assert "sale-workflow" in content
        assert "OCA" in content
        assert "16.0" in content


class TestFillFromAddonsPaths:
    def test_fills_addons_from_path(self, tmp_path):
        addon_dir = tmp_path / "my_addon"
        addon_dir.mkdir()
        manifest = addon_dir / "__manifest__.py"
        manifest.write_text('{"name": "My Addon", "version": "16.0.1.0.0", "depends": ["base"]}')

        with patch("odoo_instance_utils.addons.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="")
            addons = Addons(addons_paths=str(tmp_path))

        assert len(addons._addons) == 1
        assert addons._addons[0].name == "my_addon"
        assert addons._addons[0].manifest["version"] == "16.0.1.0.0"

    def test_fills_git_repo_from_git_dir(self, tmp_path):
        addon_dir = tmp_path / "my_addon"
        addon_dir.mkdir()
        (addon_dir / "__manifest__.py").write_text('{"name": "My Addon", "depends": []}')
        (tmp_path / ".git").mkdir()

        with patch("odoo_instance_utils.addons.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="https://github.com/OCA/repo.git\n")
            addons = Addons(addons_paths=str(tmp_path))

        assert addons._addons[0].git_repo == "https://github.com/OCA/repo.git"

    def test_ignores_dirs_without_manifest(self, tmp_path):
        (tmp_path / "not_an_addon").mkdir()
        with patch("odoo_instance_utils.addons.subprocess.run", return_value=MagicMock(stdout="")):
            addons = Addons(addons_paths=str(tmp_path))
        assert len(addons._addons) == 0

    def test_symlink_resolves_real_path_for_git_repo(self, tmp_path):
        real_repo = tmp_path / "real_repo"
        real_repo.mkdir()
        (real_repo / ".git").mkdir()
        real_addon = real_repo / "my_addon"
        real_addon.mkdir()
        (real_addon / "__manifest__.py").write_text('{"name": "My Addon", "depends": []}')

        addons_path = tmp_path / "addons"
        addons_path.mkdir()
        symlink = addons_path / "my_addon"
        symlink.symlink_to(real_addon)

        with patch("odoo_instance_utils.addons.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="https://github.com/OCA/repo.git\n")
            addons = Addons(addons_paths=str(addons_path))

        assert len(addons._addons) == 1
        assert addons._addons[0].name == "my_addon"
        assert addons._addons[0].git_repo == "https://github.com/OCA/repo.git"

    def test_addon_not_in_git_repo_gets_empty_string(self, tmp_path):
        addon_dir = tmp_path / "my_addon"
        addon_dir.mkdir()
        (addon_dir / "__manifest__.py").write_text('{"name": "My Addon", "depends": []}')

        with patch("odoo_instance_utils.addons.subprocess.run", return_value=MagicMock(stdout="")):
            addons = Addons(addons_paths=str(tmp_path))

        assert len(addons._addons) == 1
        assert addons._addons[0].name == "my_addon"
        assert addons._addons[0].git_repo == ""

    def test_duplicate_addon_name_different_path_records_conflict(self, tmp_path):
        path_a = tmp_path / "a"
        path_a.mkdir()
        addon_a = path_a / "my_addon"
        addon_a.mkdir()
        (addon_a / "__manifest__.py").write_text('{"name": "Addon A", "depends": []}')

        path_b = tmp_path / "b"
        path_b.mkdir()
        addon_b = path_b / "my_addon"
        addon_b.mkdir()
        (addon_b / "__manifest__.py").write_text('{"name": "Addon B", "depends": []}')

        addons_paths = f"{path_a},{path_b}"
        with patch("odoo_instance_utils.addons.subprocess.run", return_value=MagicMock(stdout="")):
            addons = Addons(addons_paths=addons_paths)

        assert len(addons._addons) == 1
        assert addons._addons[0].name == "my_addon"
        assert addons._addons[0].path == str(addon_a)
        assert addons._addons[0].conflicting_path == str(addon_b)
        assert addons._addons[0].mismatch_detected is True

    def test_fill_from_odoo_db_creates_installed_addons(self):
        env = MagicMock()
        module_model = MagicMock()
        env.__getitem__.return_value = module_model

        dep = MagicMock()
        dep.name = "base"

        module = MagicMock()
        module.name = "sale"
        module.installed_version = "16.0.1.0.0"
        module.state = "installed"
        module.dependencies_id = [dep]

        module_model.search.return_value = [module]

        addons = Addons()
        addons.fill_from_odoo_db(env)

        assert len(addons._addons) == 2  # sale + base (dependency)
        sale = addons["sale"]
        assert sale.db_version == "16.0.1.0.0"
        assert sale.db_state == "installed"
        assert sale.is_installed is True
        assert sale.needs_upgrade is False

        # base was created as a dependency
        base = addons["base"]
        assert sale.dependencies == [base]
        assert base.is_dependency_of == [sale]

    def test_fill_from_odoo_db_sets_needs_upgrade(self):
        env = MagicMock()
        module_model = MagicMock()
        env.__getitem__.return_value = module_model

        module = MagicMock()
        module.name = "sale"
        module.installed_version = "16.0.1.0.0"
        module.state = "to upgrade"
        module.dependencies_id = []

        module_model.search.return_value = [module]

        addons = Addons()
        addons.fill_from_odoo_db(env)

        sale = addons["sale"]
        assert sale.db_state == "to upgrade"
        assert sale.is_installed is True
        assert sale.needs_upgrade is True

    def test_fill_from_addons_paths_enriches_db_addons(self, tmp_path):
        addon_dir = tmp_path / "sale"
        addon_dir.mkdir()
        (addon_dir / "__manifest__.py").write_text(
            '{"name": "Sale", "version": "16.0.1.0.0", "depends": ["base"]}'
        )
        (tmp_path / ".git").mkdir()

        # DB first
        addons = Addons(addons_paths=str(tmp_path))
        env = MagicMock()
        module_model = MagicMock()
        env.__getitem__.return_value = module_model

        module = MagicMock()
        module.name = "sale"
        module.installed_version = "16.0.1.0.0"
        module.state = "installed"
        module.dependencies_id = []
        module_model.search.return_value = [module]

        addons.fill_from_odoo_db(env)

        with patch("odoo_instance_utils.addons.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="https://github.com/OCA/sale.git\n")
            addons.fill_from_addons_paths()

        sale = addons["sale"]
        assert sale.path == str(addon_dir)
        assert sale.git_repo == "https://github.com/OCA/sale.git"
        assert sale.manifest["version"] == "16.0.1.0.0"
        assert sale.db_version == "16.0.1.0.0"
        assert len(addons._addons) == 1  # no duplicates

    def test_fill_from_odoo_db_standalone(self):
        """fill_from_odoo_db works without prior filesystem scan."""
        addons = Addons()  # no addons_paths
        env = MagicMock()
        module_model = MagicMock()
        env.__getitem__.return_value = module_model

        module = MagicMock()
        module.name = "sale"
        module.installed_version = "16.0.1.0.0"
        module.state = "installed"
        module.dependencies_id = []
        module_model.search.return_value = [module]

        addons.fill_from_odoo_db(env)

        assert len(addons._addons) == 1
        sale = addons["sale"]
        assert sale.is_installed is True
        assert sale.path == ""  # no filesystem scan
        assert sale.missing_from_filesystem is True
        assert sale.mismatch_detected is True

    def test_fill_from_addons_paths_standalone(self, tmp_path):
        """fill_from_addons_paths still works independently."""
        addon_dir = tmp_path / "my_addon"
        addon_dir.mkdir()
        (addon_dir / "__manifest__.py").write_text('{"name": "My Addon", "depends": []}')

        with patch("odoo_instance_utils.addons.subprocess.run", return_value=MagicMock(stdout="")):
            addons = Addons(addons_paths=str(tmp_path))

        assert len(addons._addons) == 1
        assert addons._addons[0].name == "my_addon"
        assert addons._addons[0].is_installed is False  # no DB info


class TestResolveGitState:
    """Tests for Addons._resolve_git_state."""

    def test_simple_repo_no_merges(self):
        sha = "abc1234\n"
        with patch(
            "odoo_instance_utils.addons.subprocess.run",
            side_effect=[
                # git remote -v
                MagicMock(
                    stdout="OCA\thttps://github.com/OCA/repo.git (fetch)\nOCA\thttps://github.com/OCA/repo.git (push)\n"
                ),
                # git rev-parse HEAD
                MagicMock(stdout=sha),
                # git rev-parse --abbrev-ref HEAD
                MagicMock(stdout="16.0\n"),
                # git branch -r --contains HEAD
                MagicMock(stdout="OCA/16.0\n"),
                # git rev-list --parents -n 1 HEAD
                MagicMock(stdout="abc1234 abc1234\n"),
                # git branch -r --contains <parent1>
                MagicMock(stdout="OCA/16.0\n"),
            ],
        ):
            state = Addons._resolve_git_state("/fake/repo")

        assert state["remotes"] == {"OCA": "https://github.com/OCA/repo"}
        assert state["target"]["sha"] == "abc1234"
        assert state["target"]["ref"] == "16.0"
        assert state["target"]["remote"] == "OCA"
        assert len(state["merges"]) == 1
        assert state["merges"][0]["sha"] == "abc1234"
        assert state["merges"][0]["ref"] == "16.0"

    def test_merge_commit_multiple_parents(self):
        with patch(
            "odoo_instance_utils.addons.subprocess.run",
            side_effect=[
                MagicMock(
                    stdout="OCA\thttps://github.com/OCA/repo.git (fetch)\nmaisim\thttps://github.com/maisim/repo.git (fetch)\n"
                ),
                MagicMock(stdout="merge123\n"),
                MagicMock(stdout="16.0-target\n"),
                MagicMock(stdout=""),
                MagicMock(stdout="merge123 base123 feature123\n"),
                MagicMock(stdout="OCA/16.0\n"),
                MagicMock(stdout="maisim/16.0-feature\n"),
            ],
        ):
            state = Addons._resolve_git_state("/fake/repo")

        assert len(state["remotes"]) == 2
        assert state["target"]["sha"] == "merge123"
        assert state["target"]["ref"] == "16.0-target"
        assert len(state["merges"]) == 2
        assert state["merges"][0]["sha"] == "base123"
        assert state["merges"][0]["ref"] == "16.0"
        assert state["merges"][0]["remote"] == "OCA"
        assert state["merges"][1]["sha"] == "feature123"
        assert state["merges"][1]["ref"] == "16.0-feature"
        assert state["merges"][1]["remote"] == "maisim"

    def test_filters_origin_partial_clone(self):
        with patch(
            "odoo_instance_utils.addons.subprocess.run",
            side_effect=[
                MagicMock(
                    stdout=(
                        "origin\thttps://github.com/OCA/repo.git (fetch) [blob:none]\n"
                        "origin\thttps://github.com/OCA/repo.git (push)\n"
                        "OCA\thttps://github.com/OCA/repo.git (fetch)\n"
                        "OCA\thttps://github.com/OCA/repo.git (push)\n"
                    )
                ),
                MagicMock(stdout="abc1234\n"),
                MagicMock(stdout="16.0\n"),
                MagicMock(stdout="OCA/16.0\n"),
                MagicMock(stdout="abc1234 abc1234\n"),
                MagicMock(stdout="OCA/16.0\n"),
            ],
        ):
            state = Addons._resolve_git_state("/fake/repo")

        assert "origin" not in state["remotes"]
        assert "OCA" in state["remotes"]

    def test_no_origin_keeps_origin(self):
        with patch(
            "odoo_instance_utils.addons.subprocess.run",
            side_effect=[
                MagicMock(
                    stdout=(
                        "origin\thttps://github.com/OCA/repo.git (fetch)\n"
                        "origin\thttps://github.com/OCA/repo.git (push)\n"
                    )
                ),
                MagicMock(stdout="abc1234\n"),
                MagicMock(stdout="16.0\n"),
                MagicMock(stdout="origin/16.0\n"),
                MagicMock(stdout="abc1234 abc1234\n"),
                MagicMock(stdout="origin/16.0\n"),
            ],
        ):
            state = Addons._resolve_git_state("/fake/repo")

        assert "origin" in state["remotes"]

    def test_parent_unresolved_ref_is_none(self):
        sha = "abc1234\n"
        with patch(
            "odoo_instance_utils.addons.subprocess.run",
            side_effect=[
                MagicMock(stdout="OCA\thttps://github.com/OCA/repo.git (fetch)\n"),
                MagicMock(stdout=sha),
                MagicMock(stdout="HEAD\n"),
                MagicMock(stdout=""),
                MagicMock(stdout="abc1234 abc1234\n"),
                MagicMock(stdout=""),
            ],
        ):
            state = Addons._resolve_git_state("/fake/repo")

        assert state["target"]["ref"] is None
        assert state["merges"][0]["ref"] is None

    def test_target_ref_from_local_branch_but_no_tracking(self):
        """When tracking branch returns nothing, fall back to local branch name."""
        sha = "abc1234\n"
        with patch(
            "odoo_instance_utils.addons.subprocess.run",
            side_effect=[
                MagicMock(stdout="OCA\thttps://github.com/OCA/repo.git (fetch)\n"),
                MagicMock(stdout=sha),
                MagicMock(stdout="16.0-target\n"),
                MagicMock(stdout=""),
                MagicMock(stdout="abc1234 abc1234\n"),
                MagicMock(stdout=""),
            ],
        ):
            state = Addons._resolve_git_state("/fake/repo")

        assert state["target"]["ref"] == "16.0-target"
        assert state["target"]["remote"] == "OCA"  # falls back to best remote

    def test_shallow_clone_falls_back_to_target_sha(self):
        """When no parent history (shallow clone), use target SHA as merge."""
        sha = "abc1234\n"
        with patch(
            "odoo_instance_utils.addons.subprocess.run",
            side_effect=[
                MagicMock(stdout="OCA\thttps://github.com/OCA/repo.git (fetch)\n"),
                MagicMock(stdout=sha),
                MagicMock(stdout="16.0\n"),
                MagicMock(stdout="OCA/16.0\n"),
                MagicMock(stdout="abc1234\n"),  # rev-list: no parents (shallow)
            ],
        ):
            state = Addons._resolve_git_state("/fake/repo")

        assert len(state["merges"]) == 1
        assert state["merges"][0]["sha"] == "abc1234"
        assert state["merges"][0]["ref"] == "16.0"

    def test_generate_repos_lock_yaml(self):
        sale = make_addon("sale", git_repo="https://github.com/OCA/sale-workflow.git")
        sha = "abc1234\n"
        branch = "16.0\n"
        remotes_out = "OCA\thttps://github.com/OCA/sale-workflow.git (fetch)\n"
        tracking_out = "OCA/16.0\n"
        parents_out = "abc1234 abc1234\n"
        with patch(
            "odoo_instance_utils.addons.subprocess.run",
            side_effect=[
                MagicMock(stdout=sha),
                MagicMock(stdout=branch),
                MagicMock(stdout=remotes_out),
                MagicMock(stdout=sha),
                MagicMock(stdout=branch),
                MagicMock(stdout=tracking_out),
                MagicMock(stdout=parents_out),
                MagicMock(stdout=tracking_out),
            ],
        ):
            addons = make_addons(sale)
            content = addons.generate_repos_lock()

        assert "sale-workflow" in content
        assert "OCA" in content
        assert "abc1234" in content
        assert "OCA abc1234  # 16.0" in content  # inline comment

    def test_fill_from_odoo_db_finds_filesystem_path(self, tmp_path):
        addon_dir = tmp_path / "sale"
        addon_dir.mkdir()
        (addon_dir / "__manifest__.py").write_text(
            '{"name": "Sale", "version": "16.0.1.0.0", "depends": ["base"]}'
        )

        env = MagicMock()
        module_model = MagicMock()
        env.__getitem__.return_value = module_model

        dep = MagicMock()
        dep.name = "base"

        module = MagicMock()
        module.name = "sale"
        module.installed_version = "16.0.1.0.0"
        module.state = "installed"
        module.dependencies_id = [dep]
        module_model.search.return_value = [module]

        addons = Addons(addons_paths=str(tmp_path))
        addons.fill_from_odoo_db(env)

        sale = addons["sale"]
        assert sale.path == str(addon_dir)
        assert sale.manifest["version"] == "16.0.1.0.0"


class TestFindGitRepoWorktree:
    """Tests for _find_git_repo with git worktrees (.git as a file)."""

    def test_git_dir(self, tmp_path):
        """Regular repo: .git is a directory."""
        addon_dir = tmp_path / "my_addon"
        addon_dir.mkdir()
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        with patch("odoo_instance_utils.addons.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="https://github.com/OCA/repo.git\n")
            result = Addons._find_git_repo(str(addon_dir))

        assert result == "https://github.com/OCA/repo.git"

    def test_git_file_worktree(self, tmp_path):
        """Worktree: .git is a file containing a gitdir: reference."""
        addon_dir = tmp_path / "my_addon"
        addon_dir.mkdir()
        # In a worktree, .git is a file, not a directory
        git_file = tmp_path / ".git"
        git_file.write_text("gitdir: /main/.git/worktrees/wt1\n")

        with patch("odoo_instance_utils.addons.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="https://github.com/OCA/repo.git\n")
            result = Addons._find_git_repo(str(addon_dir))

        assert result == "https://github.com/OCA/repo.git"

    def test_no_git_at_all(self, tmp_path):
        """No .git file or directory anywhere."""
        addon_dir = tmp_path / "my_addon"
        addon_dir.mkdir()

        result = Addons._find_git_repo(str(addon_dir))
        assert result == ""

    def test_worktree_git_repo_populated_in_addon(self, tmp_path):
        """Integration: addon from a worktree gets its git_repo set."""
        addon_dir = tmp_path / "my_addon"
        addon_dir.mkdir()
        (addon_dir / "__manifest__.py").write_text('{"name": "My Addon", "depends": []}')
        # Worktree .git is a file
        git_file = tmp_path / ".git"
        git_file.write_text("gitdir: /main/.git/worktrees/wt1\n")

        with patch("odoo_instance_utils.addons.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="https://github.com/OCA/repo.git\n")
            addons = Addons(addons_paths=str(tmp_path))

        assert addons._addons[0].git_repo == "https://github.com/OCA/repo.git"
        assert addons._addons[0].repo_name == "repo"


class TestComposableFilters:
    """Filters should compose rather than short-circuit."""

    def test_installed_and_exclude_auto_installed(self):
        """installed=True + include_auto_installed_addons=False composes correctly."""
        crm = make_addon("crm", is_installed=True, auto_install=True)
        sale = make_addon("sale", is_installed=True, auto_install=False)
        account = make_addon("account", is_installed=False, auto_install=False)
        addons = make_addons(crm, sale, account)(
            installed=True, include_auto_installed_addons=False
        )
        assert list(addons) == [sale]

    def test_installed_and_minimize(self):
        """installed=True + minimize_list=True composes correctly."""
        account = make_addon("account", is_installed=True)
        sale = make_addon("sale", is_installed=True)
        sale.dependencies = [account]
        uninstalled = make_addon("uninstalled", is_installed=False)
        addons = make_addons(sale, account, uninstalled)(installed=True, minimize_list=True)
        result_names = [a.name for a in addons]
        assert "sale" in result_names
        assert "account" not in result_names
        assert "uninstalled" not in result_names

    def test_exclude_auto_installed_no_installed_filter(self):
        """include_auto_installed_addons=False alone returns all non-auto addons."""
        crm = make_addon("crm", is_installed=True, auto_install=True)
        sale = make_addon("sale", is_installed=False, auto_install=False)
        addons = make_addons(crm, sale)(include_auto_installed_addons=False)
        assert list(addons) == [sale]
