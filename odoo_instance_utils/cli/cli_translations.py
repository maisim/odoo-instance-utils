from __future__ import annotations

import click


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

    The file must define a module-level ``translations`` variable:
    ``dict[str, list[TranslationOverride]]`` where each override has
    ``type``, ``name``, ``src``, ``value``, and optionally ``res_id``.

    \b
    Example dataclass in the translations file:
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class TranslationOverride:
            type: str
            name: str
            src: str
            value: str
            res_id: int = 0

        translations = {
            "fr_FR": [
                TranslationOverride(
                    type="model",
                    name="sale.order,name",
                    src="Sales Order",
                    value="Commande client",
                ),
            ],
        }
    """
    from odoo_instance_utils.translations import load_translations_module

    env = ctx.obj["odoo_env"]
    result = load_translations_module(env, file, force=force)
    click.echo(
        f"Created {result['created']} translation(s), updated {result['updated']} translation(s)"
    )
