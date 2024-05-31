import click
import click_odoo

from .cli_generate_repo_yml import generate_repos_yml
from .cli_list_addons import list_addons


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


main.add_command(generate_repos_yml)
main.add_command(list_addons)
