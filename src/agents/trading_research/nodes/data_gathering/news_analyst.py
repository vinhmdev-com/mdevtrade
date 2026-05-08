import logging

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from src.agents.trading_research.states.trading_analysis_state import (
    TradingAnalysisState,
)
from src.config.settings import settings
from src.llm_clients.factory import create_llm_client

from .tools.news_tools import get_financial_news

logger = logging.getLogger(__name__)

# 1. Initialize LLM Client from Factory (based on .env config)
client = create_llm_client(
    provider="openai", model=settings.llm_deep_model, base_url=settings.llm_base_url
)
llm = client.get_llm()

# 2. Create a Sub-agent dedicated to executing Tools
# create_react_agent automatically handles the ReAct loop: LLM -> Call Tool -> Read Result -> LLM -> Conclusion.
news_agent = create_react_agent(
    model=llm,
    tools=[get_financial_news],
    prompt=(
        "You are an expert financial News Analyst. "
        "Your task is to use the provided tools to fetch the latest macroeconomic and financial news for the requested ticker. "
        "Filter out irrelevant short-term intraday noise and focus purely on catalysts that drive short-to-medium term trends (1 to 4 weeks). "
        "Apply dynamic asset logic: If analyzing Gold or broad indices, focus heavily on Macro catalysts like Interest Rates, Inflation (CPI), and Geopolitics. "
        "If analyzing individual tech/crypto assets, focus on sector news, earnings, and adoption. "
        "Format your report clearly with Markdown, and conclude with a Fundamental Bias (Bullish/Bearish/Neutral)."
    ),
)


# 3. Main Node function to be integrated into the Graph
async def news_analyst(state: TradingAnalysisState):
    logger.info(
        "📰 [3] News Analyst: Calling Tools to gather and analyze financial news..."
    )

    # Retrieve the ticker from State (Default to GC=F if not provided)
    ticker = state.get("company_of_interest", "GC=F")

    # Define the execution prompt for the sub-agent
    prompt_text = (
        f"Please fetch and analyze the latest news for {ticker}.\n"
        f"Note: The instrument to analyze is `{ticker}`. Use this exact ticker in your tool calls.\n"
        f"Evaluate if the current news cycle supports a Bullish or Bearish fundamental bias for the next 1-4 weeks."
    )

    # Run the sub-agent and wait for it to loop through the Tools
    response = await news_agent.ainvoke(
        {"messages": [HumanMessage(content=prompt_text)]}
    )

    # The final result is in the last message of the sub-agent's messages array
    final_report = response["messages"][-1].content

    # Return the report to update the TradingAnalysisState
    return {"news_report": final_report}
