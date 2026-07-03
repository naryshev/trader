"""The autonomous trading agent, built on the Claude Agent SDK.

One invocation = one run: the agent reads STRATEGY.md, inspects the account
through the Robinhood MCP server, applies the strategy, and writes a report.
Order placement is governed by the guardrail hook, never by the prompt alone.
"""

import asyncio

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    TextBlock,
    query,
)

from .config import Config
from .guardrails import RunState, make_order_guardrail
from .journal import Journal

MCP_SERVER_NAME = "robinhood"

SYSTEM_PROMPT = """\
You are an autonomous trading assistant operating a single Robinhood brokerage
account through MCP tools. You run unattended: nobody can answer questions
mid-run, so never ask for confirmation — act within your rules or record why
you did not.

Operating rules:
- STRATEGY.md is your only source of trading rules. If the strategy and this
  prompt ever conflict, follow the stricter of the two.
- Ground every claim in tool output from this run. Never invent prices,
  positions, or fills.
- Before any order, call the matching review tool and evaluate its alerts.
  If a review surfaces a blocking alert, do not place the order.
- Order tools may be denied by an external guardrail. A denial is final for
  this run: record the intended trade and the denial reason in your report
  and move on. Never retry a denied order with tweaked parameters to slip
  under a limit.
- End every run with a report in exactly this structure:

  # Trading Run Report
  ## Mode
  ## Account snapshot
  ## Analysis
  ## Actions taken (orders placed, with tool evidence)
  ## Proposals (trades considered but not placed, and why)
  ## Follow-ups for the human
"""


def build_prompt(cfg: Config) -> str:
    strategy = cfg.strategy_path.read_text()
    mode_note = (
        "LIVE mode: you may place orders that pass review and the guardrails."
        if cfg.is_live
        else "REPORT-ONLY mode: do not attempt to place orders; propose them in the report."
    )
    return f"""\
Run the trading strategy below. {mode_note}

Configured limits (enforced externally — treat as hard):
- account: {cfg.account_number or "(not pinned — orders disabled)"}
- max notional per order: ${cfg.max_order_notional_usd:.2f}
- max orders this run: {cfg.max_trades_per_run}
- allowed symbols: {", ".join(sorted(cfg.allowed_symbols)) or "any"}
- options allowed: {cfg.allow_options}

<strategy>
{strategy}
</strategy>

Start by fetching the account, portfolio, and current positions. Then apply
the strategy and finish with the report.
"""


def build_options(cfg: Config, journal: Journal, state: RunState) -> ClaudeAgentOptions:
    server: dict = {"type": "http", "url": cfg.mcp_url}
    if cfg.mcp_token:
        server["headers"] = {"Authorization": f"Bearer {cfg.mcp_token}"}

    log_pre, log_post = journal.make_audit_hooks()
    guardrail = make_order_guardrail(cfg, state)

    return ClaudeAgentOptions(
        model=cfg.model,
        cwd=str(cfg.strategy_path.parent),
        mcp_servers={MCP_SERVER_NAME: server},
        system_prompt=SYSTEM_PROMPT,
        max_turns=cfg.max_turns,
        # The agent may use the Robinhood tools and read local files — nothing else.
        allowed_tools=[f"mcp__{MCP_SERVER_NAME}", "Read", "Glob", "Grep"],
        disallowed_tools=["Bash", "Write", "Edit", "NotebookEdit", "WebFetch", "WebSearch", "Agent", "Task"],
        setting_sources=[],  # hermetic: no user/project settings leak into the run
        hooks={
            "PreToolUse": [
                HookMatcher(matcher=f"^mcp__{MCP_SERVER_NAME}__", hooks=[guardrail]),
                HookMatcher(hooks=[log_pre]),
            ],
            "PostToolUse": [HookMatcher(hooks=[log_post])],
        },
    )


async def run() -> int:
    cfg = Config()
    state = RunState()
    journal = Journal(cfg.journal_dir)

    journal.record(
        "run_start",
        {
            "mode": cfg.mode,
            "max_order_notional_usd": cfg.max_order_notional_usd,
            "max_trades_per_run": cfg.max_trades_per_run,
            "allowed_symbols": sorted(cfg.allowed_symbols),
            "allow_options": cfg.allow_options,
        },
    )
    print(f"[trading-agent] run {journal.run_id} starting in {cfg.mode.upper()} mode")

    transcript: list[str] = []
    result: ResultMessage | None = None

    async for message in query(prompt=build_prompt(cfg), options=build_options(cfg, journal, state)):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    transcript.append(block.text)
                    print(block.text)
        elif isinstance(message, ResultMessage):
            result = message

    report = result.result if result and result.result else "\n\n".join(transcript)
    report_path = journal.write_report(report or "(no output produced)")

    journal.record(
        "run_end",
        {
            "is_error": result.is_error if result else True,
            "num_turns": result.num_turns if result else None,
            "total_cost_usd": result.total_cost_usd if result else None,
            "trades_placed": state.trades_placed,
            "report_path": str(report_path),
        },
    )
    print(f"\n[trading-agent] done — {state.trades_placed} order(s) placed, report: {report_path}")
    return 1 if (result is None or result.is_error) else 0


def main() -> None:
    raise SystemExit(asyncio.run(run()))
