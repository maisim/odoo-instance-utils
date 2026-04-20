import click
import click_odoo

from .cli_addons import addons_group
from .cli_filters import filters_group
from .cli_exports import exports_group
from .cli_view import view_group


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

main.add_command(addons_group)
main.add_command(filters_group)
main.add_command(exports_group)
main.add_command(view_group)