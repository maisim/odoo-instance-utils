from .exceptions import ConflictError, IntegrityError

# OdooInstance and Addons are imported lazily — they require the `odoo`
# module which is only available inside an Odoo shell.


def __getattr__(name: str) -> object:
    if name == "OdooInstance":
        from .odoo_instance import OdooInstance as _OdooInstance

        return _OdooInstance
    if name == "Addon":
        from .addons import Addon as _Addon

        return _Addon
    if name == "Addons":
        from .addons import Addons as _Addons

        return _Addons
    raise AttributeError(name)


__all__ = [
    "Addon",
    "Addons",
    "ConflictError",
    "IntegrityError",
    "OdooInstance",
]
