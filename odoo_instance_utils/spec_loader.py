"""
Load and validate a ``foundry_addons.py`` module.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from odoo_instance_utils.spec import AddonSpec


class SpecLoadError(Exception):
    """Raised when a spec file cannot be loaded or validated."""


def load_spec(filepath: str | Path) -> AddonSpec:
    """Import *filepath* as a Python module and return its ``addon_spec``.

    Raises :class:`SpecLoadError` if the file is missing, cannot be
    imported, or does not export an ``addon_spec`` of the correct type.
    """
    path = Path(filepath).resolve()
    if not path.exists():
        raise SpecLoadError(f"{path}: file not found")

    module_name = path.stem
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise SpecLoadError(f"{path}: cannot load as Python module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise SpecLoadError(f"{path}: {exc}") from exc

    try:
        addon_spec: Any = module.addon_spec
    except AttributeError:
        raise SpecLoadError(f"{path}: module must export 'addon_spec'")

    if not isinstance(addon_spec, AddonSpec):
        raise SpecLoadError(
            f"{path}: 'addon_spec' must be an AddonSpec instance, got {type(addon_spec).__name__}"
        )
    return addon_spec
