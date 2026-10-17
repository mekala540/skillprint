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

# Hook events that fire on every prompt or tool call, matched lowercased.
HOOK_EVENTS_EVERY_ACTION = {
    # Claude Code, Codex; Copilot uses the same names in camelCase
    "pretooluse", "posttooluse", "posttoolusefailure", "userpromptsubmit",
    # Cursor
    "beforeshellexecution", "aftershellexecution", "beforemcpexecution", "aftermcpexecution",
    "beforereadfile", "afterfileedit", "beforesubmitprompt", "beforetabfileread", "aftertabfileedit",
    # GitHub Copilot
    "userpromptsubmitted", "userprompttransformed",
    # Gemini CLI (model events fire on every model call, more often than prompts)
    "beforetool", "aftertool", "beforeagent", "beforemodel", "aftermodel", "beforetoolselection",
    # Windsurf
    "pre_read_code", "post_read_code", "pre_write_code", "post_write_code", "pre_run_command",
    "post_run_command", "pre_mcp_tool_use", "post_mcp_tool_use", "pre_user_prompt",
}
# Only files that can register hooks; a reference JSON that happens to have a "hooks" key is data.
HOOK_CONFIG = re.compile(r"^(.*hooks?.*|plugin|settings(\.local)?)\.json$", re.I)
# GitHub Copilot loads every JSON file in .github/hooks/ and ~/.copilot/hooks/, whatever its name.
COPILOT_HOOK_DIR = re.compile(r"(^|/)\.(github|copilot)/hooks/[^/]+\.json$")
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


DESC_CAP_CHARS = 1536  # Claude Code truncates description + when_to_use at this length in its listing


@dataclass
class Skill:
    name: str
    path: str
    description_tokens: int          # name + description as shipped (kept for older JSON readers)
    body_tokens: int
    name_tokens: int = 0
    listing_desc_tokens: int = 0     # description after Claude Code's per-skill cap
    loaded: bool = True              # False: sits where Claude Code never looks
    source: str = ""                 # top-level folder or plugin it came from


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
    layout: str = "pack"             # "pack" (a repo), "claude-home" (~/.claude) or "claude-skills" (a skills dir)
    # Things inside folders Claude Code never loads: on disk, but never run by the agent.
    inactive_scripts: list[str] = field(default_factory=list)
    inactive_hooks: list[Hook] = field(default_factory=list)
    inactive_findings: list[Finding] = field(default_factory=list)
    domain_files: dict[str, set] = field(default_factory=dict, repr=False)  # domain -> files that mention it

    # ---- derived numbers -------------------------------------------------
    @property
    def loaded_skills(self) -> list[Skill]:
        return [s for s in self.skills if s.loaded]

    @property
    def upfront_tokens(self) -> int:
        """Description text the skills ship, before any agent-side budget."""
        return sum(s.description_tokens for s in self.loaded_skills)

    @property
    def on_use_tokens(self) -> int:
        return sum(s.body_tokens for s in self.loaded_skills)

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
        """none < light < moderate < heavy: how much it loads and runs without being asked.
        Describes size, not danger."""
        c = self.finding_counts()
        if self.hooks_every_action or c.get("pipe_to_shell") or c.get("hidden_unicode"):
            return "heavy"
        if self.hooks or self.scripts:
            return "moderate"
        if self.skills:
            return "light"
        return "none"

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "footprint": self.footprint,
            "files": self.files,
            "skills_unique": len(self.skills),
            "skill_files": self.skill_files,
            "layout": self.layout,
            "skills_loaded": len(self.loaded_skills),
            "upfront_tokens": self.upfront_tokens,
            "on_use_tokens": self.on_use_tokens,
            "scripts": len(self.scripts),
            "hooks": len(self.hooks),
            "hooks_every_action": self.hooks_every_action,
            "hook_events": sorted({h.event for h in self.hooks}),
            "hooks_by_config": {k: len(v) for k, v in self.hooks_by_config().items()},
            "test_files_skipped": self.test_files,
            "never_loaded": {"skills": len(self.skills) - len(self.loaded_skills),
                             "scripts": len(self.inactive_scripts), "hooks": len(self.inactive_hooks),
                             "findings": len(self.inactive_findings)},
            "findings": self.finding_counts(),
            "doc_mentions_ignored": self.doc_mentions,
            "network_domains": dict(sorted(self.network_domains.items(), key=lambda kv: -kv[1])),
            "skills": [asdict(s) for s in self.skills],
            "hook_list": [asdict(h) for h in self.hooks],
            "finding_list": [asdict(f) for f in self.findings],
        }


