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


# Define the Structured Output Schema
class ManagerDecision(BaseModel):
    Action: Literal["BUY", "HOLD", "SELL"] = Field(
        description="The final action to take based on the debate."
    )
    Conviction_Score: int = Field(
        ge=1,
        le=10,
        description="Conviction score of the winning argument from 1 to 10.",
    )
    ATR_Multiplier_Adjustment: float = Field(
        description="Adjustment to the ATR multiplier. For example, 0.8 for a tight range (chop) or 1.5 for strong conviction trend."
    )
    Tie_Breaker_Used: str = Field(
        description="Which tie-breaker was used (e.g. 'Tie-Breaker 1: ATR Compression', 'Tie-Breaker 2: Real Yields', 'None')."
    )
    Reasoning: str = Field(
        description="A concise summary of why this decision was made and why the winning argument prevailed."
    )


async def research_manager(state: TradingAnalysisState):
    logger.info(
        "🧑‍💼 [7] Research Manager: Adjudicating the debate and formatting JSON decision..."
    )

    client = create_llm_client(
        provider="openai", model=settings.llm_deep_model, base_url=settings.llm_base_url
    )
    llm = client.get_llm()

    # We must explicitly bind the schema if supported, but standard Langchain structured output uses with_structured_output
    structured_llm = llm.with_structured_output(ManagerDecision)

    debate_state = state.get("investment_debate_state", {})

    prompt = f"""You are the Research Manager overseeing a multi-agent debate regarding the asset {state.get("company_of_interest")}.
You are presented with 4 documents from your analysts. A Bull Thesis, a Bear Thesis, and their Cross-Examination Rebuttals.
You also have access to the original Phase 1 Data Reports to verify facts and apply Tie-Breakers.

--- PHASE 1 DATA REPORTS ---
Market:
{state.get("market_report", "N/A")}

Social Sentiment:
{state.get("sentiment_report", "N/A")}

News & Macro:
{state.get("news_report", "N/A")}

Fundamentals:
{state.get("fundamentals_report", "N/A")}
----------------------------

--- ROUND 1: BLIND THESES ---
BULL THESIS: {debate_state.get("bull_thesis", "N/A")}
BEAR THESIS: {debate_state.get("bear_thesis", "N/A")}

--- ROUND 2: CROSS-EXAMINATION ---
BULL REBUTTAL: {debate_state.get("bull_rebuttal", "N/A")}
BEAR REBUTTAL: {debate_state.get("bear_rebuttal", "N/A")}
--------------------------------

Your task is to adjudicate this debate and issue a final decision.
If the debate is a deadlock (arguments are perfectly balanced), you MUST use the Adjudication Hierarchy:
1. Tie-Breaker 1 (Chop/Range): If conviction is split, it means uncertainty. Tighten the ATR Multiplier (e.g., 0.6-0.8) to take base hits.
2. Tie-Breaker 2 (Macro Master Key): Look at Real Yields in the reports. Rising = Bear. Falling = Bull.
3. Tie-Breaker 3 (Structural Regime): Look at the 200 SMA in the Market report. Price above rising 200 SMA = Bull.
4. Tie-Breaker 4 (Contrarian): If extreme retail fear = Bull.

Evaluate the logic, apply tie-breakers if necessary, and output your decision strictly matching the JSON schema."""

    # Invoke structured LLM
    try:
        decision: ManagerDecision = await structured_llm.ainvoke(
            [SystemMessage(content=prompt)]
        )

        # Save to state
        debate_state["manager_json"] = decision.model_dump()

        # Also save the string representation for backwards compatibility or easy logging
        plan_str = f"Action: {decision.Action} | Score: {decision.Conviction_Score}/10 | ATR Mod: {decision.ATR_Multiplier_Adjustment} | Tie-Breaker: {decision.Tie_Breaker_Used}\nReasoning: {decision.Reasoning}"

        return {"investment_debate_state": debate_state, "investment_plan": plan_str}
    except Exception as e:
        logger.error(f"Failed to generate structured output: {e}")
        # Fallback mechanism if structured output fails
        fallback_plan = "Action: HOLD | Score: 5/10 | ATR Mod: 1.0 | Tie-Breaker: Error Fallback\nReasoning: LLM failed to parse structured output."
        return {"investment_plan": fallback_plan}
