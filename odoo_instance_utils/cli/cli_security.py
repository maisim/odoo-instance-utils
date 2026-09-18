from __future__ import annotations

import sys
from pathlib import Path

import click

from odoo_instance_utils.cli._guards import require_odoo as _require_odoo
from odoo_instance_utils.security_config import (
    dump_security_document,
    lint_security_directory,
    write_security_config,
)

DEFAULT_CONFIG_DIR = "odoo/custom/src/security"


def _split(values: tuple) -> list[str] | None:
    """Flatten repeatable, comma-separated options into a list of names."""
    if not values:
        return None
    names: list[str] = []
    for value in values:
        names.extend(part.strip() for part in value.split(",") if part.strip())
    return names


@click.group("security")
def security_group():
    """Access-rights configuration commands."""
    pass


@security_group.command("lint")
@click.argument(
    "config_dir",
    type=click.Path(file_okay=False),
    default=DEFAULT_CONFIG_DIR,
    required=False,
)
def security_lint(config_dir):
    """Validate the committed access-rights configuration.

    CONFIG_DIR must hold groups.json, acl.json, menus.json, roles.json and
    locks.json. Defaults to odoo/custom/src/security.

    Runs without Odoo: shape, schema and cross-file references are checked
    here, while whether a group or model actually exists is a question for
    'security check' against a live instance.
    """
    config_dir = Path(config_dir)
    if not config_dir.is_dir():
        click.echo(f"error: {config_dir} is not a directory", err=True)
        sys.exit(1)

    issues = lint_security_directory(config_dir)
    if not issues:
        click.echo(f"ok: {config_dir} is valid")
        return

    for issue in issues:
        click.echo(f"  - {issue}", err=True)
    click.echo(f"{len(issues)} issue(s) found", err=True)
    sys.exit(1)


@security_group.command("capture")
@click.option(
    "--models",
    multiple=True,
    help="Restrict ACL lines to these models (repeatable, comma-separated).",
)
@click.option(
    "--groups",
    multiple=True,
    help="Restrict groups to these xmlids (repeatable, comma-separated).",
)
@click.option(
    "--roles",
    multiple=True,
    help="Restrict roles to these xmlids (repeatable, comma-separated).",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(file_okay=False),
    default=None,
    help="Write the five policy files here (default: print JSON to stdout).",
)
@click.pass_context
def security_capture(ctx, models, groups, roles, output):
    """Capture the access rights the project manages, from the live instance.

    Scoped by design: a real database carries thousands of ACL lines shipped
    by Odoo and the OCA addons, which are not the project's to assert. Only
    what is named here is captured, so the output stays editable into a
    policy.
    """
    _require_odoo(ctx)
    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    instance = OdooInstance(env=env)  # type: ignore[operator]
    config = instance.dump_security_config(
        models=_split(models),
        groups=_split(groups),
        roles=_split(roles),
    )

    if output:
        written = write_security_config(config, output)
        click.echo(f"wrote {', '.join(path.name for path in written)} to {output}")
        return

    click.echo(dump_security_document(config))


@security_group.command("snapshot")
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False),
    default=None,
    help="Write the snapshot here (default: print JSON to stdout).",
)
@click.pass_context
def security_snapshot(ctx, output):
    """Capture the complete access-rights state of the live instance.

    Unlike 'capture', nothing is scoped: this records every group, ACL line,
    restricted menu and role, so it can be committed and compared after a
    module update moved something. It is asserted by no one and applied by
    nothing — it only serves as a reference point.
    """
    _require_odoo(ctx)
    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    instance = OdooInstance(env=env)  # type: ignore[operator]
    config = instance.dump_security_config()
    document = dump_security_document(config)

    if output:
        Path(output).write_text(document, encoding="utf-8")
        counts = {name: len(items) for name, items in _counts(config).items()}
        summary = ", ".join(f"{name}={count}" for name, count in counts.items())
        click.echo(f"wrote {output} ({summary})")
        return

    click.echo(document)


def _counts(config) -> dict:
    """Count objects per section, for the one-line write summary."""
    return {
        "groups": config.groups,
        "acl": config.acl,
        "menus": config.menus,
        "roles": config.roles,
        "locks": config.locks,
    }


__all__ = ["security_group"]
