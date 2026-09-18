import pytest

from odoo_instance_utils.security_config import (
    AclSpec,
    GroupSpec,
    LockSpec,
    MenuSpec,
    RoleSpec,
    SecurityConfig,
)
from odoo_instance_utils.security_verify import (
    MODE_EXACT,
    MODE_SUBSET,
    diff_security_config,
)


def acl(model, group, read=True, write=True, create=True, unlink=False):
    """Build an ACL line with the project's usual header rights."""
    return AclSpec(
        model=model,
        group=group,
        perm_read=read,
        perm_write=write,
        perm_create=create,
        perm_unlink=unlink,
    )


def has(issues, fragment):
    """Whether any issue mentions *fragment*."""
    return any(fragment in issue for issue in issues)


class TestSoundConfiguration:
    def test_identical_configurations_match(self):
        config = SecurityConfig(
            groups=(GroupSpec(name="Direction", slug="direction"),),
            acl=(acl("sale.order", "direction"),),
            menus=(MenuSpec(menu="sale.menu_sale_order", groups=("direction",)),),
            roles=(RoleSpec(name="Direction", slug="direction", groups=("direction",)),),
            locks=(LockSpec(model="crm.stage", message="Référence"),),
        )
        assert diff_security_config(config, config) == []

    def test_empty_configurations_match(self):
        assert diff_security_config(SecurityConfig(), SecurityConfig()) == []


class TestModeValidation:
    def test_unknown_mode_is_rejected(self):
        with pytest.raises(ValueError, match="unknown mode"):
            diff_security_config(SecurityConfig(), SecurityConfig(), mode="loose")


class TestGroups:
    def test_missing_group(self):
        expected = SecurityConfig(groups=(GroupSpec(name="Direction", slug="direction"),))
        issues = diff_security_config(expected, SecurityConfig())
        assert has(issues, "declared but missing from the instance")

    def test_renamed_group(self):
        expected = SecurityConfig(groups=(GroupSpec(name="Direction", slug="direction"),))
        live = SecurityConfig(groups=(GroupSpec(name="Dir.", slug="direction"),))
        assert has(diff_security_config(expected, live), "name is 'Dir.'")

    def test_implied_ids_drift(self):
        expected = SecurityConfig(
            groups=(GroupSpec(name="G", slug="g", implied_ids=("base.group_user",)),)
        )
        live = SecurityConfig(groups=(GroupSpec(name="G", slug="g"),))
        assert has(diff_security_config(expected, live), "implies []")

    def test_subset_mode_ignores_groups_the_project_does_not_manage(self):
        # A live Odoo carries hundreds of groups; a policy asserts only its own.
        expected = SecurityConfig(groups=(GroupSpec(name="G", slug="g"),))
        live = SecurityConfig(
            groups=(
                GroupSpec(name="G", slug="g"),
                GroupSpec(name="Paramètres", xmlid="base.group_system"),
            )
        )
        assert diff_security_config(expected, live, MODE_SUBSET) == []

    def test_exact_mode_reports_undeclared_groups(self):
        expected = SecurityConfig(groups=(GroupSpec(name="G", slug="g"),))
        live = SecurityConfig(
            groups=(
                GroupSpec(name="G", slug="g"),
                GroupSpec(name="Paramètres", xmlid="base.group_system"),
            )
        )
        issues = diff_security_config(expected, live, MODE_EXACT)
        assert has(issues, "base.group_system")
        assert has(issues, "not declared")


class TestAcl:
    def test_diverging_right(self):
        expected = SecurityConfig(acl=(acl("sale.order", "g"),))
        live = SecurityConfig(acl=(acl("sale.order", "g", create=False),))
        assert has(diff_security_config(expected, live), "perm_create is False, declared True")

    def test_missing_line(self):
        expected = SecurityConfig(acl=(acl("sale.order", "g"),))
        assert has(diff_security_config(expected, SecurityConfig()), "declared but missing")

    def test_intruder_on_a_declared_model_is_reported_in_subset_mode(self):
        # A model the project manages must not carry undeclared rights.
        expected = SecurityConfig(acl=(acl("sale.order", "g"),))
        live = SecurityConfig(acl=(acl("sale.order", "g"), acl("sale.order", "autre")))
        issues = diff_security_config(expected, live, MODE_SUBSET)
        assert has(issues, "sale.order/autre")
        assert has(issues, "on a declared model")

    def test_undeclared_model_is_silent_in_subset_mode(self):
        # Thousands of ACL lines shipped by Odoo and the OCA must not be noise.
        expected = SecurityConfig(acl=(acl("sale.order", "g"),))
        live = SecurityConfig(acl=(acl("sale.order", "g"), acl("stock.move", "autre")))
        assert diff_security_config(expected, live, MODE_SUBSET) == []

    def test_exact_mode_reports_every_undeclared_line(self):
        expected = SecurityConfig(acl=(acl("sale.order", "g"),))
        live = SecurityConfig(acl=(acl("sale.order", "g"), acl("stock.move", "autre")))
        issues = diff_security_config(expected, live, MODE_EXACT)
        assert has(issues, "stock.move/autre")


