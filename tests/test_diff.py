import json

from skillprint.cli import main
from skillprint.diff import diff
from skillprint.scan import scan

from test_scan import SKILL, write

HOOKS = {"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "node guard.js"}]}]}}


def test_identical_packs_have_no_changes(tmp_path):
    for v in ("v1", "v2"):
        write(tmp_path, f"{v}/skills/a/SKILL.md", SKILL.format(n="a", d="x"))
        write(tmp_path, f"{v}/scripts/run.sh", "#!/bin/sh\nrm -rf \"$TMP\"\n")
    d = diff(scan(tmp_path / "v1"), scan(tmp_path / "v2"))
    assert not d.changed


def test_added_hook_script_and_finding_are_reported(tmp_path):
    write(tmp_path, "v1/skills/a/SKILL.md", SKILL.format(n="a", d="x"))
    write(tmp_path, "v2/skills/a/SKILL.md", SKILL.format(n="a", d="x"))
    write(tmp_path, "v2/hooks/hooks.json", json.dumps(HOOKS))
    write(tmp_path, "v2/install.sh", "#!/bin/sh\ncurl -fsSL https://get.realtool.dev | sh\n")
    d = diff(scan(tmp_path / "v1"), scan(tmp_path / "v2"))
    assert (d.old.footprint, d.new.footprint) == ("light", "heavy")
    assert [h.command for h in d.hooks_added] == ["node guard.js"]
    assert d.scripts_added == ["install.sh"]
    assert {f.kind for f in d.findings_added} == {"pipe_to_shell"}
    assert d.domains_added == ["get.realtool.dev"]
    assert not (d.hooks_removed or d.findings_removed or d.scripts_removed)


def test_skills_added_removed_and_changed(tmp_path):
    write(tmp_path, "v1/skills/a/SKILL.md", SKILL.format(n="a", d="x"))
    write(tmp_path, "v1/skills/b/SKILL.md", SKILL.format(n="b", d="x"))
    write(tmp_path, "v2/skills/a/SKILL.md", SKILL.format(n="a", d="a much longer description now"))
    write(tmp_path, "v2/skills/c/SKILL.md", SKILL.format(n="c", d="x"))
    d = diff(scan(tmp_path / "v1"), scan(tmp_path / "v2"))
    assert [s.name for s in d.skills_added] == ["c"]
    assert [s.name for s in d.skills_removed] == ["b"]
    assert [c.name for c in d.skills_changed] == ["a"]


def test_moved_lines_are_not_new_findings(tmp_path):
    write(tmp_path, "v1/run.sh", "#!/bin/sh\nrm -rf \"$TMP\"\n")
    write(tmp_path, "v2/run.sh", "#!/bin/sh\nset -e\necho start\nrm -rf \"$TMP\"\n")
    d = diff(scan(tmp_path / "v1"), scan(tmp_path / "v2"))
    assert not d.findings_added and not d.findings_removed


def test_duplicate_findings_count_separately(tmp_path):
    write(tmp_path, "v1/run.sh", "#!/bin/sh\nrm -rf \"$TMP\"\n")
    write(tmp_path, "v2/run.sh", "#!/bin/sh\nrm -rf \"$TMP\"\nrm -rf \"$TMP\"\n")
    d = diff(scan(tmp_path / "v1"), scan(tmp_path / "v2"))
    assert len(d.findings_added) == 1 and d.findings_added[0].line == 3


def test_cli_diff_text_json_and_fail_on(tmp_path, capsys):
    write(tmp_path, "v1/skills/a/SKILL.md", SKILL.format(n="a", d="x"))
    write(tmp_path, "v2/skills/a/SKILL.md", SKILL.format(n="a", d="x"))
    write(tmp_path, "v2/hooks/hooks.json", json.dumps(HOOKS))
    old, new = str(tmp_path / "v1"), str(tmp_path / "v2")

    assert main(["diff", old, new]) == 0
    out = capsys.readouterr().out
    assert "LIGHT → HEAVY" in out and "+ hook" in out and "node guard.js" in out

    assert main(["diff", old, new, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["footprint"] == {"old": "light", "new": "heavy"}
    assert data["added"]["hooks"][0]["command"] == "node guard.js"

    assert main(["diff", old, new, "--fail-on", "heavy"]) == 1
    assert main(["diff", new, old, "--fail-on", "heavy"]) == 0


def test_cli_diff_bad_path(tmp_path, capsys):
    assert main(["diff", str(tmp_path / "nope"), str(tmp_path)]) == 2
    assert "is not a folder" in capsys.readouterr().err


def test_folder_named_diff_still_scans(tmp_path, monkeypatch, capsys):
    write(tmp_path, "diff/skills/a/SKILL.md", SKILL.format(n="a", d="x"))
    monkeypatch.chdir(tmp_path)
    assert main(["diff", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["skills_unique"] == 1
