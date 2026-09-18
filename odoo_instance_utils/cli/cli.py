from __future__ import annotations

import click

from ._guards import env_options, has_odoo
from .cli_addons import addons_group

# Subcommand groups that require the `odoo` module (only available inside
# an Odoo shell).  We import them best-effort so that `odoo-instance addons
# lint` works without an Odoo environment.
try:
    from .cli_exports import exports_group
except ImportError:
    exports_group = None  # type: ignore[assignment]
try:
    from .cli_filters import filters_group
except ImportError:
    filters_group = None  # type: ignore[assignment]
try:
    from .cli_view import view_group
except ImportError:
    view_group = None  # type: ignore[assignment]
try:
    from .cli_translations import translations_group
except ImportError:
    translations_group = None  # type: ignore[assignment]


@click.group("odoo-instance")
@env_options
@click.pass_context
@click.option(
    "--installed-addons-only/--include-all-addons",
    default=True,
    help="Work with installed addons only (default) or include not installed addons",
    show_default=False,
)
def main(ctx, **kwargs):
    ctx.ensure_object(dict)
    if has_odoo:
        ctx.obj["odoo_env"] = kwargs["env"]
    ctx.obj["installed_addons_only"] = kwargs["installed_addons_only"]


main.add_command(addons_group)
for _group in (filters_group, exports_group, view_group, translations_group):
    if _group is not None:
        main.add_command(_group)
