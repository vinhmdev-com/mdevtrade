import logging

from langchain_core.messages import SystemMessage

from src.agents.trading_research.states.trading_analysis_state import (
    TradingAnalysisState,
)
from src.config.settings import settings
from src.llm_clients.factory import create_llm_client

logger = logging.getLogger(__name__)


async def bear_thesis_node(state: TradingAnalysisState):
    logger.info("🐻 [5B] Bear Analyst (Round 1): Drafting independent thesis...")

    client = create_llm_client(
        provider="openai", model=settings.llm_deep_model, base_url=settings.llm_base_url
    )
    llm = client.get_llm()

    ticker = state.get("company_of_interest", "Unknown")

    prompt = f"""You are a Bear Analyst for {ticker}.
Identify exactly WHY the asset will fall or underperform.
Provide specific entry, take-profit, and stop-loss targets.

CRITICAL INSTRUCTION: You must base your arguments STRICTLY on the data provided in the Market Report context. DO NOT use your pre-trained knowledge to guess asset prices. You must accept the prices and data provided in the reports as the absolute truth. Calling the provided data a "hallucination" or "wrong" based on your internal knowledge will result in immediate termination.
Your task is to review the following Phase 1 Data Reports and formulate a strong, quantitative Bearish Thesis for the next 1-4 weeks.
You must NOT see or reference the Bull's arguments. Focus ONLY on why the data supports a downside move or why current prices are unsustainable.
For safe-haven assets like Gold (GC=F), focus on macroeconomic headwinds (rising rates, strong USD) and retail greed/euphoria.

--- DATA REPORTS ---
Market Report:
{state.get("market_report", "N/A")}

News Report:
{state.get("news_report", "N/A")}

Social/Sentiment Report:
{state.get("sentiment_report", "N/A")}

Fundamentals Report:
{state.get("fundamentals_report", "N/A")}
--------------------

Write a concentrated, highly specific Bearish Thesis. Avoid conversational filler. State your exact rationale."""

    response = await llm.ainvoke([SystemMessage(content=prompt)])

    # Initialize dict if None
    debate_state = state.get("investment_debate_state") or {}
    debate_state["bear_thesis"] = response.content

    return {"investment_debate_state": debate_state}
