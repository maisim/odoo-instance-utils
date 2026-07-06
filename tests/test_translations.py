from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from odoo_instance_utils.translations import (
    _generate_po,
    _resolve_res_id,
    load_translations_module,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FakeOverride:
    type: str
    name: str
    src: str
    value: str
    res_id: int = 0


def _make_env():
    """Return a mock Odoo env with minimal mocks for resolve + import."""
    env = MagicMock()
    env.ref.return_value = None  # default: XML-ID not found
    env.cr = MagicMock()
    return env


def _write_translations_file(content: str) -> Path:
    """Write *content* to a temporary ``.py`` file and return its path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".py", mode="w", encoding="utf-8", delete=False)
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# _resolve_res_id
# ---------------------------------------------------------------------------


class TestResolveResId:
    def test_returns_explicit_res_id(self):
        env = _make_env()
        override = _FakeOverride(type="model", name="x", src="x", value="x", res_id=42)
        assert _resolve_res_id(env, override) == 42

    def test_returns_zero_for_model_without_res_id(self):
        env = _make_env()
        override = _FakeOverride(type="model", name="x", src="x", value="x")
        assert _resolve_res_id(env, override) == 0

    def test_returns_zero_for_selection_without_res_id(self):
        env = _make_env()
        override = _FakeOverride(type="selection", name="x", src="x", value="x")
        assert _resolve_res_id(env, override) == 0

    def test_returns_zero_for_code_without_res_id(self):
        env = _make_env()
        override = _FakeOverride(type="code", name="x", src="x", value="x")
        assert _resolve_res_id(env, override) == 0

    def test_view_resolves_xmlid(self):
        env = _make_env()
        fake_view = MagicMock()
        fake_view.id = 99
        env.ref.return_value = fake_view
        override = _FakeOverride(type="view", name="sale.view_order_form", src="x", value="x")
        assert _resolve_res_id(env, override) == 99
        env.ref.assert_called_once_with("sale.view_order_form", raise_if_not_found=False)

    def test_view_unknown_xmlid_falls_back_to_zero(self):
        env = _make_env()
        env.ref.return_value = None
        override = _FakeOverride(type="view", name="nonexistent.view", src="x", value="x")
        assert _resolve_res_id(env, override) == 0

    def test_view_no_dot_returns_zero(self):
        env = _make_env()
        override = _FakeOverride(type="view", name="plain_name", src="x", value="x")
        assert _resolve_res_id(env, override) == 0


# ---------------------------------------------------------------------------
# _generate_po
# ---------------------------------------------------------------------------


class TestGeneratePo:
    def test_empty_for_unknown_language(self):
        env = _make_env()
        translations = {"fr_FR": [_FakeOverride(type="model", name="x", src="A", value="B")]}
        result = _generate_po(env, translations, "de_DE")
        assert result == ""

    def test_generates_valid_po(self):
        env = _make_env()
        translations = {
            "fr_FR": [
                _FakeOverride(type="model", name="sale.order,name", src="Order", value="Commande"),
            ],
        }
        po = _generate_po(env, translations, "fr_FR")
        assert 'msgid "Order"' in po
        assert 'msgstr "Commande"' in po
        assert "#. module: __custom__" in po
        assert "#: model:sale.order,name:0" in po
        assert "Content-Type: text/plain; charset=UTF-8" in po

    def test_escapes_double_quotes(self):
        env = _make_env()
        translations = {
            "fr_FR": [
                _FakeOverride(
                    type="code", name="sale", src='He said "hello"', value='Il a dit "bonjour"'
                ),
            ],
        }
        po = _generate_po(env, translations, "fr_FR")
        assert 'msgid "He said \\"hello\\""' in po
        assert 'msgstr "Il a dit \\"bonjour\\""' in po

    def test_handles_multiline(self):
        env = _make_env()
        translations = {
            "fr_FR": [
                _FakeOverride(type="code", name="x", src="Line1\nLine2", value="Ligne1\nLigne2"),
            ],
        }
        po = _generate_po(env, translations, "fr_FR")
        assert '"Line1\\n"' in po
        assert '"Line2\\n"' in po

    def test_respects_res_id(self):
        env = _make_env()
        translations = {
            "fr_FR": [
                _FakeOverride(type="model", name="x", src="A", value="B", res_id=42),
            ],
        }
        po = _generate_po(env, translations, "fr_FR")
        assert "#: model:x:42" in po

    def test_utf8_accents(self):
        env = _make_env()
        translations = {
            "fr_FR": [
                _FakeOverride(type="model", name="x", src="État", value="Étape"),
            ],
        }
        po = _generate_po(env, translations, "fr_FR")
        assert "État" in po
        assert "Étape" in po


# ---------------------------------------------------------------------------
# load_translations_module
# ---------------------------------------------------------------------------


class TestLoadTranslationsModule:
    def test_loads_and_imports_translations(self):
        env = _make_env()

        py = _write_translations_file("""
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
        TranslationOverride(type="model", name="sale.order,name", src="Order", value="Commande"),
        TranslationOverride(type="code", name="sale", src="Quote", value="Devis"),
    ],
}
""")
        try:
            with patch("odoo_instance_utils.translations._import_po") as mock_import:
                result = load_translations_module(env, str(py))
                assert result == {"created": 2, "updated": 0}
                assert mock_import.call_count == 1
                call_args = mock_import.call_args
                assert call_args[0][2] == "fr_FR"  # lang (3rd positional arg)
                assert "Commande" in call_args[0][1]  # po_content (2nd positional arg)
                assert "Devis" in call_args[0][1]
        finally:
            py.unlink()

    def test_missing_file_raises(self):
        env = _make_env()
        with pytest.raises(FileNotFoundError):
            load_translations_module(env, "/nonexistent/translations.py")

    def test_no_translations_variable_raises(self):
        env = _make_env()
        py = _write_translations_file("x = 1\n")
        try:
            with pytest.raises(ValueError, match="No 'translations' variable"):
                load_translations_module(env, str(py))
        finally:
            py.unlink()

    def test_multiple_languages(self):
        env = _make_env()
        py = _write_translations_file("""
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
        TranslationOverride(type="model", name="x", src="A", value="B"),
    ],
    "de_DE": [
        TranslationOverride(type="model", name="x", src="A", value="C"),
    ],
}
""")
        try:
            with patch("odoo_instance_utils.translations._import_po") as mock_import:
                result = load_translations_module(env, str(py))
                assert result == {"created": 2, "updated": 0}
                assert mock_import.call_count == 2
                # Check each language imported
                langs = [c[0][2] for c in mock_import.call_args_list]
                assert "fr_FR" in langs
                assert "de_DE" in langs
        finally:
            py.unlink()

    def test_force_flag_passed_to_import(self):
        env = _make_env()
        py = _write_translations_file("""
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
        TranslationOverride(type="model", name="x", src="A", value="B"),
    ],
}
""")
        try:
            with patch("odoo_instance_utils.translations._import_po") as mock_import:
                load_translations_module(env, str(py), force=True)
                call_args = mock_import.call_args
                assert call_args[0][2] == "fr_FR"  # lang
                assert call_args[1]["force"] is True  # keyword arg
        finally:
            py.unlink()
