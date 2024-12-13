import click

from odoo_instance_utils import OdooInstance


@click.command(
    help="Generate an addons.yml file for Doodba. If your addons come from git repositories, this command will generate an addons.yml file for Doodba."
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    required=False,
    help="Output file name",
)
@click.pass_context
def generate_addons_yaml(ctx, output=None):
    env = ctx.obj["odoo_env"]
    odoo_instance = OdooInstance(env=env)

    addons = odoo_instance.addons(
        installed=ctx.obj["installed_addons_only"], include_auto_installed_addons=False
    )

    addons_yaml_content = addons.generate_addons_yaml()

    # If no output file is provided, print to stdout
    if not output:
        click.echo(addons_yaml_content)
        return

    with open(output, "w") as file:
        file.write(addons_yaml_content)

    click.echo(f"Addons YAML file generated at {output}")
