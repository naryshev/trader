#!/usr/bin/env python3
"""Render reports/*.md into the Morning Ledger dashboard HTML.

Usage: python dashboard/build_dashboard.py [output.html]

Each report is a markdown file named YYYY-MM-DD*.md. Optional front-matter:

    ---
    headline: Portfolio $12,345.67 · Day +0.8% · No breaches
    ---

The newest report is rendered open; older ones collapse into <details>.
The output is a body-only HTML fragment suitable for publishing as a
claude.ai Artifact (no <html>/<head>/<body> wrapper).
"""

import html
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO / "reports"
MAX_HISTORY = 14


def parse_report(path: Path) -> dict:
    text = path.read_text().strip()
    headline = ""
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            key, _, value = line.partition(":")
            if key.strip() == "headline":
                headline = value.strip()
        text = text[m.end():].strip()
    date_str = path.stem[:10]
    try:
        date_label = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A, %B %-d, %Y")
    except ValueError:
        date_label = path.stem
    return {"date": date_str, "label": date_label, "headline": headline, "body": text}


def md_to_html(md: str) -> str:
    """Minimal markdown renderer: headings, lists, bold/code, paragraphs."""
    out: list[str] = []
    in_list = False

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    def inline(s: str) -> str:
        s = html.escape(s, quote=False)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        return s

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            close_list()
            continue
        h = re.match(r"^(#{1,4})\s+(.*)", line)
        if h:
            close_list()
            level = min(len(h.group(1)) + 1, 5)  # demote: report h1 -> h2
            out.append(f"<h{level}>{inline(h.group(2))}</h{level}>")
            continue
        li = re.match(r"^\s*[-*]\s+(.*)", line)
        if li:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(li.group(1))}</li>")
            continue
        close_list()
        out.append(f"<p>{inline(line)}</p>")
    close_list()
    return "\n".join(out)


CSS = """
:root {
  --paper: #F6F7F6; --surface: #FFFFFF; --ink: #17211C; --ink-soft: #55605A;
  --rule: #D9DED9; --accent: #2C4A6E; --gain: #12724B; --loss: #A73A28;
  --chip-bg: #EAEEEA; --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  --serif: Palatino, "Palatino Linotype", "Book Antiqua", Georgia, serif;
  --sans: system-ui, -apple-system, "Segoe UI", sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root { --paper: #111614; --surface: #171D1A; --ink: #E3E8E3; --ink-soft: #9AA69E;
          --rule: #2A322D; --accent: #93AECF; --gain: #57BD8C; --loss: #DE8A74;
          --chip-bg: #212925; }
}
:root[data-theme="dark"] { --paper: #111614; --surface: #171D1A; --ink: #E3E8E3;
  --ink-soft: #9AA69E; --rule: #2A322D; --accent: #93AECF; --gain: #57BD8C;
  --loss: #DE8A74; --chip-bg: #212925; }
:root[data-theme="light"] { --paper: #F6F7F6; --surface: #FFFFFF; --ink: #17211C;
  --ink-soft: #55605A; --rule: #D9DED9; --accent: #2C4A6E; --gain: #12724B;
  --loss: #A73A28; --chip-bg: #EAEEEA; }

body { background: var(--paper); color: var(--ink); font-family: var(--sans);
  margin: 0; line-height: 1.55; }
.wrap { max-width: 720px; margin: 0 auto; padding: 2.2rem 1.2rem 4rem; }

header.masthead { border-bottom: 2px solid var(--ink); padding-bottom: 1rem;
  margin-bottom: 1.6rem; display: flex; flex-wrap: wrap; align-items: baseline;
  gap: .4rem .8rem; }
.masthead h1 { font-family: var(--serif); font-size: 1.9rem; font-weight: 600;
  margin: 0; letter-spacing: .01em; }
.masthead .updated { margin-left: auto; color: var(--ink-soft); font-size: .8rem;
  font-family: var(--mono); }
.tagline { color: var(--ink-soft); font-size: .85rem; margin: .2rem 0 0;
  width: 100%; }

.report { background: var(--surface); border: 1px solid var(--rule);
  border-radius: 6px; padding: 1.4rem 1.5rem; margin-bottom: 1rem; }
.report .date { font-family: var(--mono); font-size: .78rem; text-transform: uppercase;
  letter-spacing: .09em; color: var(--accent); margin: 0 0 .3rem; }
.report .headline { font-family: var(--serif); font-size: 1.15rem; margin: 0 0 .8rem;
  text-wrap: balance; }
.report h2 { font-size: 1.05rem; border-bottom: 1px solid var(--rule);
  padding-bottom: .25rem; margin: 1.3rem 0 .5rem; }
.report h3 { font-size: .95rem; margin: 1rem 0 .35rem; }
.report p, .report li { font-size: .92rem; }
.report code { font-family: var(--mono); font-size: .85em; background: var(--chip-bg);
  padding: .08em .35em; border-radius: 3px; font-variant-numeric: tabular-nums; }
.report ul { padding-left: 1.2rem; margin: .3rem 0 .8rem; }

details.past { border: 1px solid var(--rule); border-radius: 6px; margin-bottom: .6rem;
  background: var(--surface); }
details.past summary { cursor: pointer; padding: .7rem 1rem; font-size: .9rem;
  display: flex; gap: .7rem; align-items: baseline; }
details.past summary::marker { color: var(--ink-soft); }
details.past summary .d { font-family: var(--mono); font-size: .78rem; color: var(--accent); }
details.past summary .h { color: var(--ink-soft); overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; }
details.past .inner { padding: 0 1.5rem 1.2rem; }
details.past summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

.empty { background: var(--surface); border: 1px dashed var(--rule); border-radius: 6px;
  padding: 2.2rem 1.5rem; text-align: center; color: var(--ink-soft); }
.empty h2 { font-family: var(--serif); color: var(--ink); margin: 0 0 .4rem; }
.gain { color: var(--gain); } .loss { color: var(--loss); }
footer { margin-top: 2.5rem; color: var(--ink-soft); font-size: .78rem;
  border-top: 1px solid var(--rule); padding-top: .8rem; }
"""


