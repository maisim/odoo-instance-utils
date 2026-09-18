"""
Optional click-odoo plumbing, isolated in one place.

``click-odoo`` and the ``odoo`` module only exist inside an Odoo
environment. Everything that reaches for them lives here, so that the
offline commands (``addons lint``, ``security lint``) keep working on a bare
checkout where the ``cli`` extra is not installed.
"""

from __future__ import annotations

import click

try:
    import click_odoo

    #: Environment decorator for the root group, bound with our defaults.
    env_options = click_odoo.env_options(default_log_level="warn")

    #: Whether the Odoo environment plumbing is available at all.
    has_odoo = True
except ImportError:
    has_odoo = False

    def env_options(f):  # type: ignore[no-redef]
        """No-op stand-in used when click-odoo is not importable."""
        return f


def require_odoo(ctx: click.Context) -> None:
    """Raise :class:`click.UsageError` if no Odoo environment is available.

    + ctx: the click context carrying ``odoo_env`` when click-odoo is active.
    """
    if not has_odoo:
        raise click.UsageError(
            "This command requires an Odoo environment (click-odoo is not installed). "
            "Run inside an Odoo shell or install click-odoo.",
            ctx,
        )
    if not isinstance(ctx.obj, dict) or "odoo_env" not in ctx.obj:
        raise click.UsageError(
            "This command requires an Odoo environment. Use the --env flag.",
            ctx,
        )
