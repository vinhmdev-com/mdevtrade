import logging
from typing import Any, Dict, Literal

from langgraph.graph import END, START, StateGraph

from src.agents.trading_research.states.trading_analysis_state import (
    TradingAnalysisState,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Thêm console handler để in log ra màn hình rõ ràng
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("%(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# --- PHASE 1: DATA GATHERING (4 Analysts) ---

# --- PHASE 5: SAVE TO DATABASE ---
import json

from src.agents.trading_binance.tools.db_client import DatabaseClient
from src.agents.trading_research.nodes.data_gathering.fundamentals_analyst import (
    fundamentals_analyst,
)
from src.agents.trading_research.nodes.data_gathering.market_analyst import (
    market_analyst,
)
from src.agents.trading_research.nodes.data_gathering.news_analyst import news_analyst
from src.agents.trading_research.nodes.data_gathering.social_analyst import (
    social_analyst,
)
from src.agents.trading_research.nodes.invest_debate.bear_rebuttal_node import (
    bear_rebuttal_node,
)
from src.agents.trading_research.nodes.invest_debate.bear_thesis_node import (
    bear_thesis_node,
)
from src.agents.trading_research.nodes.invest_debate.bull_rebuttal_node import (
    bull_rebuttal_node,
)

# --- PHASE 2: INVEST DEBATE (5 Agents - 2 Rounds) ---
from src.agents.trading_research.nodes.invest_debate.bull_thesis_node import (
    bull_thesis_node,
)
from src.agents.trading_research.nodes.invest_debate.research_manager import (
    research_manager,
)

# --- PHASE 4: RISK MANAGEMENT DEBATE (4 Agents) ---
from src.agents.trading_research.nodes.risk_management.aggressive_analyst import (
    aggressive_analyst,
)
from src.agents.trading_research.nodes.risk_management.conservative_analyst import (
    conservative_analyst,
)
from src.agents.trading_research.nodes.risk_management.neutral_analyst import (
    neutral_analyst,
)
from src.agents.trading_research.nodes.risk_management.portfolio_manager import (
    portfolio_manager,
)

# --- PHASE 3: TRADING (1 Agent) ---
from src.agents.trading_research.nodes.trading.trader import trader


def save_to_database(state: TradingAnalysisState) -> Dict[str, Any]:
    print("\n--- Saving Daily Signal to Database ---")
    try:
        final_decision = state.get("final_trade_decision", {})
        action = final_decision.get("Final_Action", "NEUTRAL")
        reasoning = final_decision.get("Review_Notes", "")

        # Filter out some data if needed before saving full_json
        # Temporarily saving the entire state as json
        db = DatabaseClient()
        signal_id = db.save_signal(
            final_action=action,
            reasoning=reasoning,
            full_json=json.dumps(
                state, default=str
            ),  # dùng default=str để xử lý datetime nếu có
        )
        print(f"✅ Successfully saved Signal to Database! (Signal ID: {signal_id})")
    except Exception as e:
        print(f"❌ Error saving signal to Database: {e}")
    return {}


# --- ROUTING LOGIC ---
# (Removed old Phase 4 sequential routing logic)


# --- GRAPH CONSTRUCTION ---


def build_research_graph():
    builder = StateGraph(TradingAnalysisState)

    # 1. Add 12 Nodes
    # Phase 1
    builder.add_node("Market_Analyst", market_analyst)
    builder.add_node("Social_Analyst", social_analyst)
    builder.add_node("News_Analyst", news_analyst)
    builder.add_node("Fundamentals_Analyst", fundamentals_analyst)

    # Phase 2
    builder.add_node("Bull_Thesis", bull_thesis_node)
    builder.add_node("Bear_Thesis", bear_thesis_node)
    builder.add_node("Bull_Rebuttal", bull_rebuttal_node)
    builder.add_node("Bear_Rebuttal", bear_rebuttal_node)
    builder.add_node("Research_Manager", research_manager)

    # Phase 3
    builder.add_node("Trader", trader)

    # Phase 4
    builder.add_node("Aggressive_Analyst", aggressive_analyst)
    builder.add_node("Conservative_Analyst", conservative_analyst)
    builder.add_node("Neutral_Analyst", neutral_analyst)
    builder.add_node("Portfolio_Manager", portfolio_manager)

    # Phase 5
    builder.add_node("Save_To_Database", save_to_database)

    # 2. Add Sequential Edges for Phase 1
    builder.add_edge(START, "Market_Analyst")
    builder.add_edge("Market_Analyst", "Social_Analyst")
    builder.add_edge("Social_Analyst", "News_Analyst")
    builder.add_edge("News_Analyst", "Fundamentals_Analyst")
    builder.add_edge("Fundamentals_Analyst", "Bull_Thesis")

    # 3. Add Sequential Edges for Phase 2 (Blind Phase -> Rebuttal Phase -> Manager)
    builder.add_edge("Bull_Thesis", "Bear_Thesis")
    builder.add_edge("Bear_Thesis", "Bull_Rebuttal")
    builder.add_edge("Bull_Rebuttal", "Bear_Rebuttal")
    builder.add_edge("Bear_Rebuttal", "Research_Manager")

    # 4. Phase 3 to Phase 4 transition
    builder.add_edge("Research_Manager", "Trader")

    # 5. Phase 4 Sequential Edges
    builder.add_edge("Trader", "Aggressive_Analyst")
    builder.add_edge("Aggressive_Analyst", "Conservative_Analyst")
    builder.add_edge("Conservative_Analyst", "Neutral_Analyst")
    builder.add_edge("Neutral_Analyst", "Portfolio_Manager")

    # 6. End
    builder.add_edge("Portfolio_Manager", "Save_To_Database")
    builder.add_edge("Save_To_Database", END)

    return builder.compile()


graph = build_research_graph()

# --- TEST EXECUTION ---
if __name__ == "__main__":
    import asyncio

    print("\n" + "=" * 60)
    print("🚀 STARTING TRADING RESEARCH GRAPH (12 NODES - SEQUENTIAL)")
    print("=" * 60 + "\n")

    # Init empty state with nested dicts for counters
    initial_state = {
        "investment_debate_state": {"count": 0},
        "risk_debate_state": {"count": 0},
    }

    async def run_graph():
        async for chunk in graph.astream(initial_state):
            pass  # Logs will be printed by the nodes directly

    asyncio.run(run_graph())

    print("\n" + "=" * 60)
    print("✅ COMPLETED!")
    print("=" * 60 + "\n")
