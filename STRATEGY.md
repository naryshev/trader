# Trading Strategy

This file is the agent's only source of trading rules. Edit it to change what
the agent does; the hard limits in the environment (notional cap, trade count,
symbol allowlist) always apply on top of anything written here.

## Objective

Maintain a small, diversified long-equity portfolio. Preserve capital first;
capture upside second.

## Universe

- Large-cap US equities and broad-market ETFs only (e.g. VOO, VTI, QQQ).
- No options, no margin, no crypto, no leveraged or inverse ETFs.

## Phases

- **Bootstrap phase (portfolio value under $500).** The account is too small
  for percentage-based sizing. Deploy the full available cash into a single
  broad-market ETF (prefer VOO, else VTI) using a dollar-based market order
  during regular hours. The position-size caps in rule 2 and the 5% cash
  threshold in rule 3 are suspended; the sell rules still apply. Additional
  deposits during bootstrap are likewise deployed in full.
- **Normal phase (portfolio value $500 or more).** All rules below apply as
  written.

## Rules

1. **Assess before acting.** Fetch the portfolio, positions, and open orders
   at the start of every run. Cancel any stale open order (older than 5
   trading days) before considering new trades.
2. **Position sizing.** No single position may exceed 20% of portfolio value
   after the trade. New positions start at no more than 10%. (Suspended
   during the bootstrap phase.)
3. **Buying.** Only buy when cash exceeds 5% of portfolio value. Prefer
   marketable limit orders at the current ask over plain market orders.
   (During bootstrap, use dollar-based market orders instead — fractional
   shares require them.)
4. **Selling.** Propose (or in live mode, place) a sell when a position is
   down more than 15% from cost basis, or exceeds 25% of portfolio value.
5. **When in doubt, do nothing.** If data is missing, a quote looks stale, or
   the market is closed, record the situation in the report instead of trading.

## Reporting

Every run ends with the standard report. Trades that the rules would have
made but the guardrails or mode blocked go under "Proposals" with the exact
order parameters that would have been used.
