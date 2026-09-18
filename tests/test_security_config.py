import json

import pytest

from odoo_instance_utils.security_config import (
    AclSpec,
    GroupSpec,
    LockSpec,
    MenuSpec,
    RoleSpec,
    SecurityConfig,
    dump_security_config,
    dump_security_document,
    lint_security_config,
    lint_security_directory,
    load_security_config,
    parse_acl,
    parse_groups,
    parse_roles,
    parse_security_document,
    write_security_config,
)

GROUPS_JSON = """\
[
  {"slug": "sales_referential_manager", "name": "Référentiels de vente", "implied_ids": ["sales_team.group_sale_salesman_all_leads"]},
  {"xmlid": "base.group_system", "name": "Paramètres"}
]
"""

ACL_JSON = """\
[
  {"model": "sale.order", "group": "sales_referential_manager", "perm_read": true, "perm_write": true, "perm_create": true, "perm_unlink": false}
]
"""

MENUS_JSON = """\
[
  {"menu": "sale.menu_sale_order", "groups": ["sales_referential_manager"]}
]
"""

ROLES_JSON = """\
[
  {"slug": "direction", "name": "Direction", "groups": ["sales_referential_manager"]}
]
"""

LOCKS_JSON = """\
[
  {"model": "crm.stage", "message": "Donnée de référence"}
]
"""


def write_config(
    directory,
    groups=GROUPS_JSON,
    acl=ACL_JSON,
    menus=MENUS_JSON,
    roles=ROLES_JSON,
    locks=LOCKS_JSON,
):
    """Write the five configuration files into *directory*."""
    for name, text in (
        ("groups.json", groups),
        ("acl.json", acl),
        ("menus.json", menus),
        ("roles.json", roles),
        ("locks.json", locks),
    ):
        (directory / name).write_text(text, encoding="utf-8")


def sample_config():
    """A small, sound configuration covering every object list."""
    return SecurityConfig(
        groups=(
            GroupSpec(
                name="Référentiels de vente",
                slug="sales_referential_manager",
                implied_ids=("sales_team.group_sale_salesman_all_leads",),
            ),
        ),
        acl=(
            AclSpec(
                model="sale.order",
                group="sales_referential_manager",
                perm_read=True,
                perm_write=True,
                perm_create=True,
                perm_unlink=False,
            ),
        ),
        menus=(MenuSpec(menu="sale.menu_sale_order", groups=("sales_referential_manager",)),),
        roles=(
            RoleSpec(name="Direction", slug="direction", groups=("sales_referential_manager",)),
        ),
        locks=(LockSpec(model="crm.stage", message="Donnée de référence"),),
    )


class TestParsing:
    def test_owned_group_uses_slug(self):
        spec = parse_groups(GROUPS_JSON)[0]
        assert spec.slug == "sales_referential_manager"
        assert spec.xmlid == ""
        assert spec.key == "sales_referential_manager"

    def test_referenced_group_uses_xmlid(self):
        spec = parse_groups(GROUPS_JSON)[1]
        assert spec.slug == ""
        assert spec.xmlid == "base.group_system"
        assert spec.key == "base.group_system"

    def test_group_requires_exactly_one_identity(self):
        with pytest.raises(ValueError, match="neither declared|exactly one"):
            parse_groups('[{"name": "Sans identité"}]')
        with pytest.raises(ValueError, match="exactly one"):
            parse_groups('[{"slug": "a", "xmlid": "base.group_system", "name": "Les deux"}]')

    def test_acl_requires_four_booleans(self):
        with pytest.raises(ValueError, match="'perm_unlink' must be true or false"):
            parse_acl(
                '[{"model": "sale.order", "group": "g", "perm_read": true, '
                '"perm_write": true, "perm_create": true}]'
            )

    def test_acl_rejects_non_boolean_perm(self):
        with pytest.raises(ValueError, match="'perm_read' must be true or false"):
            parse_acl(
                '[{"model": "sale.order", "group": "g", "perm_read": 1, '
                '"perm_write": true, "perm_create": true, "perm_unlink": false}]'
            )

    def test_roles_require_exactly_one_identity(self):
        with pytest.raises(ValueError, match="exactly one"):
            parse_roles('[{"name": "Orphelin", "groups": ["a"]}]')

    def test_empty_list_is_valid(self):
        assert parse_groups("[]") == []

    def test_empty_file_is_rejected(self):
        # Same reasoning as a missing file: an authoring accident must not
        # pass as a deliberately empty policy.
        with pytest.raises(json.JSONDecodeError):
            parse_groups("")

    def test_non_list_document_is_rejected(self):
        with pytest.raises(ValueError, match="must be a JSON list"):
            parse_groups('{"slug": "a"}')


class TestRoundTrip:
    def test_dump_then_parse_returns_the_same_config(self):
        config = sample_config()
        assert parse_groups(dump_security_config(config)["groups.json"]) == list(config.groups)
        assert parse_acl(dump_security_config(config)["acl.json"]) == list(config.acl)

    def test_directory_round_trip(self, tmp_path):
        config = sample_config()
        write_security_config(config, tmp_path)
        reloaded = load_security_config(tmp_path)
        assert reloaded == config

    def test_document_round_trip(self):
        config = sample_config()
        assert parse_security_document(dump_security_document(config)) == config

    def test_document_rejects_unknown_section(self):
        with pytest.raises(ValueError, match="unknown section"):
            parse_security_document('{"groups": [], "rules": []}')


