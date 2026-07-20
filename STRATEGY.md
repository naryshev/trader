# Trading Strategy

This file is the agent's only source of trading rules. Edit it to change what
the agent does; the hard limits in the environment (notional cap, trade count,
symbol allowlist, ALLOW_OPTIONS) always apply on top of anything written here.

## Objective

Options-centric trading on a small account: an income base (cash-secured puts,
covered calls) when capital allows, plus small directional option bets.
Aggressive by choice — per-position risk is capped at 25% of account value —
but never careless: defined risk only, liquid chains only.

The account is Level 2: long calls, long puts, covered calls, cash-secured
puts. No spreads, no naked options — never propose them.

## Phases (by account value)

- **Under $500 — bootstrap.** Options are not viable at this size. Deploy the
  full available cash into a broad-market ETF (prefer VOO, else VTI) via a
  dollar-based market order, and note in every report how far the account is
  from the $500 options threshold.
- **$500 to $3,000 — directional only.** Long calls/puts within the rules
  below. Income trades are not yet possible (collateral for 100 shares is out
  of reach). The ETF core from bootstrap may be held or sold to free premium
  budget as opportunities warrant.
- **$3,000+ — full strategy.** Income base plus directional bets.

## Universe

- Options only on highly liquid underlyings: SPY, QQQ, IWM, and large-cap
  single names with tight chains (e.g. AAPL, MSFT, NVDA, AMD, F, SOFI).
- Liquidity gate for every contract: bid-ask spread under 10% of the mid,
  open interest over 500. If a chain fails the gate, skip the trade.

## Directional rules (long calls / long puts)

1. **Risk cap:** premium paid on a single position ≤ 25% of account value.
   Total open directional premium ≤ 50% of account value.
2. **Time:** at entry, 21+ days to expiration. Exit or roll no later than
   7 days before expiration — never hold into the final week.
3. **Entry/exit discipline:** limit orders only, at or better than the mid.
   Take profit at +100% of premium; cut at −50%; otherwise reassess at the
   7-days-to-expiry mark. State the thesis for every entry in the report.
4. Expect frequent full losses on long options; that is the accepted cost of
   this style. Never average down on a losing option.

## Income rules (cash-secured puts / covered calls) — $3,000+ only

5. **Cash-secured puts:** only on underlyings worth owning at the strike;
   strike at or below recent support; 30–45 days out; collateral for a single
   CSP ≤ 50% of account value. If assigned, hold the shares and sell covered
   calls against them.
6. **Covered calls:** only above cost basis, 30–45 days out. Never sell a
   call below cost basis to chase premium.

## General rules

7. **Assess before acting.** Fetch portfolio, positions (equity AND option),
   and open orders every run. Flag any option position violating the time or
   loss rules above. Cancel stale open orders older than 5 trading days.
8. **Review before placing.** Every proposed order goes through the matching
   review tool; surface all alerts in the report.
9. **When in doubt, do nothing.** Missing data, stale quotes, wide spreads,
   or a closed market: record it and stand down.

## Reporting

Every run ends with the standard report. Proposals include exact contract
parameters (underlying, strike, expiration, side, quantity, limit price) and
the thesis. Option proposals are executed manually in the Robinhood app for
now; equity proposals can be accepted from the dashboard.
