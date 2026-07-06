from __future__ import annotations

import importlib.util
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

_CUSTOM_MODULE = "__custom__"


def _resolve_res_id(env, override: Any) -> int:
    """Return the res_id for a translation override.

    Uses the override's explicit ``res_id`` if set.  For ``view``-type
    overrides with ``res_id == 0`` and a dotted ``name``, attempts to
    resolve it as an XML-ID via ``env.ref()``.

    Returns ``0`` if resolution fails.
    """
    if override.res_id != 0:
        return override.res_id
    if override.type == "view" and "." in override.name:
        try:
            record = env.ref(override.name, raise_if_not_found=False)
            if record:
                return record.id
        except Exception:
            _logger.warning("Could not resolve view xmlid '%s'", override.name)
    return 0


def _generate_po(env, translations: dict[str, list[Any]], lang: str) -> str:
    """Generate a PO file string from translation overrides for a single language.

    The PO format uses Odoo's comment markers so that ``TranslationImporter``
    can route each entry to the correct model table + jsonb column.

    + ``#. module: <module>`` — scopes the translation (empty = not module-scoped).
    + ``#: <type>:<name>:<res_id>`` — type, model/field identifier, resource id.
    """
    lines: list[str] = []
    overrides = translations.get(lang, [])
    if not overrides:
        return ""

    lines.append("# Translation overrides for %s" % lang)
    lines.append('msgid ""')
    lines.append('msgstr ""')
    lines.append('"Content-Type: text/plain; charset=UTF-8\\n"')
    lines.append("")

    for override in overrides:
        res_id = _resolve_res_id(env, override)
        lines.append(f"#. module: {_CUSTOM_MODULE}")
        lines.append(f"#: {override.type}:{override.name}:{res_id}")
        # Escape double-quotes in src/value for PO format
        src_escaped = override.src.replace("\\", "\\\\").replace('"', '\\"')
        value_escaped = override.value.replace("\\", "\\\\").replace('"', '\\"')
        # Handle multi-line text
        if "\n" in src_escaped:
            lines.append('msgid ""')
            for line in src_escaped.split("\n"):
                lines.append(f'"{line}\\n"')
        else:
            lines.append(f'msgid "{src_escaped}"')
        if "\n" in value_escaped:
            lines.append('msgstr ""')
            for line in value_escaped.split("\n"):
                lines.append(f'"{line}\\n"')
        else:
            lines.append(f'msgstr "{value_escaped}"')
        lines.append("")

    return "\n".join(lines)


def _import_po(env, po_content: str, lang: str, force: bool = False) -> None:
    """Import a PO file string into Odoo using ``TranslationImporter``."""
    from odoo.tools.translate import TranslationImporter

    fd, po_path = tempfile.mkstemp(suffix=".po", prefix="odoo-translations-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(po_content)
        importer = TranslationImporter(env.cr)
        importer.load_file(po_path, lang)
        importer.save(overwrite=force)
    finally:
        try:
            os.unlink(po_path)
        except OSError:
            pass


def load_translations_module(env, module_path: str, force: bool = False) -> dict[str, int]:
    """Load custom translations from a Python file into the Odoo instance.

    Generates temporary PO files (one per language) and imports them via
    Odoo's ``TranslationImporter``, which writes directly to the jsonb
    translation columns on each model's database table (Odoo ≥16).

    + ``env``: Odoo environment (from ``click-odoo``).
    + ``module_path``: absolute or relative path to a ``.py`` file that
      defines a module-level ``translations`` variable:
      ``dict[str, list[TranslationOverride]]``.
    + ``force``: if ``True``, overwrite existing translations.

    Returns ``{"created": <int>, "updated": <int>}``.
    """
    path = Path(module_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Translations file not found: {module_path}")

    spec = importlib.util.spec_from_file_location("_foundry_translations", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load translations module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_foundry_translations"] = module
    spec.loader.exec_module(module)

    translations = getattr(module, "translations", None)
    if translations is None:
        raise ValueError(
            f"No 'translations' variable found in {module_path}. "
            "The file must define: translations: dict[str, list[TranslationOverride]]"
        )

    created = 0
    for lang in translations:
        po_content = _generate_po(env, translations, lang)
        if not po_content:
            continue
        count = len(translations[lang])
        _import_po(env, po_content, lang, force=force)
        created += count
        _logger.info("Imported %d translation(s) for lang '%s'", count, lang)

    _logger.info("Translations loaded: %d total from %s", created, module_path)
    return {"created": created, "updated": 0}
