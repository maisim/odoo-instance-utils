from collections import OrderedDict

import pytest

from odoo_instance_utils.addons import Addon, Addons
from odoo_instance_utils.addons_yaml import (
    dump_addons_yaml,
    parse_addons_yaml,
)
from odoo_instance_utils.lock import (
    VaultRef,
    read_vault_refs,
    rewrite_to_vault,
)
from odoo_instance_utils.repos_yaml import (
    RepoStanza,
    dump_repos_yaml,
    parse_repos_yaml,
    validate_repos_yaml,
)
from odoo_instance_utils.vault import render_tag, resolve_ref_sha
from odoo_instance_utils.verify import diff_addons_yaml

REPOS_YAML = """\
./odoo:
  defaults:
    depth: 1
  remotes:
    ocb: https://github.com/OCA/OCB.git
    odoo: https://github.com/odoo/odoo.git
  target: ocb 16.0
  merges:
  - ocb 16.0
./web:
  remotes:
    OCA: https://github.com/OCA/web.git
    maisim: https://github.com/maisim/web.git
  target: OCA 16.0
  merges:
  - OCA 16.0
  - maisim refs/pull/12/head
"""


class TestReposYaml:
    def test_roundtrip_preserves_structure(self):
        stanzas = parse_repos_yaml(REPOS_YAML)
        assert [s.path for s in stanzas] == ["./odoo", "./web"]
        odoo = stanzas[0]
        assert odoo.defaults == {"depth": 1}
        assert odoo.remotes["odoo"] == "https://github.com/odoo/odoo.git"
        assert odoo.target == "ocb 16.0"
        assert odoo.merges == ["ocb 16.0"]
        web = stanzas[1]
        assert web.merges == ["OCA 16.0", "maisim refs/pull/12/head"]
        # round-trip is stable
        assert parse_repos_yaml(dump_repos_yaml(stanzas)) == stanzas

    def test_unknown_keys_preserved(self):
        text = (
            "./web:\n"
            "  remotes:\n"
            "    OCA: https://github.com/OCA/web.git\n"
            "  target: OCA 16.0\n"
            "  merges:\n"
            "  - OCA 16.0\n"
            "  shell_command_after: echo hi\n"
        )
        stanzas = parse_repos_yaml(text)
        assert stanzas[0].extra == {"shell_command_after": "echo hi"}
        assert "shell_command_after: echo hi" in dump_repos_yaml(stanzas)

    def test_validate_local_rejects_bad_merge_remote(self):
        stanzas = [
            RepoStanza(
                path="./web",
                remotes={"OCA": "https://github.com/OCA/web.git"},
                target="OCA 16.0",
                merges=["nope 16.0"],
            )
        ]
        with pytest.raises(ValueError):
            validate_repos_yaml(stanzas)


class TestAddonsYaml:
    def test_parse_list_and_star(self):
        text = "server-tools:\n- auditlog\n- base_technical_features\nweb: '*'\n"
        parsed = parse_addons_yaml(text)
        assert parsed["server-tools"] == ["auditlog", "base_technical_features"]
        assert parsed["web"] == ["*"]

    def test_dump_star_as_scalar(self):
        out = dump_addons_yaml(OrderedDict([("web", ["*"])]))
        assert "web: '*'" in out or 'web: "*"' in out

    def test_roundtrip(self):
        data = OrderedDict([("server-tools", ["auditlog"]), ("web", ["*"])])
        assert parse_addons_yaml(dump_addons_yaml(data)) == data


class TestVaultAndLock:
    def test_render_tag(self):
        assert render_tag("{odoo_version}-{sha}", odoo_version="16.0", sha="abc") == "16.0-abc"

    def test_resolve_full_sha_passthrough(self):
        sha = "a" * 40
        assert resolve_ref_sha("https://example.invalid/repo.git", sha) == sha

    def test_rewrite_to_vault_and_back(self):
        source = parse_repos_yaml(REPOS_YAML)
        refs = {
            "./odoo": VaultRef(
                "./odoo", "https://gl/acme-locked-targets/OCB.git", "16.0-" + "a" * 40, "a" * 40
            ),
            "./web": VaultRef(
                "./web", "https://gl/acme-locked-targets/web.git", "16.0-" + "b" * 40, "b" * 40
            ),
        }
        locked = rewrite_to_vault(source, refs)
        assert locked[0].remotes == {"vault": "https://gl/acme-locked-targets/OCB.git"}
        assert locked[0].target == "vault 16.0-" + "a" * 40
        assert locked[0].merges == ["vault 16.0-" + "a" * 40]
        assert locked[0].defaults == {"depth": 1}
        recovered = read_vault_refs(locked)
        assert recovered["./web"].sha == "b" * 40
        assert recovered["./web"].vault_url == "https://gl/acme-locked-targets/web.git"

    def test_rewrite_to_vault_missing_ref(self):
        source = parse_repos_yaml(REPOS_YAML)
        with pytest.raises(KeyError):
            rewrite_to_vault(source, {})


class TestVerify:
    def _addon(self, name, repo_url):
        return Addon(name=name, path=f"/fake/{name}", git_repo=repo_url)

    def test_diff_reports_missing_and_extra(self):
        addons = Addons(
            addons=[
                self._addon("auditlog", "https://github.com/OCA/server-tools.git"),
                self._addon("extra_mod", "https://github.com/OCA/web.git"),
            ]
        )
        declared = {
            "server-tools": ["auditlog", "missing_mod"],
            "web": ["*"],
        }
        issues = diff_addons_yaml(declared, addons)
        assert "server-tools/missing_mod: declared but not found on disk" in issues
        assert all("auditlog" not in i for i in issues)
        # web is "*" and has a runtime module -> no issue
        assert all(not i.startswith("web") for i in issues)

    def test_diff_clean(self):
        addons = Addons(addons=[self._addon("auditlog", "https://github.com/OCA/server-tools.git")])
        declared = {"server-tools": ["auditlog"]}
        assert diff_addons_yaml(declared, addons) == []
