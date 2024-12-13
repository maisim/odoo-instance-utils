import click

from odoo_instance_utils import OdooInstance


@click.command(help="Restore filters")
@click.argument("filters", required=True, type=str)
@click.pass_context
def restore_filters(ctx, filters):
    env = ctx.obj["odoo_env"]

    instance = OdooInstance(env=env)
    click.echo(instance.restore_filters(filters))