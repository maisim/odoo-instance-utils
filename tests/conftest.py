import sys
from unittest.mock import MagicMock

# Mock the odoo module and its submodules before any test imports odoo_instance_utils
odoo_mock = MagicMock()
odoo_mock.release.version = "16.0"
odoo_mock.release.major_version = 16
odoo_mock.tools.config = {"addons_path": ""}

sys.modules["odoo"] = odoo_mock
sys.modules["odoo.release"] = odoo_mock.release
sys.modules["odoo.tools"] = odoo_mock.tools
sys.modules["odoo.exceptions"] = MagicMock()
sys.modules["odoo.api"] = MagicMock()
