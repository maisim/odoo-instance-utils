import click

from odoo_instance_utils import OdooInstance


@click.command(help="List python dependencies for the instance addons")
@click.pass_context
def addons_python_dependencies(ctx):
    env = ctx.obj["odoo_env"]
    odoo_instance = OdooInstance(env=env)

    addons = odoo_instance.addons(installed=ctx.obj["installed_addons_only"])

    click.echo(", ".join(addons.python_dependencies))