# ---- helpers -------------------------------------------------------------

def _iter_files(root: Path, skip: set[str] = frozenset()):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not (dirpath == str(root) and d in skip)]
        for name in filenames:
            yield Path(dirpath) / name


def is_claude_home(root: Path) -> bool:
    return root.name == ".claude" and any((root / p).exists() for p in ("settings.json", "plugins", "projects"))


def _installed_plugins(root: Path) -> list[Path]:
    """Plugin folders Claude Code actually loads. plugins/marketplaces holds the catalog of
    everything you could install; only plugins/installed_plugins.json says what you did."""
    try:
        settings = json.loads((root / "settings.json").read_text(encoding="utf-8"))
        enabled = settings.get("enabledPlugins") or {}
    except (OSError, ValueError, AttributeError):
        enabled = {}
    try:
        data = json.loads((root / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))
        plugins = data.get("plugins", {})
    except (OSError, ValueError, AttributeError):
        cache = root / "plugins" / "cache"
        return [cache] if cache.is_dir() else []
    out: list[Path] = []
    for key, entries in plugins.items() if isinstance(plugins, dict) else []:
        if isinstance(enabled, dict) and enabled.get(key) is False:
            continue
        for e in entries if isinstance(entries, list) else [entries]:
            if not isinstance(e, dict) or e.get("scope", "user") != "user":
                continue  # project and local installs only load inside that project
            p = Path(os.path.expanduser(str(e.get("installPath", ""))))
            if e.get("installPath") and p.is_dir():
                out.append(p)
    return out


# A Claude Code home also holds transcripts, history and caches; none of it loads into the agent.
CLAUDE_HOME_SKIP = {
    "plugins", "projects", "file-history", "sessions", "session-env", "shell-snapshots", "backups",
    "downloads", "cache", "todos", "statsig", "ide", "debug", "telemetry", "paste-cache", "logs",
}


def _layout(root: Path) -> str:
    if is_claude_home(root):
        return "claude-home"
    if root.name == "skills" and root.parent.name == ".claude":
        return "claude-skills"
    return "pack"


def _loaded(path: Path, root: Path, layout: str, plugin_roots: list[Path]) -> bool:
    """Claude Code loads <skills dir>/<skill-name>/SKILL.md, one level deep (plus skills synced
    from claude.ai under skills/synced/). A SKILL.md deeper than that, such as inside a whole
    repo copied into the folder, is never loaded. Outside Claude Code layouts, every skill counts."""
    if layout == "pack":
        return True
    skill_dir_parent = path.parent.parent
    skills_dirs = {root / "skills", root / "skills" / "synced"} if layout == "claude-home" \
        else {root, root / "synced"}
    if skill_dir_parent in skills_dirs:
        return True
    return any(skill_dir_parent == p / "skills" for p in plugin_roots)


def _source(path: Path, root: Path, plugin_roots: list[Path]) -> str:
    """Where a skill came from: the plugin it belongs to, or its top-level folder."""
    for p in plugin_roots:
        if p in path.parents:
            return "plugin: " + p.parent.name if p.name[:1].isdigit() else "plugin: " + p.name
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return "other"
    if parts and parts[0] == "skills" and len(parts) > 2 and (root / "skills").is_dir() and is_claude_home(root):
        parts = parts[1:]
    if parts and parts[0] == "synced" and len(parts) > 2:
        return "synced from claude.ai"
    if len(parts) == 2 and parts[1] == "SKILL.md" and _layout(root) != "pack":
        return "your personal skills"
    return parts[0] if len(parts) > 1 else "(root)"


