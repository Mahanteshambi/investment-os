---
name: Investment OS project
description: Building a personal Investment OS for Mahantesh using Claude + Kite MCP + scheduled tasks
type: project
---

Building a long-term investment automation system ("Investment OS") — NOT a trading bot.

**Why:** Mahantesh wants to invest ₹4L/month consistently without actively monitoring markets. Goals: retirement, child education, wealth building over 5-10 years.

**Core approach:**
- Weekly FII/DII analysis (not daily)
- Monthly dip-buying strategy: deploy ₹4L across the month at dips, full deployment by month-end
- Monthly rebalancing of allocation
- Sector rotation based on fundamental + technical analysis

**Skills to build:**
1. Portfolio Architect — one-time setup, maps current holdings to target allocation
2. Weekly Market Intelligence — FII/DII + sector analysis every Monday
3. Monthly Dip-Buyer — monitors dips intra-month, deploys ₹4L by month end
4. Quarterly Rebalancer — checks allocation drift, suggests rebalancing
5. Sector Rotation Analyst — fundamental + technical sector analysis
6. Portfolio Dashboard — weekly P&L and holdings summary
7. Annual Tax Agent — March tax-loss harvesting + LTCG review

**Data sources:**
- NSE FII/DII API (nseindia.com) — Cloudflare protected, needs cookie session
- Zerodha Kite MCP — historical prices, LTP, order placement (connected ✅)
- Google Drive MCP — portfolio spreadsheet "Ambi Portfolio" (id: 1VxjJti09_qU0yaE24CmjSab1j03tIobkFFDSmzn7dkE)

**Status:** Design phase. Paper trading tracker set up at paper_trades.json. Skills not yet built.

**How to apply:** When designing execution or analysis, remember this is long-term CNC investing, not trading. ETFs and index funds preferred over stock picking.
