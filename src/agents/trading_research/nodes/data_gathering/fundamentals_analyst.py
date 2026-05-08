import logging

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from src.agents.trading_research.states.trading_analysis_state import (
    TradingAnalysisState,
)
from src.config.settings import settings
from src.llm_clients.factory import create_llm_client

from .tools.fundamental_tools import get_company_fundamentals

logger = logging.getLogger(__name__)

# 1. Initialize LLM Client
client = create_llm_client(
    provider="openai", model=settings.llm_deep_model, base_url=settings.llm_base_url
)
llm = client.get_llm()

# 2. Create the Fundamentals Analyst Sub-agent
fundamentals_agent = create_react_agent(
    model=llm,
    tools=[get_company_fundamentals],
    prompt=(
        "You are an expert Fundamental Analyst. "
        "Your task is to analyze a company's financial health, valuation, and growth prospects using the provided tools. "
        "Evaluate metrics such as P/E ratio, PEG ratio, Profit Margins, and ROE. "
        "Determine if the asset is Undervalued, Overvalued, or Fairly Valued compared to historical and market norms. "
        "Write a concise report highlighting the key strengths and weaknesses of the company's fundamentals. "
        "Conclude with a Fundamental Bias (Bullish/Bearish/Neutral) from a long-term value investing perspective."
    ),
)


# 3. Main Node function to be integrated into the Graph
async def fundamentals_analyst(state: TradingAnalysisState):
    logger.info("🏢 [4] Fundamentals Analyst: Checking execution flag...")

    # Bypass logic: Check if fundamentals analysis is enabled
    # Default to False to save LLM tokens for commodities like Gold
    is_enabled = state.get("enable_fundamentals", False)

    if not is_enabled:
        logger.info("🏢 [4] Fundamentals Analyst: Disabled by user. Bypassing node.")
        return {
            "fundamentals_report": "Fundamentals analysis disabled or not applicable for this run."
        }

    logger.info(
        "🏢 [4] Fundamentals Analyst: Calling Tools to gather financial metrics..."
    )

    ticker = state.get("company_of_interest", "AAPL")

    prompt_text = (
        f"Please fetch and analyze the latest fundamental metrics for {ticker}.\n"
        f"Note: Use the exact ticker in your tool calls.\n"
        f"Evaluate if the company's fundamentals support a Bullish or Bearish setup for a medium-to-long term investment."
    )

    # Run the sub-agent
    response = await fundamentals_agent.ainvoke(
        {"messages": [HumanMessage(content=prompt_text)]}
    )

    # The final result is in the last message
    final_report = response["messages"][-1].content

    return {"fundamentals_report": final_report}
