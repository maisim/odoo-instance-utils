import click

from odoo_instance_utils import OdooInstance


@click.command(help="List modules that depend on the given module")
@click.argument("addon_name", required=True, type=str)
@click.pass_context
def addon_why(ctx, addon_name):
    env = ctx.obj["odoo_env"]
    odoo_instance = OdooInstance(env=env)

    addons = odoo_instance.addons(installed=ctx.obj["installed_addons_only"])

    addon = addons[addon_name]
    addons_that_depend_on = ", ".join([a.name for a in addon.is_dependency_of])
    click.echo(f"Addons that depend on {addon_name}: {addons_that_depend_on}")
