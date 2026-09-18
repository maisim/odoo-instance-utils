"""
Declarative Odoo security configuration: parsing, rendering and linting.

A project describes the access rights it manages with five JSON files, one
per object::

    groups.json   groups the configuration owns or references
    acl.json      ir.model.access lines
    menus.json    menu visibility granted to groups
    roles.json    base_user_role roles and the groups they carry
    locks.json    master-data write locks

Each file is a JSON list of flat objects, rendered one record per line so
that a review diff stays readable and a snapshot stays compact.

This module is deliberately free of any ``odoo`` import: ``security lint``
must run on a bare checkout, with no instance and no click-odoo. It is
equally usable for a policy file set (what the project asserts) and for a
snapshot (the observed state), which share this shape — see
:mod:`odoo_instance_utils.security_verify` for how the two are compared.

Identities
----------

A group or role is identified either by a ``slug`` — a local name for
something the configuration owns — or by an ``xmlid``, the fully-qualified
name of something another module owns. Exactly one of the two is set; the
identity used to match entries across configurations is :func:`entity_key`.

Capturing a live instance yields xmlids, since that is what a running
database holds. Authoring a policy yields slugs for the groups it is about
to create. Both forms coexist in the same file, which is what makes
``capture`` output directly editable into a policy.

Any other group reference — in ``implied_ids``, ``acl.json``,
``menus.json``, ``roles.json``, ``locks.json`` — is either a slug declared
in ``groups.json`` or an xmlid (any reference containing a dot).
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

GROUP_FILE = "groups.json"
ACL_FILE = "acl.json"
MENU_FILE = "menus.json"
ROLE_FILE = "roles.json"
LOCK_FILE = "locks.json"

#: Every file a complete security configuration is made of, in dump order.
SECURITY_FILES = (GROUP_FILE, ACL_FILE, MENU_FILE, ROLE_FILE, LOCK_FILE)

#: The four rights carried by an ``ir.model.access`` line, in report order.
PERM_FIELDS = ("perm_read", "perm_write", "perm_create", "perm_unlink")

_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_XMLID_RE = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")


def entity_key(slug: str, xmlid: str, namespace: str = "") -> str:
    """Return the identity used to match an entry across configurations.

    A policy names what it owns by slug; an instance holds what was created,
    under the xmlid of whichever module owns it. Passing *namespace* bridges
    the two, so a policy declaring ``slug="direction"`` with
    ``namespace="odoo_foundry"`` matches a live role whose xmlid is
    ``odoo_foundry.direction``.

    + slug: local name of an entry the configuration owns, or ``""``.
    + xmlid: fully-qualified name of an entry another module owns, or ``""``.
    + namespace: module owning slug-based entries, or ``""`` to compare
      identities as written.
    """
    if xmlid:
        return xmlid
    return f"{namespace}.{slug}" if namespace else slug


@dataclass(frozen=True)
class GroupSpec:
    """A group the configuration owns or references.

    + name: human-readable label.
    + slug: local name of a group the configuration owns.
    + xmlid: fully-qualified name of a group owned elsewhere.
    + implied_ids: group references this group implies.
    """

    name: str
    slug: str = ""
    xmlid: str = ""
    implied_ids: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        """Identity of this group, for matching across configurations."""
        return entity_key(self.slug, self.xmlid)


@dataclass(frozen=True)
class AclSpec:
    """One ``ir.model.access`` line: a group's rights on a model.

    + model: technical model name (``"sale.order"``).
    + group: group reference.
    + perm_read: read right.
    + perm_write: write right.
    + perm_create: create right.
    + perm_unlink: unlink right.
    """

    model: str
    group: str
    perm_read: bool
    perm_write: bool
    perm_create: bool
    perm_unlink: bool


@dataclass(frozen=True)
class MenuSpec:
    """Menu visibility granted to groups.

    Visibility is additive in a policy: applying a spec adds the listed
    groups to the menu and never removes one Odoo or an addon granted. A
    snapshot records the complete list instead — the mode passed to
    :func:`odoo_instance_utils.security_verify.diff_security_config` decides
    which reading applies.

    + menu: menu xmlid.
    + groups: group references that must see the menu.
    """

    menu: str
    groups: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoleSpec:
    """A ``base_user_role`` role and the groups it carries.

    + name: human-readable label.
    + slug: local name of a role the configuration owns.
    + xmlid: fully-qualified name of a role owned elsewhere.
    + groups: group references the role grants.
    """

    name: str
    slug: str = ""
    xmlid: str = ""
    groups: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        """Identity of this role, for matching across configurations."""
        return entity_key(self.slug, self.xmlid)


@dataclass(frozen=True)
class LockSpec:
    """A master-data write lock.

    + model: technical model name whose writes are restricted.
    + allowed_groups: groups still allowed to write. Empty means the
      enforcement module's default, not "nobody".
    + message: user-facing reason, shown when a write is refused.
    """

    model: str
    allowed_groups: tuple[str, ...] = ()
    message: str = ""


@dataclass(frozen=True)
class SecurityConfig:
    """A complete security configuration, policy or snapshot alike."""

    groups: tuple[GroupSpec, ...] = ()
    acl: tuple[AclSpec, ...] = ()
    menus: tuple[MenuSpec, ...] = ()
    roles: tuple[RoleSpec, ...] = ()
    locks: tuple[LockSpec, ...] = ()

    def group_keys(self) -> set[str]:
        """Return every group identity declared in ``groups.json``."""
        return {spec.key for spec in self.groups}

    def acl_models(self) -> set[str]:
        """Return the set of models carrying at least one declared ACL line."""
        return {spec.model for spec in self.acl}

    def is_empty(self) -> bool:
        """Whether every object list is empty."""
        return not (self.groups or self.acl or self.menus or self.roles or self.locks)


# ── Records ─────────────────────────────────────────────────────────────────


def _record(key_order: tuple[str, ...], values: dict) -> "OrderedDict[str, object]":
    """Build a record with a fixed key order, dropping empty optional values."""
    record: "OrderedDict[str, object]" = OrderedDict()
    for key in key_order:
        value = values.get(key)
        if value == "" or value == () or value == []:
            continue
        record[key] = list(value) if isinstance(value, tuple) else value
    return record


def _group_record(spec: GroupSpec) -> "OrderedDict[str, object]":
    return _record(
        ("slug", "xmlid", "name", "implied_ids"),
        {
            "slug": spec.slug,
            "xmlid": spec.xmlid,
            "name": spec.name,
            "implied_ids": spec.implied_ids,
        },
    )


def _acl_record(spec: AclSpec) -> "OrderedDict[str, object]":
    return _record(
        ("model", "group") + PERM_FIELDS,
        {
            "model": spec.model,
            "group": spec.group,
            "perm_read": spec.perm_read,
            "perm_write": spec.perm_write,
            "perm_create": spec.perm_create,
            "perm_unlink": spec.perm_unlink,
        },
    )


def _menu_record(spec: MenuSpec) -> "OrderedDict[str, object]":
    return _record(
        ("menu", "groups"),
        {"menu": spec.menu, "groups": spec.groups},
    )


def _role_record(spec: RoleSpec) -> "OrderedDict[str, object]":
    return _record(
        ("slug", "xmlid", "name", "groups"),
        {
            "slug": spec.slug,
            "xmlid": spec.xmlid,
            "name": spec.name,
            "groups": spec.groups,
        },
    )


def _lock_record(spec: LockSpec) -> "OrderedDict[str, object]":
    return _record(
        ("model", "allowed_groups", "message"),
        {"model": spec.model, "allowed_groups": spec.allowed_groups, "message": spec.message},
    )


# ── Parsing ─────────────────────────────────────────────────────────────────


def _expect_list(data: object, filename: str) -> list:
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError(f"{filename}: must be a JSON list of objects")
    return data


def _expect_mapping(entry: object, filename: str, index: int) -> dict:
    if not isinstance(entry, dict):
        raise ValueError(f"{filename}: entry {index} must be a JSON object")
    return entry


def _expect_str(entry: dict, key: str, filename: str, index: int) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{filename}: entry {index}: {key!r} must be a non-empty string")
    return value


def _expect_optional_str(entry: dict, key: str, filename: str, index: int) -> str:
    value = entry.get(key) or ""
    if not isinstance(value, str):
        raise ValueError(f"{filename}: entry {index}: {key!r} must be a string")
    return value


def _expect_bool(entry: dict, key: str, filename: str, index: int) -> bool:
    value = entry.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{filename}: entry {index}: {key!r} must be true or false")
    return value


def _expect_ref_list(entry: dict, key: str, filename: str, index: int) -> tuple[str, ...]:
    value = entry.get(key) or []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{filename}: entry {index}: {key!r} must be a list of strings")
    return tuple(value)


def _expect_identity(entry: dict, filename: str, index: int) -> tuple[str, str]:
    """Read the ``slug``/``xmlid`` pair, requiring exactly one of them."""
    slug = _expect_optional_str(entry, "slug", filename, index)
    xmlid = _expect_optional_str(entry, "xmlid", filename, index)
    if bool(slug) == bool(xmlid):
        raise ValueError(
            f"{filename}: entry {index}: exactly one of 'slug' (owned here) "
            "and 'xmlid' (owned elsewhere) is required"
        )
    return slug, xmlid


def parse_groups(text: str, filename: str = GROUP_FILE) -> list[GroupSpec]:
    """Parse a ``groups.json`` document, raising on the first bad entry."""
    specs = []
    for index, entry in enumerate(_expect_list(json.loads(text), filename)):
        entry = _expect_mapping(entry, filename, index)
        slug, xmlid = _expect_identity(entry, filename, index)
        specs.append(
            GroupSpec(
                name=_expect_str(entry, "name", filename, index),
                slug=slug,
                xmlid=xmlid,
                implied_ids=_expect_ref_list(entry, "implied_ids", filename, index),
            )
        )
    return specs


def parse_acl(text: str, filename: str = ACL_FILE) -> list[AclSpec]:
    """Parse an ``acl.json`` document, raising on the first bad entry."""
    specs = []
    for index, entry in enumerate(_expect_list(json.loads(text), filename)):
        entry = _expect_mapping(entry, filename, index)
        specs.append(
            AclSpec(
                model=_expect_str(entry, "model", filename, index),
                group=_expect_str(entry, "group", filename, index),
                perm_read=_expect_bool(entry, "perm_read", filename, index),
                perm_write=_expect_bool(entry, "perm_write", filename, index),
                perm_create=_expect_bool(entry, "perm_create", filename, index),
                perm_unlink=_expect_bool(entry, "perm_unlink", filename, index),
            )
        )
    return specs


def parse_menus(text: str, filename: str = MENU_FILE) -> list[MenuSpec]:
    """Parse a ``menus.json`` document, raising on the first bad entry."""
    specs = []
    for index, entry in enumerate(_expect_list(json.loads(text), filename)):
        entry = _expect_mapping(entry, filename, index)
        specs.append(
            MenuSpec(
                menu=_expect_str(entry, "menu", filename, index),
                groups=_expect_ref_list(entry, "groups", filename, index),
            )
        )
    return specs


def parse_roles(text: str, filename: str = ROLE_FILE) -> list[RoleSpec]:
    """Parse a ``roles.json`` document, raising on the first bad entry."""
    specs = []
    for index, entry in enumerate(_expect_list(json.loads(text), filename)):
        entry = _expect_mapping(entry, filename, index)
        slug, xmlid = _expect_identity(entry, filename, index)
        specs.append(
            RoleSpec(
                name=_expect_str(entry, "name", filename, index),
                slug=slug,
                xmlid=xmlid,
                groups=_expect_ref_list(entry, "groups", filename, index),
            )
        )
    return specs


def parse_locks(text: str, filename: str = LOCK_FILE) -> list[LockSpec]:
    """Parse a ``locks.json`` document, raising on the first bad entry."""
    specs = []
    for index, entry in enumerate(_expect_list(json.loads(text), filename)):
        entry = _expect_mapping(entry, filename, index)
        message = entry.get("message") or ""
        if not isinstance(message, str):
            raise ValueError(f"{filename}: entry {index}: 'message' must be a string")
        specs.append(
            LockSpec(
                model=_expect_str(entry, "model", filename, index),
                allowed_groups=_expect_ref_list(entry, "allowed_groups", filename, index),
                message=message,
            )
        )
    return specs


_PARSERS = (
    (GROUP_FILE, parse_groups),
    (ACL_FILE, parse_acl),
    (MENU_FILE, parse_menus),
    (ROLE_FILE, parse_roles),
    (LOCK_FILE, parse_locks),
)


def _config_from_parsed(parsed: dict) -> SecurityConfig:
    return SecurityConfig(
        groups=tuple(parsed[GROUP_FILE]),
        acl=tuple(parsed[ACL_FILE]),
        menus=tuple(parsed[MENU_FILE]),
        roles=tuple(parsed[ROLE_FILE]),
        locks=tuple(parsed[LOCK_FILE]),
    )


def load_security_config(directory: str | Path) -> SecurityConfig:
    """Read and parse the five files of a security configuration directory.

    Raises :class:`ValueError` if a file is missing or malformed — an absent
    file is an error, not a silence, so that a typo cannot pass as an empty
    policy.

    + directory: path holding ``groups.json``, ``acl.json``, ``menus.json``,
      ``roles.json`` and ``locks.json``.
    """
    directory = Path(directory)
    parsed = {}
    for filename, parser in _PARSERS:
        path = directory / filename
        if not path.is_file():
            raise ValueError(f"{path}: missing (an absent file is an error, not an empty policy)")
        try:
            parsed[filename] = parser(path.read_text(encoding="utf-8"), filename)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{exc.lineno}:{exc.colno}: {exc.msg}") from exc
    return _config_from_parsed(parsed)


# ── Rendering ───────────────────────────────────────────────────────────────


def _dump_records(records: list) -> str:
    """Render *records* one per line, so a diff reads record by record."""
    if not records:
        return "[]\n"
    body = ",\n".join(
        "  " + json.dumps(record, ensure_ascii=False, separators=(", ", ": ")) for record in records
    )
    return "[\n" + body + "\n]\n"


def dump_groups(specs: tuple[GroupSpec, ...] | list[GroupSpec]) -> str:
    """Render groups, sorted by identity, as ``groups.json`` text."""
    return _dump_records([_group_record(s) for s in sorted(specs, key=lambda s: s.key)])


def dump_acl(specs: tuple[AclSpec, ...] | list[AclSpec]) -> str:
    """Render ACL lines, sorted by model then group, as ``acl.json`` text."""
    return _dump_records([_acl_record(s) for s in sorted(specs, key=lambda s: (s.model, s.group))])


def dump_menus(specs: tuple[MenuSpec, ...] | list[MenuSpec]) -> str:
    """Render menus, sorted by menu xmlid, as ``menus.json`` text."""
    return _dump_records([_menu_record(s) for s in sorted(specs, key=lambda s: s.menu)])


def dump_roles(specs: tuple[RoleSpec, ...] | list[RoleSpec]) -> str:
    """Render roles, sorted by identity, as ``roles.json`` text."""
    return _dump_records([_role_record(s) for s in sorted(specs, key=lambda s: s.key)])


def dump_locks(specs: tuple[LockSpec, ...] | list[LockSpec]) -> str:
    """Render locks, sorted by model, as ``locks.json`` text."""
    return _dump_records([_lock_record(s) for s in sorted(specs, key=lambda s: s.model)])


def dump_security_config(config: SecurityConfig) -> dict[str, str]:
    """Render every object list to its file text, keyed by filename."""
    return {
        GROUP_FILE: dump_groups(config.groups),
        ACL_FILE: dump_acl(config.acl),
        MENU_FILE: dump_menus(config.menus),
        ROLE_FILE: dump_roles(config.roles),
        LOCK_FILE: dump_locks(config.locks),
    }


def write_security_config(config: SecurityConfig, directory: str | Path) -> list[Path]:
    """Write the five configuration files into *directory*.

    Returns the paths written, in :data:`SECURITY_FILES` order.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for filename, text in dump_security_config(config).items():
        path = directory / filename
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


