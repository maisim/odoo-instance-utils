import click

import odoo

from odoo_instance_utils import OdooInstance


@click.command(
    help="Generate repos.yml file for git-aggregator. If your addons come from git repositories, this command will generate a repos.yml file for git-aggregate."
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    required=False,
    help="Output file for repos.yml",
)
@click.pass_context
def generate_repos_yml(ctx, output=None):
    env = ctx.obj["odoo_env"]
    odoo_instance = OdooInstance(odoo=odoo, env=env)

    addons = odoo_instance.addons(installed=ctx.obj["installed_addons_only"])

    repos_yaml_content = addons.generate_repos_yaml()

    # If no output file is provided, print to stdout
    if not output:
        click.echo(repos_yaml_content)
        return

    with open(output, "w") as file:
        file.write(repos_yaml_content)

    click.echo(f"Repos YAML file generated at {output}")
