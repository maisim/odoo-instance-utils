import click
import json

from odoo_instance_utils import OdooInstance


@click.command(help="List addons and their status")
@click.option(
    "--minimize-list",
    is_flag=True,
    default=False,
    help="Minimize the list of addons (to install) with the game of dependencies",
)
@click.option("--format", type=click.Choice(["flat", "json", "csv"]), default="flat")
@click.pass_context
def list_addons(ctx, minimize_list, format):
    env = ctx.obj["odoo_env"]
    odoo_instance = OdooInstance(env=env)

    addons = odoo_instance.addons(installed=ctx.obj["installed_addons_only"])

    if minimize_list:
        addons = [a for a in addons if not a.is_dependency_of]

    if format == "json":
        click.echo(json.dumps(list(addons.to_dict())))
        return
    elif format == "csv":
        for addon in addons:
            click.echo(f"{addon.name},{addon.manifest.get('name', '')}")
    else:
        click.echo(",".join(addon.name for addon in addons))
