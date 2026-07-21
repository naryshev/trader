Morning reports live here as YYYY-MM-DD.md files, committed daily by the
morning routine and rendered into the dashboard by dashboard/build_dashboard.py.

Front-matter format:

    ---
    headline: one-line summary shown in the dashboard masthead and push notification
    proposal: {"account_number":"973317647","symbol":"VOO","side":"buy","type":"market","dollar_amount":"10.95","note":"why"}
    ---

`proposal:` may repeat, one JSON object per line. Each proposal in the LATEST
report becomes an actionable card on the dashboard: Accept runs a broker
review (review_equity_order), displays the compliance quote disclosure
verbatim, and places the order (place_equity_order) only after the user
presses Confirm. Supported keys mirror the equity order tools: symbol, side,
type, quantity or dollar_amount, limit_price, stop_price, time_in_force,
market_hours, plus a free-text note.

Option proposals additionally carry `option_id` (the contract instrument id
from get_option_instruments — required for the dashboard's checkbox build
flow) and `eli5` (a plain-language explanation of the pick, shown on the
card). Option proposals without option_id render as manual-execution cards.
