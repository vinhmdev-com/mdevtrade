import logging

from langchain_core.messages import SystemMessage

from src.agents.trading_research.states.trading_analysis_state import (
    TradingAnalysisState,
)
from src.config.settings import settings
from src.llm_clients.factory import create_llm_client

logger = logging.getLogger(__name__)


async def aggressive_analyst(state: TradingAnalysisState):
    logger.info(
        "🔥 [9] Aggressive Analyst: Reviewing Trader Proposal for maximum yield..."
    )

    client = create_llm_client(
        provider="openai", model=settings.llm_deep_model, base_url=settings.llm_base_url
    )
    llm = client.get_llm()

    proposal = state.get("trader_investment_plan", {})
    if proposal.get("Action", "HOLD") == "HOLD":
        evaluation = "No action proposed. Holding cash is safest but yields zero."
    else:
        prompt = f"""You are the Aggressive Risk Analyst.
Your goal is to maximize yield. You prefer wider Stop-Losses to avoid getting wicked out by noise, and you push for higher Position Sizes if the conviction is high.

--- TRADER PROPOSAL ---
Action: {proposal.get("Action")}
Entry: {proposal.get("Entry_Price")}
Stop-Loss: {proposal.get("Stop_Loss")}
Take-Profit: {proposal.get("Take_Profit")}
Position Size: {proposal.get("Position_Size_Pct")}%
-----------------------

Evaluate this proposal. Argue why the position size should be increased or why the Stop-Loss should be widened to let the trade breathe. Be critical if the proposal is too timid. Keep it concise."""

        response = await llm.ainvoke([SystemMessage(content=prompt)])
        evaluation = response.content

    # Initialize dict if None
    risk_state = state.get("risk_debate_state") or {}
    risk_state["aggressive_evaluation"] = evaluation
    return {"risk_debate_state": risk_state}
