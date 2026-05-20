# odoo-instance-utils

> **Alpha stage — not production-ready.** This project is under active development.
> The API, CLI interface, and behavior may change without notice between releases.
> Use at your own risk; no backward compatibility guarantees until 1.0.

CLI utilities for auditing and managing Odoo instances.

### Installation

```bash
pip install odoo-instance-utils[cli]
```

### Usage

```
Usage: odoo-instance [OPTIONS] COMMAND [ARGS]...

Options:
  -c, --config FILE        Odoo configuration file
  -d, --database TEXT      Database name
  --log-level TEXT         Logging level (debug, info, warn, error)
  --rollback               Rollback the transaction
  --help                   Show this message and exit

Commands:
  addon-why                   List modules that depend on the given module
  addons-python-dependencies  List python dependencies for the instance addons
  generate-repos-yaml         Generate repos.yml for git-aggregator
  list-addons                 List addons and their status
```

### Development

```bash
git clone https://github.com/maisim/odoo-instance-utils
cd odoo-instance-utils
uv sync
pre-commit install
```

### Releasing

This project uses [commitizen](https://commitizen-tools.github.io/commitizen/) with
[Conventional Commits](https://www.conventionalcommits.org/) and
[setuptools-scm](https://github.com/pypa/setuptools-scm) for versioning.

Commits must follow the conventional format:

```
feat: add addon export command
fix: handle missing manifest in list-addons
refactor: extract addon resolution logic
```

To create a release:

```bash
cz bump                    # reads commits → bumps version → creates tag + CHANGELOG
git push --follow-tags
```

The GitHub Actions workflow then builds and publishes the matching version to PyPI.

### License

MIT — see `LICENSE`.
