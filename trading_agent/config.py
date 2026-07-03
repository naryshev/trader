"""Configuration for the trading agent, loaded from environment variables.

Every safety-relevant setting defaults to the most conservative value:
report-only mode, no options, small notional cap.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_symbols(name: str) -> frozenset[str]:
    raw = os.environ.get(name, "")
    return frozenset(s.strip().upper() for s in raw.split(",") if s.strip())


@dataclass(frozen=True)
class Config:
    # "report": the agent analyzes and proposes trades but every order tool is blocked.
    # "live": orders allowed, subject to all guardrails below.
    mode: str = field(default_factory=lambda: os.environ.get("TRADING_MODE", "report").strip().lower())

    # Orders may only target this account. Live mode refuses to trade without it.
    account_number: str = field(default_factory=lambda: os.environ.get("ROBINHOOD_ACCOUNT_NUMBER", "").strip())

    max_order_notional_usd: float = field(
        default_factory=lambda: float(os.environ.get("MAX_ORDER_NOTIONAL_USD", "200"))
    )
    max_trades_per_run: int = field(default_factory=lambda: int(os.environ.get("MAX_TRADES_PER_RUN", "3")))

    # Empty set = any symbol allowed.
    allowed_symbols: frozenset[str] = field(default_factory=lambda: _env_symbols("ALLOWED_SYMBOLS"))

    allow_options: bool = field(default_factory=lambda: _env_bool("ALLOW_OPTIONS", False))

    mcp_url: str = field(
        default_factory=lambda: os.environ.get("ROBINHOOD_MCP_URL", "https://agent.robinhood.com/mcp/trading")
    )
    # Optional bearer token for the MCP server. If unset, the SDK relies on
    # OAuth credentials stored by an interactive `claude` session (/mcp login).
    mcp_token: str = field(default_factory=lambda: os.environ.get("ROBINHOOD_MCP_TOKEN", "").strip())

    model: str = field(default_factory=lambda: os.environ.get("AGENT_MODEL", "claude-opus-4-8"))
    max_turns: int = field(default_factory=lambda: int(os.environ.get("AGENT_MAX_TURNS", "50")))

    strategy_path: Path = REPO_ROOT / "STRATEGY.md"
    journal_dir: Path = REPO_ROOT / "journal"

    @property
    def is_live(self) -> bool:
        return self.mode == "live"
