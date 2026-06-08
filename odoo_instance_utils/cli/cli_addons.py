from __future__ import annotations

import sys
from pathlib import Path

import click

from odoo_instance_utils.addons_yaml import load_addons_yaml
from odoo_instance_utils.repos_yaml import load_repos_yaml, validate_repos_yaml
from odoo_instance_utils.verify import diff_addons_yaml


def _require_odoo(ctx: click.Context) -> None:
    """Raise :class:`click.UsageError` if the Odoo env is unavailable."""
    if "odoo_env" not in ctx.obj:
        raise click.UsageError(
            "This command requires an Odoo environment. "
            "Run inside an Odoo shell with the --env flag.",
            ctx,
        )


@click.group("addons")
def addons_group():
    """Addon management commands."""
    pass


@addons_group.command("lint")
@click.argument(
    "src_dir",
    type=click.Path(exists=True, file_okay=False),
    default="odoo/custom/src",
    required=False,
)
def addons_lint(src_dir):
    """Validate the committed addon source declaration.

    SRC_DIR must contain ``repos.yaml`` (and optionally ``addons.yaml``).
    Defaults to ``odoo/custom/src``.
    """
    src = Path(src_dir)
    repos_path = src / "repos.yaml"
    if not repos_path.is_file():
        click.echo(f"error: {repos_path} not found", err=True)
        sys.exit(1)

    try:
        stanzas = load_repos_yaml(repos_path)
        validate_repos_yaml(stanzas)
    except Exception as exc:
        click.echo(f"error: {repos_path}: {exc}", err=True)
        sys.exit(1)

    addons_path = src / "addons.yaml"
    declared = 0
    if addons_path.is_file():
        try:
            declared = len(load_addons_yaml(addons_path))
        except Exception as exc:
            click.echo(f"error: {addons_path}: {exc}", err=True)
            sys.exit(1)

    click.echo(f"ok: {src_dir} is valid")
    click.echo(f"  repos   = {len(stanzas)}")
    click.echo(f"  addons  = {declared}")


@addons_group.command("resolve")
@click.argument("module_name", required=True)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "flat"]),
    default="json",
    help="Output format (default: json)",
)
@click.pass_context
def addons_resolve(ctx, module_name, fmt):
    """Resolve a module and its transitive dependencies."""
    _require_odoo(ctx)
    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    instance = OdooInstance(env=env)  # type: ignore[operator]

    addon = instance.addons[module_name]
    deps = instance.addons.transitive_dependencies(module_name)

    by_repo: dict[str, list[str]] = {}
    missing: list[str] = []
    for dep_name in sorted(deps):
        dep = instance.addons[dep_name]
        if dep.repo_name:
            by_repo.setdefault(dep.repo_name, []).append(dep_name)
        else:
            missing.append(dep_name)

    if fmt == "json":
        import json

        click.echo(
            json.dumps(
                {
                    "module": module_name,
                    "repo": addon.repo_name or None,
                    "dependencies": sorted(deps),
                    "by_repo": by_repo,
                    "missing": missing,
                }
            )
        )
    else:
        click.echo(f"{module_name} ({addon.repo_name or 'no repo'})")
        for dep in sorted(deps):
            dep_addon = instance.addons[dep]
            click.echo(f"  {dep} ({dep_addon.repo_name or 'no repo'})")


@addons_group.command("capture")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["files", "full"]),
    default="files",
    help="files=write repos.yaml+addons.yaml+repos.lock.yaml, full=single JSON blob",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(file_okay=False),
    default=None,
    help="Output directory for 'files' format (default: odoo/custom/src)",
)
@click.pass_context
def addons_capture(ctx, fmt, output):
    """Capture the addon source declaration from the live instance."""
    _require_odoo(ctx)
    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    instance = OdooInstance(env=env)  # type: ignore[operator]
    addons = instance.addons

    if fmt == "full":
        import json

        click.echo(
            json.dumps(
                {
                    "repos_yaml": addons.generate_repos_yaml(),
                    "addons_yaml": addons.generate_addons_yaml(),
                    "repos_lock": addons.generate_repos_lock(),
                    "dependencies": {
                        "pip": addons.python_dependencies,
                        "apt": addons.apt_dependencies,
                        "npm": addons.npm_dependencies,
                        "gem": addons.gem_dependencies,
                    },
                }
            )
        )
        return

    out_dir = Path(output) if output else Path("odoo/custom/src")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "repos.yaml").write_text(addons.generate_repos_yaml())
    (out_dir / "addons.yaml").write_text(addons.generate_addons_yaml())
    (out_dir / "repos.lock.yaml").write_text(addons.generate_repos_lock())
    click.echo(f"wrote repos.yaml, addons.yaml, repos.lock.yaml to {out_dir}")


