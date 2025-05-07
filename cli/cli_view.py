import json
import click
import click_odoo
import sys
from odoo_instance_utils.views import export, diff 

@click.group("view")
def view_group():
    """Odoo view utilities."""
    pass

@view_group.command("export")
@click.argument("xmlid")
@click.pass_context
def export_view(ctx, xmlid):
    """Export an Odoo view to JSON via its external id (xmlid)"""
    env = ctx.obj["odoo_env"]
    view_data = export(env, xmlid)
    if not view_data:
        click.echo(json.dumps({"error": f"View with xmlid '{xmlid}' not found."}, indent=2))
        sys.exit(1)
    click.echo(json.dumps(view_data, indent=2))
    sys.exit(0)

@view_group.command("diff")
@click.option("--verbose", is_flag=True, help="Print detailed diff output")
@click.argument("xmlid")
@click.argument("filepath", type=click.Path(exists=True))
@click.pass_context
def diff_view(ctx, xmlid, filepath, verbose):
    """Compare an Odoo view with a local file via its external id (xmlid)"""
    env = ctx.obj["odoo_env"]
    result = diff(env, xmlid, filepath)
    if not result.get("found"):
        click.echo(f"Error: View with xmlid '{xmlid}' not found.")
        sys.exit(2)
    if not result["match"]:
        if verbose:
            click.echo(result["diff"])
        else:
            click.echo(f"{xmlid}: Mismatch detected.")
        sys.exit(1)
    else:
        click.echo(f"{xmlid}: Match")
        sys.exit(0)
