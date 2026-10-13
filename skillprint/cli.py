"""Command line: skillprint <path-or-git-url> [--json] [--badge] [--details]"""
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
from .scan import scan, Report, HOOK_EVENTS_EVERY_ACTION

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


def badge(r: Report) -> str:
    biggest = max((len(v) for v in r.hooks_by_config().values()), default=0)
    hooks = "1 hook" if biggest == 1 else f"{biggest} hooks"
    msg = f"{r.footprint} footprint · {_fmt(r.upfront_tokens)} tokens · {hooks}"
    url = f"https://img.shields.io/badge/skillprint-{quote(msg.replace('-', '--'))}-{COLORS[r.footprint]}"
    return f"[![skillprint]({url})](https://github.com/mekala540/skillprint)"


def text_report(r: Report, details: bool) -> str:
    out = []
    out.append(f"skillprint {__version__} · {r.root}")
    out.append("")
    out.append(f"  Footprint            {r.footprint.upper()}")
    copies = f" ({_fmt(r.skill_files)} SKILL.md files incl. copies)" if r.skill_files != len(r.skills) else ""
    out.append(f"  Skills               {_fmt(len(r.skills))}{copies}")
    out.append(f"  Loaded up front      ≈{_fmt(r.upfront_tokens)} tokens (names + descriptions, every session)")
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
        out.append(f"    domains: {top}")
    ignored = sum(r.doc_mentions.values())
    if ignored:
        out.append(f"  ({_fmt(ignored)} pattern matches in docs and prose ignored: they describe, they don't run)")
    if r.test_files:
        out.append(f"  ({_fmt(r.test_files)} test files skipped: they don't ship to the agent)")
    if details:
        out.append("")
        out.append("  Hooks:")
        for h in r.hooks:
            out.append(f"    {h.event:<20} {h.command[:90]}   ({h.source})")
        out.append("  Findings:")
        for f in r.findings:
            out.append(f"    {f.kind:<15} {f.path}:{f.line}  {f.excerpt}")
        out.append("  Largest skills (tokens up front / when used):")
        for s in sorted(r.skills, key=lambda s: -s.body_tokens)[:10]:
            out.append(f"    {s.description_tokens:>5} / {s.body_tokens:>6}  {s.name}")
    out.append("")
    out.append("  Counts describe capability, not intent. Token figures are estimates (chars / 4).")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="skillprint", description="Measure what an agent skill pack loads and runs.")
    p.add_argument("target", help="path to a skill pack, or a git URL")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--badge", action="store_true", help="print a README badge")
    p.add_argument("--details", action="store_true", help="list every hook, finding and the largest skills")
    p.add_argument("--fail-on", choices=["moderate", "heavy", "medium", "high"], help="exit 1 if footprint is at least this (for CI)")
    p.add_argument("--version", action="version", version=__version__)
    a = p.parse_args(argv)

    tmp = None
    target = a.target
    if target.startswith(("https://", "git@")):
        tmp = tempfile.mkdtemp(prefix="skillprint-")
        # Never let git stop and ask for a username: a missing or private repo should fail fast.
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        res = subprocess.run(["git", "clone", "--depth", "1", "-q", target, tmp],
                             capture_output=True, text=True, env=env)
        if res.returncode:
            shutil.rmtree(tmp, ignore_errors=True)
            print(f"skillprint: could not download {target}. Check the URL, and that the repo is public.",
                  file=sys.stderr)
            return 2
        target = tmp
    elif not os.path.isdir(target):
        print(f"skillprint: {target} is not a folder. Give a skill pack folder or a git URL.", file=sys.stderr)
        return 2
    try:
        r = scan(target)
        if tmp:
            r.root = a.target
        if not r.skills and not r.hooks and not a.json:
            print("skillprint: no SKILL.md files or hooks found here. Is this an agent skill pack?",
                  file=sys.stderr)
        if a.json:
            print(json.dumps(r.to_dict(), indent=2))
        elif a.badge:
            print(badge(r))
        else:
            print(text_report(r, a.details))
        fail_on = OLD_NAMES.get(a.fail_on, a.fail_on)
        if fail_on and ORDER.index(r.footprint) >= ORDER.index(fail_on):
            return 1
        return 0
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
