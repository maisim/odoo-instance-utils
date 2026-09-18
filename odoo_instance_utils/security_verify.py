"""
Compare two security configurations.

The expected side is either the project's policy (``security/*.json``) or a
committed snapshot; the live side is what a running instance reports. Both
share the shape modelled by :mod:`odoo_instance_utils.security_config`, which
is what lets one function serve both uses.

Two modes differ in how much they report:

- :data:`MODE_SUBSET` — the policy reading. Asserts what is declared and
  stays silent about the rest, with one exception: an ACL line sitting on a
  model the project declares is reported even when it is not declared, since
  a managed model should not carry undeclared rights. Menu visibility is
  additive here: the declared groups must see the menu, and removing a group
  Odoo granted is not reported.
- :data:`MODE_EXACT` — the snapshot reading. Reports every difference in both
  directions, and treats a declared menu's group list as complete.

Within a declared entity, every declared field is asserted, in both modes.
The mode therefore defines the semantics of ``menus.json``; each artifact is
compared in the mode matching its nature — policy as subset, snapshot as
exact.
"""

from __future__ import annotations

from odoo_instance_utils.security_config import (
    ACL_FILE,
    GROUP_FILE,
    LOCK_FILE,
    MENU_FILE,
    PERM_FIELDS,
    ROLE_FILE,
    SecurityConfig,
    entity_key,
)

MODE_SUBSET = "subset"
MODE_EXACT = "exact"
MODES = (MODE_SUBSET, MODE_EXACT)


def diff_security_config(
    expected: SecurityConfig,
    live: SecurityConfig,
    mode: str = MODE_SUBSET,
    namespace: str = "",
) -> list[str]:
    """Compare an expected configuration against a live one.

    + expected: the policy or snapshot being asserted.
    + live: the state read from the instance.
    + mode: :data:`MODE_SUBSET` or :data:`MODE_EXACT`.
    + namespace: module owning the entries *expected* names by slug, so that
      they match the xmlids a live instance reports. Left empty, identities
      are compared as written, which only matches configs using the same
      form on both sides.

    Returns a list of human-readable discrepancies (empty = match).
    """
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}, expected one of {MODES}")

    issues: list[str] = []
    _diff_groups(expected, live, mode, namespace, issues)
    _diff_acl(expected, live, mode, issues)
    _diff_menus(expected, live, mode, issues)
    _diff_roles(expected, live, mode, namespace, issues)
    _diff_locks(expected, live, mode, issues)
    return issues


def _key(spec, namespace: str) -> str:
    """Identity of a group or role, folding in the owning module."""
    return entity_key(spec.slug, spec.xmlid, namespace)


def _diff_groups(
    expected: SecurityConfig,
    live: SecurityConfig,
    mode: str,
    namespace: str,
    issues: list[str],
) -> None:
    live_by_key = {_key(spec, namespace): spec for spec in live.groups}
    for spec in expected.groups:
        where = f"{GROUP_FILE}: group {_key(spec, namespace)!r}"
        actual = live_by_key.get(_key(spec, namespace))
        if actual is None:
            issues.append(f"{where}: declared but missing from the instance")
            continue
        if actual.name != spec.name:
            issues.append(f"{where}: name is {actual.name!r}, declared {spec.name!r}")
        if tuple(actual.implied_ids) != tuple(spec.implied_ids):
            issues.append(
                f"{where}: implies {list(actual.implied_ids)}, declared {list(spec.implied_ids)}"
            )
    if mode == MODE_EXACT:
        declared = {_key(spec, namespace) for spec in expected.groups}
        for spec in live.groups:
            key = _key(spec, namespace)
            if key not in declared:
                issues.append(
                    f"{GROUP_FILE}: group {key!r}: present on the instance but not declared"
                )


