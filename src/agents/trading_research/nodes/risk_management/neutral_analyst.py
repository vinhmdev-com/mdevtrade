import logging

from langchain_core.messages import SystemMessage

from src.agents.trading_research.states.trading_analysis_state import (
    TradingAnalysisState,
)
from src.config.settings import settings
from src.llm_clients.factory import create_llm_client

logger = logging.getLogger(__name__)


async def neutral_analyst(state: TradingAnalysisState):
    logger.info("⚖️ [11] Neutral Analyst: Evaluating Risk/Reward mathematics...")

    client = create_llm_client(
        provider="openai", model=settings.llm_deep_model, base_url=settings.llm_base_url
    )
    llm = client.get_llm()

    proposal = state.get("trader_investment_plan", {})
    if proposal.get("Action", "HOLD") == "HOLD":
        evaluation = "Mathematical R/R is N/A for HOLD."
    else:
        prompt = f"""You are the Neutral Quantitative Analyst.
Your only goal is to evaluate the mathematical Risk/Reward Ratio (R/R) of the trade. You have no emotional bias.
A standard acceptable R/R is at least 1:1.5 or 1:2.

--- TRADER PROPOSAL ---
Action: {proposal.get("Action")}
Entry: {proposal.get("Entry_Price")}
Stop-Loss: {proposal.get("Stop_Loss")}
Take-Profit: {proposal.get("Take_Profit")}
Risk/Reward Ratio: {proposal.get("Risk_Reward_Ratio")}
-----------------------

Evaluate if this mathematical setup is statistically sound. If the R/R is too low (e.g. risking 1 to make 0.5), explicitly state that this trade should be REJECTED. Keep it concise."""

        response = await llm.ainvoke([SystemMessage(content=prompt)])
        evaluation = response.content

    risk_state = state.get("risk_debate_state") or {}
    risk_state["neutral_evaluation"] = evaluation
    return {"risk_debate_state": risk_state}
