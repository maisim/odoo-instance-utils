import sys
from .addons import Addons


class OdooInstance:

    def __init__(self, odoo=None, env=None):
        self.odoo = odoo
        self.env = env

        self.version = odoo.release.version
        self.major_version = odoo.release.major_version
        self.addons = Addons(addons_paths=odoo.tools.config["addons_path"])

        self.update_modules_status()

    def __str__(self):
        return f"Odoo {self.env.cr.dbname}"

    def update_modules_status(self):
        OdooInstanceModule = self.env["ir.module.module"]
        for module in OdooInstanceModule.search([("state", "=", "installed")]):
            self.addons[module.name].is_installed = True
            for dep in module.dependencies_id:
                self.addons[dep.name].is_dependency = True
                self.addons[module.name].dependencies.append(self.addons[dep.name])

    @property
    def python_version(self):
        """Get running Python version"""
        return sys.version.split(" ")[0]
