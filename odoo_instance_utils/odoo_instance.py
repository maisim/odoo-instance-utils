import json
import logging
import sys
from typing import Any, Dict, List

import odoo
from odoo.exceptions import ValidationError

from .addons import Addons
from .security_config import (
    AclSpec,
    GroupSpec,
    LockSpec,
    MenuSpec,
    RoleSpec,
    SecurityConfig,
)

_logger = logging.getLogger(__name__)


class OdooInstance:
    FILTER_FIELDS = [
        "name",
        "model_id",
        "domain",
        "user_id",
        "context",
        "action_id",
        "sort",
        "active",
        "is_default",
        "create_uid",
    ]
    EXPORT_FIELDS = ["name", "resource", "display_name", "create_uid"]
    EXPORT_LINE_FIELDS = ["name", "sequence", "create_uid"]

    def __init__(self, odoo=odoo, env=None):
        self.env = env
        self.version = odoo.release.version
        self.major_version = odoo.release.major_version
        self.addons = Addons(addons_paths=odoo.tools.config["addons_path"])
        self.addons.fill_from_odoo_db(env)  # DB first: authoritative list
        self.addons.fill_from_addons_paths()  # FS second: paths, git_repo, manifests

    def __str__(self):
        return f"Odoo {self.env.cr.dbname}"

    def install_addons(self, addons_names: List[str]) -> List[str]:
        """Install addons by name and return the list of installed addon names."""
        OdooInstanceModule = self.env["ir.module.module"]
        addons_to_install = OdooInstanceModule.search(
            [("name", "in", addons_names), ("state", "!=", "installed")]
        )
        addons_to_install.button_immediate_install()
        return addons_to_install.mapped("name")

    def list_filters(self) -> list:
        """Return all filters as a list of dicts with id, name and model_id."""
        filters = self.env["ir.filters"].search([])
        return filters.read(fields=["id", "name", "model_id"], load=None)

    def dump_filters(self, ids: List[int]) -> str:
        """Export filters as JSON."""
        ids = [int(i) for i in ids]
        filters = self.env["ir.filters"].search([("id", "in", ids)])
        dump = filters.read(fields=self.FILTER_FIELDS, load=None)
        for filter_data in dump:
            filter_data.pop("id", None)
        return json.dumps(dump)

    def restore_filters(self, filters_json: str) -> None:
        """Restore filters from JSON."""
        filters = json.loads(filters_json)
        _logger.info(
            "Restoring filters on database '%s' using Python %s",
            self.env.cr.dbname,
            self.python_version,
        )
        _logger.info("Current user: %s (id: %s)", self.env.user.name, self.env.user.id)
        for filter_data in filters:
            self._restore_single_filter(filter_data)

    def _restore_single_filter(self, filter_data: Dict[str, Any]) -> None:
        """Restore a single filter, deleting any existing one with the same name/model/user."""
        existing_filters = self.env["ir.filters"].search(
            [
                ("name", "=", filter_data["name"]),
                ("model_id", "=", filter_data["model_id"]),
                ("user_id", "=", filter_data["user_id"]),
            ]
        )
        _logger.info(
            "Found %s existing filters with name '%s' and model '%s'",
            len(existing_filters),
            filter_data["name"],
            filter_data["model_id"],
        )
        existing_filters.unlink()
        _logger.info(
            "Creating filter '%s' on model '%s'", filter_data["name"], filter_data["model_id"]
        )
        filter_owner = self.env["res.users"].browse(filter_data.pop("create_uid"))
        filter_data["create_uid"] = filter_owner.id
        filter_id = self.env["ir.filters"].with_user(filter_owner).create(filter_data).id
        _logger.info("Created filter '%s' with ID %s", filter_data["name"], filter_id)
        _logger.debug("Filter data: %s", filter_data)

    def dump_exports(self, ids: List[int]) -> str:
        """Export exports as JSON, including their lines."""
        ids = [int(i) for i in ids]
        exports = self.env["ir.exports"].search([("id", "in", ids)])
        dump = exports.read(fields=self.EXPORT_FIELDS, load=None)
        for export in dump:
            export_fields = (
                self.env["ir.exports.line"]
                .search([("export_id", "=", export["id"])], order="sequence")
                .read(fields=self.EXPORT_LINE_FIELDS, load=None)
            )
            for export_field in export_fields:
                export_field.pop("id", None)
            export["export_fields"] = export_fields
        for export in dump:
            export.pop("id", None)
        return json.dumps(dump)

    def restore_exports(self, exports_json: str) -> None:
        """Restore exports from JSON, including their lines."""
        exports = json.loads(exports_json)
        _logger.info(
            "Restoring exports on database '%s' using Python %s",
            self.env.cr.dbname,
            self.python_version,
        )
        _logger.info("Current user: %s (id: %s)", self.env.user.name, self.env.user.id)
        for export in exports:
            self._restore_single_export(export)

    def _restore_single_export(self, export: Dict[str, Any]) -> None:
        existing_exports = self.env["ir.exports"].search(
            [
                ("name", "=", export["name"]),
                ("resource", "=", export["resource"]),
                ("create_uid.id", "=", export["create_uid"]),
            ]
        )
        _logger.info(
            "Found %s existing exports with name '%s' and resource '%s'",
            len(existing_exports),
            export["name"],
            export["resource"],
        )
        existing_exports.unlink()
        _logger.info("Creating export '%s' on model '%s'", export["name"], export["resource"])
        export_owner = self.env["res.users"].browse(export.pop("create_uid"))
        export_group = self.env.ref("base.group_allow_export")
        if export_group and export_owner not in export_group.users:
            _logger.info("Adding user '%s' to group '%s'", export_owner.name, export_group.name)
            export_group.sudo().write({"users": [(4, export_owner.id)]})
        export_fields = export.pop("export_fields")
        export_id = self.env["ir.exports"].with_user(export_owner).create(export).id
        _logger.info("Created export '%s' with ID %s", export["name"], export_id)
        _logger.debug("Export fields: %s", export_fields)
        for export_field in export_fields:
            field_name = export_field.get("name")
            if not field_name:
                _logger.warning("Export line has no 'name' key. Skipping.")
                continue
            export_field["export_id"] = export_id
            try:
                self.env["ir.exports.line"].with_context(skip_check=True).create(export_field)
            except ValidationError as e:
                _logger.warning("Error creating export line: %s. Skipping", e)
                continue

    def dump_security_config(
        self,
        models: List[str] | None = None,
        groups: List[str] | None = None,
        roles: List[str] | None = None,
    ) -> SecurityConfig:
        """Read the live security state into a configuration object.

        + models: restrict ACL lines to these technical model names. ``None``
          reads every model.
        + groups: restrict groups to these xmlids. ``None`` reads every group.
        + roles: restrict roles to these xmlids. ``None`` reads every role.

        The scope arguments exist because a real database carries thousands of
        ACL lines shipped by Odoo and the OCA addons: reading everything is
        what a snapshot wants, reading a named subset is what a policy capture
        wants.

        Two things the model deliberately does not carry, and which are
        therefore absent from the result: ACL lines with no group (global
        rights, visible to every user) and menus visible to everyone. Locks
        are empty until the enforcement module exists.
        """
        group_specs, group_keys = self._read_groups(groups)
        return SecurityConfig(
            groups=group_specs,
            acl=tuple(self._read_acl(models, group_keys)),
            menus=tuple(self._read_menus(group_keys)),
            roles=tuple(self._read_roles(roles, group_keys)),
            locks=tuple(self._read_locks()),
        )

    def _xmlid_map(self, model: str, res_ids: List[int]) -> Dict[int, str]:
        """Map record ids to one xmlid each, chosen deterministically.

        A record may carry several xmlids; the alphabetically first
        ``module.name`` wins so that repeated reads produce the same answer.
        """
        if not res_ids:
            return {}
        data = self.env["ir.model.data"].search(
            [("model", "=", model), ("res_id", "in", list(res_ids))]
        )
        mapping: Dict[int, str] = {}
        for record in sorted(data, key=lambda d: (d.module, d.name)):
            mapping.setdefault(record.res_id, f"{record.module}.{record.name}")
        return mapping

    def _identity(self, model: str, record, xmlids: Dict[int, str]) -> str:
        """Return a stable identity for *record*, falling back to its id.

        A group created by hand in the interface carries no xmlid. Odoo's own
        convention for such records is used instead, so the entry is not lost
        — at the cost of an identity that is stable within one database but
        not across two.
        """
        return xmlids.get(record.id) or f"{model},{record.id}"

    def _read_groups(self, wanted: List[str] | None) -> tuple:
        """Read groups, returning the specs and the keys used to match them."""
        domain = []
        if wanted:
            ids = [self.env.ref(ref, raise_if_not_found=False).id for ref in wanted]
            domain = [("id", "in", [i for i in ids if i])]
        records = self.env["res.groups"].search(domain, order="id")
        xmlids = self._xmlid_map("res.groups", records.ids)
        keyed = {record.id: self._identity("res.groups", record, xmlids) for record in records}

        specs = []
        for record in records:
            implied_ids = record.implied_ids.ids
            implied_xmlids = self._xmlid_map("res.groups", implied_ids)
            implied = [
                keyed.get(group.id) or self._identity("res.groups", group, implied_xmlids)
                for group in record.implied_ids
            ]
            specs.append(
                GroupSpec(
                    name=record.name or "",
                    xmlid=keyed[record.id],
                    implied_ids=tuple(sorted(implied)),
                )
            )
        return tuple(specs), keyed

    def _read_acl(self, models: List[str] | None, group_keys: Dict[int, str]) -> List[AclSpec]:
        """Read ``ir.model.access`` lines that carry a group."""
        domain = []
        if models:
            domain = [("model_id.model", "in", list(models))]
        records = self.env["ir.model.access"].search(domain, order="id")
        access_xmlids = self._xmlid_map(
            "res.groups", [r.group_id.id for r in records if r.group_id]
        )
        specs = []
        for record in records:
            if not record.group_id:
                continue
            group = group_keys.get(record.group_id.id) or self._identity(
                "res.groups", record.group_id, access_xmlids
            )
            specs.append(
                AclSpec(
                    model=record.model_id.model,
                    group=group,
                    perm_read=record.perm_read,
                    perm_write=record.perm_write,
                    perm_create=record.perm_create,
                    perm_unlink=record.perm_unlink,
                )
            )
        return specs

    def _read_menus(self, group_keys: Dict[int, str]) -> List[MenuSpec]:
        """Read menus that are restricted to at least one group."""
        records = self.env["ir.ui.menu"].search([("groups_id", "!=", False)], order="id")
        menu_xmlids = self._xmlid_map("ir.ui.menu", records.ids)
        menu_group_xmlids = self._xmlid_map(
            "res.groups", [g.id for r in records for g in r.groups_id]
        )
        specs = []
        for record in records:
            groups = [
                group_keys.get(group.id) or self._identity("res.groups", group, menu_group_xmlids)
                for group in record.groups_id
            ]
            specs.append(
                MenuSpec(
                    menu=self._identity("ir.ui.menu", record, menu_xmlids),
                    groups=tuple(sorted(groups)),
                )
            )
        return specs

    def _read_roles(self, wanted: List[str] | None, group_keys: Dict[int, str]) -> List[RoleSpec]:
        """Read ``base_user_role`` roles, empty when that addon is absent."""
        Role = self.env.get("res.users.role")
        if Role is None:
            return []

        domain = []
        if wanted:
            ids = [self.env.ref(ref, raise_if_not_found=False).id for ref in wanted]
            domain = [("id", "in", [i for i in ids if i])]
        records = Role.search(domain, order="id")
        role_xmlids = self._xmlid_map("res.users.role", records.ids)
        role_group_xmlids = self._xmlid_map(
            "res.groups", [g.id for r in records for g in r.implied_ids]
        )

        specs = []
        for record in records:
            groups = [
                group_keys.get(group.id) or self._identity("res.groups", group, role_group_xmlids)
                for group in record.implied_ids
            ]
            specs.append(
                RoleSpec(
                    name=record.name or "",
                    xmlid=self._identity("res.users.role", record, role_xmlids),
                    groups=tuple(sorted(groups)),
                )
            )
        return specs

    def _read_locks(self) -> List[LockSpec]:
        """Read master-data locks.

        Empty until the enforcement module exists: a lock only counts once
        something enforces it, and nothing does yet.
        """
        return []

    @property
    def python_version(self) -> str:
        """Get running Python version."""
        return sys.version.split(" ")[0]
