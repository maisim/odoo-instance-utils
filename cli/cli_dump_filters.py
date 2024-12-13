import click

from odoo_instance_utils import OdooInstance


@click.command(help="Dump filters")
@click.argument("ids", required=True, type=str)
@click.pass_context
def dump_filters(ctx, ids):
    env = ctx.obj["odoo_env"]
    ids = [id.strip() for id in ids.split(",")]

    instance = OdooInstance(env=env)
    click.echo(instance.dump_filters(ids))