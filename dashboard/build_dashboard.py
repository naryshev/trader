#!/usr/bin/env python3
"""Render reports/*.md into the Morning Ledger dashboard HTML.

Usage: python dashboard/build_dashboard.py [output.html]

Each report is a markdown file named YYYY-MM-DD*.md. Optional front-matter:

    ---
    headline: Portfolio $12,345.67 · Day +0.8% · No breaches
    proposal: {"account_number":"...","symbol":"VOO","side":"buy","type":"market","dollar_amount":"10.95","note":"bootstrap buy"}
    ---

`proposal:` may repeat; each becomes an actionable card on the dashboard.
The page is published as a claude.ai Artifact with the `mcp` capability so
Refresh and Accept buttons call the viewer's Robinhood connector directly
(review -> explicit confirm -> place).
"""

import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO / "reports"
MAX_HISTORY = 14
# The agent-accessible ("Agentic") account; used for live refresh calls.
AGENTIC_ACCOUNT = "973317647"
MCP_SERVER = "Robinhood"


def parse_report(path: Path) -> dict:
    text = path.read_text().strip()
    headline = ""
    proposals: list[dict] = []
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            key, _, value = line.partition(":")
            key = key.strip()
            if key == "headline":
                headline = value.strip()
            elif key == "proposal":
                try:
                    proposals.append(json.loads(value.strip()))
                except json.JSONDecodeError:
                    pass
        text = text[m.end():].strip()
    date_str = path.stem[:10]
    session = " · closing bell" if "close" in path.stem else (" · opening bell" if "open" in path.stem else "")
    try:
        date_label = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A, %B %-d, %Y") + session
    except ValueError:
        date_label = path.stem
    short = date_str + (" close" if "close" in path.stem else (" open" if "open" in path.stem else ""))
    return {"date": short, "label": date_label, "headline": headline,
            "proposals": proposals, "body": text}


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
  --warn: #8A6A14; --chip-bg: #EAEEEA;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  --serif: Palatino, "Palatino Linotype", "Book Antiqua", Georgia, serif;
  --sans: system-ui, -apple-system, "Segoe UI", sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root { --paper: #111614; --surface: #171D1A; --ink: #E3E8E3; --ink-soft: #9AA69E;
          --rule: #2A322D; --accent: #93AECF; --gain: #57BD8C; --loss: #DE8A74;
          --warn: #D8B45E; --chip-bg: #212925; }
}
:root[data-theme="dark"] { --paper: #111614; --surface: #171D1A; --ink: #E3E8E3;
  --ink-soft: #9AA69E; --rule: #2A322D; --accent: #93AECF; --gain: #57BD8C;
  --loss: #DE8A74; --warn: #D8B45E; --chip-bg: #212925; }
:root[data-theme="light"] { --paper: #F6F7F6; --surface: #FFFFFF; --ink: #17211C;
  --ink-soft: #55605A; --rule: #D9DED9; --accent: #2C4A6E; --gain: #12724B;
  --loss: #A73A28; --warn: #8A6A14; --chip-bg: #EAEEEA; }

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
.tagline { color: var(--ink-soft); font-size: .85rem; margin: .2rem 0 0; width: 100%; }

button { font: inherit; cursor: pointer; border-radius: 5px;
  border: 1px solid var(--rule); background: var(--surface); color: var(--ink);
  padding: .45rem .9rem; }
button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
button.primary { background: var(--accent); border-color: var(--accent); color: var(--paper); }
button:disabled { opacity: .55; cursor: default; }

.live { background: var(--surface); border: 1px solid var(--rule); border-radius: 6px;
  padding: 1rem 1.2rem; margin-bottom: 1.2rem; }
.live .live-head { display: flex; align-items: center; gap: .8rem; flex-wrap: wrap; }
.live h2 { font-size: .8rem; text-transform: uppercase; letter-spacing: .09em;
  color: var(--accent); margin: 0; font-family: var(--mono); }
.live .live-updated { color: var(--ink-soft); font-size: .75rem; font-family: var(--mono);
  margin-left: auto; }
.live .figures { display: flex; flex-wrap: wrap; gap: .4rem 1.6rem; margin: .7rem 0 0;
  font-variant-numeric: tabular-nums; }
.live .fig { font-size: .9rem; }
.live .fig b { font-family: var(--mono); font-weight: 600; }
.live .fig .lbl { color: var(--ink-soft); font-size: .78rem; display: block; }
.live .msg { margin: .7rem 0 0; font-size: .85rem; color: var(--ink-soft); }
.live .msg.warn { color: var(--warn); }

.proposal-card { border: 1px solid var(--accent); border-radius: 6px;
  background: var(--surface); padding: .9rem 1.1rem; margin: .8rem 0; }
.proposal-card .p-title { font-weight: 600; font-size: .92rem; margin: 0 0 .2rem; }
.proposal-card .p-params { font-family: var(--mono); font-size: .8rem;
  color: var(--ink-soft); margin: 0 0 .6rem; overflow-x: auto; }
.proposal-card .p-note { font-size: .85rem; margin: 0 0 .6rem; }
.review-box { border-top: 1px solid var(--rule); margin-top: .7rem; padding-top: .7rem;
  font-size: .85rem; }
.review-box .disclosure { font-family: var(--mono); font-size: .75rem;
  color: var(--ink-soft); margin: .5rem 0; }
.review-box .alert { color: var(--warn); font-weight: 600; }
.review-box .actions { display: flex; gap: .6rem; margin-top: .6rem; }
.result-ok { color: var(--gain); font-weight: 600; }
.result-err { color: var(--loss); }

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

# JS uses __PLACEHOLDER__ substitution (not f-strings) to keep braces sane.
JS = r"""
(function () {
  "use strict";
  var SERVER = "__SERVER__";
  var ACCOUNT = "__ACCOUNT__";
  var PROPOSALS = __PROPOSALS__;

  var mcpOk = typeof window.claude !== "undefined" && window.claude.mcp !== undefined;
  var liveMsg = document.getElementById("live-msg");
  var refreshBtn = document.getElementById("refresh-btn");

  function fmtUsd(v) {
    var n = Number(v);
    return isNaN(n) ? String(v) : "$" + n.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
  }

  function errorCopy(err) {
    var code = err && err.code ? err.code : "upstream_error";
    switch (code) {
      case "needs_reauth":
        return "Robinhood needs to be reconnected — claude.ai Settings → Connectors → " + SERVER + ".";
      case "server_not_connected":
        return "Add the " + SERVER + " connector in claude.ai Settings → Connectors.";
      case "selection_required":
        return "Multiple " + SERVER + " connectors found — choose one in the claude.ai prompt, then retry.";
      case "not_in_manifest":
      case "blocked_by_policy":
      case "approval_required":
        return "This action isn't permitted from the page (" + code + ").";
      case "tool_error":
        return "Robinhood reported an error: " + (err.message || "unknown");
      case "server_unavailable":
        return "Robinhood is temporarily unreachable. Try again in a moment.";
      case "not_granted":
      case "capability_disabled":
      case "capability_removed":
        return "Live data isn't available in this view.";
      default:
        return "Something went wrong (" + code + "): " + (err.message || "");
    }
  }

  function setMsg(el, text, cls) {
    el.textContent = text;
    el.className = "msg" + (cls ? " " + cls : "");
  }

  // ---------- Live refresh ----------
  var refreshing = false;
  function refresh(force) {
    if (!mcpOk) { setMsg(liveMsg, "Live data isn't available in this view.", "warn"); return; }
    if (refreshing) return;
    refreshing = true;
    refreshBtn.disabled = true;
    setMsg(liveMsg, "Fetching…");
    var opts = force ? {cache: {refresh: true}} : {cache: {staleTime: 60000}};
    var receivedAt = null;

    window.claude.mcp.callTool(SERVER, "get_portfolio", {account_number: ACCOUNT}, opts)
      .then(function (res) {
        receivedAt = res.cache && res.cache.storedAt ? res.cache.storedAt : Date.now();
        var p = res.payload && res.payload.data ? res.payload.data : {};
        document.getElementById("fig-total").textContent = fmtUsd(p.total_value);
        document.getElementById("fig-cash").textContent = fmtUsd(p.cash);
        var bp = p.buying_power && p.buying_power.buying_power;
        document.getElementById("fig-bp").textContent = fmtUsd(bp);
        return window.claude.mcp.callTool(SERVER, "get_equity_positions", {account_number: ACCOUNT}, opts);
      })
      .then(function (res) {
        var positions = (res.payload && res.payload.data && res.payload.data.positions) || [];
        document.getElementById("fig-pos").textContent = String(positions.length);
        var when = new Date(receivedAt).toLocaleTimeString();
        document.getElementById("live-updated").textContent = "as of " + when;
        setMsg(liveMsg, positions.length === 0 ? "No open positions." : "");
      })
      .catch(function (err) {
        var retriable = err && err.retryable === true;
        if (retriable && force !== "retried") {
          var delay = (err.retryAfterMs || 1500) + Math.random() * 500;
          setTimeout(function () { refreshing = false; refresh("retried"); }, delay);
          return;
        }
        setMsg(liveMsg, errorCopy(err), "warn");
      })
      .finally(function () { refreshing = false; refreshBtn.disabled = false; });
  }
  if (refreshBtn) {
    refreshBtn.addEventListener("click", function () { refresh(true); });
    refresh(false); // initial load, cache-friendly
  }

  // ---------- On-demand option scan ("Find fresh options") ----------
  var UNIVERSE = ["F", "SOFI", "PLTR", "AAL", "NIO", "LCID", "INTC"];
  var scanBtn = document.getElementById("scan-btn");
  var scanOut = document.getElementById("scan-out");

  function dte(expStr) {
    var d = new Date(expStr + "T21:00:00Z");
    return Math.round((d - Date.now()) / 86400000);
  }
  function pickList(obj, keys) {
    for (var i = 0; i < keys.length; i++) {
      var v = obj && obj[keys[i]];
      if (Array.isArray(v)) return v;
    }
    return null;
  }
  function num(v) { var n = Number(v); return isNaN(n) ? null : n; }

  async function callData(tool, input) {
    var res = await window.claude.mcp.callTool(SERVER, tool, input, {cache: false});
    var p = res.payload;
    if (p && typeof p === "object" && p.data) return p.data;
    if (p && typeof p === "object") return p;
    throw {code: "shape", message: tool + " returned an unexpected payload"};
  }

  // Request/response shapes verified against live calls on 2026-07-21.
  async function scanSymbol(sym, budget, found) {
    var chainsData = await callData("get_option_chains", {underlying_symbol: sym});
    var chain = (pickList(chainsData, ["chains"]) || [])[0] || {};
    var exps = (chain.expiration_dates || [])
      .map(String).filter(function (e) { var d = dte(e); return d >= 7 && d <= 30; }).slice(0, 3);
    if (!exps.length || !chain.id) return sym + ": no expirations in the 7–30 day window";

    var px = null;
    try {
      var eq = await callData("get_equity_quotes", {symbols: [sym]});
      var q0 = (pickList(eq, ["results"]) || [])[0] || {};
      px = num((q0.quote || q0).last_trade_price);
    } catch (e) { /* ranking degrades gracefully without underlying price */ }

    var instData = await callData("get_option_instruments",
      {chain_id: chain.id, expiration_dates: exps.join(",")});
    var insts = (pickList(instData, ["instruments"]) || []).map(function (it) {
      return {id: it.id, strike: num(it.strike_price), kind: it.type,
              exp: String(it.expiration_date)};
    }).filter(function (it) { return it.id && it.strike; });
    if (px) insts.sort(function (a, b) { return Math.abs(a.strike - px) - Math.abs(b.strike - px); });
    insts = insts.slice(0, 16);
    if (!insts.length) return sym + ": no contracts listed";

    var quotesData = await callData("get_option_quotes",
      {instrument_ids: insts.map(function (it) { return it.id; })});
    (pickList(quotesData, ["results"]) || []).forEach(function (r) {
      var q = r.quote || r;
      var inst = insts.filter(function (it) { return it.id === q.instrument_id; })[0];
      if (!inst) return;
      var bid = num(q.bid_price), ask = num(q.ask_price);
      var oi = num(q.open_interest);
      if (bid == null || ask == null || ask <= 0) return;
      var mid = (bid + ask) / 2;
      var cost = mid * 100;
      var spreadFrac = mid > 0 ? (ask - bid) / mid : 1;
      if (cost > budget || cost <= 0) return;
      if (spreadFrac > 0.25) return;
      if (oi != null && oi < 100) return;
      found.push({sym: sym, kind: inst.kind, strike: inst.strike, exp: inst.exp,
                  mid: mid, cost: cost, spread: spreadFrac, oi: oi,
                  dist: px ? Math.abs(inst.strike - px) / px : 9});
    });
    return null;
  }

  async function runScan() {
    scanBtn.disabled = true;
    scanOut.innerHTML = '<p class="msg">Scanning…</p>';
    var notes = [];
    try {
      var port = await callData("get_portfolio", {account_number: ACCOUNT});
      var budget = num(port.cash) || 0;
      if (budget < 1) {
        scanOut.innerHTML = '<p class="msg warn">No cash available to scan against.</p>';
        return;
      }
      var found = [];
      for (var i = 0; i < UNIVERSE.length && found.length < 8; i++) {
        var sym = UNIVERSE[i];
        scanOut.innerHTML = '<p class="msg">Scanning ' + sym + "… (" + found.length + " candidates so far)</p>";
        try {
          var note = await scanSymbol(sym, budget, found);
          if (note) notes.push(note);
        } catch (err) {
          if (err && err.code === "shape") { notes.push(sym + ": " + err.message); continue; }
          if (err && (err.code === "needs_reauth" || err.code === "server_not_connected" ||
                      err.code === "not_granted" || err.code === "capability_disabled")) throw err;
          notes.push(sym + ": " + (err && err.message ? String(err.message).slice(0, 120) : "failed"));
        }
      }
      found.sort(function (a, b) { return (a.dist - b.dist) || ((b.oi || 0) - (a.oi || 0)); });
      var top = found.slice(0, 5);
      var h = "<h3>Fresh candidates (budget " + fmtUsd(budget) + ")</h3>";
      if (!top.length) {
        h += '<p class="msg warn">Nothing passes the gates right now (cost ≤ budget, spread ≤ 25% of mid, OI ≥ 100, 7–30 DTE).</p>';
      }
      top.forEach(function (c) {
        h += '<div class="proposal-card"><p class="p-title">' +
          c.sym + " " + String(c.kind).toUpperCase() + " $" + c.strike + " exp " + c.exp +
          " · " + dte(c.exp) + "d</p>" +
          '<p class="p-params">limit at mid ' + fmtUsd(c.mid) + "/sh · cost ≈ " + fmtUsd(c.cost) +
          " · spread " + Math.round(c.spread * 100) + "% · OI " + (c.oi == null ? "?" : c.oi) + "</p>" +
          '<p class="p-note">Execute manually in the Robinhood app (limit order at the mid).</p></div>';
      });
      if (notes.length) {
        h += '<p class="msg">' + notes.map(function (n) { return n.replace(/[<>&]/g, ""); }).join(" · ") + "</p>";
      }
      scanOut.innerHTML = h;
    } catch (err) {
      scanOut.innerHTML = '<p class="msg warn">' + errorCopy(err).replace(/[<>&]/g, "") + "</p>";
    } finally {
      scanBtn.disabled = false;
    }
  }
  if (scanBtn) {
    if (!mcpOk) { scanBtn.disabled = true; }
    else scanBtn.addEventListener("click", function () { runScan(); });
  }

  // ---------- Proposal accept flow: review -> explicit confirm -> place ----------
  function uuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      var r = Math.random() * 16 | 0; return (c === "x" ? r : (r & 3 | 8)).toString(16);
    });
  }

  function orderParams(p) {
    var o = {account_number: p.account_number || ACCOUNT, symbol: p.symbol,
             side: p.side, type: p.type};
    ["quantity", "dollar_amount", "limit_price", "stop_price", "time_in_force",
     "market_hours"].forEach(function (k) { if (p[k] != null) o[k] = String(p[k]); });
    return o;
  }

  PROPOSALS.forEach(function (p, i) {
    var card = document.getElementById("prop-" + i);
    if (!card) return;
    var acceptBtn = card.querySelector(".accept-btn");
    var box = card.querySelector(".review-box");
    if (!mcpOk) { acceptBtn.disabled = true; acceptBtn.textContent = "Unavailable in this view"; return; }

    acceptBtn.addEventListener("click", function () {
      acceptBtn.disabled = true;
      box.hidden = false;
      box.innerHTML = "<p>Requesting broker review…</p>";
      window.claude.mcp.callTool(SERVER, "review_equity_order", orderParams(p), {cache: false})
        .then(function (res) {
          var d = (res.payload && res.payload.data) || {};
          var q = d.quote_data || {};
          var checks = d.order_checks || {};
          var checkKeys = Object.keys(checks);
          var el = document.createElement("div");
          var head = document.createElement("p");
          head.innerHTML = "<strong>Broker review</strong> — last trade " +
            fmtUsd(q.last_trade_price) + ", bid " + fmtUsd(q.bid_price) +
            ", ask " + fmtUsd(q.ask_price);
          el.appendChild(head);
          if (checkKeys.length) {
            checkKeys.forEach(function (k) {
              var a = document.createElement("p");
              a.className = "alert";
              a.textContent = "Alert (" + k + "): " + JSON.stringify(checks[k]);
              el.appendChild(a);
            });
          } else {
            var ok = document.createElement("p");
            ok.textContent = "No broker alerts.";
            el.appendChild(ok);
          }
          if (d.market_data_disclosure) {
            // Compliance: shown verbatim, unmodified.
            var disc = document.createElement("p");
            disc.className = "disclosure";
            disc.textContent = d.market_data_disclosure;
            el.appendChild(disc);
          }
          var actions = document.createElement("div");
          actions.className = "actions";
          var confirmBtn = document.createElement("button");
          confirmBtn.className = "primary";
          confirmBtn.textContent = "Confirm — place real order";
          var cancelBtn = document.createElement("button");
          cancelBtn.textContent = "Cancel";
          actions.appendChild(confirmBtn);
          actions.appendChild(cancelBtn);
          el.appendChild(actions);
          box.innerHTML = "";
          box.appendChild(el);

          cancelBtn.addEventListener("click", function () {
            box.hidden = true; box.innerHTML = ""; acceptBtn.disabled = false;
          });
          confirmBtn.addEventListener("click", function () {
            confirmBtn.disabled = true; cancelBtn.disabled = true;
            var params = orderParams(p);
            params.ref_id = uuid();
            box.insertAdjacentHTML("beforeend", "<p>Placing order…</p>");
            window.claude.mcp.callTool(SERVER, "place_equity_order", params, {cache: false})
              .then(function (res2) {
                var d2 = (res2.payload && res2.payload.data) || res2.payload || {};
                var state = d2.state || (d2.order && d2.order.state) || "submitted";
                box.insertAdjacentHTML("beforeend",
                  '<p class="result-ok">Order submitted (state: ' +
                  String(state).replace(/[<>&]/g, "") +
                  "). Verify in the Robinhood app.</p>");
              })
              .catch(function (err) {
                var code = err && err.code;
                if (code === "server_unavailable" || code === "upstream_error" || code === "cancelled") {
                  box.insertAdjacentHTML("beforeend",
                    '<p class="result-err">The order attempt did not confirm — but it MAY still have gone through. ' +
                    "Check the Robinhood app before trying again.</p>");
                } else {
                  box.insertAdjacentHTML("beforeend",
                    '<p class="result-err">Order not placed. ' + errorCopy(err).replace(/[<>&]/g, "") + "</p>");
                }
              });
          });
        })
        .catch(function (err) {
          box.innerHTML = '<p class="result-err">Review failed — no order was placed. ' +
            errorCopy(err).replace(/[<>&]/g, "") + "</p>";
          acceptBtn.disabled = false;
        });
    });
  });
})();
"""


def colorize(fragment: str) -> str:
    """Wrap +$x.xx / -x.x% figures in gain/loss spans."""
    fragment = re.sub(r"(?<![\w>])(\+\$?[\d,]+(?:\.\d+)?%?)", r'<span class="gain">\1</span>', fragment)
    fragment = re.sub(r"(?<![\w>])(−|-)(\$?[\d,]+(?:\.\d+)?%)", r'<span class="loss">\1\2</span>', fragment)
    return fragment


def describe_proposal(p: dict) -> str:
    bits = [str(p.get("side", "")).upper(), str(p.get("symbol", ""))]
    if p.get("dollar_amount"):
        bits.append(f"${p['dollar_amount']}")
    if p.get("quantity"):
        bits.append(f"{p['quantity']} sh")
    bits.append(str(p.get("type", "")))
    if p.get("limit_price"):
        bits.append(f"limit ${p['limit_price']}")
    return " · ".join(b for b in bits if b)


def build() -> str:
    # Two reports per trading day: -open and -close. For a given date the
    # close run outranks the open run.
    reports = sorted(
        (p for p in REPORTS_DIR.glob("*.md") if re.match(r"\d{4}-\d{2}-\d{2}", p.stem)),
        key=lambda p: (p.stem[:10], "close" in p.stem, p.stem),
        reverse=True,
    ) if REPORTS_DIR.exists() else []
    parsed = [parse_report(p) for p in reports[:MAX_HISTORY]]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    proposals = parsed[0]["proposals"] if parsed else []

    parts = [
        "<title>Morning Ledger</title>",
        f"<style>{CSS}</style>",
        '<div class="wrap">',
        '<header class="masthead">',
        "<h1>Morning Ledger</h1>",
        f'<span class="updated">report generated {now}</span>',
        '<p class="tagline">Daily Robinhood report &middot; the daily run never trades &middot; '
        "orders happen only when you confirm them below</p>",
        "</header>",
        # Live panel
        '<section class="live">',
        '<div class="live-head"><h2>Live account</h2>'
        '<button id="refresh-btn" type="button">Refresh</button>'
        '<button id="scan-btn" type="button">Find fresh options</button>'
        '<span class="live-updated" id="live-updated"></span></div>',
        '<div class="figures">'
        '<span class="fig"><span class="lbl">Account value</span><b id="fig-total">—</b></span>'
        '<span class="fig"><span class="lbl">Cash</span><b id="fig-cash">—</b></span>'
        '<span class="fig"><span class="lbl">Buying power</span><b id="fig-bp">—</b></span>'
        '<span class="fig"><span class="lbl">Positions</span><b id="fig-pos">—</b></span>'
        "</div>",
        '<p class="msg" id="live-msg"></p>',
        '<div id="scan-out"></div>',
        "</section>",
    ]

    # Actionable proposals from the latest report. Only plain equity orders get
    # an Accept button — the on-page flow speaks review/place_equity_order.
    # Option proposals (legs/strike/expiration/option_id) render info-only.
    OPTION_KEYS = ("legs", "option_id", "strike", "expiration", "price")
    equity_proposals: list[dict] = []
    for p in proposals:
        parts_idx = len(equity_proposals)
        is_option = any(k in p for k in OPTION_KEYS) or p.get("instrument") == "option"
        card_id = f'id="prop-{parts_idx}"' if not is_option else ""
        parts.append(f'<div class="proposal-card" {card_id}>')
        parts.append(f'<p class="p-title">Proposed: {html.escape(describe_proposal(p))}</p>')
        if p.get("note"):
            parts.append(f'<p class="p-note">{html.escape(str(p["note"]))}</p>')
        shown = {k: v for k, v in p.items() if k not in ("note",)}
        if "account_number" in shown:
            shown["account_number"] = "••••" + str(shown["account_number"])[-4:]
        parts.append(f'<p class="p-params">{html.escape(json.dumps(shown))}</p>')
        if is_option:
            parts.append('<p class="p-note">Option order — execute manually in the '
                         "Robinhood app for now.</p>")
        else:
            parts.append('<button class="accept-btn" type="button">Accept — review with broker</button>')
            parts.append('<div class="review-box" hidden></div>')
            equity_proposals.append(p)
        parts.append("</div>")

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

    parts.append("<footer>Generated by the trading agent. Proposals are not financial advice. "
                 "The daily run is report-only; an order is placed only when you press "
                 "Confirm after a broker review on this page.</footer>")
    parts.append("</div>")

    js = (JS.replace("__SERVER__", MCP_SERVER)
            .replace("__ACCOUNT__", AGENTIC_ACCOUNT)
            .replace("__PROPOSALS__", json.dumps(equity_proposals)))
    parts.append(f"<script>{js}</script>")
    return "\n".join(parts)


if __name__ == "__main__":
    out = build()
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(out)
        print(f"wrote {sys.argv[1]} ({len(out)} bytes)")
    else:
        print(out)
