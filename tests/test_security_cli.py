import importlib
import sys

import pytest
from click.testing import CliRunner

from odoo_instance_utils.cli.cli_security import security_group

VALID_GROUPS = """\
[
  {"slug": "sales_referential_manager", "name": "Référentiels de vente"}
]
"""

VALID_ACL = """\
[
  {"model": "sale.order", "group": "sales_referential_manager", "perm_read": true, "perm_write": true, "perm_create": true, "perm_unlink": false}
]
"""


def write_config(directory, acl=VALID_ACL):
    """Write a complete, sound configuration into *directory*."""
    (directory / "groups.json").write_text(VALID_GROUPS, encoding="utf-8")
    (directory / "acl.json").write_text(acl, encoding="utf-8")
    (directory / "menus.json").write_text("[]\n", encoding="utf-8")
    (directory / "roles.json").write_text("[]\n", encoding="utf-8")
    (directory / "locks.json").write_text("[]\n", encoding="utf-8")


def reload_without_click_odoo(monkeypatch):
    """Import the security CLI as if click-odoo were not installed."""
    monkeypatch.setitem(sys.modules, "click_odoo", None)
    for name in ("odoo_instance_utils.cli._guards", "odoo_instance_utils.cli.cli_security"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    return importlib.import_module("odoo_instance_utils.cli.cli_security")


@pytest.fixture
def runner():
    return CliRunner()


class TestLint:
    def test_sound_configuration_passes(self, runner, tmp_path):
        write_config(tmp_path)
        result = runner.invoke(security_group, ["lint", str(tmp_path)])
        assert result.exit_code == 0
        assert "is valid" in result.output

    def test_broken_configuration_fails_and_names_the_file(self, runner, tmp_path):
        write_config(tmp_path, acl=VALID_ACL.replace("sales_referential_manager", "inconnu"))
        result = runner.invoke(security_group, ["lint", str(tmp_path)])
        assert result.exit_code == 1
        assert "acl.json" in result.output
        assert "inconnu" in result.output

    def test_missing_directory_is_reported_clearly(self, runner, tmp_path):
        result = runner.invoke(security_group, ["lint", str(tmp_path / "absent")])
        assert result.exit_code == 1
        assert "is not a directory" in result.output

    def test_lint_needs_no_odoo_environment(self, runner, tmp_path, monkeypatch):
        """The whole point of the offline half: no click-odoo, still works."""
        write_config(tmp_path)
        module = reload_without_click_odoo(monkeypatch)
        result = runner.invoke(module.security_group, ["lint", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert "is valid" in result.output


class TestGuardedCommands:
    def test_capture_without_an_environment_fails_cleanly(self, runner):
        # A UsageError, not a KeyError: the guard is what makes the message.
        result = runner.invoke(security_group, ["capture"])
        assert result.exit_code == 2
        assert "requires an Odoo environment" in result.output

    def test_snapshot_without_an_environment_fails_cleanly(self, runner):
        result = runner.invoke(security_group, ["snapshot"])
        assert result.exit_code == 2
        assert "requires an Odoo environment" in result.output

    def test_guarded_commands_report_cleanly_without_click_odoo(self, runner, monkeypatch):
        module = reload_without_click_odoo(monkeypatch)
        result = runner.invoke(module.security_group, ["capture"])
        assert result.exit_code == 2
        assert "click-odoo is not installed" in result.output
