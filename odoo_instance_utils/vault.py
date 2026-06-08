"""
Content-addressed *vaulting* of upstream commits into your own git repos.

The vault pattern (inspired by ``uvault``) protects a project against
deleted or force-pushed upstream commits: a resolved commit SHA is pushed
as an **immutable, content-addressed tag** into a repository you control.
Because the SHA is part of the tag name, re-pushing the same commit is a
no-op and two builds resolving the same commit produce the same tag — so
the operation is idempotent and race-free.

All git calls use ``subprocess`` with list arguments (never a shell), so
user-controlled values cannot be interpreted as shell syntax.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def resolve_ref_sha(remote_url: str, ref: str) -> str | None:
    """Resolve *ref* on *remote_url* to a commit SHA via ``git ls-remote``.

    + remote_url: upstream clone URL.
    + ref: a branch name, tag, ``refs/...`` ref, or a full 40-char SHA.

    Returns the 40-char SHA, or ``None`` if it cannot be resolved. A *ref*
    that is already a full SHA is returned as-is when ``ls-remote`` finds
    no matching ref.
    """
    try:
        result = subprocess.run(
            ["git", "ls-remote", remote_url, ref],
            capture_output=True,
            text=True,
            check=True,
        )
        output = result.stdout.strip()
        if output:
            return output.split()[0]
    except subprocess.CalledProcessError:
        pass
    if _SHA_RE.match(ref):
        return ref
    return None


def remote_tag_exists(vault_url: str, tag_name: str) -> bool:
    """Return ``True`` when *tag_name* already exists on *vault_url*."""
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", vault_url, tag_name],
            capture_output=True,
            text=True,
            check=True,
        )
        return bool(result.stdout.strip())
    except subprocess.CalledProcessError:
        return False


def vault_commit(
    origin_url: str,
    sha: str,
    vault_url: str,
    tag_name: str,
    repo_dir: str | Path,
) -> None:
    """Push *sha* from *origin_url* as tag *tag_name* into *vault_url*.

    + origin_url: upstream clone URL to fetch the commit from.
    + sha: commit SHA to vault (must be reachable on *origin_url*).
    + vault_url: clone URL of the vault repository to push the tag into.
    + tag_name: immutable tag to create (content-addressed).
    + repo_dir: local bare clone cache directory (created if absent).

    Uses a bare clone as an object cache, fetches the exact commit, then
    pushes it as a tag ref. No-op safe: callers should skip when
    :func:`remote_tag_exists` is already ``True``.
    """
    repo_dir = Path(repo_dir)
    if not repo_dir.exists():
        subprocess.run(
            ["git", "clone", "--bare", origin_url, str(repo_dir)],
            check=True,
        )
    subprocess.run(
        ["git", "-C", str(repo_dir), "fetch", origin_url, sha],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_dir), "push", vault_url, f"{sha}:refs/tags/{tag_name}"],
        check=True,
    )


def render_tag(template: str, *, odoo_version: str, sha: str) -> str:
    """Render a vault tag name from *template*.

    + template: e.g. ``"{odoo_version}-{sha}"``.
    + odoo_version: Odoo series (e.g. ``"16.0"``).
    + sha: 40-char commit SHA.
    """
    return template.format(odoo_version=odoo_version, sha=sha)
