from unittest.mock import MagicMock, patch

import pytest

from odoo_instance_utils.addons import Addon
from odoo_instance_utils.exceptions import ConflictError, IntegrityError


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

    def test_version(self):
        addon = make_addon(manifest={"version": "16.0.1.0.0"})
        assert addon.version == "16.0.1.0.0"

    def test_version_missing(self):
        assert make_addon().version is None

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
        assert make_addon().git_branch == ""

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

    def test_git_branch_detached_raises(self):
        addon = make_addon(git_repo="https://github.com/OCA/sale-workflow.git")
        mock_result = MagicMock()
        mock_result.stdout = "HEAD\n"
        with patch("odoo_instance_utils.addons.subprocess.run", return_value=mock_result):
            with pytest.raises(IntegrityError):
                _ = addon.git_branch

    def test_git_branch_calls_subprocess(self):
        addon = make_addon(git_repo="https://github.com/OCA/sale-workflow.git")
        mock_result = MagicMock()
        mock_result.stdout = "16.0\n"
        with patch("odoo_instance_utils.addons.subprocess.run", return_value=mock_result):
            assert addon.git_branch == "16.0"
