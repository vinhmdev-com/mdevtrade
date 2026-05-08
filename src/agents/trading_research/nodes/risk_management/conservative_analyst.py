import logging

from langchain_core.messages import SystemMessage

from src.agents.trading_research.states.trading_analysis_state import (
    TradingAnalysisState,
)
from src.config.settings import settings
from src.llm_clients.factory import create_llm_client

logger = logging.getLogger(__name__)


async def conservative_analyst(state: TradingAnalysisState):
    logger.info(
        "🛡️ [10] Conservative Analyst: Reviewing Trader Proposal for capital preservation..."
    )

    client = create_llm_client(
        provider="openai", model=settings.llm_deep_model, base_url=settings.llm_base_url
    )
    llm = client.get_llm()

    proposal = state.get("trader_investment_plan", {})
    if proposal.get("Action", "HOLD") == "HOLD":
        evaluation = "Holding cash is the ultimate capital preservation. I approve."
    else:
        prompt = f"""You are the Conservative Risk Analyst.
Your goal is capital preservation. You hate wide Stop-Losses and you prefer minimal Position Sizes to protect against tail-risk events.

--- TRADER PROPOSAL ---
Action: {proposal.get("Action")}
Entry: {proposal.get("Entry_Price")}
Stop-Loss: {proposal.get("Stop_Loss")}
Take-Profit: {proposal.get("Take_Profit")}
Position Size: {proposal.get("Position_Size_Pct")}%
-----------------------

Evaluate this proposal. Argue why the position size should be decreased or why the Stop-Loss should be tightened to protect capital. Be critical if the proposal is too reckless. Keep it concise."""

        response = await llm.ainvoke([SystemMessage(content=prompt)])
        evaluation = response.content

    risk_state = state.get("risk_debate_state") or {}
    risk_state["conservative_evaluation"] = evaluation
    return {"risk_debate_state": risk_state}