class TestMenus:
    def test_group_that_cannot_see_the_menu(self):
        expected = SecurityConfig(menus=(MenuSpec(menu="sale.menu_sale_order", groups=("g",)),))
        live = SecurityConfig(menus=(MenuSpec(menu="sale.menu_sale_order", groups=("autre",)),))
        assert has(diff_security_config(expected, live), "'g' cannot see the menu")

    def test_missing_menu(self):
        expected = SecurityConfig(menus=(MenuSpec(menu="sale.menu_sale_order", groups=("g",)),))
        assert has(diff_security_config(expected, SecurityConfig()), "declared but missing")

    def test_subset_mode_is_additive_about_extra_groups(self):
        # Odoo grants its own groups; a policy opens the menu further, it does
        # not claim to be the complete list.
        expected = SecurityConfig(menus=(MenuSpec(menu="sale.menu_sale_order", groups=("g",)),))
        live = SecurityConfig(
            menus=(
                MenuSpec(
                    menu="sale.menu_sale_order",
                    groups=("g", "sales_team.group_sale_salesman"),
                ),
            )
        )
        assert diff_security_config(expected, live, MODE_SUBSET) == []

    def test_exact_mode_treats_the_group_list_as_complete(self):
        expected = SecurityConfig(menus=(MenuSpec(menu="sale.menu_sale_order", groups=("g",)),))
        live = SecurityConfig(
            menus=(
                MenuSpec(
                    menu="sale.menu_sale_order",
                    groups=("g", "sales_team.group_sale_salesman"),
                ),
            )
        )
        issues = diff_security_config(expected, live, MODE_EXACT)
        assert has(issues, "can see the menu but is not declared")


class TestRoles:
    def test_role_group_drift(self):
        expected = SecurityConfig(roles=(RoleSpec(name="Direction", slug="d", groups=("g",)),))
        live = SecurityConfig(roles=(RoleSpec(name="Direction", slug="d", groups=("g", "autre")),))
        assert has(diff_security_config(expected, live), "carries ['g', 'autre']")

    def test_missing_role(self):
        expected = SecurityConfig(roles=(RoleSpec(name="Direction", slug="d", groups=("g",)),))
        assert has(diff_security_config(expected, SecurityConfig()), "declared but missing")

    def test_slug_and_xmlid_do_not_match_without_a_namespace(self):
        # A policy names what it owns by slug; an instance holds the xmlid the
        # creating module gave it. Without being told the owning module there
        # is nothing to bridge the two, so they are reported.
        expected = SecurityConfig(roles=(RoleSpec(name="D", slug="d", groups=("g",)),))
        live = SecurityConfig(roles=(RoleSpec(name="D", xmlid="odoo_foundry.d", groups=("g",)),))
        issues = diff_security_config(expected, live)
        assert has(issues, "declared but missing from the instance")

    def test_namespace_bridges_policy_slugs_and_live_xmlids(self):
        # The same comparison, told which module owns the slug-based entries.
        expected = SecurityConfig(roles=(RoleSpec(name="D", slug="d", groups=("g",)),))
        live = SecurityConfig(roles=(RoleSpec(name="D", xmlid="odoo_foundry.d", groups=("g",)),))
        assert diff_security_config(expected, live, namespace="odoo_foundry") == []

    def test_namespace_is_folded_into_reported_identities(self):
        expected = SecurityConfig(roles=(RoleSpec(name="D", slug="d", groups=("g",)),))
        issues = diff_security_config(expected, SecurityConfig(), namespace="odoo_foundry")
        assert has(issues, "'odoo_foundry.d'")


class TestLocks:
    def test_missing_lock(self):
        expected = SecurityConfig(locks=(LockSpec(model="crm.stage"),))
        assert has(diff_security_config(expected, SecurityConfig()), "the lock is absent")

    def test_allowed_groups_drift(self):
        expected = SecurityConfig(locks=(LockSpec(model="crm.stage"),))
        live = SecurityConfig(locks=(LockSpec(model="crm.stage", allowed_groups=("g",)),))
        assert has(diff_security_config(expected, live), "allows ['g']")

    def test_message_drift(self):
        expected = SecurityConfig(locks=(LockSpec(model="crm.stage", message="Attendu"),))
        live = SecurityConfig(locks=(LockSpec(model="crm.stage", message="Autre"),))
        assert has(diff_security_config(expected, live), "message is 'Autre'")

    def test_exact_mode_reports_a_lock_added_by_hand(self):
        expected = SecurityConfig(locks=(LockSpec(model="crm.stage"),))
        live = SecurityConfig(locks=(LockSpec(model="crm.stage"), LockSpec(model="uom.uom")))
        issues = diff_security_config(expected, live, MODE_EXACT)
        assert has(issues, "uom.uom")
        assert has(issues, "locked on the instance but not declared")


class TestSnapshotDrift:
    """The use case a snapshot exists for: a module update moved something."""

    def test_identical_reads_are_silent(self):
        state = SecurityConfig(
            groups=(GroupSpec(name="Ventes", xmlid="sales_team.group_sale_salesman"),),
            acl=(acl("sale.order", "sales_team.group_sale_salesman"),),
        )
        assert diff_security_config(state, state, MODE_EXACT) == []

    def test_a_module_update_that_rewrote_a_right_is_caught(self):
        before = SecurityConfig(acl=(acl("sale.order", "sales_team.group_sale_salesman"),))
        after = SecurityConfig(
            acl=(acl("sale.order", "sales_team.group_sale_salesman", create=False),)
        )
        issues = diff_security_config(before, after, MODE_EXACT)
        assert has(issues, "perm_create is False, declared True")

    def test_a_module_update_that_added_an_acl_line_is_caught(self):
        before = SecurityConfig(acl=(acl("sale.order", "g"),))
        after = SecurityConfig(acl=(acl("sale.order", "g"), acl("sale.order", "nouveau")))
        issues = diff_security_config(before, after, MODE_EXACT)
        assert has(issues, "sale.order/nouveau")
