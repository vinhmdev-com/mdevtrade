import logging

from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field

from src.agents.trading_research.states.trading_analysis_state import (
    TradingAnalysisState,
)
from src.config.settings import settings
from src.llm_clients.factory import create_llm_client

logger = logging.getLogger(__name__)


class TraderProposal(BaseModel):
    Action: str = Field(description="BUY, SELL, or HOLD. Must match Manager's action.")
    Entry_Price: float = Field(
        description="The proposed entry price. Usually close to current price."
    )
    Stop_Loss: float = Field(description="The proposed stop loss price.")
    Take_Profit: float = Field(description="The proposed take profit price.")
    Risk_Reward_Ratio: float = Field(
        description="The risk/reward ratio (e.g. 2.5 means risking 1 to make 2.5)."
    )
    Position_Size_Pct: float = Field(
        description="Proposed percentage of portfolio to risk on this trade (e.g. 1.0 to 5.0)."
    )
    Reasoning: str = Field(description="Concise rationale for SL/TP placement.")


async def trader(state: TradingAnalysisState):
    logger.info(
        "💹 [8] Trader: Formulating precise Trading Proposal based on Manager's JSON..."
    )

    client = create_llm_client(
        provider="openai", model=settings.llm_deep_model, base_url=settings.llm_base_url
    )
    llm = client.get_llm()
    structured_llm = llm.with_structured_output(TraderProposal)

    debate_state = state.get("investment_debate_state", {})
    manager_json = debate_state.get("manager_json", {})

    # Extract manager context
    action = manager_json.get("Action", "HOLD")
    atr_mod = manager_json.get("ATR_Multiplier_Adjustment", 1.0)
    score = manager_json.get("Conviction_Score", 5)

    current_price = state.get("current_price", 0.0)

    prompt = f"""You are the Execution Trader.
Your job is to formulate a precise mathematical Trading Proposal based on the Research Manager's instructions.

--- MANAGER INSTRUCTIONS ---
Action: {action}
Conviction Score: {score}/10
ATR Multiplier Adjustment: {atr_mod}
Current Asset Price: {current_price}
----------------------------

--- TECHNICAL CONTEXT ---
{state.get("market_report", "N/A")}
-------------------------

Rules for your proposal:
1. If Action is HOLD, output zeros for prices and size.
2. If BUY/SELL, set Entry_Price near the Current Asset Price.
3. Use the ATR value from the Technical Context (if available) multiplied by the Manager's ATR Multiplier Adjustment to calculate Stop_Loss and Take_Profit.
4. Position Size should be dynamic: higher conviction = higher size (e.g. up to 5%).
5. Calculate Risk/Reward Ratio strictly based on Entry, SL, and TP.

Return your exact proposal in JSON format."""

    try:
        proposal: TraderProposal = await structured_llm.ainvoke(
            [SystemMessage(content=prompt)]
        )



        return {"trader_investment_plan": proposal.model_dump()}
    except Exception as e:
        logger.error(f"Trader failed to generate structured output: {e}")
        fallback = {
            "Action": action,
            "Entry_Price": current_price,
            "Stop_Loss": 0.0,
            "Take_Profit": 0.0,
            "Risk_Reward_Ratio": 0.0,
            "Position_Size_Pct": 0.0,
            "Reasoning": f"Fallback triggered due to error: {e}",
        }
        return {"trader_investment_plan": fallback}