def _pack_files(root: Path):
    """Every file in the pack. For ~/.claude: your own skills and settings, plus installed plugins."""
    if not is_claude_home(root):
        yield from _iter_files(root)
        return
    yield from _iter_files(root, skip=CLAUDE_HOME_SKIP)
    for plugin in _installed_plugins(root):
        yield from _iter_files(plugin)


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
    """Only fenced code in a SKILL.md is something the agent may run.
    Everything outside the fences is blanked, so line numbers still match the file."""
    out, inside = [], False
    for line in markdown.split("\n"):
        if line.lstrip().startswith("```"):
            inside = not inside
            out.append("")
        else:
            out.append(line if inside else "")
    return "\n".join(out)


def _hook_command(c: dict) -> str:
    """Claude Code, Cursor, Gemini and Windsurf use "command"; Copilot uses "bash" and
    "powershell" (or "exec" with "args"), and its http hooks call a "url"."""
    for k in ("command", "bash", "powershell"):
        if c.get(k):
            return str(c[k])
    if c.get("exec"):
        args = c.get("args") if isinstance(c.get("args"), list) else []
        return " ".join(str(x) for x in [c["exec"], *args])
    return str(c.get("url", ""))


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
                cmd = _hook_command(c) if isinstance(c, dict) else str(c)
                hooks.append(Hook(event=event, command=str(cmd)[:200], source=source))
    return hooks


SHELL_EXT = {"sh", "bash", "zsh"}
COMMENT_LINE = re.compile(r"^\s*(#(?!!)|//|/\*|\*|<!--|--\s)")


def _strip_comments(text: str) -> str:
    """Blank out whole-line comments, keeping line numbers. Comments describe; they don't run."""
    return "\n".join("" if COMMENT_LINE.match(line) else line for line in text.split("\n"))


def _is_shell(path: Path, text: str) -> bool:
    first = text.split("\n", 1)[0]
    return path.suffix.lower().lstrip(".") in SHELL_EXT or (first.startswith("#!") and "sh" in first)


def _scan_hidden(rel: str, text: str, report: Report) -> None:
    """Invisible characters matter where the agent or a shell reads text as instructions.
    A joiner between two non-Latin characters is ordinary writing, not hidden text."""
    for m in HIDDEN_UNICODE.finditer(text):
        ch, i = m.group(), m.start()
        if ch in "\u200c\u200d":
            # Joiners between two non-Latin characters are ordinary writing: emoji
            # sequences, or Persian, Arabic and Indic scripts.
            before = text[i - 1] if i else ""
            after = text[i + 1] if i + 1 < len(text) else ""
            if before and after and ord(before) > 0x2FF and ord(after) > 0x2FF:
                continue
        line = text.count("\n", 0, i) + 1
        report.findings.append(Finding("hidden_unicode", rel, line, f"U+{ord(ch):04X}"))
        return


def _scan_text(rel: str, text: str, report: Report, as_findings: bool, shell: bool = True) -> None:
    """shell=False for code in other languages: there `curl ... | bash` is almost always a
    message telling the user how to install something, not a command being run."""
    if as_findings:
        text = _strip_comments(text)
    for kind, pat in PATTERNS.items():
        if as_findings and kind == "pipe_to_shell" and not shell:
            continue
        for m in re.finditer(pat, text, re.I):
            if as_findings:
                line = text.count("\n", 0, m.start()) + 1
                excerpt = text.splitlines()[line - 1].strip()[:140] if text else ""
                report.findings.append(Finding(kind, rel, line, excerpt))
            else:
                report.doc_mentions[kind] = report.doc_mentions.get(kind, 0) + 1
    if as_findings:
        for m in URL_RE.finditer(text):
            d = m.group(1).lower()
            if PLACEHOLDER_DOMAIN.search(d):
                continue
            report.network_domains[d] = report.network_domains.get(d, 0) + 1
            report.domain_files.setdefault(d, set()).add(rel)


