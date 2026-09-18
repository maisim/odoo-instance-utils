"""Every command that needs an Odoo environment must say so.

Commands used to read ``ctx.obj["odoo_env"]`` directly, which with click-odoo
absent raised a bare ``KeyError: 'odoo_env'`` through the real entry point —
and a ``TypeError`` when a group was invoked on its own and ``ctx.obj`` was
still ``None``. Both are failures a user cannot act on.
"""

import importlib
import sys

import pytest
from click.testing import CliRunner

MODULES = (
    "odoo_instance_utils.cli._guards",
    "odoo_instance_utils.cli.cli_addons",
    "odoo_instance_utils.cli.cli_exports",
    "odoo_instance_utils.cli.cli_filters",
    "odoo_instance_utils.cli.cli_security",
    "odoo_instance_utils.cli.cli_translations",
    "odoo_instance_utils.cli.cli_view",
    "odoo_instance_utils.cli.cli",
)


@pytest.fixture
def cli_without_odoo(monkeypatch):
    """The CLI as it loads when click-odoo is not installed."""
    monkeypatch.setitem(sys.modules, "click_odoo", None)
    for name in MODULES:
        monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module("odoo_instance_utils.cli.cli")
    assert module.has_odoo is False, "the fixture must exercise the fallback"
    return module


@pytest.mark.parametrize(
    "argv",
    [
        ["exports", "dump", "1"],
        ["exports", "restore", "{}"],
        ["filters", "list"],
        ["filters", "dump", "1"],
        ["filters", "restore", "{}"],
        ["translations", "load", __file__],
        ["view", "export", "sale.view_order_form"],
        ["security", "capture"],
        ["security", "snapshot"],
    ],
)
def test_missing_environment_is_reported_cleanly(argv, cli_without_odoo):
    result = CliRunner().invoke(cli_without_odoo.main, argv)
    assert result.exit_code == 2, result.output
    assert "requires an Odoo environment" in result.output
    assert not isinstance(result.exception, (KeyError, TypeError))


def test_lint_still_runs_without_an_environment(cli_without_odoo, tmp_path):
    """The offline half keeps working: no guard where none is needed."""
    for name in ("groups.json", "acl.json", "menus.json", "roles.json", "locks.json"):
        (tmp_path / name).write_text("[]\n", encoding="utf-8")
    result = CliRunner().invoke(cli_without_odoo.main, ["security", "lint", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "is valid" in result.output
