"""
Build and read the *vault-mode* ``repos.lock.yaml``.

``repos.lock.yaml`` is not a new file format: it is a ``repos.yaml`` whose
every stanza points at a vault repository and an immutable, content-addressed
tag instead of upstream remotes and mutable branches. It is consumed verbatim
by git-aggregator at preprod/prod build time (delivered under the name
``repos.yaml``), producing a deterministic checkout with zero real merge.

This module turns a *source* ``repos.yaml`` plus a set of resolved vault
references into the locked stanzas, and reads them back.
"""

from __future__ import annotations

from dataclasses import dataclass

from odoo_instance_utils.repos_yaml import RepoStanza

DEFAULT_VAULT_REMOTE = "vault"


@dataclass(frozen=True)
class VaultRef:
    """A resolved vault reference for one addon repository.

    + path: ``repos.yaml`` destination path (e.g. ``"./web"``).
    + vault_url: clone URL of the vault repository.
    + tag: immutable, content-addressed tag (e.g. ``"16.0-<sha>"``).
    + sha: the 40-char commit SHA the tag points at.
    """

    path: str
    vault_url: str
    tag: str
    sha: str


def rewrite_to_vault(
    source_stanzas: list[RepoStanza],
    vault_refs: dict[str, VaultRef],
    remote_name: str = DEFAULT_VAULT_REMOTE,
) -> list[RepoStanza]:
    """Rewrite *source_stanzas* into vault-mode stanzas.

    + source_stanzas: parsed source ``repos.yaml`` stanzas.
    + vault_refs: mapping of stanza path to its resolved :class:`VaultRef`.
      Must cover every stanza in *source_stanzas*.
    + remote_name: remote name to use in the locked stanzas.

    Each locked stanza keeps its ``defaults`` (e.g. depth) but replaces
    remotes/target/merges with a single vault remote pointing at the tag.
    Raises :class:`KeyError` if a stanza has no matching vault ref.
    """
    locked: list[RepoStanza] = []
    for stanza in source_stanzas:
        ref = vault_refs.get(stanza.path)
        if ref is None:
            raise KeyError(f"no vault ref for repos.yaml path {stanza.path!r}")
        locked.append(
            RepoStanza(
                path=stanza.path,
                remotes={remote_name: ref.vault_url},
                target=f"{remote_name} {ref.tag}",
                merges=[f"{remote_name} {ref.tag}"],
                defaults=dict(stanza.defaults),
            )
        )
    return locked


def read_vault_refs(
    locked_stanzas: list[RepoStanza],
    remote_name: str = DEFAULT_VAULT_REMOTE,
) -> dict[str, VaultRef]:
    """Read vault references back from locked (vault-mode) stanzas.

    The SHA is recovered from the tag's trailing ``-<sha>`` segment when
    present, otherwise left empty.
    """
    refs: dict[str, VaultRef] = {}
    for stanza in locked_stanzas:
        vault_url = stanza.remotes.get(remote_name, "")
        tag = stanza.target.split(" ", 1)[-1] if stanza.target else ""
        sha = tag.rsplit("-", 1)[-1] if "-" in tag else ""
        refs[stanza.path] = VaultRef(
            path=stanza.path,
            vault_url=vault_url,
            tag=tag,
            sha=sha,
        )
    return refs
