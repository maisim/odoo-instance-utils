import click

import odoo
import json

from odoo_instance_utils import OdooInstance


@click.command(help="List addons and their status")
@click.option("--format", type=click.Choice(["flat", "json", "csv"]), default="flat")
@click.pass_context
def list_addons(ctx, format):
    env = ctx.obj["odoo_env"]
    odoo_instance = OdooInstance(odoo=odoo, env=env)

    addons = odoo_instance.addons(installed=ctx.obj["installed_addons_only"])

    if format == "json":
        click.echo(json.dumps(list(addons.to_dict())))
        return
    elif format == "csv":
        click.echo("name,path,installed")
        for addon in addons:
            click.echo(f"{addon.name},{addon.path},{addon.is_installed}")
        return
    else:
        for addon in addons:
            click.echo(addon)
