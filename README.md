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
  --installed-addons-only / --include-all-addons
  --help                          Show this message and exit.

Commands:
  addons        Addon management commands.
  exports       Export management commands.
  filters       Filter management commands.
  security      Access-rights configuration commands.
  translations  Translation management commands.
  view          View management commands (requires click-odoo).
```

#### Addons

```
odoo-instance addons lint           Validate addons.yaml + repos.yaml
odoo-instance addons capture        Capture addon state from a remote instance
odoo-instance addons verify         Compare addons.yaml against the live DB
odoo-instance addons install <list> Install addons (comma-separated)
odoo-instance addons list           List addons and their status
odoo-instance addons why <module>   Show modules that depend on a module
odoo-instance addons resolve <m>    Resolve transitive dependencies
odoo-instance addons audit          Audit version mismatches, uncommitted changes
odoo-instance addons python-deps    List Python dependencies for instance addons
odoo-instance addons generate-addons-yaml   Generate addons.yaml for Doodba
odoo-instance addons generate-repos-yaml    Generate repos.yaml for git-aggregator
odoo-instance addons generate-repos-lock    Generate repos.lock.yaml with pinned SHAs
```

#### Security

```
odoo-instance security lint [CONFIG_DIR]    Validate the committed configuration (offline)
odoo-instance security capture [-o DIR]     Capture the managed subset from the live instance
odoo-instance security snapshot [-o FILE]   Capture the complete state from the live instance
```

Describes the access rights a project manages as five JSON files, one per
object, so they can be reviewed, versioned and compared:

```
odoo/custom/src/security/
    groups.json     groups the project owns or references
    acl.json        ir.model.access lines
    menus.json      menu visibility granted to groups
    roles.json      base_user_role roles and the groups they carry
    locks.json      master-data write locks
```

`lint` runs with no Odoo and no click-odoo: it checks the schema, the shape
of every group reference, and the cross-file consistency. Whether a group or
model actually exists needs a live instance, and is left to a check against
one.

A group or role is identified either by a `slug`, a local name for something
the project owns, or by an `xmlid`, the fully-qualified name of something
another module owns — exactly one of the two. Capturing yields xmlids, since
that is what a running database holds; authoring yields slugs for what is
about to be created. Both forms live in the same file, which is what makes
capture output directly editable into a policy.

`capture` is scoped by design (`--models`, `--groups`, `--roles`): a real
database carries thousands of ACL lines shipped by Odoo and the OCA addons,
which are not the project's to assert. `snapshot` records everything instead
and is asserted by no one — it exists to show what a module update moved, so
it is committed and compared rather than applied.

Each file is rendered one record per line and sorted by identity, so repeated
reads are byte-identical and a diff reads record by record.

#### Exports

```
odoo-instance exports dump <ids>    Dump exports as JSON
odoo-instance exports restore <data> Restore exports from JSON
```

#### Filters

```
odoo-instance filters list          List all filters
odoo-instance filters dump <ids>    Dump filters as JSON
odoo-instance filters restore <data> Restore filters from JSON
```

#### View

```
odoo-instance view export <module>  Export views from a module
odoo-instance view diff <module>    Diff exported views against the database
```

#### Translations

```
odoo-instance translations load <file.py> [--force]
```

Load custom translation overrides from a Python file into an Odoo instance
(Odoo ≥16, uses `TranslationImporter` / jsonb).

The file must define a `TranslationOverride` dataclass and a module-level
`translations` dict keyed by language code:

```python
# odoo/custom/configuration/translations/fr_FR.py
from dataclasses import dataclass

@dataclass(frozen=True)
class TranslationOverride:
    type: str       # model, code, selection, view
    name: str       # "model,field" or module name or XML-ID
    src: str        # original English text
    value: str      # translated text
    res_id: int = 0 # default 0; resolved via XML-ID for view types

translations = {
    "fr_FR": [
        TranslationOverride(
            type="code", name="base", src="Individual", value="Personne",
        ),
        TranslationOverride(
            type="code", name="base", src="Individuals", value="Personnes",
        ),
    ],
}
```

The command generates temporary PO files (one per language) and imports them
via Odoo's `TranslationImporter`, which writes directly to the jsonb
translation columns on each model's database table. All overrides are created
with `module="__custom__"` so they survive module upgrades.

Use `--force` to overwrite existing translations instead of merging.

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
