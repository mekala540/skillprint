# skillprint

[![tests](https://github.com/mekala540/skillprint/actions/workflows/tests.yml/badge.svg)](https://github.com/mekala540/skillprint/actions/workflows/tests.yml) ![license](https://img.shields.io/badge/license-MIT-blue) ![python](https://img.shields.io/badge/python-3.9%2B-blue)

**See what an agent skill pack loads and runs — before you install it.**

Skill packs for Claude Code, Cursor, Codex, GitHub Copilot, Gemini CLI, Windsurf and OpenClaw now collect hundreds of thousands of stars. Stars tell you a pack is popular. They don't tell you that it adds 25,000 tokens to every session, or registers 27 hooks that run code before your agent's tool calls.

`skillprint` reads a pack and reports:

- **Context cost** — tokens loaded up front every session (skill names and descriptions) and tokens loaded when skills are used
- **Auto-run hooks** — what runs without you asking, grouped per tool config, and how many fire on every prompt or tool call
- **What its code can do** — shell commands, destructive commands, package installs, credential and secret access, download-into-shell, hidden Unicode, network domains
- **A footprint level** — `light` (instructions only), `moderate` (ships scripts or session hooks), `heavy` (hooks on every action, download-into-shell, or hidden characters). It describes how much a pack does, not whether it's safe.

It is not a malware scanner. Snyk Agent Scan, Mondoo, Socket and VirusTotal already do that. skillprint answers a different question: *what am I actually signing up for?*

## Install

```bash
pipx install skillprint
```

No pipx yet? `brew install pipx` on macOS, `sudo apt install pipx` on Debian/Ubuntu, or `python3 -m pip install --user pipx` anywhere, then `pipx ensurepath` and open a new terminal. pipx puts `skillprint` on your PATH in its own environment, so it never touches your system Python. Plain `pip install skillprint` works too.

No dependencies. Python 3.9+.

## Use

```bash
skillprint ~/.claude                                # what your Claude Code setup loads today
skillprint ./my-skills                              # a local folder
skillprint https://github.com/obra/superpowers      # any git URL
skillprint ./my-skills --details                    # every hook, finding, and the largest skills
skillprint ./my-skills --json                       # machine-readable
skillprint ./my-skills --badge                      # README badge markdown
skillprint ./my-skills --fail-on heavy              # exit 1 in CI if footprint is heavy
skillprint ~/.claude --html report.html             # one-page report to share (no network, safe to email)
skillprint ~/.claude --html r.html --internal-domain yourcompany.com --redact   # flag outside domains, hide internal names
skillprint diff ./skills-v1 ./skills-v2             # what changed between two versions
```

`skillprint diff OLD NEW` takes two folders or git URLs and lists skills, scripts, hooks, flagged code and network domains that were added or removed, plus skills whose `SKILL.md` changed (any edit, even one that keeps the size). `--json` and `--fail-on` work the same way (`--fail-on` checks the new version).

## What the most-starred packs look like

We scanned 24 of the most-starred skill repos on 12 October 2026. **Full results: [BENCHMARK.md](BENCHMARK.md).**

| Pack | Stars | Footprint | Skills | Names only in Claude Code (200k model) | Auto-run hooks (on every prompt or tool call) |
| --- | --- | --- | --- | --- | --- |
| [obra/superpowers](https://github.com/obra/superpowers) | 285k | moderate | 15 | 0 | 1 (0) |
| [affaan-m/ECC](https://github.com/affaan-m/ECC) | 268k | heavy | 314 | all 314 | 27 (15) |
| [mattpocock/skills](https://github.com/mattpocock/skills) | 260k | moderate | 38 | 0 | 0 |
| [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) | 212k | light | 1 | 0 | 0 |
| [Yeachan-Heo/oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) | 39k | heavy | 48 | 7 | 30 (9) |

Claude Code gives the whole skill list a small budget (about 1% of the context window). One large pack can use it all, so every skill, including your own, shows as a bare name and is rarely picked. And 7 of 18 packs run code on every prompt or tool call. None showed signs of malice; that's exactly what a star count hides.

## How it decides

- **`~/.claude`** is read as an install, not a pack: your own skills and `settings.json` hooks, plus the plugins listed in `plugins/installed_plugins.json` that are installed for your user and not disabled in `enabledPlugins`. The plugin marketplace catalogs (everything you *could* install), project-scoped plugins, transcripts and history are skipped.
- **Skills** are found by `SKILL.md`. Copies of the same skill (per-tool folders, translations) count once; the canonical copy is preferred.
- **Up-front tokens** = name + description of each skill, which agents load into every session so they know what's available. **On-use tokens** = the skill bodies. Both are estimated as characters ÷ 4.
- **Hooks** are read from hook, plugin and settings JSON files (`*hook*.json`, `plugin.json`, `settings.json`) and from every JSON file in GitHub Copilot's `.github/hooks/` and `~/.copilot/hooks/`, in Claude Code, Cursor, Codex, Copilot, Gemini CLI, Windsurf and Qoder formats, grouped by file, since you install one tool's config. Other JSON that happens to contain a `hooks` key is data, not config.
- **Capability patterns** are matched only where code can run: scripts, hook commands, and fenced code blocks inside `SKILL.md`. Mentions in docs and prose are counted separately and ignored — a security guide that says "never `curl | bash`" is not a finding. Whole-line comments and test files are skipped.
- **Download piped into a shell** counts only in shell contexts: shell scripts, hook commands and `SKILL.md` code blocks. In Python or JavaScript, `curl … | bash` is almost always an install hint in an error message.
- **Hidden Unicode** (zero-width and bidi-control characters) is checked across the whole `SKILL.md`, because the agent reads every word, plus shell scripts and hook commands. Joiners between two non-Latin characters (emoji, Persian, Arabic, Indic scripts) are normal writing and are not flagged.
- **Diff mode** matches skills by name, hooks by config file, event and command, and flagged code by file and line text, so a finding that only moved to a different line is not reported as new. A skill counts as changed when its `SKILL.md` content changed (a hash is kept per skill), even if its size did not.
- Counts describe **capability, not intent**. A `rm -rf "$TMP_DIR"` in a cleanup script is normal. Read the `--details` output before judging.
- **What the agent really sees.** Claude Code loads skills from `<skills folder>/<skill-name>/SKILL.md`, one level deep. A `SKILL.md` deeper than that, such as inside a whole repo copied into `~/.claude/skills`, is never loaded, so it's reported separately; its scripts, hooks and flagged lines are set aside too, because they never run. Scanning a GitHub repo treats every skill in it as installed.
- **The skill listing.** Claude Code lists every skill's name each turn and drops descriptions once the listing passes about 1% of the model's context window (≈2,000 tokens for a 200k model; use `--context-window 1000000` for 1M models). Each description is capped at 1,536 characters. Which skills keep their description depends on usage, which isn't visible on disk, so the split is an estimate.
- **Review first** = reads credential files, pipes a download into a shell, hidden Unicode. These are the few lines worth a human look; running shell commands is normal for tools and is shown as context only.

## Use it in CI

```yaml
# .github/workflows/skillprint.yml
name: skillprint
on: [pull_request]
jobs:
  footprint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install skillprint
      - run: skillprint . --details --fail-on heavy
```

## Roadmap

- [x] Footprint: context cost, hooks, capabilities, badge, CI mode
- [ ] Exact token counts per model tokenizer
- [x] Diff mode: what changed between two versions of a pack (`skillprint diff OLD NEW`)
- [ ] **Lift**: run a fixed task suite with and without a skill, per model, and report whether it actually helps
- [ ] Public ratings page for the most-starred skills
- [ ] Pull in Snyk / Socket / VirusTotal verdicts where they exist

## Contributing

Found a false positive or a pattern we miss? Open an issue with the file and line. Rules live in `skillprint/scan.py` and every rule has a test in `tests/`.

```bash
pip install -e . pytest && pytest
```

## License

MIT