@addons_group.command("verify")
@click.option(
    "-f",
    "--file",
    "filepath",
    type=click.Path(exists=True),
    default="odoo/custom/src/addons.yaml",
    help="Path to addons.yaml (default: ./odoo/custom/src/addons.yaml)",
)
@click.pass_context
def addons_verify(ctx, filepath):
    """Compare a declared addons.yaml against the live instance."""
    _require_odoo(ctx)
    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    instance = OdooInstance(env=env)  # type: ignore[operator]

    declared = load_addons_yaml(filepath)
    issues = diff_addons_yaml(declared, instance.addons)
    if not issues:
        click.echo(f"ok: {filepath} matches the live instance")
        return

    for issue in issues:
        click.echo(f"  - {issue}")
    click.echo(f"{len(issues)} discrepancy(ies) found")
    sys.exit(1)


@addons_group.command("install")
@click.argument("addons_names", required=True, type=str)
@click.pass_context
def addons_install(ctx, addons_names):
    """Install addons, separated by comma."""
    _require_odoo(ctx)
    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    addons_names = [addon_name.strip() for addon_name in addons_names.split(",")]
    instance = OdooInstance(env=env)  # type: ignore[operator]
    installed_addons_names = instance.install_addons(addons_names)
    click.echo(f"Installed addons: {', '.join(installed_addons_names)}")


@addons_group.command("list")
@click.option(
    "--minimize-list",
    is_flag=True,
    default=False,
    help="Minimize the list of addons (to install) with the game of dependencies",
)
@click.option(
    "--needs-upgrade",
    is_flag=True,
    default=False,
    help="Only show addons that need an upgrade",
)
@click.option("--format", type=click.Choice(["flat", "json", "csv"]), default="flat")
@click.pass_context
def list_addons(ctx, minimize_list, needs_upgrade, format):
    """List addons and their status."""
    _require_odoo(ctx)
    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    odoo_instance = OdooInstance(env=env)  # type: ignore[operator]
    addons = odoo_instance.addons(
        installed=ctx.obj["installed_addons_only"],
        minimize_list=minimize_list,
        needs_upgrade=True if needs_upgrade else None,
    )
    if format == "json":
        import json

        click.echo(json.dumps(list(addons.to_dict())))
        return
    elif format == "csv":
        for addon in addons:
            click.echo(f"{addon.name},{addon.manifest.get('name', '')}")
    else:
        click.echo(",".join(addon.name for addon in addons))


@addons_group.command("why")
@click.argument("addon_name", required=True, type=str)
@click.pass_context
def addon_why(ctx, addon_name):
    """List modules that depend on the given module."""
    _require_odoo(ctx)
    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    odoo_instance = OdooInstance(env=env)  # type: ignore[operator]
    addons = odoo_instance.addons(installed=ctx.obj["installed_addons_only"])
    addon = addons[addon_name]
    addons_that_depend_on = ", ".join([a.name for a in addon.is_dependency_of])
    click.echo(f"Addons that depend on {addon_name}: {addons_that_depend_on}")


@addons_group.command("python-dependencies")
@click.pass_context
def addons_python_dependencies(ctx):
    """List python dependencies for the instance addons."""
    _require_odoo(ctx)
    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    odoo_instance = OdooInstance(env=env)  # type: ignore[operator]
    addons = odoo_instance.addons(installed=ctx.obj["installed_addons_only"])
    click.echo(", ".join(addons.python_dependencies))


