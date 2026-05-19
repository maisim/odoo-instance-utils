from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from odoo_instance_utils.spec import AddonSpec
from odoo_instance_utils.spec_loader import SpecLoadError, load_spec

if TYPE_CHECKING:
    pass


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
@click.argument("filepath", type=click.Path(exists=True), required=True)
def addons_lint(filepath):
    """Validate a foundry_addons.py file.

    FILEPATH must be a Python module exporting an ``addon_spec``
    of type ``AddonSpec``.
    """
    try:
        spec = load_spec(filepath)
    except SpecLoadError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"ok: {filepath} is valid")
    click.echo(f"  repos     = {len(spec.repos)}")
    click.echo(f"  selections = {len(spec.selections)}")


@addons_group.command("capture")
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default="foundry_addons.py",
    help="Output file path (default: foundry_addons.py)",
)
@click.pass_context
def addons_capture(ctx, output):
    """Generate a foundry_addons.py file from the live instance."""
    _require_odoo(ctx)
    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    instance = OdooInstance(env=env)  # type: ignore[operator]
    spec = AddonSpec.from_instance(instance)

    lines: list[str] = [
        '"""Addon specification captured from live instance."""',
        "",
        "from odoo_instance_utils.spec import AddonRepo, AddonSelection, AddonSpec",
        "",
        "addon_spec = AddonSpec(",
        "    repos=(",
    ]
    for repo in spec.repos:
        lines.append(f"        AddonRepo(name={repo.name!r}, url={repo.url!r},")
        lines.append(f"                 remote={repo.remote!r}, target={repo.target!r}),")
    lines.append("    ),")
    lines.append("    selections=(")
    for sel in spec.selections:
        lines.append(f"        AddonSelection(repo={sel.repo!r}, modules={sel.modules!r}),")
    lines.append("    ),")
    lines.append(")")

    content = "\n".join(lines) + "\n"
    Path(output).write_text(content)
    click.echo(f"foundry_addons.py written to {output}")
    click.echo(f"  {len(spec.repos)} repos, {sum(len(s.modules) for s in spec.selections)} modules")


@addons_group.command("verify")
@click.option(
    "-f",
    "--file",
    "filepath",
    type=click.Path(exists=True),
    default="foundry_addons.py",
    help="Path to foundry_addons.py (default: ./foundry_addons.py)",
)
@click.pass_context
def addons_verify(ctx, filepath):
    """Compare foundry_addons.py against the live instance."""
    _require_odoo(ctx)
    from odoo_instance_utils import OdooInstance

    env = ctx.obj["odoo_env"]
    instance = OdooInstance(env=env)  # type: ignore[operator]

    try:
        spec = load_spec(filepath)
    except SpecLoadError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)

    issues = spec.diff(instance)
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

        fs_ver = addon.version or ("(missing)" if not addon.path else "(no version)")
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
        elif fs_ver and db_ver and fs_ver != "-" and db_ver != "-" and fs_ver != db_ver:
            flag = " ~"  # version differs between fs and db
        elif not addon.path and addon.is_installed:
            flag = " ?"  # installed in DB but missing from filesystem

        line = (
            f"{addon.name:<{col['name']}}  "
            f"{state:<{col['state']}}  "
            f"{fs_ver:<{col['fs_ver']}}  "
            f"{db_ver:<{col['db_ver']}}  "
            f"{repo:<{col['repo']}}  "
            f"{ref}{flag}"
        )
        click.echo(line)