# ---- main entry ----------------------------------------------------------

def scan(root: str | os.PathLike) -> Report:
    root = Path(root).resolve()
    layout = _layout(root)
    plugin_roots = _installed_plugins(root) if layout == "claude-home" else []
    report = Report(root=str(root), layout=layout)
    seen_skills: dict[str, Skill] = {}
    loaded_dirs: set[str] = set()

    for path in _pack_files(root):
        rel = os.path.relpath(path, root)
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
            when = fm.get("when_to_use", "")
            listing = (desc + (" " + when if when else ""))[:DESC_CAP_CHARS]
            cand = Skill(name, rel, est_tokens(f"{name}: {desc}"), est_tokens(body),
                         name_tokens=est_tokens(name), listing_desc_tokens=est_tokens(listing),
                         loaded=_loaded(path, root, layout, plugin_roots), source=_source(path, root, plugin_roots))
            if cand.loaded:
                loaded_dirs.add(os.path.normpath(str(path.parent)))
            prev = seen_skills.get(key)  # copies for other tools or languages count once
            if prev is None or _rank(cand.path) < _rank(prev.path):
                seen_skills[key] = cand
            _scan_text(rel, _code_blocks(text), report, as_findings=True)
            _scan_hidden(rel, text, report)  # the agent reads every word of a SKILL.md
            _scan_text(rel, re.sub(r"```.*?```", "", text, flags=re.S), report, as_findings=False)
            continue

        if TEST_PATH.search(rel.replace(os.sep, "/")):
            report.test_files += 1  # tests are not installed into the agent
            continue

        if _is_script(path, text):
            report.scripts.append(rel)
            shell = _is_shell(path, text)
            _scan_text(rel, text, report, as_findings=True, shell=shell)
            if shell:
                _scan_hidden(rel, text, report)
            continue

        if (HOOK_CONFIG.search(path.name) or COPILOT_HOOK_DIR.search(rel.replace(os.sep, "/"))) \
                and "hooks" in text:
            try:
                new = _collect_hooks(json.loads(text), rel)
                report.hooks.extend(new)
                for h in new:  # a hook command runs without asking, so it counts
                    _scan_text(rel, h.command, report, as_findings=True)
                    _scan_hidden(rel, h.command, report)
            except ValueError:
                pass
            continue

        if path.suffix.lower().lstrip(".") not in CONFIG_EXT:
            _scan_text(rel, text, report, as_findings=False)  # docs: counted, not flagged

    report.skills = sorted(seen_skills.values(), key=lambda s: s.path)
    if layout != "pack":
        _set_aside_inactive(report, root, loaded_dirs)
    return report


def _set_aside_inactive(report: Report, root: Path, loaded_dirs: set[str]) -> None:
    """Inside the skills folder, only files belonging to a loaded skill can ever run. A repo copied
    in wholesale brings scripts, hooks and flagged code that the agent never sees."""
    skills_dir = os.path.normpath(str(root / "skills" if report.layout == "claude-home" else root))

    def active(rel: str) -> bool:
        ap = os.path.normpath(os.path.join(str(root), rel))
        if not (ap == skills_dir or ap.startswith(skills_dir + os.sep)):
            return True
        return any(ap.startswith(d + os.sep) for d in loaded_dirs)

    report.inactive_scripts = [p for p in report.scripts if not active(p)]
    report.scripts = [p for p in report.scripts if active(p)]
    report.inactive_hooks = [h for h in report.hooks if not active(h.source)]
    report.hooks = [h for h in report.hooks if active(h.source)]
    report.inactive_findings = [f for f in report.findings if not active(f.path)]
    report.findings = [f for f in report.findings if active(f.path)]
    for d, files in list(report.domain_files.items()):
        if not any(active(p) for p in files):
            report.network_domains.pop(d, None)
