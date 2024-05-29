import click
import click_odoo

import odoo

from odoo_instance_utils import OdooInstance


@click.group()
@click_odoo.env_options(default_log_level="debug")
@click.pass_context
def cli(ctx, **kwargs):
    ctx.ensure_object(dict)
    ctx.obj["odoo_env"] = kwargs["env"]


@cli.command()
@click.option(
    "-o", "--output", type=click.Path(), required=True, help="Output file for repos.yml"
)
@click.pass_context
def generate_repos_yml(ctx, output):
    env = ctx.obj["odoo_env"]
    odoo_instance = OdooInstance(odoo=odoo, env=env)

    addons = odoo_instance.addons(installed=True)

    repos_yaml_content = addons.generate_repos_yaml()

    with open(output, "w") as file:
        file.write(repos_yaml_content)

    click.echo(f"Repos YAML file generated at {output}")


if __name__ == "__main__":
    cli()
