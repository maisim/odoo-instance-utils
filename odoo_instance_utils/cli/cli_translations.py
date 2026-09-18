from __future__ import annotations

import click

from odoo_instance_utils.cli._guards import require_odoo as _require_odoo


@click.group("translations")
def translations_group():
    """Translation management commands."""
    pass


@translations_group.command("load")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Delete and recreate existing translations instead of updating",
)
@click.pass_context
def load_translations(ctx, file, force):
    """Load custom translations from a Python file.

    \b
    The file must expose a ``translations`` dict keyed by language code.
    Each entry is a ``TranslationOverride`` dataclass with fields:
    ``type``, ``name``, ``src``, ``value``, and optionally ``res_id``.
    See the README for a complete example of the expected file format.
    """
    _require_odoo(ctx)
    from odoo_instance_utils.translations import load_translations_module

    env = ctx.obj["odoo_env"]
    result = load_translations_module(env, file, force=force)
    click.echo(
        f"Created {result['created']} translation(s), updated {result['updated']} translation(s)"
    )