@addons_group.command("generate-addons-yaml")
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    required=False,
    help="Output file name",
)
@click.pass_context
def generate_addons_yaml(ctx, output=None):
    """Generate an addons.yml file for Doodba."""
    _require_odoo(ctx)
    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    odoo_instance = OdooInstance(env=env)  # type: ignore[operator]
    addons = odoo_instance.addons(
        installed=ctx.obj["installed_addons_only"], include_auto_installed_addons=False
    )
    addons_yaml_content = addons.generate_addons_yaml()
    if not output:
        click.echo(addons_yaml_content)
        return
    with open(output, "w") as file:
        file.write(addons_yaml_content)
    click.echo(f"Addons YAML file generated at {output}")


@addons_group.command("generate-repos-yaml")
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    required=False,
    help="Output file for repos.yml",
)
@click.option(
    "--use-head",
    is_flag=True,
    default=False,
    help="Pin repos to current HEAD commit instead of branch name",
)
@click.pass_context
def generate_repos_yaml(ctx, output=None, use_head=False):
    """Generate repos.yml file for git-aggregator."""
    _require_odoo(ctx)
    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    odoo_instance = OdooInstance(env=env)  # type: ignore[operator]
    addons = odoo_instance.addons(installed=ctx.obj["installed_addons_only"])
    repos_yaml_content = addons.generate_repos_yaml(use_head=use_head)
    if not output:
        click.echo(repos_yaml_content)
        return
    with open(output, "w") as file:
        file.write(repos_yaml_content)
    click.echo(f"Repos YAML file generated at {output}")


@addons_group.command("generate-repos-lock")
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    required=False,
    help="Output file for repos.lock.yml (default: stdout)",
)
@click.pass_context
def generate_repos_lock(ctx, output=None):
    """Generate repos.lock.yml with pinned SHAs for reproducible builds."""
    _require_odoo(ctx)
    from pathlib import Path

    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    odoo_instance = OdooInstance(env=env)  # type: ignore[operator]
    addons = odoo_instance.addons(installed=ctx.obj["installed_addons_only"])
    content = addons.generate_repos_lock()
    if not output:
        click.echo(content)
        return
    Path(output).write_text(content)
    click.echo(f"repos.lock.yml written to {output}")


@addons_group.command("audit")
@click.pass_context
def audit_addons(ctx):
    """Audit installed addons: version mismatches, missing from filesystem, pending upgrades."""
    _require_odoo(ctx)
    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    odoo_instance = OdooInstance(env=env)  # type: ignore[operator]
    # All addons: installed in DB + present on filesystem
    all_addons = odoo_instance.addons(installed=None)

    # Column widths
    col = {"name": 35, "state": 12, "fs_ver": 18, "db_ver": 18, "repo": 28, "ref": 12}
    header = (
        f"{'ADDON':<{col['name']}}  "
        f"{'STATE':<{col['state']}}  "
        f"{'FS VERSION':<{col['fs_ver']}}  "
        f"{'DB VERSION':<{col['db_ver']}}  "
        f"{'REPO':<{col['repo']}}  "
        f"REF"
    )
    click.echo(header)
    click.echo("-" * (sum(col.values()) + len(col) * 2))

    for addon in sorted(all_addons, key=lambda a: a.name):
        if not addon.db_state and not addon.is_installed:
            continue  # filesystem-only, never touched by Odoo

        fs_ver = addon.fs_version or ("(missing)" if not addon.path else "(no version)")
        db_ver = addon.db_version or "-"
        state = addon.db_state or "fs-only"
        repo = addon.repo_name or "-"
        ref = (
            (addon.git_branch or addon.git_head[:8] if addon.git_head else "-")
            if addon.git_repo
            else "-"
        )

        # Highlight mismatches
        flag = ""
        if addon.needs_upgrade:
            flag = " !"
        elif addon.version_mismatch:
            flag = " ~"  # version differs between fs and db
        elif addon.missing_from_filesystem:
            flag = " ?"  # installed in DB but missing from filesystem
        elif addon.conflicting_path:
            flag = " #"  # same addon name found at another path

        line = (
            f"{addon.name:<{col['name']}}  "
            f"{state:<{col['state']}}  "
            f"{fs_ver:<{col['fs_ver']}}  "
            f"{db_ver:<{col['db_ver']}}  "
            f"{repo:<{col['repo']}}  "
            f"{ref}{flag}"
        )
        click.echo(line)
