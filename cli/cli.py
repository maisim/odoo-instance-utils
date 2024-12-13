import click
import click_odoo

from .cli_generate_repo_yaml import generate_repos_yaml
from .cli_addons_generate_addons_yaml import generate_addons_yaml
from .cli_list_addons import list_addons
from .cli_addon_why import addon_why
from .cli_addons_python_dependencies import addons_python_dependencies


@click.group("odoo-instance")
@click_odoo.env_options(default_log_level="warn")
@click.pass_context
@click.option(
    "--installed-addons-only/--include-all-addons",
    default=True,
    help="Work with installed addons only (default) or include not installed addons",
    show_default=False,
)
def main(ctx, **kwargs):
    ctx.ensure_object(dict)
    ctx.obj["odoo_env"] = kwargs["env"]

    ctx.obj["installed_addons_only"] = kwargs["installed_addons_only"]


main.add_command(generate_repos_yaml)
main.add_command(generate_addons_yaml)
main.add_command(list_addons)
main.add_command(addon_why)
main.add_command(addons_python_dependencies)
