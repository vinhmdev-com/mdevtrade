import logging

from langchain_core.messages import SystemMessage

from src.agents.trading_research.states.trading_analysis_state import (
    TradingAnalysisState,
)
from src.config.settings import settings
from src.llm_clients.factory import create_llm_client

logger = logging.getLogger(__name__)


async def bear_rebuttal_node(state: TradingAnalysisState):
    logger.info("🐻⚔️ [6B] Bear Analyst (Round 2): Cross-examining Bull Thesis...")

    client = create_llm_client(
        provider="openai", model=settings.llm_deep_model, base_url=settings.llm_base_url
    )
    llm = client.get_llm()

    debate_state = state.get("investment_debate_state", {})
    bull_thesis = debate_state.get("bull_thesis", "N/A")

    market_data = state.get("market_report", "N/A")
    social_data = state.get("sentiment_report", "N/A")
    news_data = state.get("news_report", "N/A")
    fundamentals_data = state.get("fundamentals_report", "N/A")

    prompt = f"""You are the Bear Analyst. 
First, review the original data reports to ground your facts:

--- PHASE 1 DATA REPORTS ---
Market:
{market_data}

Social Sentiment:
{social_data}

News & Macro:
{news_data}

Fundamentals:
{fundamentals_data}
----------------------------
In Round 1, your opponent (the Bull Analyst) wrote the following Bullish Thesis:

--- BULL THESIS ---
{bull_thesis}
-------------------

Your ONLY task in Round 2 is to write a targeted rebuttal. 
DO NOT restate your original thesis. 
Identify the single weakest logical assumption, ignored data point, or macroeconomic vulnerability in the Bull's argument, and dismantle it.
Be sharp, analytical, and highly critical of their logic. Keep it concise.

CRITICAL INSTRUCTION: You must base your arguments STRICTLY on the data provided in the Market Report context. DO NOT use your pre-trained knowledge to guess asset prices. You must accept the prices and data provided in the reports as the absolute truth. Calling the provided data a "hallucination" or "wrong" based on your internal knowledge will result in immediate termination."""

    response = await llm.ainvoke([SystemMessage(content=prompt)])
    debate_state["bear_rebuttal"] = response.content

    return {"investment_debate_state": debate_state}
