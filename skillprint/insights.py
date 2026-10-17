"""Turns a scan into conclusions: what the agent really sees, where things came from,
what deserves a look first, and what to do about it. No detection logic lives here."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from .scan import Report, HOOK_EVENTS_EVERY_ACTION

# Claude Code's skill listing: every name is always listed; descriptions are dropped once the
# listing passes a budget of 1% of the model's context window (see the Claude Code docs,
# "Skill descriptions are cut short"). Modelled in tokens, so figures are estimates.
LISTING_BUDGET_FRACTION = 0.01
ENTRY_OVERHEAD_TOKENS = 3  # list marker, separators

# What to look at first. Ordinary tool behaviour (running commands) is context, not a concern.
REVIEW_FIRST = {"pipe_to_shell", "hidden_unicode", "secrets_access"}
WORTH_A_LOOK = {"destructive", "env_secrets", "auto_install"}

LABELS = {
    "shell_exec": "runs shell commands",
    "pipe_to_shell": "pipes a download into a shell",
    "destructive": "destructive commands (rm -rf, force push)",
    "secrets_access": "reads credential files",
    "env_secrets": "reads secret env vars",
    "auto_install": "installs packages",
    "hidden_unicode": "hidden Unicode characters",
}


@dataclass
class Listing:
    context_window: int
    budget: int                 # tokens the listing may use
    skills: int                 # skills in the listing
    names_tokens: int           # cost of listing every name, always paid
    full_tokens: int            # cost if every description fit
    tokens: int                 # what the listing actually costs per turn
    described: int              # skills that keep their description
    names_only: int             # skills listed by name alone


@dataclass
class Source:
    name: str
    skill_files: int = 0
    loaded: int = 0
    upfront_tokens: int = 0
    scripts: int = 0
    review_first: int = 0


@dataclass
class Insights:
    listing: Listing
    sources: list[Source]
    not_loaded: int
    review_first: list = field(default_factory=list)   # Findings, most serious kinds first
    worth_a_look: dict = field(default_factory=dict)   # kind -> count
    every_action_hooks: list = field(default_factory=list)
    external_domains: list = field(default_factory=list)
    internal_domains: list = field(default_factory=list)
    actions: list = field(default_factory=list)
    headline: str = ""


def listing(r: Report, context_window: int = 200_000) -> Listing:
    loaded = r.loaded_skills
    budget = int(context_window * LISTING_BUDGET_FRACTION)
    names = sum(s.name_tokens + ENTRY_OVERHEAD_TOKENS for s in loaded)
    descs = sorted(s.listing_desc_tokens for s in loaded)
    full = names + sum(descs)
    if full <= budget:
        return Listing(context_window, budget, len(loaded), names, full, full, len(loaded), 0)
    # Over budget: Claude Code keeps descriptions for the skills you use most. Usage isn't
    # visible on disk, so count how many average-sized descriptions fit in what's left.
    room = max(0, budget - names)
    avg = (sum(descs) / len(descs)) if descs else 0
    described = min(len(loaded), int(room // avg)) if avg else len(loaded)
    tokens = max(names, budget) if described < len(loaded) else full
    return Listing(context_window, budget, len(loaded), names, full, min(tokens, full), described,
                   len(loaded) - described)


def _source_of(path: str, r: Report) -> str:
    for s in r.skills:
        if path.startswith(os.path.dirname(s.path) + os.sep) or path == s.path:
            return s.source
    parts = path.split(os.sep)
    if r.layout == "claude-home" and parts[0] == "skills" and len(parts) > 2:
        return parts[1]
    return parts[0] if len(parts) > 1 else "(root)"


def _is_internal(domain: str, internal: list[str]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in internal)


def analyse(r: Report, context_window: int = 200_000, internal_domains: list[str] | None = None) -> Insights:
    internal = [d.lower().lstrip(".") for d in (internal_domains or [])]
    lst = listing(r, context_window)

    by: dict[str, Source] = {}
    for s in r.skills:
        src = by.setdefault(s.source or "(root)", Source(s.source or "(root)"))
        src.skill_files += 1
        if s.loaded:
            src.loaded += 1
            src.upfront_tokens += s.name_tokens + ENTRY_OVERHEAD_TOKENS + s.listing_desc_tokens
    for path in r.scripts:
        by.setdefault(_source_of(path, r), Source(_source_of(path, r))).scripts += 1

    order = ["secrets_access", "pipe_to_shell", "hidden_unicode"]
    review = sorted((f for f in r.findings if f.kind in REVIEW_FIRST), key=lambda f: (order.index(f.kind), f.path, f.line))
    for f in review:
        name = _source_of(f.path, r)
        by.setdefault(name, Source(name)).review_first += 1
    worth: dict[str, int] = {}
    for f in r.findings:
        if f.kind in WORTH_A_LOOK:
            worth[f.kind] = worth.get(f.kind, 0) + 1

    # A repo often ships one hook config per tool and a user installs one, so count the main
    # config; an installed setup (~/.claude) runs all of its hooks.
    hook_pool = r.hooks if r.layout != "pack" else next(iter(r.hooks_by_config().values()), [])
    every = [h for h in hook_pool if h.event.lower() in HOOK_EVENTS_EVERY_ACTION]
    doms = sorted(r.network_domains, key=lambda d: -r.network_domains[d])
    ext = [d for d in doms if not _is_internal(d, internal)]
    intl = [d for d in doms if _is_internal(d, internal)]

    sources = sorted(by.values(), key=lambda s: (-s.loaded, -s.skill_files, s.name))
    not_loaded = sum(1 for s in r.skills if not s.loaded)
    ins = Insights(lst, sources, not_loaded, review, worth, every, ext, intl)
    ins.actions = _actions(r, ins, bool(internal))
    ins.headline = _headline(r, ins)
    return ins


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n:,} {one if n == 1 else (many or one + 's')}"


def _headline(r: Report, ins: Insights) -> str:
    lst = ins.listing
    if not r.skills and not r.hooks:
        return "Nothing is installed here: no skills or hooks."
    parts = []
    if r.layout != "pack":
        parts.append(f"The agent can use {_plural(lst.skills, 'skill')}")
        if ins.not_loaded:
            parts[-1] += f"; {ins.not_loaded:,} more SKILL.md files sit where Claude Code never loads them"
        if lst.names_only:
            parts.append(f"{lst.names_only:,} of the usable ones show as names only, so the agent can rarely pick them")
    else:
        parts.append(f"This pack adds {_plural(len(r.skills), 'skill')}")
        if lst.names_only:
            parts.append(f"installed into Claude Code, about {lst.names_only:,} would show as names only")
    n = len(ins.every_action_hooks)
    if n:
        parts.append(f"{_plural(n, 'hook')} {'runs' if n == 1 else 'run'} on every prompt or tool call")
    n = len(ins.review_first)
    if n:
        parts.append(f"{_plural(n, 'place')} in its code {'deserves' if n == 1 else 'deserve'} a look first")
    return "; ".join(parts) + "."


def _top_sources(ins: Insights, attr: str, n: int = 3) -> str:
    top = sorted((s for s in ins.sources if getattr(s, attr)), key=lambda s: -getattr(s, attr))[:n]
    return ", ".join(f"{s.name} ({getattr(s, attr):,})" for s in top)


def _actions(r: Report, ins: Insights, has_internal: bool) -> list[str]:
    acts: list[str] = []
    lst = ins.listing
    if ins.not_loaded:
        deep = [s for s in ins.sources if s.skill_files > s.loaded]
        names = ", ".join(s.name for s in sorted(deep, key=lambda s: -(s.skill_files - s.loaded))[:3])
        extra = []
        if r.inactive_scripts:
            extra.append(_plural(len(r.inactive_scripts), "script"))
        if r.inactive_findings:
            extra.append(_plural(len(r.inactive_findings), "flagged line"))
        tail = (f" They also hold {' and '.join(extra)}, which never run for the same reason." if extra else "")
        acts.append(f"Clean up {ins.not_loaded:,} SKILL.md files the agent never loads (in {names}). They sit deeper "
                    f"than Claude Code looks (<skills folder>/<skill-name>/SKILL.md).{tail} If a team wants one of "
                    f"these skills, install it as its own folder; otherwise delete the copy so nobody assumes it's active.")
    if lst.names_only:
        acts.append(f"Trim the skill list: {lst.skills:,} skills share a listing budget of about {lst.budget:,} tokens, "
                    f"so about {lst.names_only:,} appear by name only and are rarely chosen. Run /skill-doctor in "
                    f"Claude Code to see which are never used, then remove them or set them to name-only in "
                    f"skillOverrides. Biggest contributors: {_top_sources(ins, 'loaded')}.")
    if ins.review_first:
        kinds: dict[str, int] = {}
        for f in ins.review_first:
            kinds[f.kind] = kinds.get(f.kind, 0) + 1
        what = ", ".join(f"{n:,} {LABELS[k]}" for k, n in kinds.items())
        acts.append(f"Review the {_plural(len(ins.review_first), 'place')} listed under 'Review first' ({what}). "
                    f"Most will be legitimate; confirm each has an owner. Most are in: {_top_sources(ins, 'review_first')}.")
    if ins.every_action_hooks:
        n = len(ins.every_action_hooks)
        what = "the hook that runs" if n == 1 else f"each of the {n:,} hooks that run"
        acts.append(f"Confirm an owner for {what} on every prompt or tool call: "
                    f"{'it runs' if n == 1 else 'they run'} on the developer's machine all day.")
    if has_internal and ins.external_domains:
        acts.append(f"Check the {_plural(len(ins.external_domains), 'external domain')} its code contacts: "
                    f"{', '.join(ins.external_domains[:5])}{'…' if len(ins.external_domains) > 5 else ''}.")
    if not acts:
        acts.append("Nothing needs action: the setup is small and nothing stands out.")
    return acts


# ---- redaction --------------------------------------------------------------

def redactor(internal_domains: list[str] | None, root: str):
    """Returns a function that hides internal domains, home folders and user names, for
    sharing a report outside the team. Skill and folder names are kept."""
    internal = sorted({d.lower().lstrip(".") for d in (internal_domains or [])}, key=len, reverse=True)
    home = os.path.expanduser("~")
    user = os.path.basename(home)
    seen: dict[str, str] = {}
    dom_re = re.compile(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

    def hide(text: str) -> str:
        text = text.replace(home, "~")
        if user and len(user) > 2:
            text = re.sub(re.escape(user), "<user>", text, flags=re.I)

        def sub(m):
            d = m.group(0).lower()
            if any(d == i or d.endswith("." + i) for i in internal):
                seen.setdefault(d, f"internal-host-{len(seen) + 1}")
                return seen[d]
            return m.group(0)
        return dom_re.sub(sub, text) if internal else text
    return hide
