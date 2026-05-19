"""
Code fingerprinting for Odoo addon modules.

Computes a deterministic SHA256 hash over the source files of a module
so that a captured spec can later detect manual patches (tampered code
on a live instance that doesn't match any known version).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# Only hash files whose content matters for the module's behaviour.
_HASHED_SUFFIXES = frozenset({".py", ".xml", ".csv", ".js", ".css", ".mako", ".rst"})


def fingerprint_module(module_path: str | Path) -> str:
    """Return a SHA256 hex digest of the module at *module_path*.

    Walks the directory tree in sorted order, hashing the relative
    path and file content of every relevant file.  The result is a
    compact, deterministic identifier suitable for detecting tampering.

    Returns ``""`` if *module_path* does not exist or contains no
    hashable files.
    """
    root = Path(module_path)
    if not root.is_dir():
        return ""

    digest = hashlib.sha256()
    file_count = 0

    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.suffix not in _HASHED_SUFFIXES:
            continue
        rel = file_path.relative_to(root).as_posix()
        digest.update(rel.encode())
        digest.update(b"\x00")
        digest.update(file_path.read_bytes())
        digest.update(b"\x00")
        file_count += 1

    return digest.hexdigest() if file_count else ""
