import click

from odoo_instance_utils import OdooInstance


@click.group("addons")
def addons_group():
    """Addon management commands."""
    pass

@addons_group.command("install")
@click.argument("addons_names", required=True, type=str)
@click.pass_context
def addons_install(ctx, addons_names):
    """Install addons, separated by comma."""
    env = ctx.obj["odoo_env"]
    addons_names = [addon_name.strip() for addon_name in addons_names.split(",")]
    instance = OdooInstance(env=env)
    installed_addons_names = instance.install_addons(addons_names)
    click.echo(f"Installed addons: {', '.join(installed_addons_names)}")

@addons_group.command("list")
@click.option(
    "--minimize-list",
    is_flag=True,
    default=False,
    help="Minimize the list of addons (to install) with the game of dependencies",
)
@click.option(
    "--needs-upgrade",
    is_flag=True,
    default=False,
    help="Only show addons that need an upgrade",
)
@click.option("--format", type=click.Choice(["flat", "json", "csv"]), default="flat")
@click.pass_context
def list_addons(ctx, minimize_list, needs_upgrade, format):
    """List addons and their status."""
    env = ctx.obj["odoo_env"]
    odoo_instance = OdooInstance(env=env)
    addons = odoo_instance.addons(
        installed=ctx.obj["installed_addons_only"],
        minimize_list=minimize_list,
        needs_upgrade=True if needs_upgrade else None,
    )
    if format == "json":
        import json
        click.echo(json.dumps(list(addons.to_dict())))
        return
    elif format == "csv":
        for addon in addons:
            click.echo(f"{addon.name},{addon.manifest.get('name', '')}")
    else:
        click.echo(",".join(addon.name for addon in addons))

@addons_group.command("why")
@click.argument("addon_name", required=True, type=str)
@click.pass_context
def addon_why(ctx, addon_name):
    """List modules that depend on the given module."""
    env = ctx.obj["odoo_env"]
    odoo_instance = OdooInstance(env=env)
    addons = odoo_instance.addons(installed=ctx.obj["installed_addons_only"])
    addon = addons[addon_name]
    addons_that_depend_on = ", ".join([a.name for a in addon.is_dependency_of])
    click.echo(f"Addons that depend on {addon_name}: {addons_that_depend_on}")

@addons_group.command("python-dependencies")
@click.pass_context
def addons_python_dependencies(ctx):
    """List python dependencies for the instance addons."""
    env = ctx.obj["odoo_env"]
    odoo_instance = OdooInstance(env=env)
    addons = odoo_instance.addons(installed=ctx.obj["installed_addons_only"])
    click.echo(", ".join(addons.python_dependencies))

@addons_group.command("generate-addons-yaml")
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    required=False,
    help="Output file name",
)
@click.pass_context
def generate_addons_yaml(ctx, output=None):
    """Generate an addons.yml file for Doodba."""
    env = ctx.obj["odoo_env"]
    odoo_instance = OdooInstance(env=env)
    addons = odoo_instance.addons(
        installed=ctx.obj["installed_addons_only"], include_auto_installed_addons=False
    )
    addons_yaml_content = addons.generate_addons_yaml()
    if not output:
        click.echo(addons_yaml_content)
        return
    with open(output, "w") as file:
        file.write(addons_yaml_content)
    click.echo(f"Addons YAML file generated at {output}")

@addons_group.command("generate-repos-yaml")
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    required=False,
    help="Output file for repos.yml",
)
@click.pass_context
def generate_repos_yaml(ctx, output=None):
    """Generate repos.yml file for git-aggregator."""
    env = ctx.obj["odoo_env"]
    odoo_instance = OdooInstance(env=env)
    addons = odoo_instance.addons(installed=ctx.obj["installed_addons_only"])
    repos_yaml_content = addons.generate_repos_yaml()
    if not output:
        click.echo(repos_yaml_content)
        return
    with open(output, "w") as file:
        file.write(repos_yaml_content)
    click.echo(f"Repos YAML file generated at {output}")
