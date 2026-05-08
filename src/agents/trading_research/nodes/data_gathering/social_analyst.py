import logging

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from src.agents.trading_research.states.trading_analysis_state import (
    TradingAnalysisState,
)
from src.config.settings import settings
from src.llm_clients.factory import create_llm_client

from .tools.social_tools import get_stocktwits_sentiment

logger = logging.getLogger(__name__)

# 1. Initialize LLM Client from Factory (based on .env config)
client = create_llm_client(
    provider="openai", model=settings.llm_deep_model, base_url=settings.llm_base_url
)
llm = client.get_llm()

# 2. Create the Social Analyst Sub-agent
# create_react_agent automatically handles the ReAct loop: LLM -> Call Tool -> Read Result -> LLM -> Conclusion.
social_agent = create_react_agent(
    model=llm,
    tools=[get_stocktwits_sentiment],
    prompt=(
        "You are an expert Social Media & Crowd Psychology Analyst. "
        "Your task is to analyze social sentiment from platforms like StockTwits to gauge Retail/Trader Sentiment. "
        "Filter out spam and focus on identifying whether the crowd is currently driven by Extreme Fear (Panic) or Extreme Greed (Euphoria). "
        "Apply dynamic asset logic: If the requested ticker is a safe-haven asset (like Gold), remember that Crowd Fear is usually a Bullish catalyst. "
        "If the requested ticker is a risk-on asset (like Stocks or Crypto), Crowd Fear is usually a Bearish catalyst. "
        "Write a concise report highlighting the current psychological state of retail traders and conclude with a Sentiment Bias (Bullish/Bearish/Neutral) for the next 1-4 weeks."
    ),
)


# 3. Main Node function to be integrated into the Graph
async def social_analyst(state: TradingAnalysisState):
    logger.info(
        "📱 [2] Social Analyst: Calling Tools to gather Market Sentiment (Fear/Greed)..."
    )

    # Retrieve the ticker from State (Default to GC=F if not provided)
    ticker = state.get("company_of_interest", "GC=F")

    # Define the execution prompt for the sub-agent
    prompt_text = (
        f"Please fetch and analyze the latest social sentiment for {ticker}.\n"
        f"Note: Use the exact ticker in your tool calls (the tool will handle formatting).\n"
        f"Evaluate if the current crowd psychology supports a Bullish or Bearish setup for the next 1-4 weeks."
    )

    # Run the sub-agent and wait for it to loop through the Tools
    response = await social_agent.ainvoke(
        {"messages": [HumanMessage(content=prompt_text)]}
    )

    # The final result is in the last message of the sub-agent's messages array
    final_report = response["messages"][-1].content

    # Return the report to update the TradingAnalysisState
    return {"sentiment_report": final_report}
