# Trailing Stop Strategy (Adapted from Alpaca → Zerodha Kite)

## Original Source
Extracted from Claude Club "Trailing Stop Prompt" skill file (Trading category).
Original used Alpaca paper trading — adapted here for Zerodha Kite via MCP.

---

## Strategy Prompt Template

I want you to be my trading bot. Here's how this is going to work.

I want to buy [STOCK/MF] using my Zerodha Kite account.

Buy [X] shares/units at market price right now.

Now set up these rules:

**FLOOR:** If the stock drops to [PRICE], sell everything. That's my stop loss.
I don't want to lose more than that on this trade.

**TRAILING FLOOR:** If the stock goes up 10% from what I paid, move my stop loss
up to 5% below the current price. Every time it climbs another 5%, move the
floor up again. The floor only goes up, never down.

**LADDER IN:** If the stock drops to [PRICE], buy [X] more shares.
If it drops to [PRICE], buy [X] more shares.
This way I'm getting better prices on the way down instead of just losing money.

After you set this up, show me a summary of every order and rule you've placed
so I can confirm it looks right.

---

## How This Maps to Kite MCP Tools

| Rule | Kite Tool | Order Type |
|---|---|---|
| Initial Buy | `place_order` | MARKET or LIMIT, CNC (delivery) |
| FLOOR (stop loss) | `place_order` | SL-M (Stop Loss Market) |
| TRAILING FLOOR | Monitored via `get_ltp` + `modify_order` | Modify SL price upward |
| LADDER IN (buy dips) | `place_gtt_order` | GTT trigger at lower prices |

## Notes
- **CNC** = Cash and Carry (delivery/long-term holding) — use for equities
- **MIS** = Intraday — use only if closing same day
- **GTT** = Good Till Triggered — perfect for LADDER IN and FLOOR rules (persists across sessions)
- Trailing Floor requires active monitoring (Claude checks LTP and modifies SL order)
- Mutual Funds: use `place_order` on MF exchange — no intraday, no SL orders (MF only supports CNC)