class TestDeterminism:
    def test_repeated_dumps_are_byte_identical(self):
        config = sample_config()
        assert dump_security_document(config) == dump_security_document(config)

    def test_order_of_the_source_list_does_not_change_the_dump(self):
        ordered = sample_config()
        shuffled = SecurityConfig(
            groups=ordered.groups,
            acl=ordered.acl,
            menus=ordered.menus,
            roles=ordered.roles,
            locks=(
                LockSpec(model="uom.uom"),
                LockSpec(model="crm.stage", message="Donnée de référence"),
            ),
        )
        assert dump_security_config(shuffled)["locks.json"] == (
            "[\n"
            '  {"model": "crm.stage", "message": "Donnée de référence"},\n'
            '  {"model": "uom.uom"}\n'
            "]\n"
        )

    def test_non_ascii_labels_are_not_escaped(self):
        text = dump_security_document(sample_config())
        assert "Référentiels de vente" in text
        assert "\\u00e9" not in text

    def test_json_document_is_valid_json(self):
        json.loads(dump_security_document(sample_config()))


class TestLintRules:
    def test_sound_config_has_no_issue(self):
        assert lint_security_config(sample_config()) == []

    def test_duplicate_group_entry(self):
        config = SecurityConfig(
            groups=(
                GroupSpec(name="Un", slug="meme_slug"),
                GroupSpec(name="Deux", slug="meme_slug"),
            )
        )
        assert any("duplicate entry" in issue for issue in lint_security_config(config))

    def test_invalid_slug_shape(self):
        config = SecurityConfig(groups=(GroupSpec(name="Un", slug="Pas-Bon"),))
        assert any("slug must match" in issue for issue in lint_security_config(config))

    def test_unknown_group_reference(self):
        config = SecurityConfig(
            groups=(GroupSpec(name="Connu", slug="connu"),),
            acl=(
                AclSpec(
                    model="sale.order",
                    group="inconnu",
                    perm_read=True,
                    perm_write=False,
                    perm_create=False,
                    perm_unlink=False,
                ),
            ),
        )
        issues = lint_security_config(config)
        assert any("'inconnu' is neither declared" in issue for issue in issues)

    def test_reference_to_another_module_is_accepted(self):
        config = SecurityConfig(
            acl=(
                AclSpec(
                    model="sale.order",
                    group="account.group_account_readonly",
                    perm_read=True,
                    perm_write=False,
                    perm_create=False,
                    perm_unlink=False,
                ),
            )
        )
        assert lint_security_config(config) == []

    def test_duplicate_acl_pair(self):
        line = AclSpec(
            model="sale.order",
            group="connu",
            perm_read=True,
            perm_write=False,
            perm_create=False,
            perm_unlink=False,
        )
        config = SecurityConfig(groups=(GroupSpec(name="Connu", slug="connu"),), acl=(line, line))
        assert any("duplicate line" in issue for issue in lint_security_config(config))

    def test_menu_without_group_opens_nothing(self):
        config = SecurityConfig(menus=(MenuSpec(menu="sale.menu_sale_order"),))
        assert any("declares no group" in issue for issue in lint_security_config(config))

    def test_role_granting_nothing(self):
        config = SecurityConfig(roles=(RoleSpec(name="Vide", slug="vide"),))
        assert any("grants no group" in issue for issue in lint_security_config(config))

    def test_duplicate_lock(self):
        config = SecurityConfig(locks=(LockSpec(model="crm.stage"), LockSpec(model="crm.stage")))
        assert any("duplicate lock" in issue for issue in lint_security_config(config))

    def test_malformed_xmlid_reference(self):
        config = SecurityConfig(
            groups=(GroupSpec(name="Un", slug="un", implied_ids=("base..system",)),)
        )
        assert any("is not a valid xmlid" in issue for issue in lint_security_config(config))


class TestLintDirectory:
    def test_sound_directory(self, tmp_path):
        write_config(tmp_path)
        assert lint_security_directory(tmp_path) == []

    def test_missing_file_is_an_error_not_a_silence(self, tmp_path):
        write_config(tmp_path)
        (tmp_path / "locks.json").unlink()
        issues = lint_security_directory(tmp_path)
        assert any("locks.json: missing" in issue for issue in issues)

    def test_malformed_json_names_the_line(self, tmp_path):
        write_config(tmp_path, acl="[\n  {\n")
        issues = lint_security_directory(tmp_path)
        assert any(issue.startswith("acl.json:") for issue in issues)

    def test_semantic_checks_are_skipped_while_a_file_is_missing(self, tmp_path):
        write_config(tmp_path)
        (tmp_path / "locks.json").unlink()
        issues = lint_security_directory(tmp_path)
        assert any("semantic checks skipped" in issue for issue in issues)

    def test_all_files_are_reported_not_just_the_first(self, tmp_path):
        write_config(tmp_path, groups="not json", acl="not json either")
        issues = lint_security_directory(tmp_path)
        assert any(issue.startswith("groups.json:") for issue in issues)
        assert any(issue.startswith("acl.json:") for issue in issues)

    def test_semantic_issues_are_reported_when_everything_parses(self, tmp_path):
        write_config(tmp_path, acl=ACL_JSON.replace("sales_referential_manager", "inconnu"))
        issues = lint_security_directory(tmp_path)
        assert any("'inconnu' is neither declared" in issue for issue in issues)
