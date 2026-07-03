import pytest

from trading_agent.config import Config
from trading_agent.guardrails import RunState, evaluate_order

PLACE = "mcp__robinhood__place_equity_order"
REVIEW = "mcp__robinhood__review_equity_order"
PLACE_OPT = "mcp__robinhood__place_option_order"
REVIEW_OPT = "mcp__robinhood__review_option_order"


def make_cfg(**overrides) -> Config:
    defaults = dict(
        mode="live",
        account_number="ACC123",
        max_order_notional_usd=200.0,
        max_trades_per_run=3,
        allowed_symbols=frozenset(),
        allow_options=False,
    )
    defaults.update(overrides)
    return Config(**defaults)


def reviewed_state(*symbols: str) -> RunState:
    state = RunState()
    state.reviewed_equity_symbols.update(s.upper() for s in symbols)
    return state


def buy(symbol="VOO", **kw) -> dict:
    order = dict(account_number="ACC123", symbol=symbol, side="buy", type="market")
    order.update(kw)
    return order


def test_read_tools_always_allowed():
    cfg = make_cfg(mode="report")
    assert evaluate_order("mcp__robinhood__get_portfolio", {}, cfg, RunState()) is None


def test_report_mode_blocks_orders():
    cfg = make_cfg(mode="report")
    reason = evaluate_order(PLACE, buy(dollar_amount="50"), cfg, reviewed_state("VOO"))
    assert reason is not None and "report" in reason


def test_live_requires_pinned_account():
    cfg = make_cfg(account_number="")
    reason = evaluate_order(PLACE, buy(dollar_amount="50"), cfg, reviewed_state("VOO"))
    assert reason is not None and "ROBINHOOD_ACCOUNT_NUMBER" in reason


def test_wrong_account_denied():
    cfg = make_cfg()
    order = buy(dollar_amount="50")
    order["account_number"] = "OTHER"
    reason = evaluate_order(PLACE, order, cfg, reviewed_state("VOO"))
    assert reason is not None and "account" in reason


def test_review_required_before_place():
    cfg = make_cfg()
    reason = evaluate_order(PLACE, buy(dollar_amount="50"), cfg, RunState())
    assert reason is not None and "review_equity_order" in reason


def test_review_then_place_allowed_and_counted():
    cfg = make_cfg()
    state = RunState()
    assert evaluate_order(REVIEW, {"symbol": "voo"}, cfg, state) is None
    assert evaluate_order(PLACE, buy(dollar_amount="150"), cfg, state) is None
    assert state.trades_placed == 1


def test_notional_cap_on_dollar_amount():
    cfg = make_cfg()
    reason = evaluate_order(PLACE, buy(dollar_amount="500"), cfg, reviewed_state("VOO"))
    assert reason is not None and "cap" in reason


def test_notional_cap_on_limit_order():
    cfg = make_cfg()
    order = buy(type="limit", quantity="3", limit_price="100")
    reason = evaluate_order(PLACE, order, cfg, reviewed_state("VOO"))
    assert reason is not None and "cap" in reason


def test_unbounded_market_buy_denied():
    cfg = make_cfg()
    reason = evaluate_order(PLACE, buy(quantity="10"), cfg, reviewed_state("VOO"))
    assert reason is not None and "bound" in reason


def test_sell_allowed_without_notional():
    cfg = make_cfg()
    order = buy(quantity="10")
    order["side"] = "sell"
    assert evaluate_order(PLACE, order, cfg, reviewed_state("VOO")) is None


def test_symbol_allowlist():
    cfg = make_cfg(allowed_symbols=frozenset({"VOO"}))
    reason = evaluate_order(PLACE, buy(symbol="GME", dollar_amount="50"), cfg, reviewed_state("GME"))
    assert reason is not None and "ALLOWED_SYMBOLS" in reason


def test_trade_count_limit():
    cfg = make_cfg(max_trades_per_run=1)
    state = reviewed_state("VOO")
    assert evaluate_order(PLACE, buy(dollar_amount="50"), cfg, state) is None
    reason = evaluate_order(PLACE, buy(dollar_amount="50"), cfg, state)
    assert reason is not None and "limit" in reason.lower()


def test_options_disabled_by_default():
    cfg = make_cfg()
    reason = evaluate_order(PLACE_OPT, {"account_number": "ACC123", "quantity": "1"}, cfg, RunState())
    assert reason is not None and "ALLOW_OPTIONS" in reason


def test_option_flow_when_enabled():
    cfg = make_cfg(allow_options=True)
    state = RunState()
    order = {"account_number": "ACC123", "quantity": "1", "price": "1.50", "type": "limit"}

    reason = evaluate_order(PLACE_OPT, order, cfg, state)
    assert reason is not None and "review_option_order" in reason

    assert evaluate_order(REVIEW_OPT, {}, cfg, state) is None
    assert evaluate_order(PLACE_OPT, order, cfg, state) is None  # $150 notional, under cap

    big = dict(order, price="5.00")  # $500 notional
    reason = evaluate_order(PLACE_OPT, big, cfg, state)
    assert reason is not None and "cap" in reason


def test_option_market_order_denied():
    cfg = make_cfg(allow_options=True)
    state = RunState()
    state.option_reviews = 1
    order = {"account_number": "ACC123", "quantity": "1", "type": "market"}
    reason = evaluate_order(PLACE_OPT, order, cfg, state)
    assert reason is not None and "limit order" in reason


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