def _diff_acl(expected: SecurityConfig, live: SecurityConfig, mode: str, issues: list[str]) -> None:
    live_by_pair = {(spec.model, spec.group): spec for spec in live.acl}
    declared_pairs = {(spec.model, spec.group) for spec in expected.acl}

    for spec in expected.acl:
        where = f"{ACL_FILE}: {spec.model}/{spec.group}"
        actual = live_by_pair.get((spec.model, spec.group))
        if actual is None:
            issues.append(f"{where}: declared but missing from the instance")
            continue
        for perm in PERM_FIELDS:
            if getattr(actual, perm) != getattr(spec, perm):
                issues.append(
                    f"{where}: {perm} is {getattr(actual, perm)}, declared {getattr(spec, perm)}"
                )

    managed_models = expected.acl_models() if mode == MODE_SUBSET else None
    for spec in live.acl:
        if (spec.model, spec.group) in declared_pairs:
            continue
        if managed_models is not None and spec.model not in managed_models:
            continue
        suffix = "on a declared model" if managed_models is not None else "on the instance"
        issues.append(f"{ACL_FILE}: {spec.model}/{spec.group}: present {suffix} but not declared")


def _diff_menus(
    expected: SecurityConfig, live: SecurityConfig, mode: str, issues: list[str]
) -> None:
    live_by_menu = {spec.menu: spec for spec in live.menus}

    for spec in expected.menus:
        where = f"{MENU_FILE}: menu {spec.menu!r}"
        actual = live_by_menu.get(spec.menu)
        if actual is None:
            issues.append(f"{where}: declared but missing from the instance")
            continue
        for group in spec.groups:
            if group not in actual.groups:
                issues.append(f"{where}: {group!r} cannot see the menu")
        if mode == MODE_EXACT:
            for group in actual.groups:
                if group not in spec.groups:
                    issues.append(f"{where}: {group!r} can see the menu but is not declared")

    if mode == MODE_EXACT:
        declared = {spec.menu for spec in expected.menus}
        for spec in live.menus:
            if spec.menu not in declared:
                issues.append(
                    f"{MENU_FILE}: menu {spec.menu!r}: visible on the instance but not declared"
                )


def _diff_roles(
    expected: SecurityConfig,
    live: SecurityConfig,
    mode: str,
    namespace: str,
    issues: list[str],
) -> None:
    live_by_key = {_key(spec, namespace): spec for spec in live.roles}
    for spec in expected.roles:
        where = f"{ROLE_FILE}: role {_key(spec, namespace)!r}"
        actual = live_by_key.get(_key(spec, namespace))
        if actual is None:
            issues.append(f"{where}: declared but missing from the instance")
            continue
        if actual.name != spec.name:
            issues.append(f"{where}: name is {actual.name!r}, declared {spec.name!r}")
        if tuple(actual.groups) != tuple(spec.groups):
            issues.append(f"{where}: carries {list(actual.groups)}, declared {list(spec.groups)}")
    if mode == MODE_EXACT:
        declared = {_key(spec, namespace) for spec in expected.roles}
        for spec in live.roles:
            key = _key(spec, namespace)
            if key not in declared:
                issues.append(
                    f"{ROLE_FILE}: role {key!r}: present on the instance but not declared"
                )


def _diff_locks(
    expected: SecurityConfig, live: SecurityConfig, mode: str, issues: list[str]
) -> None:
    live_by_model = {spec.model: spec for spec in live.locks}
    for spec in expected.locks:
        where = f"{LOCK_FILE}: model {spec.model!r}"
        actual = live_by_model.get(spec.model)
        if actual is None:
            issues.append(f"{where}: declared but the lock is absent")
            continue
        if tuple(actual.allowed_groups) != tuple(spec.allowed_groups):
            issues.append(
                f"{where}: allows {list(actual.allowed_groups)}, "
                f"declared {list(spec.allowed_groups)}"
            )
        if actual.message != spec.message:
            issues.append(f"{where}: message is {actual.message!r}, declared {spec.message!r}")
    if mode == MODE_EXACT:
        declared = {spec.model for spec in expected.locks}
        for spec in live.locks:
            if spec.model not in declared:
                issues.append(
                    f"{LOCK_FILE}: model {spec.model!r}: locked on the instance but not declared"
                )
