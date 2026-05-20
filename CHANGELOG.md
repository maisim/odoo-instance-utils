## v0.4.3 (2026-05-20)

### Fix

- update Python package configuration and pre-commit hooks

## v0.4.2 (2026-05-19)

## v0.4.1 (2026-05-19)

## v0.4.0 (2026-05-19)

### Feat

- **capture**: add --host mode for remote capture via pyinfra
- add declarative addon spec types + CLI lint/capture/verify

### Fix

- remove pyinfra dependency, simplify capture to local-only
- make CLI importable without the odoo module

## v0.3.0 (2026-04-22)

### Feat

- add audit command, db_version/db_state tracking, --use-head on repos-yaml

## v0.2.0 (2026-04-22)

### Feat

- add filters list command
- add needs_upgrade filter to list addons pending upgrade

### Fix

- addons not in addons_path (e.g. base) missing from list
- allow 0.x versioning in semantic-release (allow_zero_version=true)
- resolve all mypy type errors
- remove unused ValidationError import, fix addons_paths type annotation
- add missing python_version attribute to OdooInstance
- security and bug fixes in addons.py

### Refactor

- move cli/ into odoo_instance_utils/, remove root __init__.py

## v0.1.0 (2025-05-07)
