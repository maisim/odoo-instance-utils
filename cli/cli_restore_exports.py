import click

from odoo_instance_utils import OdooInstance


@click.command(help="Restore exports")
@click.argument("exports", required=True, type=str)
@click.pass_context
def restore_exports(ctx, exports):
    env = ctx.obj["odoo_env"]

    instance = OdooInstance(env=env)
    click.echo(instance.restore_exports(exports))