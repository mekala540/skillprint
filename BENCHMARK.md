# 24 of the most-starred agent skill repos, scanned

Scanned **12 October 2026** with skillprint 0.1.1; footprint labels renamed in 0.1.2 (low/medium/high → light/moderate/heavy). Star counts are approximate, taken from public rankings between 12 Sep and 12 Oct 2026 (sources in `benchmark/packs.txt`).

## Headline

- **Up-front context cost varies 400×.** Every installed skill puts its name and description into every session. Across the 18 packs below, that ranges from about 60 tokens (andrej-karpathy-skills) to about 25,600 (ECC). The median is about 1,200.
- **7 of 18 packs run code on every prompt or tool call** through auto-run hooks. Only one pack is pure instructions with no scripts or hooks.
- **No signs of malice in any pack.** "Heavy" means a pack loads a lot or runs code automatically and often, not that it is dangerous. Read `skillprint <repo> --details` before judging.

## Packs you install as a unit

| Pack | Stars | Footprint | Skills | Tokens up front | Auto-run hooks | …on every prompt or tool call | Scripts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [obra/superpowers](https://github.com/obra/superpowers) | 285k | moderate | 15 | ≈673 | 1 | 0 | 23 |
| [affaan-m/ECC](https://github.com/affaan-m/ECC) | 268k | heavy | 314 | ≈25,637 | 27 | 15 | 736 |
| [mattpocock/skills](https://github.com/mattpocock/skills) | 260k | moderate | 38 | ≈1,505 | 0 | 0 | 7 |
| [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) | 212k | light | 1 | ≈60 | 0 | 0 | 0 |
| [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) | 146k | heavy | 6 | ≈424 | 3 | 1 | 32 |
| [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | 131k | moderate | 7 | ≈689 | 0 | 0 | 97 |
| [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) | 108k | heavy | 22 | ≈1,085 | 4 | 1 | 215 |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | 99k | moderate | 25 | ≈2,341 | 0 | 0 | 22 |
| [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem) | 95k | heavy | 27 | ≈1,843 | 9 | 4 | 692 |
| [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | 90k | moderate | 13 | ≈1,197 | 0 | 0 | 6 |
| [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) | 63k | moderate | 1 | ≈65 | 0 | 0 | 132 |
| [blader/humanizer](https://github.com/blader/humanizer) | 52k | moderate | 1 | ≈89 | 0 | 0 | 1 |
| [Imbad0202/academic-research-skills](https://github.com/Imbad0202/academic-research-skills) | 50k | heavy | 5 | ≈1,202 | 2 | 1 | 242 |
| [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design) | 42k | moderate | 1 | ≈210 | 0 | 0 | 87 |
| [Yeachan-Heo/oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) | 39k | heavy | 48 | ≈2,115 | 30 | 9 | 822 |
| [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 34k | moderate | 177 | ≈17,895 | 0 | 0 | 539 |
| [OthmanAdi/planning-with-files](https://github.com/OthmanAdi/planning-with-files) | 26k | heavy | 6 | ≈884 | 7 | 3 | 404 |
| [phuryn/pm-skills](https://github.com/phuryn/pm-skills) | 25k | moderate | 69 | ≈4,888 | 0 | 0 | 1 |

*Auto-run hooks* counts the largest hook config the pack ships (packs often ship one per tool). *Heavy* = hooks that fire on every prompt or tool call, a download piped into a shell, or hidden characters in instructions.

## Catalogs you pick from

These repos are marketplaces or collections. You normally install a few plugins or skills from them, not everything, so the whole-repo totals are an upper bound, not what a user pays.

| Catalog | Stars | Kind | Skills | Tokens up front if installed whole |
| --- | --- | --- | --- | --- |
| [anthropics/skills](https://github.com/anthropics/skills) | 169k | marketplace, 5 plugin bundles | 20 | ≈2,448 |
| [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) | 76k | curated collection | 864 | ≈29,018 |
| [sickn33/agentic-awesome-skills](https://github.com/sickn33/agentic-awesome-skills) | 47k | marketplace, 59 plugins | 2,676 | ≈115,407 |
| [wshobson/agents](https://github.com/wshobson/agents) | 40k | marketplace, 94 plugins | 184 | ≈12,939 |
| [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | 37k | marketplace, 315 plugins | 29 | ≈2,896 |
| [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | 24k | marketplace, 99 plugins | 446 | ≈49,715 |

Not included: [gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done) (64k stars), which uses slash commands rather than `SKILL.md` skills.

## Method

- Shallow clone of each repo's default branch, scanned with `skillprint --json`.
- Tokens are estimated as characters ÷ 4.
- Patterns count only where code can run (scripts, hook commands, code blocks in `SKILL.md`); comments, docs and tests are ignored.
- Reproduce with `python benchmark/run.py`. Raw numbers: `benchmark/results.json`.

Spotted a wrong number for your pack? Open an issue. Every rule has a test and we fix false positives quickly.
