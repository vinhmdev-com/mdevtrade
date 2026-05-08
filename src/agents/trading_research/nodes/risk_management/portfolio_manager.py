import logging
from typing import Literal

from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field

from src.agents.trading_research.states.trading_analysis_state import (
    TradingAnalysisState,
)
from src.config.settings import settings
from src.llm_clients.factory import create_llm_client

logger = logging.getLogger(__name__)


class FinalTradeDecision(BaseModel):
    Status: Literal["APPROVED", "REJECTED", "MODIFIED"] = Field(
        description="The final status of the trade proposal."
    )
    Final_Action: str = Field(description="BUY, SELL, or HOLD.")
    Final_Entry: float = Field(description="The approved entry price.")
    Final_Stop_Loss: float = Field(description="The approved stop loss price.")
    Final_Take_Profit: float = Field(description="The approved take profit price.")
    Position_Size_Pct: float = Field(
        description="The approved position size percentage."
    )
    Review_Notes: str = Field(
        description="Summary of why the risk team made these modifications."
    )


async def portfolio_manager(state: TradingAnalysisState):
    logger.info("🏦 [12] Portfolio Manager: Making final structured trade decision...")

    client = create_llm_client(
        provider="openai", model=settings.llm_deep_model, base_url=settings.llm_base_url
    )
    llm = client.get_llm()
    structured_llm = llm.with_structured_output(FinalTradeDecision)

    proposal = state.get("trader_investment_plan", {})
    risk_state = state.get("risk_debate_state", {})

    if proposal.get("Action", "HOLD") == "HOLD":
        fallback = {
            "Status": "APPROVED",
            "Final_Action": "HOLD",
            "Final_Entry": 0.0,
            "Final_Stop_Loss": 0.0,
            "Final_Take_Profit": 0.0,
            "Position_Size_Pct": 0.0,
            "Review_Notes": "Manager and Trader agreed on HOLD.",
        }
        return {"final_trade_decision": fallback}

    prompt = f"""You are the Head Portfolio Manager.
You have received a Trading Proposal from the Trader, and 3 critical evaluations from your Risk Team.

--- TRADER PROPOSAL ---
Action: {proposal.get("Action")}
Entry: {proposal.get("Entry_Price")}
Stop-Loss: {proposal.get("Stop_Loss")}
Take-Profit: {proposal.get("Take_Profit")}
Position Size: {proposal.get("Position_Size_Pct")}%
-----------------------

--- RISK TEAM EVALUATIONS ---
Aggressive Analyst: {risk_state.get("aggressive_evaluation", "N/A")}
Conservative Analyst: {risk_state.get("conservative_evaluation", "N/A")}
Neutral Analyst (R/R Check): {risk_state.get("neutral_evaluation", "N/A")}
-----------------------------

Your job is to make the FINAL decision.
1. If the Neutral Analyst says R/R is fundamentally flawed, you MUST REJECT the trade.
2. If the proposal is mathematically sound but risky, you can choose 'MODIFIED' and adjust the Position Size down or tweak the Stop-Loss based on the Conservative/Aggressive debate.
3. If the proposal is perfect, choose 'APPROVED' and keep the numbers the same.

Return the final parameters in strict JSON format."""

    try:
        decision: FinalTradeDecision = await structured_llm.ainvoke(
            [SystemMessage(content=prompt)]
        )
        return {"final_trade_decision": decision.model_dump()}
    except Exception as e:
        logger.error(f"Portfolio Manager failed to generate structured output: {e}")
        fallback = {
            "Status": "REJECTED",
            "Final_Action": proposal.get("Action"),
            "Final_Entry": 0.0,
            "Final_Stop_Loss": 0.0,
            "Final_Take_Profit": 0.0,
            "Position_Size_Pct": 0.0,
            "Review_Notes": f"Fallback to REJECTED due to JSON parsing error: {e}",
        }
        return {"final_trade_decision": fallback}
