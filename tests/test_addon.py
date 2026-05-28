from unittest.mock import MagicMock, patch

import pytest

from odoo_instance_utils.addons import Addon
from odoo_instance_utils.exceptions import ConflictError


def make_addon(name="sale", git_repo="", manifest=None):
    addon = Addon(name=name, path=f"/fake/{name}", git_repo=git_repo)
    addon.manifest = manifest or {}
    return addon


class TestAddonProperties:
    def test_str(self):
        assert str(make_addon("sale")) == "sale"

    def test_repr(self):
        assert repr(make_addon("sale")) == "<Addon sale>"

    def test_repo_name(self):
        addon = make_addon(git_repo="https://github.com/OCA/sale-workflow.git")
        assert addon.repo_name == "sale-workflow"

    def test_repo_name_no_git(self):
        assert make_addon().repo_name == ""

    def test_remote(self):
        addon = make_addon(git_repo="https://github.com/OCA/sale-workflow.git")
        assert addon.remote == "OCA"

    def test_remote_no_git(self):
        assert make_addon().remote == ""

    def test_fs_version(self):
        addon = make_addon(manifest={"version": "16.0.1.0.0"})
        assert addon.fs_version == "16.0.1.0.0"

    def test_fs_version_missing(self):
        assert make_addon().fs_version is None

    def test_target_version(self):
        addon = make_addon(manifest={"version": "16.0.1.0.0"})
        assert addon.target_version == "16.0"

    def test_target_version_missing(self):
        assert make_addon().target_version is None

    def test_python_dependencies(self):
        addon = make_addon(manifest={"external_dependencies": {"python": ["babel", "num2words"]}})
        assert addon.python_dependencies == ["babel", "num2words"]

    def test_python_dependencies_empty(self):
        assert make_addon().python_dependencies == []

    def test_auto_install_true(self):
        addon = make_addon(manifest={"auto_install": True})
        assert addon.auto_install is True

    def test_auto_install_default(self):
        assert make_addon().auto_install is False

    def test_path_conflict_raises(self):
        addon = Addon(name="sale", path="/path/a")
        with pytest.raises(ConflictError):
            addon.path = "/path/b"

    def test_path_same_value_ok(self):
        addon = Addon(name="sale", path="/path/a")
        addon.path = "/path/a"  # should not raise

    def test_git_head_no_repo(self):
        assert make_addon().git_head == ""

    def test_git_branch_no_repo(self):
        assert make_addon().git_branch is None

    def test_git_head_calls_subprocess(self):
        addon = make_addon(git_repo="https://github.com/OCA/sale-workflow.git")
        mock_result = MagicMock()
        mock_result.stdout = "abc1234\n"
        with patch(
            "odoo_instance_utils.addons.subprocess.run", return_value=mock_result
        ) as mock_run:
            assert addon.git_head == "abc1234"
            mock_run.assert_called_once_with(
                ["git", "rev-parse", "HEAD"],
                cwd=addon.path,
                capture_output=True,
                text=True,
            )

    def test_git_branch_detached_returns_none(self):
        addon = make_addon(git_repo="https://github.com/OCA/sale-workflow.git")
        mock_result = MagicMock()
        mock_result.stdout = "HEAD\n"
        with patch("odoo_instance_utils.addons.subprocess.run", return_value=mock_result):
            assert addon.git_branch is None

    def test_git_branch_calls_subprocess(self):
        addon = make_addon(git_repo="https://github.com/OCA/sale-workflow.git")
        mock_result = MagicMock()
        mock_result.stdout = "16.0\n"
        with patch("odoo_instance_utils.addons.subprocess.run", return_value=mock_result):
            assert addon.git_branch == "16.0"


class TestDependencies:
    def test_python_dependencies(self):
        addon = make_addon(manifest={"external_dependencies": {"python": ["babel", "num2words"]}})
        assert addon.python_dependencies == ["babel", "num2words"]

    def test_python_dependencies_empty(self):
        assert make_addon().python_dependencies == []

    def test_apt_dependencies(self):
        addon = make_addon(
            manifest={"external_dependencies": {"deb": ["libssl-dev", "postgresql-client"]}}
        )
        assert addon.apt_dependencies == ["libssl-dev", "postgresql-client"]

    def test_apt_dependencies_empty(self):
        assert make_addon().apt_dependencies == []

    def test_npm_dependencies_dict(self):
        addon = make_addon(
            manifest={"external_dependencies": {"npm": {"sass": "1.0", "less": "2.0"}}}
        )
        assert addon.npm_dependencies == ["sass@1.0", "less@2.0"]

    def test_npm_dependencies_list(self):
        addon = make_addon(manifest={"external_dependencies": {"npm": ["sass", "less"]}})
        assert addon.npm_dependencies == ["sass", "less"]

    def test_npm_dependencies_empty(self):
        assert make_addon().npm_dependencies == []

    def test_gem_dependencies(self):
        addon = make_addon(manifest={"external_dependencies": {"gem": ["sassc", "bootstrap"]}})
        assert addon.gem_dependencies == ["sassc", "bootstrap"]

    def test_gem_dependencies_empty(self):
        assert make_addon().gem_dependencies == []


