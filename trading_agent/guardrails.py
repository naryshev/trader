"""Hard guardrails for order placement, enforced as an Agent SDK PreToolUse hook.

These run outside the model: a denied decision blocks the tool call no matter
what the prompt or the model says. The pure decision logic lives in
``evaluate_order`` so it can be unit-tested without the SDK.
"""

from dataclasses import dataclass, field

from .config import Config

PLACE_EQUITY = "place_equity_order"
PLACE_OPTION = "place_option_order"
REVIEW_EQUITY = "review_equity_order"
REVIEW_OPTION = "review_option_order"
ORDER_TOOLS = (PLACE_EQUITY, PLACE_OPTION)


@dataclass
class RunState:
    """Mutable per-run state shared across hook invocations."""

    trades_placed: int = 0
    reviewed_equity_symbols: set[str] = field(default_factory=set)
    option_reviews: int = 0


def _bare_tool_name(tool_name: str) -> str:
    # "mcp__robinhood__place_equity_order" -> "place_equity_order"
    return tool_name.split("__")[-1]


def _parse_price(value: object) -> float | None:
    try:
        price = float(str(value))
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None


def _equity_notional(tool_input: dict) -> float | None:
    """Best-effort client-side notional estimate; None if not computable."""
    dollar_amount = _parse_price(tool_input.get("dollar_amount"))
    if dollar_amount is not None:
        return dollar_amount
    quantity = _parse_price(tool_input.get("quantity"))
    limit_price = _parse_price(tool_input.get("limit_price"))
    if quantity is not None and limit_price is not None:
        return quantity * limit_price
    return None


def _option_notional(tool_input: dict) -> float | None:
    quantity = _parse_price(tool_input.get("quantity"))
    price = _parse_price(tool_input.get("price"))
    if quantity is not None and price is not None:
        return quantity * price * 100  # standard contract multiplier
    return None


def evaluate_order(tool_name: str, tool_input: dict, cfg: Config, state: RunState) -> str | None:
    """Return a denial reason for an order-placing tool call, or None to allow.

    Non-order tools (quotes, positions, reviews, cancels, ...) always pass;
    review calls are recorded so the review-before-place rule can be enforced.
    """
    bare = _bare_tool_name(tool_name)

    if bare == REVIEW_EQUITY:
        symbol = str(tool_input.get("symbol", "")).upper()
        if symbol:
            state.reviewed_equity_symbols.add(symbol)
        return None
    if bare == REVIEW_OPTION:
        state.option_reviews += 1
        return None
    if bare not in ORDER_TOOLS:
        return None

    # --- everything below is a real-money order ---

    if not cfg.is_live:
        return (
            "TRADING_MODE is 'report': placing orders is disabled. "
            "Record this trade as a proposal in your report instead."
        )

    if not cfg.account_number:
        return "Live mode requires ROBINHOOD_ACCOUNT_NUMBER to be set; refusing to place orders."
    if str(tool_input.get("account_number", "")).strip() != cfg.account_number:
        return "Order targets an account other than the configured ROBINHOOD_ACCOUNT_NUMBER."

    if state.trades_placed >= cfg.max_trades_per_run:
        return f"Trade limit reached: at most {cfg.max_trades_per_run} orders may be placed per run."

    if bare == PLACE_OPTION:
        if not cfg.allow_options:
            return "Options trading is disabled (ALLOW_OPTIONS=false)."
        if state.option_reviews == 0:
            return "Call review_option_order and report the alerts before placing an option order."
        notional = _option_notional(tool_input)
        if notional is None:
            return (
                "Cannot bound this order's cost client-side. Use a limit order with an "
                "explicit price and integer quantity."
            )
        if notional > cfg.max_order_notional_usd:
            return (
                f"Order notional ~${notional:.2f} exceeds the per-order cap of "
                f"${cfg.max_order_notional_usd:.2f}."
            )
        state.trades_placed += 1
        return None

    # Equity order
    symbol = str(tool_input.get("symbol", "")).upper()
    if cfg.allowed_symbols and symbol not in cfg.allowed_symbols:
        return f"Symbol {symbol} is not in ALLOWED_SYMBOLS ({', '.join(sorted(cfg.allowed_symbols))})."
    if symbol not in state.reviewed_equity_symbols:
        return f"Call review_equity_order for {symbol} and report the result before placing the order."

    side = str(tool_input.get("side", "")).lower()
    if side == "buy":
        notional = _equity_notional(tool_input)
        if notional is None:
            return (
                "Cannot bound this buy's cost client-side. Use dollar_amount, or a "
                "limit order with quantity and limit_price."
            )
        if notional > cfg.max_order_notional_usd:
            return (
                f"Order notional ~${notional:.2f} exceeds the per-order cap of "
                f"${cfg.max_order_notional_usd:.2f}."
            )

    state.trades_placed += 1
    return None


def make_order_guardrail(cfg: Config, state: RunState):
    """Build the PreToolUse hook callback the Agent SDK will invoke."""

    async def order_guardrail(input_data, tool_use_id, context):
        reason = evaluate_order(
            input_data.get("tool_name", ""),
            input_data.get("tool_input") or {},
            cfg,
            state,
        )
        if reason is None:
            return {}
        return {
            "hookSpecificOutput": {
                "hookEventName": input_data.get("hook_event_name", "PreToolUse"),
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }

    return order_guardrail
