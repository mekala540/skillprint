"""Command line: skillprint <path-or-git-url> [--json] [--badge] [--details]
              skillprint diff <old> <new> [--json] [--fail-on LEVEL]"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import quote

from . import __version__
from pathlib import Path

from .diff import Diff, diff
from .scan import scan, is_claude_home, Report, HOOK_EVENTS_EVERY_ACTION
from .insights import analyse, redactor, Insights
from . import html as html_report

LABELS = {
    "shell_exec": "runs shell commands",
    "pipe_to_shell": "pipes a download into a shell",
    "destructive": "destructive commands (rm -rf, force push)",
    "secrets_access": "reads credential files",
    "env_secrets": "reads secret env vars",
    "auto_install": "installs packages",
    "hidden_unicode": "hidden Unicode characters",
}
COLORS = {"none": "brightgreen", "light": "green", "moderate": "blue", "heavy": "lightgrey"}
ORDER = ["none", "light", "moderate", "heavy"]
# Names used before 0.1.2, still accepted by --fail-on so existing CI configs keep working.
OLD_NAMES = {"low": "light", "medium": "moderate", "high": "heavy"}


def _fmt(n: int) -> str:
    return f"{n:,}"


TRY_URL = "To check a pack before you install it: skillprint https://github.com/OWNER/REPO"


def _tilde(path: str) -> str:
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path == home or path.startswith(home + os.sep) else path


def missing_message(target: str) -> str:
    """Point people at what to run instead. The most common miss is ~/.claude/skills, which
    Claude Code only creates once you add a personal skill."""
    p = Path(os.path.abspath(os.path.expanduser(target)))
    home = next((a for a in [p, *p.parents] if a.name == ".claude"), None)
    if home is not None and not home.is_dir():
        return (f"{_tilde(str(home))} doesn't exist: Claude Code creates it the first time it runs.\n"
                f"{TRY_URL}")
    if home is not None:
        return (f"{_tilde(str(p))} doesn't exist, so nothing is installed there.\n"
                f"To see everything Claude Code loads (your skills, plugins and hooks): skillprint {_tilde(str(home))}")
    return f"{target} is not a folder. Give a skill pack folder or a git URL."


def badge(r: Report) -> str:
    biggest = max((len(v) for v in r.hooks_by_config().values()), default=0)
    hooks = "1 hook" if biggest == 1 else f"{biggest} hooks"
    msg = f"{r.footprint} footprint · {_fmt(r.upfront_tokens)} tokens · {hooks}"
    url = f"https://img.shields.io/badge/skillprint-{quote(msg.replace('-', '--'))}-{COLORS[r.footprint]}"
    return f"[![skillprint]({url})](https://github.com/mekala540/skillprint)"


def text_report(r: Report, details: bool, ins: Insights | None = None, hide=lambda t: t) -> str:
    ins = ins or analyse(r)
    lst = ins.listing
    out = []
    out.append(f"skillprint {__version__} · {hide(_tilde(r.root))}")
    out.append("")
    out.append("  " + ins.headline)
    out.append("")
    out.append(f"  Footprint            {r.footprint.upper()}")
    if r.layout != "pack":
        extra = f"  (+{_fmt(ins.not_loaded)} SKILL.md files Claude Code never loads)" if ins.not_loaded else ""
        out.append(f"  Agent can use        {_fmt(lst.skills)} skills{extra}")
    else:
        copies = f" ({_fmt(r.skill_files)} SKILL.md files incl. copies)" if r.skill_files != len(r.skills) else ""
        out.append(f"  Skills               {_fmt(len(r.skills))}{copies}")
    shown = f"{_fmt(lst.described)} with descriptions, {_fmt(lst.names_only)} names only" if lst.names_only \
        else "all with descriptions"
    out.append(f"  Skill listing        ≈{_fmt(lst.tokens)} tokens every turn in Claude Code ({shown};"
               f" budget ≈{_fmt(lst.budget)} for a {lst.context_window // 1000}k-token model)")
    if lst.full_tokens > lst.tokens:
        out.append(f"                       descriptions shipped: ≈{_fmt(lst.full_tokens)} tokens, most cut by the budget")
    out.append(f"  Loaded when used     ≈{_fmt(r.on_use_tokens)} tokens (all skill bodies)")
    out.append(f"  Scripts              {_fmt(len(r.scripts))}")
    groups = r.hooks_by_config()
    if not groups:
        out.append("  Auto-run hooks       0")
    for i, (src, hs) in enumerate(groups.items()):
        every = sum(1 for h in hs if h.event.lower() in HOOK_EVENTS_EVERY_ACTION)
        events = ", ".join(sorted({h.event for h in hs}))
        head = "  Auto-run hooks       " if i == 0 else "                       "
        tail = f", {every} on every prompt or tool call" if every else ""
        out.append(f"{head}{len(hs):>3} in {src}{tail}")
        out.append(f"                         [{events}]")
    counts = r.finding_counts()
    out.append("")
    out.append("  What its code can do (scripts, hook commands, code blocks in skills):")
    if not counts:
        out.append("    nothing flagged")
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        out.append(f"    {v:>5}  {LABELS.get(k, k)}")
    if r.network_domains:
        top = ", ".join(list(dict(sorted(r.network_domains.items(), key=lambda kv: -kv[1])))[:6])
        out.append(f"    domains: {hide(top)}")
    ignored = sum(r.doc_mentions.values())
    if ignored:
        out.append(f"  ({_fmt(ignored)} pattern matches in docs and prose ignored: they describe, they don't run)")
    if r.test_files:
        out.append(f"  ({_fmt(r.test_files)} test file{'s' if r.test_files != 1 else ''} skipped: they don't ship to the agent)")
    if r.inactive_scripts or r.inactive_findings or r.inactive_hooks:
        out.append(f"  ({_fmt(len(r.inactive_scripts))} scripts, {_fmt(len(r.inactive_hooks))} hooks and "
                   f"{_fmt(len(r.inactive_findings))} flagged lines sit in folders the agent never loads: not counted above)")
    if details:
        out.append("")
        out.append("  Hooks:")
        for h in r.hooks:
            out.append(f"    {h.event:<20} {hide(h.command[:90])}   ({hide(h.source)})")
        out.append("  Findings:")
        for f in r.findings:
            out.append(f"    {f.kind:<15} {hide(f.path)}:{f.line}  {hide(f.excerpt)}")
        out.append("  Largest skills (tokens up front / when used):")
        for s in sorted(r.skills, key=lambda s: -s.body_tokens)[:10]:
            out.append(f"    {s.description_tokens:>5} / {s.body_tokens:>6}  {s.name}")
    out.append("")
    out.append("  Recommended actions:")
    for i, a in enumerate(ins.actions, 1):
        out.append(f"    {i}. {hide(a)}")
    out.append("")
    out.append("  Counts describe capability, not intent. Token figures are estimates (chars / 4).")
    out.append("  For a shareable one-page report: --html report.html")
    return "\n".join(out)


class TargetError(Exception):
    pass


def _load(target: str) -> Report:
    """Scan a folder or a git URL. Raises TargetError with a message for the user."""
    if target.startswith(("https://", "git@")):
        tmp = tempfile.mkdtemp(prefix="skillprint-")
        try:
            # Never let git stop and ask for a username: a missing or private repo should fail fast.
            env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
            res = subprocess.run(["git", "clone", "--depth", "1", "-q", target, tmp],
                                 capture_output=True, text=True, env=env)
            if res.returncode:
                raise TargetError(f"could not download {target}. Check the URL, and that the repo is public.")
            r = scan(tmp)
            r.root = target
            return r
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    if not os.path.isdir(target):
        raise TargetError(missing_message(target))
    return scan(target)


def _signed(n: int) -> str:
    return f"+{_fmt(n)}" if n > 0 else ("±0" if n == 0 else f"-{_fmt(-n)}")


def diff_report(d: Diff) -> str:
    o, n = d.old, d.new
    out = [f"skillprint {__version__} · diff", f"  old: {o.root}", f"  new: {n.root}", ""]

    def row(label: str, a: int, b: int, unit: str = "") -> None:
        approx = "≈" if unit else ""
        change = f"  ({_signed(b - a)})" if a != b else ""
        out.append(f"  {label:<21}{approx}{_fmt(a)} → {approx}{_fmt(b)}{unit}{change}")

    arrow = "unchanged" if o.footprint == n.footprint else f"→ {n.footprint.upper()}"
    out.append(f"  {'Footprint':<21}{o.footprint.upper()} {arrow}")
    row("Skills", len(o.skills), len(n.skills))
    row("Loaded up front", o.upfront_tokens, n.upfront_tokens, " tokens")
    row("Loaded when used", o.on_use_tokens, n.on_use_tokens, " tokens")
    row("Scripts", len(o.scripts), len(n.scripts))
    row("Auto-run hooks", len(o.hooks), len(n.hooks))
    row("  on every action", o.hooks_every_action, n.hooks_every_action)

    if not d.changed:
        out += ["", "  No changes in skills, scripts, hooks or flagged code."]
        return "\n".join(out)

    for sign, title, skills, scripts, hooks, findings, domains in (
        ("+", "Added", d.skills_added, d.scripts_added, d.hooks_added, d.findings_added, d.domains_added),
        ("-", "Removed", d.skills_removed, d.scripts_removed, d.hooks_removed, d.findings_removed,
         d.domains_removed),
    ):
        lines = [f"    {sign} skill    {s.name}  (≈{_fmt(s.description_tokens)} up front / "
                 f"≈{_fmt(s.body_tokens)} when used)" for s in skills]
        lines += [f"    {sign} script   {p}" for p in scripts]
        lines += [f"    {sign} hook     {h.event:<18} {h.command[:80]}   ({h.source})" for h in hooks]
        lines += [f"    {sign} {LABELS.get(f.kind, f.kind)}  {f.path}:{f.line}  {f.excerpt[:100]}" for f in findings]
        lines += [f"    {sign} domain   {x}" for x in domains]
        if lines:
            out += ["", f"  {title}:"] + lines
    if d.skills_changed:
        out += ["", "  Changed skills (tokens up front / when used):"]
        for c in d.skills_changed:
            out.append(f"    ~ {c.name}  {_fmt(c.old.description_tokens)} → {_fmt(c.new.description_tokens)}"
                       f" / {_fmt(c.old.body_tokens)} → {_fmt(c.new.body_tokens)}")
    out += ["", "  Counts describe capability, not intent. Token figures are estimates (chars / 4)."]
    return "\n".join(out)


def _fails(footprint: str, fail_on: str | None) -> bool:
    fail_on = OLD_NAMES.get(fail_on, fail_on)
    return bool(fail_on) and ORDER.index(footprint) >= ORDER.index(fail_on)


def diff_main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="skillprint diff",
                                description="Show what changed between two versions of a skill pack.")
    p.add_argument("old", help="the old version: a folder or a git URL")
    p.add_argument("new", help="the new version: a folder or a git URL")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--fail-on", choices=["moderate", "heavy", "medium", "high"],
                   help="exit 1 if the new version's footprint is at least this (for CI)")
    a = p.parse_args(argv)
    try:
        d = diff(_load(a.old), _load(a.new))
    except TargetError as e:
        print(f"skillprint: {e}", file=sys.stderr)
        return 2
    print(json.dumps(d.to_dict(), indent=2) if a.json else diff_report(d))
    return 1 if _fails(d.new.footprint, a.fail_on) else 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # "skillprint diff OLD NEW". A pack folder that happens to be called "diff" still scans alone.
    if argv[:1] == ["diff"] and len([x for x in argv[1:] if not x.startswith("-")]) >= 2:
        return diff_main(argv[1:])
    p = argparse.ArgumentParser(prog="skillprint", description="Measure what an agent skill pack loads and runs.",
                                epilog="To compare two versions of a pack: skillprint diff OLD NEW")
    p.add_argument("target", help="path to a skill pack, or a git URL")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--badge", action="store_true", help="print a README badge")
    p.add_argument("--details", action="store_true", help="list every hook, finding and the largest skills")
    p.add_argument("--fail-on", choices=["moderate", "heavy", "medium", "high"], help="exit 1 if footprint is at least this (for CI)")
    p.add_argument("--html", metavar="FILE", help="write a one-page report to FILE (no network, safe to email)")
    p.add_argument("--internal-domain", action="append", default=[], metavar="DOMAIN",
                   help="your company's domain, e.g. example.com (repeatable); other domains are flagged as external")
    p.add_argument("--redact", action="store_true",
                   help="hide internal domains, your home folder and user name in the output")
    p.add_argument("--context-window", type=int, default=200_000, metavar="TOKENS",
                   help="model context window for the Claude Code listing budget (default 200000; 1000000 for 1M models)")
    p.add_argument("--version", action="version", version=__version__)
    a = p.parse_args(argv)

    try:
        r = _load(a.target)
    except TargetError as e:
        print(f"skillprint: {e}", file=sys.stderr)
        return 2
    if not r.skills and not r.hooks and not a.json:
        local = not a.target.startswith(("https://", "git@"))
        if local and is_claude_home(Path(a.target).resolve()):
            print(f"skillprint: nothing installed in {_tilde(r.root)} yet: no skills, plugins or hooks.\n"
                  f"{TRY_URL}", file=sys.stderr)
        else:
            print("skillprint: no SKILL.md files or hooks found here. Is this an agent skill pack?",
                  file=sys.stderr)
    ins = analyse(r, a.context_window, a.internal_domain)
    hide = redactor(a.internal_domain, r.root) if a.redact else (lambda t: t)
    if a.json:
        d = r.to_dict()
        d["listing"] = ins.listing.__dict__
        d["headline"], d["actions"] = ins.headline, ins.actions
        d["external_domains"] = ins.external_domains
        text = json.dumps(d, indent=2)
        print(hide(text) if a.redact else text)
    elif a.badge:
        print(badge(r))
    else:
        print(text_report(r, a.details, ins, hide))
    if a.html:
        Path(a.html).write_text(html_report.render(r, ins, __version__, hide, _tilde(r.root)), encoding="utf-8")
        print(f"\nReport written to {os.path.abspath(a.html)}", file=sys.stderr)
    return 1 if _fails(r.footprint, a.fail_on) else 0


if __name__ == "__main__":
    sys.exit(main())
