from __future__ import annotations

import click

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
    import click_odoo

    _env_options = click_odoo.env_options(default_log_level="warn")
    _has_odoo = True
except ImportError:
    _has_odoo = False

    def _env_options(f):  # type: ignore[no-redef]
        return f


def _require_odoo(ctx: click.Context) -> None:
    """Fail with a clear message if the Odoo env is unavailable."""
    if not _has_odoo:
        raise click.UsageError(
            "This command requires an Odoo environment (click-odoo is not installed). "
            "Run inside an Odoo shell or install click-odoo.",
            ctx,
        )
    if "odoo_env" not in ctx.obj:
        raise click.UsageError(
            "This command requires an Odoo environment. Use the --env flag.",
            ctx,
        )


@click.group("odoo-instance")
@_env_options
@click.pass_context
@click.option(
    "--installed-addons-only/--include-all-addons",
    default=True,
    help="Work with installed addons only (default) or include not installed addons",
    show_default=False,
)
def main(ctx, **kwargs):
    ctx.ensure_object(dict)
    if _has_odoo:
        ctx.obj["odoo_env"] = kwargs["env"]
    ctx.obj["installed_addons_only"] = kwargs["installed_addons_only"]


main.add_command(addons_group)
for _group in (filters_group, exports_group, view_group):
    if _group is not None:
        main.add_command(_group)
