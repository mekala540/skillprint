"""Diff mode: what changed between two versions of a skill pack."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field

from .scan import Finding, Hook, Report, Skill


@dataclass
class SkillChange:
    name: str
    old: Skill
    new: Skill


@dataclass
class Diff:
    old: Report
    new: Report
    skills_added: list[Skill] = field(default_factory=list)
    skills_removed: list[Skill] = field(default_factory=list)
    skills_changed: list[SkillChange] = field(default_factory=list)
    scripts_added: list[str] = field(default_factory=list)
    scripts_removed: list[str] = field(default_factory=list)
    hooks_added: list[Hook] = field(default_factory=list)
    hooks_removed: list[Hook] = field(default_factory=list)
    findings_added: list[Finding] = field(default_factory=list)
    findings_removed: list[Finding] = field(default_factory=list)
    domains_added: list[str] = field(default_factory=list)
    domains_removed: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(
            self.old.footprint != self.new.footprint or self.skills_added or self.skills_removed
            or self.skills_changed or self.scripts_added or self.scripts_removed or self.hooks_added
            or self.hooks_removed or self.findings_added or self.findings_removed
            or self.domains_added or self.domains_removed
        )

    def to_dict(self) -> dict:
        def pair(a, b) -> dict:
            return {"old": a, "new": b}

        o, n = self.old, self.new
        return {
            "old": o.root,
            "new": n.root,
            "changed": self.changed,
            "footprint": pair(o.footprint, n.footprint),
            "skills_unique": pair(len(o.skills), len(n.skills)),
            "upfront_tokens": pair(o.upfront_tokens, n.upfront_tokens),
            "on_use_tokens": pair(o.on_use_tokens, n.on_use_tokens),
            "scripts": pair(len(o.scripts), len(n.scripts)),
            "hooks": pair(len(o.hooks), len(n.hooks)),
            "hooks_every_action": pair(o.hooks_every_action, n.hooks_every_action),
            "findings": pair(o.finding_counts(), n.finding_counts()),
            "added": {
                "skills": [asdict(s) for s in self.skills_added],
                "scripts": self.scripts_added,
                "hooks": [asdict(h) for h in self.hooks_added],
                "findings": [asdict(f) for f in self.findings_added],
                "network_domains": self.domains_added,
            },
            "removed": {
                "skills": [asdict(s) for s in self.skills_removed],
                "scripts": self.scripts_removed,
                "hooks": [asdict(h) for h in self.hooks_removed],
                "findings": [asdict(f) for f in self.findings_removed],
                "network_domains": self.domains_removed,
            },
            "skills_changed": [
                {"name": c.name, "old": asdict(c.old), "new": asdict(c.new)} for c in self.skills_changed
            ],
        }


def _finding_key(f: Finding) -> tuple:
    # Line numbers shift whenever lines are added above a match; the same code is the same finding.
    return (f.kind, f.path, f.excerpt)


def _multiset_diff(old: list, new: list, key) -> tuple[list, list]:
    """Items in new but not old, and in old but not new, counting duplicates."""
    left = Counter(key(x) for x in old)
    right = Counter(key(x) for x in new)
    added, removed = [], []
    for x in new:
        k = key(x)
        if left[k]:
            left[k] -= 1
        else:
            added.append(x)
    for x in old:
        k = key(x)
        if right[k]:
            right[k] -= 1
        else:
            removed.append(x)
    return added, removed


def diff(old: Report, new: Report) -> Diff:
    d = Diff(old=old, new=new)

    # Skills are matched by name, the same key scan() uses to merge copies.
    olds = {s.name.strip().lower(): s for s in old.skills}
    news = {s.name.strip().lower(): s for s in new.skills}
    d.skills_added = [news[k] for k in sorted(news.keys() - olds.keys())]
    d.skills_removed = [olds[k] for k in sorted(olds.keys() - news.keys())]
    for k in sorted(olds.keys() & news.keys()):
        a, b = olds[k], news[k]
        # The digest catches edits that keep the size; packs scanned before it existed fall back to size.
        if (a.description_tokens, a.body_tokens) != (b.description_tokens, b.body_tokens) or (
                a.digest and b.digest and a.digest != b.digest):
            d.skills_changed.append(SkillChange(b.name, a, b))

    d.scripts_added = sorted(set(new.scripts) - set(old.scripts))
    d.scripts_removed = sorted(set(old.scripts) - set(new.scripts))
    hook_key = lambda h: (h.source, h.event, h.command)  # noqa: E731
    d.hooks_added, d.hooks_removed = _multiset_diff(old.hooks, new.hooks, hook_key)
    d.findings_added, d.findings_removed = _multiset_diff(old.findings, new.findings, _finding_key)
    d.domains_added = sorted(new.network_domains.keys() - old.network_domains.keys())
    d.domains_removed = sorted(old.network_domains.keys() - new.network_domains.keys())
    return d
