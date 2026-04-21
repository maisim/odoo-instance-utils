from unittest.mock import MagicMock, patch

from odoo_instance_utils.addons import Addon, Addons


def make_addon(name, is_installed=False, auto_install=False, git_repo="", python_deps=None, manifest=None):
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


class TestAddonsGenerateYaml:
    def test_generate_addons_yaml(self):
        sale = make_addon("sale", git_repo="https://github.com/OCA/sale-workflow.git")
        account = make_addon("account", git_repo="https://github.com/OCA/account-financial-tools.git")
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
        mock_head = MagicMock(stdout="abc1234\n")
        mock_branch = MagicMock(stdout="16.0\n")
        # git_head is evaluated before git_branch in the dict literal
        with patch("odoo_instance_utils.addons.subprocess.run", side_effect=[mock_head, mock_branch]):
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
