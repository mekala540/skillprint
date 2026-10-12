"""Core scanner: walks a skill pack and measures what it loads and what it runs."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
BINARY_EXT = {
    "png", "jpg", "jpeg", "gif", "webp", "ico", "svg", "pdf", "zip", "gz", "tgz",
    "woff", "woff2", "ttf", "otf", "mp4", "mov", "mp3", "wav", "so", "dylib", "dll",
    "exe", "bin", "lock",
}
SCRIPT_EXT = {"sh", "bash", "zsh", "py", "js", "mjs", "cjs", "ts", "ps1", "cmd", "bat", "rb", "pl"}
CONFIG_EXT = {"json", "yaml", "yml", "toml"}
MAX_BYTES = 1_000_000

# Hook events that fire on every prompt or tool call (Claude Code, Cursor, Codex naming).
HOOK_EVENTS_EVERY_ACTION = {
    "pretooluse", "posttooluse", "posttoolusefailure", "userpromptsubmit",
    "beforeshellexecution", "aftershellexecution", "beforemcpexecution", "aftermcpexecution",
    "beforereadfile", "afterfileedit", "beforesubmitprompt", "beforetabfileread", "aftertabfileedit",
}
TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec|fixtures?)(/|$)|(\.test\.|\.spec\.|_test\.py$|(^|/)test_[^/]*\.py$)")
PLACEHOLDER_DOMAIN = re.compile(r"(^|\.)(example\.(com|org|net|test)|localhost|w3\.org|schema\.org|test|invalid)$")

# Capability patterns. They describe what code CAN do, not intent.
PATTERNS = {
    "shell_exec": r"(subprocess\.|child_process|\bexecSync\(|\bexec\(|os\.system\(|\bspawn(Sync)?\(|\bbash -c\b)",
    "pipe_to_shell": r"(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh\b",
    "destructive": r"(rm\s+-[a-z]*r[a-z]*f|rm\s+-[a-z]*f[a-z]*r|git\s+push\s+(-f|--force)|git\s+reset\s+--hard|DROP\s+TABLE|mkfs\.)",
    "secrets_access": r"(~/\.ssh|\.ssh/id_|~/\.aws|\.aws/credentials|security\s+find-(generic|internet)-password|SecItemCopyMatching|\bkeytar\b|\.netrc\b|~/\.npmrc|~/\.pypirc)",
    "env_secrets": r"(process\.env\.[A-Z_]*(KEY|TOKEN|SECRET)|os\.environ(\.get)?\(?\[?['\"][A-Z_]*(KEY|TOKEN|SECRET))",
    "auto_install": r"(\bnpm\s+(i|install)\b|\bpip3?\s+install\b|\bnpx\s+-y\b|\bbrew\s+install\b|\bcargo\s+install\b|\bgo\s+install\b)",
}
HIDDEN_UNICODE = re.compile("[​‌‍⁠‪-‮⁦-⁩]")
URL_RE = re.compile(r"https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


def est_tokens(text: str) -> int:
    """Rough token estimate (characters / 4). Good enough to compare packs."""
    return (len(text) + 3) // 4


@dataclass
class Skill:
    name: str
    path: str
    description_tokens: int
    body_tokens: int


@dataclass
class Hook:
    event: str
    command: str
    source: str


@dataclass
class Finding:
    kind: str
    path: str
    line: int
    excerpt: str


@dataclass
class Report:
    root: str
    files: int = 0
    skills: list[Skill] = field(default_factory=list)
    skill_files: int = 0
    scripts: list[str] = field(default_factory=list)
    hooks: list[Hook] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    doc_mentions: dict[str, int] = field(default_factory=dict)
    test_files: int = 0
    network_domains: dict[str, int] = field(default_factory=dict)

    # ---- derived numbers -------------------------------------------------
    @property
    def upfront_tokens(self) -> int:
        return sum(s.description_tokens for s in self.skills)

    @property
    def on_use_tokens(self) -> int:
        return sum(s.body_tokens for s in self.skills)

    @property
    def hooks_every_action(self) -> int:
        return sum(1 for h in self.hooks if h.event.lower() in HOOK_EVENTS_EVERY_ACTION)

    def hooks_by_config(self) -> dict[str, list[Hook]]:
        """Packs often ship one hook config per tool; a user installs one of them."""
        out: dict[str, list[Hook]] = {}
        for h in self.hooks:
            out.setdefault(h.source, []).append(h)
        return dict(sorted(out.items(), key=lambda kv: -len(kv[1])))

    def finding_counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for f in self.findings:
            out[f.kind] = out.get(f.kind, 0) + 1
        return out

    @property
    def footprint(self) -> str:
        """none < low < medium < high, from what runs without being asked."""
        c = self.finding_counts()
        if self.hooks_every_action or c.get("pipe_to_shell") or c.get("hidden_unicode"):
            return "high"
        if self.hooks or self.scripts:
            return "medium"
        if self.skills:
            return "low"
        return "none"

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "footprint": self.footprint,
            "files": self.files,
            "skills_unique": len(self.skills),
            "skill_files": self.skill_files,
            "upfront_tokens": self.upfront_tokens,
            "on_use_tokens": self.on_use_tokens,
            "scripts": len(self.scripts),
            "hooks": len(self.hooks),
            "hooks_every_action": self.hooks_every_action,
            "hook_events": sorted({h.event for h in self.hooks}),
            "hooks_by_config": {k: len(v) for k, v in self.hooks_by_config().items()},
            "test_files_skipped": self.test_files,
            "findings": self.finding_counts(),
            "doc_mentions_ignored": self.doc_mentions,
            "network_domains": dict(sorted(self.network_domains.items(), key=lambda kv: -kv[1])),
            "skills": [asdict(s) for s in self.skills],
            "hook_list": [asdict(h) for h in self.hooks],
            "finding_list": [asdict(f) for f in self.findings],
        }


# ---- helpers -------------------------------------------------------------

def _iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            yield Path(dirpath) / name


def _read_text(path: Path) -> str | None:
    if path.suffix.lower().lstrip(".") in BINARY_EXT:
        return None
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:4096]:
        return None
    return raw.decode("utf-8", errors="ignore")


def _is_script(path: Path, text: str) -> bool:
    return path.suffix.lower().lstrip(".") in SCRIPT_EXT or text.startswith("#!")


def _parse_frontmatter(text: str) -> dict[str, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fields: dict[str, str] = {}
    key = None
    for line in m.group(1).splitlines():
        km = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if km:
            key = km.group(1).lower()
            fields[key] = km.group(2).strip()
        elif key and line.startswith((" ", "\t")):
            fields[key] += " " + line.strip()
    return fields


def _rank(path: str) -> tuple:
    """Prefer the canonical copy of a skill: not under docs/, then the shortest path."""
    return (path.startswith("docs"), path.count("/"), len(path))


def _code_blocks(markdown: str) -> str:
    """Only fenced code in a SKILL.md is something the agent may run."""
    return "\n".join(re.findall(r"```[^\n]*\n(.*?)```", markdown, re.S))


def _collect_hooks(data, source: str) -> list[Hook]:
    hooks: list[Hook] = []
    block = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(block, dict):
        return hooks
    for event, entries in block.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            inner = entry.get("hooks") if isinstance(entry, dict) else None
            cmds = inner if isinstance(inner, list) else [entry]
            for c in cmds:
                cmd = c.get("command", "") if isinstance(c, dict) else str(c)
                hooks.append(Hook(event=event, command=str(cmd)[:200], source=source))
    return hooks


def _scan_text(rel: str, text: str, report: Report, as_findings: bool) -> None:
    for kind, pat in PATTERNS.items():
        for m in re.finditer(pat, text, re.I):
            if as_findings:
                line = text.count("\n", 0, m.start()) + 1
                excerpt = text.splitlines()[line - 1].strip()[:140] if text else ""
                report.findings.append(Finding(kind, rel, line, excerpt))
            else:
                report.doc_mentions[kind] = report.doc_mentions.get(kind, 0) + 1
    if as_findings:
        for m in HIDDEN_UNICODE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            report.findings.append(Finding("hidden_unicode", rel, line, f"U+{ord(m.group()):04X}"))
            break
        for m in URL_RE.finditer(text):
            d = m.group(1).lower()
            if PLACEHOLDER_DOMAIN.search(d):
                continue
            report.network_domains[d] = report.network_domains.get(d, 0) + 1


# ---- main entry ----------------------------------------------------------

def scan(root: str | os.PathLike) -> Report:
    root = Path(root).resolve()
    report = Report(root=str(root))
    seen_skills: dict[str, Skill] = {}

    for path in _iter_files(root):
        rel = str(path.relative_to(root))
        text = _read_text(path)
        report.files += 1
        if text is None:
            continue

        if path.name == "SKILL.md":
            report.skill_files += 1
            fm = _parse_frontmatter(text)
            name = fm.get("name") or path.parent.name
            desc = fm.get("description", "")
            body = FRONTMATTER_RE.sub("", text, count=1)
            key = name.strip().lower()
            cand = Skill(name, rel, est_tokens(f"{name}: {desc}"), est_tokens(body))
            prev = seen_skills.get(key)  # copies for other tools or languages count once
            if prev is None or _rank(cand.path) < _rank(prev.path):
                seen_skills[key] = cand
            _scan_text(rel, _code_blocks(text), report, as_findings=True)
            _scan_text(rel, re.sub(r"```.*?```", "", text, flags=re.S), report, as_findings=False)
            continue

        if TEST_PATH.search(rel.replace(os.sep, "/")):
            report.test_files += 1  # tests are not installed into the agent
            continue

        if _is_script(path, text):
            report.scripts.append(rel)
            _scan_text(rel, text, report, as_findings=True)
            continue

        if path.suffix.lower().lstrip(".") == "json" and "hooks" in text:
            try:
                new = _collect_hooks(json.loads(text), rel)
                report.hooks.extend(new)
                for h in new:  # a hook command runs without asking, so it counts
                    _scan_text(rel, h.command, report, as_findings=True)
            except ValueError:
                pass
            continue

        if path.suffix.lower().lstrip(".") not in CONFIG_EXT:
            _scan_text(rel, text, report, as_findings=False)  # docs: counted, not flagged

    report.skills = sorted(seen_skills.values(), key=lambda s: s.path)
    return report
