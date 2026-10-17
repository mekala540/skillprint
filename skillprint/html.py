"""One-page HTML report. Self-contained: no scripts, no fonts or images from the network,
so it can be opened offline, attached to an email and printed."""
from __future__ import annotations

import datetime as _dt
from html import escape

from .insights import Insights, LABELS, WORTH_A_LOOK
from .scan import Report

MAX_ROWS = 25

CSS = """
:root{--bg:#fbfaf7;--card:#fff;--ink:#1d1d1b;--muted:#6b6a64;--line:#e6e3dc;--accent:#2f5d8a;
--accent-soft:#e8eff6;--warn:#8a5a14;--warn-soft:#f7efe2;--bar:#c9d6e3}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--card:#1f1f1d;--ink:#ecebe6;--muted:#a3a19a;
--line:#34332f;--accent:#8cb4dc;--accent-soft:#22303d;--warn:#e0b067;--warn-soft:#352b1c;--bar:#3a4b5c}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",
Roboto,"Helvetica Neue",Arial,sans-serif}
main{max-width:980px;margin:0 auto;padding:40px 24px 56px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.01em}
h2{font-size:17px;margin:36px 0 12px}
.meta{color:var(--muted);font-size:13px}
.verdict{margin:22px 0 8px;padding:16px 18px;border-left:4px solid var(--accent);background:var(--accent-soft);
border-radius:6px;font-size:16px}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:18px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.tile .label{color:var(--muted);font-size:12.5px}
.tile .value{font-size:26px;font-weight:650;margin:2px 0;font-variant-numeric:tabular-nums}
.tile .sub{color:var(--muted);font-size:12.5px}
ol.actions{margin:0;padding-left:22px}
ol.actions li{margin:0 0 10px;padding-left:4px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;
overflow:hidden;font-size:13.5px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-weight:600;color:var(--muted);font-size:12.5px;background:var(--bg)}
tr:last-child td{border-bottom:0}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
code{font:12.5px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-wrap:anywhere}
.bar{height:6px;background:var(--bar);border-radius:3px;margin-top:5px}
.tag{display:inline-block;font-size:12px;padding:1px 8px;border-radius:999px;background:var(--warn-soft);
color:var(--warn);white-space:nowrap}
.muted{color:var(--muted)}
.note{color:var(--muted);font-size:12.5px;margin-top:8px}
footer{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:12.5px}
footer li{margin-bottom:4px}
@media (max-width:760px){.tiles{grid-template-columns:repeat(2,1fr)}}
@media print{body{background:#fff}main{padding:0}.tile,table{break-inside:avoid}}
"""


def _n(x: int) -> str:
    return f"{x:,}"