class TestAnalysisProperties:
    def make_addon(self, **kwargs):
        addon = Addon(
            name=kwargs.get("name", "test_addon"),
            path=kwargs.get("path", "/fake/test_addon"),
            git_repo=kwargs.get("git_repo", ""),
        )
        addon.manifest = kwargs.get("manifest", {})
        addon.is_installed = kwargs.get("is_installed", False)
        addon.needs_upgrade = kwargs.get("needs_upgrade", False)
        addon.db_version = kwargs.get("db_version", "")
        addon.db_state = kwargs.get("db_state", "")
        addon.conflicting_path = kwargs.get("conflicting_path", "")
        return addon

    def test_fs_version_from_manifest(self):
        addon = self.make_addon(manifest={"version": "16.0.1.0.0"})
        assert addon.fs_version == "16.0.1.0.0"

    def test_fs_version_none_when_no_manifest_version(self):
        addon = self.make_addon()
        assert addon.fs_version is None

    def test_missing_from_filesystem_true(self):
        addon = self.make_addon(path="", is_installed=True)
        assert addon.missing_from_filesystem is True

    def test_missing_from_filesystem_false_when_not_installed(self):
        addon = self.make_addon(path="", is_installed=False)
        assert addon.missing_from_filesystem is False

    def test_missing_from_filesystem_false_when_path_exists(self):
        addon = self.make_addon(path="/fake/test_addon", is_installed=True)
        assert addon.missing_from_filesystem is False

    def test_version_mismatch_true(self):
        addon = self.make_addon(
            manifest={"version": "16.0.1.0.0"},
            db_version="16.0.2.0.0",
        )
        assert addon.version_mismatch is True

    def test_version_mismatch_false_when_versions_match(self):
        addon = self.make_addon(
            manifest={"version": "16.0.1.0.0"},
            db_version="16.0.1.0.0",
        )
        assert addon.version_mismatch is False

    def test_version_mismatch_false_when_no_fs_version(self):
        addon = self.make_addon(db_version="16.0.1.0.0")
        assert addon.version_mismatch is False

    def test_version_mismatch_false_when_no_db_version(self):
        addon = self.make_addon(manifest={"version": "16.0.1.0.0"})
        assert addon.version_mismatch is False

    def test_mismatch_detected_needs_upgrade(self):
        addon = self.make_addon(needs_upgrade=True)
        assert addon.mismatch_detected is True

    def test_mismatch_detected_missing_from_fs(self):
        addon = self.make_addon(path="", is_installed=True)
        assert addon.mismatch_detected is True

    def test_mismatch_detected_version_mismatch(self):
        addon = self.make_addon(
            manifest={"version": "16.0.1.0.0"},
            db_version="16.0.2.0.0",
        )
        assert addon.mismatch_detected is True

    def test_mismatch_detected_to_remove_still_on_disk(self):
        addon = self.make_addon(path="/fake/test_addon", db_state="to remove")
        assert addon.mismatch_detected is True

    def test_mismatch_detected_conflicting_path(self):
        addon = self.make_addon(conflicting_path="/other/path/test_addon")
        assert addon.mismatch_detected is True

    def test_mismatch_detected_false_when_consistent(self):
        addon = self.make_addon(
            manifest={"version": "16.0.1.0.0"},
            db_version="16.0.1.0.0",
            is_installed=True,
            path="/fake/test_addon",
        )
        assert addon.mismatch_detected is False

    def test_conflicting_path_triggers_mismatch(self):
        addon = self.make_addon(
            path="/fake/test_addon",
            conflicting_path="/other/test_addon",
        )
        assert addon.mismatch_detected is True

    def test_to_dict_includes_new_properties(self):
        addon = self.make_addon(
            manifest={"version": "16.0.1.0.0"},
            conflicting_path="/other/test_addon",
        )
        d = addon.to_dict()
        assert d["fs_version"] == "16.0.1.0.0"
        assert "version" not in d
        assert d["conflicting_path"] == "/other/test_addon"
        assert "missing_from_filesystem" in d
        assert "version_mismatch" in d
        assert "mismatch_detected" in d
