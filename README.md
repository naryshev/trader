# Robinhood Trading Agent

An autonomous trading agent built on the **Claude Agent SDK**. Each run, the
agent reads [`STRATEGY.md`](STRATEGY.md), inspects your Robinhood account
through the official Robinhood trading MCP server, applies the strategy, and
writes a report. It starts in **report-only mode**: it proposes trades but a
hard guardrail blocks every order tool until you explicitly go live.

## How it works

```
run_agent.py
  └─ trading_agent/agent.py      builds ClaudeAgentOptions and runs query()
       ├─ MCP: robinhood         https://agent.robinhood.com/mcp/trading
       ├─ hooks: guardrails.py   PreToolUse hook — blocks/permits order tools
       ├─ hooks: journal.py      JSONL audit log of every tool call
       └─ STRATEGY.md            the trading rules the model follows
```

The safety model has two layers:

1. **Prompt-level** — `STRATEGY.md` and the system prompt tell the model what
   to do (review before placing, report structure, when to do nothing).
2. **Hook-level (hard)** — a `PreToolUse` hook runs outside the model and
   denies `place_equity_order` / `place_option_order` unless every check
   passes. The model cannot talk its way past this layer.

Hard checks enforced by the hook:

| Check | Setting | Default |
|---|---|---|
| Report-only vs live | `TRADING_MODE` | `report` (orders blocked) |
| Pinned account | `ROBINHOOD_ACCOUNT_NUMBER` | unset (orders blocked in live) |
| Per-order notional cap | `MAX_ORDER_NOTIONAL_USD` | `200` |
| Max orders per run | `MAX_TRADES_PER_RUN` | `3` |
| Symbol allowlist | `ALLOWED_SYMBOLS` (comma-separated) | empty = any |
| Options trading | `ALLOW_OPTIONS` | `false` |
| Review before place | always on | — |
| Unbounded market buys | always denied (use `dollar_amount` or a limit) | — |

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**Anthropic auth** — one of:
- `export ANTHROPIC_API_KEY=sk-ant-...`, or
- an existing Claude Code login on this machine (the SDK reuses it).

**Robinhood MCP auth** — one of:
- Run `claude` in this repo once and complete the OAuth flow (`/mcp`); the SDK
  reuses the stored credentials for the `.mcp.json` server, or
- `export ROBINHOOD_MCP_TOKEN=...` if you have a bearer token; it is sent as
  an `Authorization` header.

## Run

```bash
# Report-only (default): analyzes and proposes, places nothing
python run_agent.py

# Live, with tight limits
TRADING_MODE=live \
ROBINHOOD_ACCOUNT_NUMBER=YOUR_ACCOUNT \
MAX_ORDER_NOTIONAL_USD=100 \
MAX_TRADES_PER_RUN=2 \
ALLOWED_SYMBOLS=VOO,VTI \
python run_agent.py
```

Each run writes:
- `journal/run-<id>.jsonl` — every tool call and result (audit trail)
- `journal/reports/report-<id>.md` — the agent's run report

## Run it on a schedule

Cron example (weekdays at 10:30 ET, report-only):

```cron
30 10 * * 1-5  cd /path/to/trader && .venv/bin/python run_agent.py >> journal/cron.log 2>&1
```

Recommended rollout: run report-only on a schedule for a week or two, read the
reports, then flip `TRADING_MODE=live` with a small `MAX_ORDER_NOTIONAL_USD`
and a short `ALLOWED_SYMBOLS` list.

## Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

The tests cover the guardrail decision logic (mode gating, account pinning,
notional caps, allowlist, review-before-place, trade counting, options gating).

## Disclaimer

This software places real orders with real money when `TRADING_MODE=live`.
Nothing here is financial advice. Review every change to `STRATEGY.md`, keep
the notional caps small, and monitor the journal.