def render(r: Report, ins: Insights, version: str, hide=lambda t: t, shown_root: str | None = None) -> str:
    e = lambda t: escape(hide(str(t)))  # noqa: E731
    lst = ins.listing
    today = _dt.date.today().isoformat()
    root = shown_root or r.root
    kinds: dict[str, int] = {}
    for f in ins.review_first:
        kinds[f.kind] = kinds.get(f.kind, 0) + 1

    if r.layout != "pack":
        t1 = ("Skills the agent can use", _n(lst.skills),
              f"+{_n(ins.not_loaded)} never loaded" if ins.not_loaded else "all installed skills load")
    else:
        t1 = ("Skills in this pack", _n(len(r.skills)), f"{_n(r.skill_files)} SKILL.md files incl. copies"
              if r.skill_files != len(r.skills) else "no duplicate copies")
    t2 = ("Skill listing, every turn", f"≈{_n(lst.tokens)}",
          f"tokens · {_n(lst.names_only)} skills name-only" if lst.names_only else "tokens · all fully described")
    every = len(ins.every_action_hooks)
    t3 = ("Auto-run hooks", _n(len(r.hooks)), f"{_n(every)} on every prompt or tool call" if every else "none on every action")
    t4 = ("Review first", _n(len(ins.review_first)),
          ", ".join(f"{n} {LABELS[k].split(' (')[0]}" for k, n in kinds.items()) or "nothing flagged")

    h = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
         '<meta name="viewport" content="width=device-width,initial-scale=1">',
         f"<title>Agent skills report</title><style>{CSS}</style></head><body><main>",
         "<h1>Agent skills report</h1>",
         f'<div class="meta">{e(root)} · scanned {today} · skillprint {escape(version)}</div>',
         f'<div class="verdict">{e(ins.headline)}</div>',
         '<div class="tiles">']
    for label, value, sub in (t1, t2, t3, t4):
        h.append(f'<div class="tile"><div class="label">{escape(label)}</div><div class="value">{escape(value)}</div>'
                 f'<div class="sub">{e(sub)}</div></div>')
    h.append("</div>")

    h.append("<h2>Recommended actions</h2><ol class=\"actions\">")
    h += [f"<li>{e(a)}</li>" for a in ins.actions]
    h.append("</ol>")

    srcs = [s for s in ins.sources if s.skill_files or s.scripts or s.review_first][:MAX_ROWS]
    if srcs:
        top = max((s.skill_files for s in srcs), default=1) or 1
        h.append("<h2>Where the skills come from</h2><table><thead><tr><th>Source</th>"
                 "<th class=num>Skills the agent sees</th><th class=num>SKILL.md files</th>"
                 "<th class=num>Listing tokens</th><th class=num>Scripts</th><th class=num>Review first</th>"
                 "</tr></thead><tbody>")
        for s in srcs:
            width = max(1, int(100 * s.skill_files / top)) if s.skill_files else 0
            inner = int(100 * s.loaded / s.skill_files) if s.skill_files else 0
            bar = (f'<div class=bar style="width:{width}%"><div class=bar style="width:{inner}%;margin:0;'
                   f'background:var(--accent)"></div></div>') if width else ""
            h.append(f"<tr><td>{e(s.name)}{bar}</td>"
                     f"<td class=num>{_n(s.loaded)}</td><td class=num>{_n(s.skill_files)}</td>"
                     f"<td class=num>≈{_n(s.upfront_tokens)}</td><td class=num>{_n(s.scripts)}</td>"
                     f"<td class=num>{_n(s.review_first) if s.review_first else '–'}</td></tr>")
        h.append("</tbody></table>")
        h.append('<div class="note">Bar: all SKILL.md files in the source; dark part: the ones the agent '
                 'actually loads.</div>')

    if ins.review_first:
        h.append("<h2>Review first</h2><table><thead><tr><th style=width:20%>What</th><th style=width:34%>Where</th><th>Line</th></tr></thead><tbody>")
        for f in ins.review_first[:MAX_ROWS]:
            h.append(f"<tr><td><span class=tag>{escape(LABELS[f.kind])}</span></td>"
                     f"<td><code>{e(f.path)}:{f.line}</code></td><td><code>{e(f.excerpt)}</code></td></tr>")
        h.append("</tbody></table>")
        more = len(ins.review_first) - MAX_ROWS
        h.append(f'<div class="note">{"+" + _n(more) + " more: run with --details for the full list. " if more > 0 else ""}'
                 "These describe what code can do, not intent: most will be legitimate.</div>")

    if ins.every_action_hooks:
        h.append("<h2>Hooks that run on every prompt or tool call</h2><table><thead><tr><th>Event</th>"
                 "<th>Command</th><th>Config</th></tr></thead><tbody>")
        for hk in ins.every_action_hooks[:MAX_ROWS]:
            h.append(f"<tr><td>{e(hk.event)}</td><td><code>{e(hk.command[:160])}</code></td>"
                     f"<td><code>{e(hk.source)}</code></td></tr>")
        h.append("</tbody></table>")

    worth = [(k, n) for k, n in ins.worth_a_look.items() if k in WORTH_A_LOOK]
    if worth or ins.external_domains or ins.internal_domains:
        h.append("<h2>Other things its code can do</h2><ul>")
        for k, n in sorted(worth, key=lambda kv: -kv[1]):
            h.append(f"<li>{_n(n)} × {escape(LABELS[k])}</li>")
        if ins.external_domains:
            n = len(ins.external_domains)
            h.append(f"<li>Contacts {_n(n)} external domain{'' if n == 1 else 's'}: "
                     f"<code>{e(', '.join(ins.external_domains[:12]))}</code>"
                     f"{' …' if len(ins.external_domains) > 12 else ''}</li>")
        if ins.internal_domains:
            n = len(ins.internal_domains)
            h.append(f"<li>Contacts {_n(n)} internal domain{'' if n == 1 else 's'}</li>")
        h.append("</ul>")

    budget_note = (f"Claude Code lists every skill's name each turn and drops descriptions once the listing passes "
                   f"about 1% of the model's context window (≈{_n(lst.budget)} tokens for a "
                   f"{lst.context_window // 1000}k-token model). Which skills keep their description depends on "
                   f"usage, which isn't visible on disk, so the split is an estimate.")
    h.append("<footer><strong>How to read this</strong><ul>"
             "<li>Counts describe what code <em>can</em> do, not what it intends. Matches in docs, comments and "
             "tests are ignored.</li>"
             f"<li>{escape(budget_note)}</li>"
             "<li>Claude Code loads skills from <code>&lt;skills folder&gt;/&lt;skill-name&gt;/SKILL.md</code>; "
             "copies nested deeper are counted as never loaded.</li>"
             "<li>Token figures are estimates (characters ÷ 4).</li>"
             "<li>Generated locally by skillprint. Nothing was sent anywhere.</li>"
             "</ul></footer></main></body></html>")
    return "\n".join(h)
