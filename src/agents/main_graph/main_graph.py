import logging
from typing import Any, Dict

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


def push_notification_node(state: MainState) -> Dict[str, Any]:
    print("\n" + "=" * 60)
    print("🚀 [NODE: Push Notification] Pushing final report to user...")
    
    # Lấy kết quả từ Research
    decision = state.get("final_trade_decision", {})
    action = decision.get("Final_Action", "NEUTRAL")
    reasoning = decision.get("Review_Notes", "No reasoning provided.")
    
    # Lấy kết quả từ Execution
    exec_action = state.get("action_taken", "NONE")
    exec_msg = state.get("action_message", "No execution message.")
    exec_amount = state.get("action_amount", 0.0)
    
    report = f"""
==== 📊 BÁO CÁO GIAO DỊCH (TỔNG HỢP) ====
[🧠 RESEARCH]
- Quyết định: {action}
- Lý do: {reasoning}

[⚡ EXECUTION]
- Hành động thực tế: {exec_action}
- Số lượng: {exec_amount} USD
- Trạng thái: {exec_msg}
=======================================
    """
    print(report)
    print("✅ Notification Sent Successfully (Simulated/Webhook ready).")
    print("=" * 60 + "\n")
    
    # Ở đây có thể tích hợp requests.post(WEBHOOK_URL) hoặc Telegram Bot
    
    return {}


def build_main_graph():
    builder = StateGraph(MainState)
    
    # Thêm 2 Subgraphs như là 2 Nodes
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
