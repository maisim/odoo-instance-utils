import sys
import json

import odoo
from odoo.exceptions import ValidationError
import logging
from .addons import Addons

_logger = logging.getLogger(__name__)


class OdooInstance:

    def __init__(self, odoo=odoo, env=None):
        self.env = env

        self.version = odoo.release.version
        self.major_version = odoo.release.major_version
        self.addons = Addons(addons_paths=odoo.tools.config["addons_path"])

        self.update_addons_status()

    def __str__(self):
        return f"Odoo {self.env.cr.dbname}"

    def update_addons_status(self):
        OdooInstanceModule = self.env["ir.module.module"]
        for module in OdooInstanceModule.search([("state", "=", "installed")]):
            self.addons[module.name].is_installed = True
            for dep in module.dependencies_id:
                self.addons[dep.name].is_dependency_of.append(self.addons[module.name])
                self.addons[module.name].dependencies.append(self.addons[dep.name])


    def install_addons(self, addons_names):
        OdooInstanceModule = self.env["ir.module.module"]
        addons_to_install = OdooInstanceModule.search([("name", "in", addons_names), ("state", "!=", "installed")])
        addons_to_install.button_immediate_install()

        return addons_to_install.mapped("name")

    def dump_filters(self, ids):
        ids = [int(id) for id in ids]

        filters = self.env["ir.filters"].search([("id", "in", ids)])

        # Return filters in JSON format to be restored using the restore_filters method
        dump = filters.read(fields=["name", "model_id", "domain", "user_id", "context", "action_id", "sort", "active", "is_default", "create_uid"], load=None)

        for filter_data in dump:
            # Remove id from filter_data
            _ = filter_data.pop("id")


        return json.dumps(dump)   

    def restore_filters(self, filters_json):
        filters = json.loads(filters_json)

        # Log the db name and the Python version
        _logger.info("Restoring filters on database '%s' using Python %s", self.env.cr.dbname, self.python_version)

        # Log current user
        _logger.info("Current user: %s (id: %s)", self.env.user.name, self.env.user.id)

        for filter_data in filters:
            # Delete the filter if it already exists
            existing_filters = self.env["ir.filters"].search([
                ("name", "=", filter_data["name"]),
                ("model_id", "=", filter_data["model_id"]),
                ("user_id", "=", filter_data["user_id"]),
            ])

            # TODO: Test the filter domain before creating it
            # Make a query with the new filter to test the filter
#           _logger.debug(f"Testing filter {filter_data['name']} on model {filter_data['model_id']} with domain {filter_data['domain']}")
#           try:
#               self.env[filter_data["model_id"]].search([filter_data["domain"]])
#           except Exception as e:
#               _logger.warning("Error testing filter domain: %s. Skipping", e)
#               continue

            _logger.info("Found %s existing filters with name '%s' and model '%s'", len(existing_filters), filter_data["name"], filter_data["model_id"])
            existing_filters.unlink()

            _logger.info("Creating filter '%s' on model '%s'", filter_data["name"], filter_data["model_id"])

            filter_owner = self.env["res.users"].browse(filter_data.pop("create_uid"))

            filter_data["create_uid"] = filter_owner.id

            # Create the filter
            filter_id = self.env["ir.filters"].with_user(filter_owner).create(filter_data).id

            _logger.info("Created filter '%s' with ID %s", filter_data["name"], filter_id)
            _logger.debug("Filter data: %s", filter_data)

    def dump_exports(self, ids):
        ids = [int(id) for id in ids]

        exports = self.env["ir.exports"].search([("id", "in", ids)])

        # Return exports in JSON format to be restored using the restore_exports method
        dump = exports.read(fields=["name", "resource", "display_name", "create_uid"], load=None)

        for export in dump:

            export_fields = self.env["ir.exports.line"].search([("export_id", "=", export["id"])], order="sequence").read(
                fields=["name", "sequence", "create_uid"],
                load=None
            )

            # Remove id from export_fields
            _ = [export_field.pop("id") for export_field in export_fields]

            export["export_fields"] = export_fields

        # remove id from exports
        _ = [export.pop("id") for export in dump]

        return json.dumps(dump)
        

    def restore_exports(self, exports):
        exports = json.loads(exports)

        # Log the db name and the python version
        _logger.info("Restoring exports on database '%s' using Python %s", self.env.cr.dbname, self.python_version)

        # Log current user
        _logger.info("Current user: %s (id: %s)", self.env.user.name, self.env.user.id)
    
        for export in exports:
            # Delete the export if it already exists
            existing_exports =  self.env["ir.exports"].search([
                ("name", "=", export["name"]),
                ("resource", "=", export["resource"]),
                ("create_uid.id", "=", export["create_uid"])
            ])

            _logger.info("Found %s existing exports with name '%s' and resource '%s'", len(existing_exports), export["name"], export["resource"])
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
                # Check if 'name' is present
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


    @property
    def python_version(self):
        """Get running Python version"""
        return sys.version.split(" ")[0]
