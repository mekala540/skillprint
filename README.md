# skillprint

[![tests](https://github.com/mekala540/skillprint/actions/workflows/tests.yml/badge.svg)](https://github.com/mekala540/skillprint/actions/workflows/tests.yml) ![license](https://img.shields.io/badge/license-MIT-blue) ![python](https://img.shields.io/badge/python-3.9%2B-blue)

**See what an agent skill pack loads and runs — before you install it.**

Skill packs for Claude Code, Cursor, Codex and OpenClaw now collect hundreds of thousands of stars. Stars tell you a pack is popular. They don't tell you that it adds 25,000 tokens to every session, or registers 27 hooks that run code before your agent's tool calls.

`skillprint` reads a pack and reports:

- **Context cost** — tokens loaded up front every session (skill names and descriptions) and tokens loaded when skills are used
- **Auto-run hooks** — what runs without you asking, grouped per tool config, and how many fire on every prompt or tool call
- **What its code can do** — shell commands, destructive commands, package installs, credential and secret access, download-into-shell, hidden Unicode, network domains
- **A footprint level** — `low` (instructions only), `medium` (ships scripts or session hooks), `high` (hooks on every action, download-into-shell, or hidden characters)

It is not a malware scanner. Snyk Agent Scan, Mondoo, Socket and VirusTotal already do that. skillprint answers a different question: *what am I actually signing up for?*

## Install

```bash
pipx install skillprint        # or: pip install skillprint
```

No dependencies. Python 3.9+.

## Use

```bash
skillprint ./my-skills                              # a local folder
skillprint https://github.com/obra/superpowers      # any git URL
skillprint ./my-skills --details                    # every hook, finding, and the largest skills
skillprint ./my-skills --json                       # machine-readable
skillprint ./my-skills --badge                      # README badge markdown
skillprint ./my-skills --fail-on high               # exit 1 in CI if footprint is high
```

## What the most-starred packs look like

We scanned 24 of the most-starred skill repos on 12 October 2026. **Full results: [BENCHMARK.md](BENCHMARK.md).**

| Pack | Stars | Footprint | Tokens up front | Auto-run hooks (on every prompt or tool call) |
| --- | --- | --- | --- | --- |
| [obra/superpowers](https://github.com/obra/superpowers) | 285k | medium | ≈670 | 1 (0) |
| [affaan-m/ECC](https://github.com/affaan-m/ECC) | 268k | high | ≈25,600 | 27 (15) |
| [mattpocock/skills](https://github.com/mattpocock/skills) | 260k | medium | ≈1,500 | 0 |
| [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) | 212k | low | ≈60 | 0 |
| [Yeachan-Heo/oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) | 39k | high | ≈2,100 | 30 (9) |

Up-front context cost varies 400×, and 7 of 18 packs run code on every prompt or tool call. None showed signs of malice; that's exactly what a star count hides.

## How it decides

- **Skills** are found by `SKILL.md`. Copies of the same skill (per-tool folders, translations) count once; the canonical copy is preferred.
- **Up-front tokens** = name + description of each skill, which agents load into every session so they know what's available. **On-use tokens** = the skill bodies. Both are estimated as characters ÷ 4.
- **Hooks** are read from hook, plugin and settings JSON files (`*hook*.json`, `plugin.json`, `settings.json`) in Claude Code, Cursor, Codex and Qoder formats, grouped by file, since you install one tool's config. Other JSON that happens to contain a `hooks` key is data, not config.
- **Capability patterns** are matched only where code can run: scripts, hook commands, and fenced code blocks inside `SKILL.md`. Mentions in docs and prose are counted separately and ignored — a security guide that says "never `curl | bash`" is not a finding. Whole-line comments and test files are skipped.
- **Download piped into a shell** counts only in shell contexts: shell scripts, hook commands and `SKILL.md` code blocks. In Python or JavaScript, `curl … | bash` is almost always an install hint in an error message.
- **Hidden Unicode** (zero-width and bidi-control characters) is checked across the whole `SKILL.md`, because the agent reads every word, plus shell scripts and hook commands. Joiners between two non-Latin characters (emoji, Persian, Arabic, Indic scripts) are normal writing and are not flagged.
- Counts describe **capability, not intent**. A `rm -rf "$TMP_DIR"` in a cleanup script is normal. Read the `--details` output before judging.

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
      - run: skillprint . --details --fail-on high
```

## Roadmap

- [x] Footprint: context cost, hooks, capabilities, badge, CI mode
- [ ] Exact token counts per model tokenizer
- [ ] Diff mode: what changed between two versions of a pack
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
