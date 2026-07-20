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

- **Under $500 — moonshot experiment.** A deliberate, user-chosen experiment:
  attempt to ladder the starting ~$11 to $500 through sequential cheap long
  option trades. **The expected outcome is losing the entire stake; the user
  has accepted this explicitly.** Rules for this phase only:
  - One position at a time, funded with the full available cash (diversification
    is impossible at this size). Do not deploy cash into equities.
  - Candidate contracts: long calls or puts priced within available cash on
    liquid low-priced underlyings (e.g. F, SOFI, PLTR, AAL, NIO, LCID, and
    similar), 7–30 days to expiration, strike as close to the money as the
    budget allows — prefer a nearer strike over a longer date. The standard
    liquidity gate is relaxed to: spread ≤ 25% of mid, open interest ≥ 100.
  - Every proposal states the thesis (momentum, catalyst, or setup — not a
    random pick), the contract's full parameters, and a limit price at the mid.
  - Exit ladder: take profit at +100% to +200% and roll the full proceeds into
    the next trade; cut at −50% only if the remainder can still buy another
    contract, otherwise ride it to resolution. Never hold into the final
    2 days before expiration.
  - Progress math in every report: account value, number of consecutive
    doubles still needed to reach $500 (~$11 needs about six), and the
    running win/loss ledger of the experiment.
  - **Experiment ends** when the account cannot afford any qualifying contract
    (report it as concluded, hold cash) or when value crosses $500 (graduate
    to the next phase). Fresh deposits restart or accelerate the ladder.
- **$500 to $3,000 — directional only.** Long calls/puts within the standard
  rules below (the moonshot relaxations no longer apply). Income trades are
  not yet possible (collateral for 100 shares is out of reach).
- **$3,000+ — full strategy.** Income base plus directional bets.

## Universe

- Options only on highly liquid underlyings: SPY, QQQ, IWM, and large-cap
  single names with tight chains (e.g. AAPL, MSFT, NVDA, AMD, F, SOFI).
- Liquidity gate for every contract: bid-ask spread under 10% of the mid,
  open interest over 500. If a chain fails the gate, skip the trade.
- During the moonshot phase, that phase's own universe and relaxed liquidity
  gate replace the two rules above.

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
