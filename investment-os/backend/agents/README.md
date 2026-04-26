# Agents — Google ADK (Phase 2)

This folder will contain agents built with Google Agent Development Kit (ADK).

Planned agents:
- PortfolioAgent — reads holdings, computes health metrics
- MarketAnalystAgent — web search for Nifty P/E, FII flows, RBI stance
- SectorRotationAgent — tracks NSE sector indices, relative strength
- RebalancerAgent — computes drift from target allocation, suggests trades

Each agent will:
1. Be implemented as a Google ADK Agent class
2. Use tools: Kite MCP (via mcp-remote), web_search, DuckDB query tool
3. Expose its output via /api/agents/* endpoints
4. Store reasoning in the agent_outputs table

Setup will require: `uv add google-adk`