def dump_security_document(config: SecurityConfig) -> str:
    """Render a whole configuration as a single JSON document.

    This is the snapshot shape: one file holding every object list, so it can
    be committed and compared as a unit without scattering five files.
    """
    sections = dump_security_config(config)
    body = ",\n".join(
        f"  {json.dumps(name)}: {_inline_records(sections[name])}" for name in SECURITY_FILES
    )
    return "{\n" + body + "\n}\n"


def _inline_records(text: str) -> str:
    """Re-indent a rendered record list to sit inline under a document key."""
    stripped = text.rstrip("\n")
    if stripped == "[]":
        return "[]"
    lines = stripped.split("\n")
    if len(lines) == 1:
        return "[]"
    body = ",\n".join("  " + line for line in lines[1:-1])
    return "[\n" + body + "\n  ]"


def parse_security_document(text: str, filename: str = "snapshot") -> SecurityConfig:
    """Parse a single-document configuration back into a :class:`SecurityConfig`."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{filename}:{exc.lineno}:{exc.colno}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{filename}: must be a JSON object keyed by object name")
    unknown = sorted(set(data) - set(SECURITY_FILES))
    if unknown:
        raise ValueError(f"{filename}: unknown section(s): {', '.join(unknown)}")
    return _config_from_parsed(
        {name: parser(json.dumps(data.get(name) or []), filename) for name, parser in _PARSERS}
    )


# ── Linting ─────────────────────────────────────────────────────────────────


def is_xmlid(reference: str) -> bool:
    """Whether *reference* is a fully-qualified xmlid rather than a local slug."""
    return "." in reference


def _check_ref(reference: str, where: str, keys: set[str], issues: list[str]) -> None:
    if is_xmlid(reference):
        if not _XMLID_RE.match(reference):
            issues.append(f"{where}: {reference!r} is not a valid xmlid")
    elif reference not in keys:
        issues.append(
            f"{where}: {reference!r} is neither declared in {GROUP_FILE} "
            "nor a fully-qualified xmlid"
        )


def _check_identity_shape(spec: GroupSpec | RoleSpec, where: str, issues: list[str]) -> None:
    """Check the shape of the slug/xmlid pair groups and roles share."""
    if spec.slug and not _SLUG_RE.match(spec.slug):
        issues.append(f"{where}: slug must match [a-z][a-z0-9_]*")
    if spec.xmlid and not _XMLID_RE.match(spec.xmlid):
        issues.append(f"{where}: xmlid must look like 'module.name'")


def lint_security_config(config: SecurityConfig) -> list[str]:
    """Check the rules that hold without a database.

    Returns human-readable issues, empty when the configuration is sound.
    A reference can only be checked for shape here: whether the group, model
    or module actually exists is a question for a live instance, and belongs
    to ``security check``.

    + config: the configuration to check.
    """
    issues: list[str] = []
    keys = config.group_keys()

    seen_groups: set[str] = set()
    for group in config.groups:
        where = f"{GROUP_FILE}: group {group.key!r}"
        _check_identity_shape(group, where, issues)
        if group.key in seen_groups:
            issues.append(f"{where}: duplicate entry")
        seen_groups.add(group.key)
        for ref in group.implied_ids:
            _check_ref(ref, f"{where}: implied_ids", keys, issues)

    seen_acl: set[tuple[str, str]] = set()
    for line in config.acl:
        where = f"{ACL_FILE}: {line.model}/{line.group}"
        pair = (line.model, line.group)
        if pair in seen_acl:
            issues.append(f"{where}: duplicate line for this model and group")
        seen_acl.add(pair)
        _check_ref(line.group, where, keys, issues)

    seen_menus: set[str] = set()
    for menu in config.menus:
        where = f"{MENU_FILE}: menu {menu.menu!r}"
        if menu.menu in seen_menus:
            issues.append(f"{where}: duplicate menu entry")
        seen_menus.add(menu.menu)
        if not menu.groups:
            issues.append(f"{where}: declares no group, so it opens nothing")
        for ref in menu.groups:
            _check_ref(ref, where, keys, issues)

    seen_roles: set[str] = set()
    for role in config.roles:
        where = f"{ROLE_FILE}: role {role.key!r}"
        _check_identity_shape(role, where, issues)
        if role.key in seen_roles:
            issues.append(f"{where}: duplicate entry")
        seen_roles.add(role.key)
        if not role.groups:
            issues.append(f"{where}: grants no group")
        for ref in role.groups:
            _check_ref(ref, where, keys, issues)

    seen_locks: set[str] = set()
    for lock in config.locks:
        where = f"{LOCK_FILE}: model {lock.model!r}"
        if lock.model in seen_locks:
            issues.append(f"{where}: duplicate lock")
        seen_locks.add(lock.model)
        for ref in lock.allowed_groups:
            _check_ref(ref, where, keys, issues)

    return issues


def lint_security_directory(directory: str | Path) -> list[str]:
    """Lint a configuration directory, reporting every problem found.

    Collects issues per file rather than stopping at the first, so one run
    shows everything to fix. A missing or malformed file is reported and the
    remaining files are still checked.

    + directory: path holding the five configuration files.
    """
    directory = Path(directory)
    issues: list[str] = []
    parsed: dict[str, list] = {}
    for filename, parser in _PARSERS:
        path = directory / filename
        if not path.is_file():
            issues.append(f"{filename}: missing (an absent file is an error, not an empty policy)")
            continue
        try:
            parsed[filename] = parser(path.read_text(encoding="utf-8"), filename)
        except json.JSONDecodeError as exc:
            issues.append(f"{filename}:{exc.lineno}:{exc.colno}: {exc.msg}")
        except ValueError as exc:
            issues.append(str(exc))
    if issues:
        # Cross-file references cannot be judged against a section that did
        # not parse, so the semantic rules wait for the next run rather than
        # reporting references as unknown for lack of a file.
        issues.append("semantic checks skipped until every file parses")
        return issues
    return lint_security_config(_config_from_parsed(parsed))
