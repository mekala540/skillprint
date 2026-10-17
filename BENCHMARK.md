# 24 of the most-starred agent skill repos, scanned

Scanned **12 October 2026**; listing figures recomputed with skillprint 0.2.0, which models Claude Code's skill-listing budget. Footprint labels renamed in 0.1.2 (low/medium/high → light/moderate/heavy). Star counts are approximate, taken from public rankings between 12 Sep and 12 Oct 2026 (sources in `benchmark/packs.txt`).

## Headline

- **One big pack crowds out every other skill.** Claude Code lists every installed skill's name each turn, and drops descriptions once that listing passes about 1% of the model's context window: roughly 2,000 tokens on a 200k-token model, 10,000 on a 1M-token model. ECC ships about 26,500 tokens of descriptions for 314 skills, so on its own it pushes **every** skill, your own included, down to a bare name on a 200k model. K-Dense (177 skills) and wshobson/agents (184) do nearly the same. Small packs (andrej-karpathy-skills ≈63 tokens, superpowers ≈716) fit with room to spare.
- **7 of 18 packs run code on every prompt or tool call** through auto-run hooks. Only one pack is pure instructions with no scripts or hooks.
- **No signs of malice in any pack.** "Heavy" means a pack loads a lot or runs code automatically and often, not that it is dangerous. Read `skillprint <repo> --details` before judging.

## Packs you install as a unit

| Pack | Stars | Footprint | Skills | Descriptions shipped (tokens) | Names only in Claude Code (200k / 1M model) | Auto-run hooks | …on every prompt or tool call | Scripts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [obra/superpowers](https://github.com/obra/superpowers) | 285k | moderate | 15 | ≈716 | 0 / 0 | 1 | 0 | 23 |
| [affaan-m/ECC](https://github.com/affaan-m/ECC) | 268k | heavy | 314 | ≈26,543 | 314 / 216 | 27 | 15 | 736 |
| [mattpocock/skills](https://github.com/mattpocock/skills) | 260k | moderate | 38 | ≈1,618 | 0 / 0 | 0 | 0 | 7 |
| [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) | 212k | light | 1 | ≈63 | 0 / 0 | 0 | 0 | 0 |
| [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) | 146k | heavy | 6 | ≈440 | 0 / 0 | 3 | 1 | 32 |
| [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | 131k | moderate | 7 | ≈712 | 0 / 0 | 0 | 0 | 97 |
| [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) | 108k | heavy | 22 | ≈1,149 | 0 / 0 | 4 | 1 | 215 |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | 99k | moderate | 25 | ≈2,409 | 5 / 0 | 0 | 0 | 22 |
| [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem) | 95k | heavy | 27 | ≈1,920 | 0 / 0 | 9 | 4 | 692 |
| [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | 90k | moderate | 13 | ≈1,238 | 0 / 0 | 0 | 0 | 6 |
| [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) | 63k | moderate | 1 | ≈68 | 0 / 0 | 0 | 0 | 132 |
| [blader/humanizer](https://github.com/blader/humanizer) | 52k | moderate | 1 | ≈92 | 0 / 0 | 0 | 0 | 1 |
| [Imbad0202/academic-research-skills](https://github.com/Imbad0202/academic-research-skills) | 50k | heavy | 5 | ≈1,217 | 0 / 0 | 2 | 1 | 242 |
| [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design) | 42k | moderate | 1 | ≈213 | 0 / 0 | 0 | 0 | 87 |
| [Yeachan-Heo/oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) | 39k | heavy | 48 | ≈2,248 | 7 / 0 | 30 | 9 | 822 |
| [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 34k | moderate | 177 | ≈18,401 | 169 / 87 | 0 | 0 | 539 |
| [OthmanAdi/planning-with-files](https://github.com/OthmanAdi/planning-with-files) | 26k | heavy | 6 | ≈900 | 0 / 0 | 7 | 3 | 404 |
| [phuryn/pm-skills](https://github.com/phuryn/pm-skills) | 25k | moderate | 69 | ≈5,090 | 47 / 0 | 0 | 0 | 1 |

*Names only*: how many of the pack's skills Claude Code would list without a description if this pack were all you had installed. Which ones depends on use. *Auto-run hooks* counts the largest hook config the pack ships (packs often ship one per tool). *Heavy* = hooks that fire on every prompt or tool call, a download piped into a shell, or hidden characters in instructions.

## Catalogs you pick from

These repos are marketplaces or collections. You normally install a few plugins or skills from them, not everything, so the whole-repo totals are an upper bound, not what a user pays.

| Catalog | Stars | Kind | Skills | Descriptions shipped (tokens) | Names only if installed whole (200k / 1M model) |
| --- | --- | --- | --- | --- | --- |
| [anthropics/skills](https://github.com/anthropics/skills) | 169k | marketplace, 5 plugin bundles | 20 | ≈2,504 | 5 / 0 |
| [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) | 76k | curated collection | 864 | ≈31,585 | 864 / 766 |
| [sickn33/agentic-awesome-skills](https://github.com/sickn33/agentic-awesome-skills) | 47k | marketplace, 59 plugins | 2,676 | ≈123,309 | 2,676 / 2,676 |
| [wshobson/agents](https://github.com/wshobson/agents) | 40k | marketplace, 94 plugins | 184 | ≈13,477 | 178 / 54 |
| [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | 37k | marketplace, 315 plugins | 29 | ≈2,980 | 11 / 0 |
| [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | 24k | marketplace, 99 plugins | 446 | ≈50,978 | 446 / 384 |

Not included: [gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done) (64k stars), which uses slash commands rather than `SKILL.md` skills.

## Method

- Shallow clone of each repo's default branch, scanned with `skillprint --json`.
- Tokens are estimated as characters ÷ 4. The listing budget follows the Claude Code docs ("Skill descriptions are cut short"): names always listed, descriptions dropped past about 1% of the context window, each description capped at 1,536 characters.
- Patterns count only where code can run (scripts, hook commands, code blocks in `SKILL.md`); comments, docs and tests are ignored.
- Reproduce with `python benchmark/run.py`. Raw numbers: `benchmark/results.json`.

Spotted a wrong number for your pack? Open an issue. Every rule has a test and we fix false positives quickly.