def colorize(fragment: str) -> str:
    """Wrap +$x.xx / -x.x% figures in gain/loss spans."""
    fragment = re.sub(r"(?<![\w>])(\+\$?[\d,]+(?:\.\d+)?%?)", r'<span class="gain">\1</span>', fragment)
    fragment = re.sub(r"(?<![\w>])(−|-)(\$?[\d,]+(?:\.\d+)?%)", r'<span class="loss">\1\2</span>', fragment)
    return fragment


def build() -> str:
    reports = sorted(
        (p for p in REPORTS_DIR.glob("*.md") if re.match(r"\d{4}-\d{2}-\d{2}", p.stem)),
        reverse=True,
    ) if REPORTS_DIR.exists() else []
    parsed = [parse_report(p) for p in reports[:MAX_HISTORY]]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    parts = [
        "<title>Morning Ledger</title>",
        f"<style>{CSS}</style>",
        '<div class="wrap">',
        '<header class="masthead">',
        "<h1>Morning Ledger</h1>",
        f'<span class="updated">updated {now}</span>',
        '<p class="tagline">Daily Robinhood report &middot; report-only, nothing is executed &middot; rules in STRATEGY.md</p>',
        "</header>",
    ]

    if not parsed:
        parts.append(
            '<div class="empty"><h2>Awaiting the first morning run</h2>'
            "<p>The agent reports here every morning around 8:00 AM ET.</p></div>"
        )
    else:
        latest = parsed[0]
        parts.append('<article class="report">')
        parts.append(f'<p class="date">{html.escape(latest["label"])}</p>')
        if latest["headline"]:
            parts.append(f'<p class="headline">{colorize(html.escape(latest["headline"], quote=False))}</p>')
        parts.append(colorize(md_to_html(latest["body"])))
        parts.append("</article>")

        if parsed[1:]:
            parts.append("<h2>Previous mornings</h2>")
        for r in parsed[1:]:
            parts.append('<details class="past"><summary>')
            parts.append(f'<span class="d">{html.escape(r["date"])}</span>')
            if r["headline"]:
                parts.append(f'<span class="h">{html.escape(r["headline"], quote=False)}</span>')
            parts.append('</summary><div class="inner">')
            parts.append(colorize(md_to_html(r["body"])))
            parts.append("</div></details>")

    parts.append("<footer>Generated by the trading agent. Proposals are not financial advice; "
                 "no orders are placed by this report.</footer>")
    parts.append("</div>")
    return "\n".join(parts)


if __name__ == "__main__":
    out = build()
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(out)
        print(f"wrote {sys.argv[1]} ({len(out)} bytes)")
    else:
        print(out)
