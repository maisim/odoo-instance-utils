from __future__ import annotations

import click


@click.group("exports")
def exports_group():
    """Export management commands."""
    pass


@exports_group.command("dump")
@click.argument("ids", required=True, type=str)
@click.pass_context
def dump_exports(ctx, ids):
    """Dump exports."""
    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    ids = [id.strip() for id in ids.split(",")]
    instance = OdooInstance(env=env)  # type: ignore[operator]
    click.echo(instance.dump_exports(ids))


@exports_group.command("restore")
@click.argument("exports", required=True, type=str)
@click.pass_context
def restore_exports(ctx, exports):
    """Restore exports."""
    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    instance = OdooInstance(env=env)  # type: ignore[operator]
    instance.restore_exports(exports)
