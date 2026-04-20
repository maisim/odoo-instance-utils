import difflib
from typing import Any, Dict, Optional

from odoo.api import Environment


def export(env: Environment, xmlid: str) -> Optional[Dict[str, Any]]:
    """
    Export an Odoo view as a dictionary via its external id (xmlid).
    Returns None if not found.
    """
    view = env.ref(xmlid, raise_if_not_found=False)
    if not view:
        return None
    return {
        "id": view.id,
        "name": view.name,
        "model": view.model,
        "type": view.type,
        "priority": view.priority,
        "active": view.active,
        "mode": view.mode,
        "inherit_id": view.inherit_id.id if view.inherit_id else None,
        "create_date": view.create_date.isoformat() if view.create_date else None,
        "write_date": view.write_date.isoformat() if view.write_date else None,
        "key": view.key,
        "customize_show": view.customize_show,
        "arch_updated": view.arch_updated,
        "arch": view.arch,
        "arch_db": view.arch_db,
        "arch_prev": view.arch_prev,
    }

def diff(env: Environment, xmlid: str, filepath: str) -> Dict[str, Any]:
    """
    Compare an Odoo view with a local file via its external id (xmlid).
    Returns a dict with keys: 'found', 'match', 'diff', 'error'.
    """
    view = env.ref(xmlid, raise_if_not_found=False)
    if not view:
        return {"found": False, "error": f"View with xmlid '{xmlid}' not found."}
    with open(filepath, 'r', encoding='utf-8') as f:
        file_content = f.read().splitlines()
    raw_view = env['ir.ui.view'].browse(view.id).with_context(lang=None)
    view_content = raw_view.arch_db.splitlines()
    diff = difflib.unified_diff(
        view_content,
        file_content,
        fromfile=f"Odoo view ({xmlid})",
        tofile=f"Local file ({filepath})",
        lineterm='',
    )
    diff_output = '\n'.join(diff)
    return {
        "found": True,
        "match": not bool(diff_output),
        "diff": diff_output,
    }
