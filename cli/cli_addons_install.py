import click

from odoo_instance_utils import OdooInstance


@click.command(help="Install addons, separated by comma")
@click.argument("addons_names", required=True, type=str)
@click.pass_context
def addons_install(ctx, addons_names):
    env = ctx.obj["odoo_env"]
    addons_names = [addon_name.strip() for addon_name in addons_names.split(",")]

    instance = OdooInstance(env=env)
    installed_addons_names = instance.install_addons(addons_names)
    click.echo(f"Installed addons: {', '.join(installed_addons_names)}")