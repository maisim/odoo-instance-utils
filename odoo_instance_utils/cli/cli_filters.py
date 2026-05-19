from __future__ import annotations

import click


@click.group("filters")
def filters_group():
    """Filter management commands."""
    pass


@filters_group.command("list")
@click.pass_context
def list_filters(ctx):
    """List all filters with their id, name and model."""
    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    instance = OdooInstance(env=env)  # type: ignore[operator]
    for f in instance.list_filters():
        click.echo(f"{f['id']}\t{f['model_id']}\t{f['name']}")


@filters_group.command("dump")
@click.argument("ids", required=True, type=str)
@click.pass_context
def dump_filters(ctx, ids):
    """Dump filters."""
    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    ids = [id.strip() for id in ids.split(",")]
    instance = OdooInstance(env=env)  # type: ignore[operator]
    click.echo(instance.dump_filters(ids))


@filters_group.command("restore")
@click.argument("filters", required=True, type=str)
@click.pass_context
def restore_filters(ctx, filters):
    """Restore filters."""
    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    instance = OdooInstance(env=env)  # type: ignore[operator]
    instance.restore_filters(filters)
