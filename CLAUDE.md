# skillprint

CLI that reports what an AI agent skill pack loads and runs before you install it:
context tokens (up front and on use), auto-run hooks, scripts, and risky commands,
rolled up into a `light` / `moderate` / `heavy` footprint (size, not danger; never call a pack risky or dangerous). It describes capability, not
intent. It is not a malware scanner.

## Setup and tests

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e . pytest
pytest -q                      # unit tests
skillprint . --json > /dev/null  # smoke test, same as CI
```

No runtime dependencies; keep it that way. Supports Python 3.9+ (CI runs 3.9, 3.11 and 3.13),
so no syntax newer than 3.9 outside `from __future__ import annotations`.

## Code layout

- `skillprint/scan.py`: rules and scanning. `PATTERNS` (capability regexes),
  `HIDDEN_UNICODE`, `TEST_PATH`, `PLACEHOLDER_DOMAIN`, hook event sets, the
  `Skill`/`Hook`/`Finding`/`Report` dataclasses, footprint logic (`Report.footprint`),
  and `scan(root)`, the single entry point.
- `skillprint/insights.py`: turns a scan into conclusions. Claude Code listing-budget model
  (`listing`), sources, "review first" priorities, plain-language recommended actions, redaction.
  Wording here is shown to leadership: neutral, specific, never "risky" or "dangerous".
- `skillprint/html.py`: the one-page `--html` report. Self-contained: no scripts, no network
  assets, everything escaped. Keep it that way so it can be emailed and opened offline.
- `skillprint/cli.py`: output only. Text report, `--details`, `--json`, `--badge`,
  `--fail-on`, git URL cloning. No detection logic belongs here.
- `tests/test_scan.py`: builds fake packs in `tmp_path` with the `write()` helper.

## Rules

- **Every new pattern needs a test.** Add or change an entry in `PATTERNS` (or any
  other rule in `scan.py`) together with a test in `tests/` that shows it matches
  real code. If false positives are a risk, add a test that shows it does not match them too.
- **Matches in docs and tests must never be counted as findings.** Patterns count as
  findings only where code can run: scripts, hook commands, and fenced code blocks
  inside `SKILL.md`. Matches in prose or docs go to `doc_mentions` (`_scan_text` with
  `as_findings=False`), and files that match `TEST_PATH` are skipped. A security guide
  that says "never `curl | bash`" is not a finding. Don't weaken this when adding rules.
- Duplicate skills (per-tool folders, translations) count once, and the canonical copy wins.
- Token estimates are characters ÷ 4 (`est_tokens`).
- In Claude Code layouts (`~/.claude`, a `.claude/skills` folder) only `<skills dir>/<name>/SKILL.md`
  loads; anything deeper is "never loaded" and its scripts, hooks and findings are set aside
  (`_set_aside_inactive`). A scanned repo (`layout == "pack"`) counts every skill as installed.
- The listing model follows the Claude Code docs: names always listed, descriptions dropped past
  ~1% of the context window, 1,536-char cap per description. If those docs change, update
  `insights.py`, README "How it decides" and the HTML footer together.
- Keep README's "How it decides" section in sync with any behavior change.

## Roadmap (from README)

- [x] Footprint: context cost, hooks, capabilities, badge, CI mode
- [ ] Exact token counts per model tokenizer
- [ ] Diff mode: what changed between two versions of a pack
- [ ] **Lift**: run a fixed task suite with and without a skill, per model, and report whether it helps
- [ ] Public ratings page for the most-starred skills
- [ ] Pull in Snyk / Socket / VirusTotal verdicts where they exist
