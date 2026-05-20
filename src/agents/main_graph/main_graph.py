import json
import logging
from typing import Any, Dict

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph

from src.agents.main_graph.state import MainState
from src.agents.trading_binance.execution_graph import graph as execution_graph
from src.agents.trading_research.research_graph import graph as research_graph

logger = logging.getLogger(__name__)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("%(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)


def _section(title: str, body: str) -> str:
    body = (body or "").strip()
    if not body:
        return ""
    return f"## {title}\n\n{body}\n"


def _format_decision(decision: dict | str) -> str:
    if not decision:
        return "_No decision._"
    if isinstance(decision, str):
        return decision
    action = decision.get("Final_Action", "—")
    notes = decision.get("Review_Notes") or decision.get("reasoning") or ""
    extras = {
        k: v
        for k, v in decision.items()
        if k not in {"Final_Action", "Review_Notes", "reasoning"}
    }
    out = [f"**Decision:** `{action}`"]
    if notes:
        out.append(f"\n**Reasoning:**\n\n{notes}")
    if extras:
        out.append("\n<details><summary>Decision details (JSON)</summary>\n\n```json\n"
                   + json.dumps(extras, ensure_ascii=False, indent=2, default=str)
                   + "\n```\n\n</details>")
    return "\n".join(out)


def _format_debate(debate: dict | None, title: str) -> str:
    if not debate or not isinstance(debate, dict):
        return ""
    rounds = debate.get("history") or debate.get("rounds") or debate.get("transcript")
    if not rounds:
        # Fall back to dumping non-empty fields.
        body = {k: v for k, v in debate.items() if v not in (None, "", 0, [])}
        if not body:
            return ""
        return _section(
            title,
            "<details><summary>Debate details</summary>\n\n```json\n"
            + json.dumps(body, ensure_ascii=False, indent=2, default=str)
            + "\n```\n\n</details>",
        )
    text = (
        rounds
        if isinstance(rounds, str)
        else "\n\n".join(
            f"- **{r.get('agent', '?')}**: {r.get('content', '')}"
            for r in rounds
            if isinstance(r, dict)
        )
    )
    return _section(
        title,
        f"<details><summary>View full debate</summary>\n\n{text}\n\n</details>",
    )


def push_notification_node(state: MainState) -> Dict[str, Any]:
    print("\n" + "=" * 60)
    print("🚀 [NODE: Push Notification] Pushing final report to user...")

    ticker = state.get("company_of_interest", "—")
    trade_date = state.get("trade_date", "—")
    current_price = state.get("current_price", 0.0)
    entry_price = state.get("entry_price", 0.0)

    decision = state.get("final_trade_decision", {}) or {}
    action = decision.get("Final_Action", "NEUTRAL") if isinstance(decision, dict) else "NEUTRAL"
    exec_action = state.get("action_taken", "NONE")
    exec_msg = state.get("action_message", "")
    exec_amount = state.get("action_amount", 0.0)

    portfolio_value = state.get("portfolio_value", 0.0)
    drawdown = state.get("drawdown_pct", 0.0)
    usdt_balance = state.get("usdt_balance", 0.0)
    xaut_balance = state.get("xaut_balance", 0.0)

    trader_plan = state.get("trader_investment_plan") or {}
    trader_plan_json = (
        "```json\n" + json.dumps(trader_plan, ensure_ascii=False, indent=2, default=str) + "\n```"
        if trader_plan
        else ""
    )

    sections = [
        f"# 📊 Trading report — {ticker} ({trade_date})\n",
        f"**Final decision:** `{action}`  \n"
        f"**Action taken:** `{exec_action}` ({exec_amount} USD)  \n"
        f"**Execution status:** {exec_msg or '—'}  \n"
        f"**Current / entry price:** {current_price} / {entry_price}\n",
        _section(
            "💼 Portfolio status",
            f"- Portfolio value: **{portfolio_value:.2f} USD**\n"
            f"- Drawdown: {drawdown:.2f}%\n"
            f"- USDT balance: {usdt_balance:.2f}\n"
            f"- XAUT balance: {xaut_balance:.6f}",
        ),
        _section("📈 Market Analyst", state.get("market_report", "")),
        _section("📰 News Analyst", state.get("news_report", "")),
        _section("💬 Social / Sentiment Analyst", state.get("sentiment_report", "")),
        _section("🏦 Fundamentals Analyst", state.get("fundamentals_report", "")),
        _format_debate(state.get("investment_debate_state"), "🥊 Investment debate (Bull vs Bear)"),
        _section("🧠 Investment Plan (Research Manager)", state.get("investment_plan", "")),
        _section(
            "📋 Trader Investment Plan",
            trader_plan_json,
        ),
        _format_debate(state.get("risk_debate_state"), "⚖️ Risk debate"),
        _section("✅ Final decision (Portfolio Manager)", _format_decision(decision)),
    ]
    report_md = "\n".join(s for s in sections if s)

    print(report_md)
    print("✅ Notification Sent Successfully.")
    print("=" * 60 + "\n")

    return {"messages": [AIMessage(content=report_md)]}


def build_main_graph():
    builder = StateGraph(MainState)

    # Add the 2 subgraphs as nodes
    builder.add_node("Research_Subgraph", research_graph)
    builder.add_node("Execution_Subgraph", execution_graph)
    builder.add_node("Push_Notification", push_notification_node)
    
    builder.add_edge(START, "Research_Subgraph")
    builder.add_edge("Research_Subgraph", "Execution_Subgraph")
    builder.add_edge("Execution_Subgraph", "Push_Notification")
    builder.add_edge("Push_Notification", END)
    
    return builder.compile()


graph = build_main_graph()

if __name__ == "__main__":
    import asyncio
    
    print("\n🚀 STARTING MAIN ORCHESTRATOR GRAPH 🚀\n")
    
    initial_state = {
        "company_of_interest": "XAUT",
        "trade_date": "2024-05-11",
        "enable_fundamentals": False,
        "current_price": 0.0,
        "investment_debate_state": {"count": 0},
        "risk_debate_state": {"count": 0},
        "messages": []
    }
    
    async def run():
        async for chunk in graph.astream(initial_state):
            pass
            
    asyncio.run(run())
