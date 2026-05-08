import logging
from datetime import datetime

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.prebuilt import create_react_agent

from src.agents.trading_research.states.trading_analysis_state import (
    TradingAnalysisState,
)
from src.config.settings import settings
from src.llm_clients.factory import create_llm_client

from .tools.market_tools import get_indicators, get_stock_data

logger = logging.getLogger(__name__)

# 1. Initialize LLM Client from Factory
client = create_llm_client(
    provider="openai", model=settings.llm_deep_model, base_url=settings.llm_base_url
)
llm = client.get_llm()

# Define the comprehensive system message for the Market Analyst
system_message = (
    "You are an expert financial Market Analyst. Your role is to select the **most relevant indicators** for a given market condition or trading strategy from the following list. "
    "The goal is to choose up to **8 indicators** that provide complementary insights without redundancy. Categories and each category's indicators are:\n\n"
    "Moving Averages:\n"
    "- close_50_sma: 50 SMA: A medium-term trend indicator. Usage: Identify trend direction and serve as dynamic support/resistance.\n"
    "- close_200_sma: 200 SMA: A long-term trend benchmark. Usage: Confirm overall market trend and identify golden/death cross setups.\n"
    "- close_10_ema: 10 EMA: A responsive short-term average. Usage: Capture quick shifts in momentum and potential entry points.\n\n"
    "MACD Related:\n"
    "- macd: MACD: Computes momentum via differences of EMAs. Usage: Look for crossovers and divergence as signals of trend changes.\n"
    "- macds: MACD Signal: An EMA smoothing of the MACD line. Usage: Use crossovers with the MACD line to trigger trades.\n"
    "- macdh: MACD Histogram: Shows the gap between the MACD line and its signal. Usage: Visualize momentum strength and spot divergence early.\n\n"
    "Momentum Indicators:\n"
    "- rsi: RSI: Measures momentum to flag overbought/oversold conditions. Usage: Apply 70/30 thresholds and watch for divergence to signal reversals.\n\n"
    "Volatility Indicators:\n"
    "- boll: Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. Usage: Acts as a dynamic benchmark for price movement.\n"
    "- boll_ub: Bollinger Upper Band: Typically 2 standard deviations above the middle line. Usage: Signals potential overbought conditions and breakout zones.\n"
    "- boll_lb: Bollinger Lower Band: Typically 2 standard deviations below the middle line. Usage: Indicates potential oversold conditions.\n"
    "- atr: ATR: Averages true range to measure volatility. Usage: Set stop-loss levels and adjust position sizes based on current market volatility.\n\n"
    "Volume-Based Indicators:\n"
    "- vwma: VWMA: A moving average weighted by volume. Usage: Confirm trends by integrating price action with volume data.\n"
    "- mfi: MFI: The Money Flow Index is a momentum indicator that uses both price and volume to measure buying and selling pressure.\n\n"
    "INSTRUCTIONS:\n"
    "1. Select indicators that provide diverse and complementary information. Avoid redundancy (e.g., do not select both rsi and stochrsi).\n"
    "2. Briefly explain why they are suitable for the given market context.\n"
    "3. ALWAYS call `get_stock_data` first to retrieve the OHLCV CSV that is needed to understand the basic price movement.\n"
    "4. Then use `get_indicators` with the specific indicator names you selected (comma-separated if multiple).\n"
    "5. Write a very detailed and nuanced report of the trends you observe based strictly on the data you retrieved. DO NOT HALLUCINATE OR GUESS INDICATOR VALUES.\n"
    "6. Provide specific, actionable insights with supporting evidence to help traders make informed decisions.\n"
    "7. Append a Markdown table at the end of the report to organize key points."
)

# 2. Create a Sub-agent dedicated to running Tools
market_agent = create_react_agent(
    model=llm, tools=[get_stock_data, get_indicators], prompt=system_message
)


# 3. Main Node function to be plugged into the Graph
async def market_analyst(state: TradingAnalysisState):
    logger.info("📊 [1] Market Analyst: Calling Technical Analysis Tools...")

    import pytz

    ticker = state.get("company_of_interest", "GC=F")

    # Normalize crypto tickers for Yahoo Finance (e.g., BTC/USDT -> BTC-USD)
    yf_ticker = ticker
    if "/" in ticker:
        base = ticker.split("/")[0]
        yf_ticker = f"{base}-USD"

    # Fallback to US Eastern Time (New York) since yfinance data is aligned with the US market
    ny_date = datetime.now(pytz.timezone("America/New_York")).strftime("%Y-%m-%d")
    trade_date = state.get("trade_date", ny_date)

    # Optimize data input (Prof. Reyrod's advice)
    # Pass only 30 days of raw OHLCV data to the LLM to prevent 'Lost in the middle' hallucination
    from datetime import timedelta

    try:
        trade_dt = datetime.strptime(trade_date, "%Y-%m-%d")
    except Exception:
        trade_dt = datetime.now()

    start_dt = trade_dt - timedelta(days=30)
    end_dt = trade_dt + timedelta(
        days=1
    )  # yfinance end_date is exclusive, add 1 day to include today

    start_date_30d = start_dt.strftime("%Y-%m-%d")
    end_date_inclusive = end_dt.strftime("%Y-%m-%d")

    prompt_text = (
        f"Please analyze {yf_ticker} (original asset: {ticker}). The current trading date is {trade_date}.\n"
        f"Note: The instrument to analyze is `{yf_ticker}`. Use this exact ticker in every tool call, preserving any exchange suffix.\n"
        f"First, fetch the basic stock data (raw OHLCV) using exactly start_date='{start_date_30d}' and end_date='{end_date_inclusive}' (Note: end_date is exclusive, so it fetches up to {trade_date}) to understand the recent 30-day microstructure.\n"
        f"Then, you MUST select and pull the following 5 specific indicators: close_50_sma, close_200_sma, rsi, macd, atr. Use exactly curr_date='{trade_date}' for the indicators.\n"
        f"Finally, generate the comprehensive technical analysis report. Focus on identifying the 1-3 months trend bias, and finding 1-4 weeks tactical entry points/take-profit levels."
    )

    # Run the sub-agent and wait for it to loop through the Tools
    response = await market_agent.ainvoke(
        {"messages": [HumanMessage(content=prompt_text)]}
    )

    # The final result is in the last message of the sub-agent's messages array
    final_report = response["messages"][-1].content

    # Extract current_price directly using yfinance to avoid LLM hallucination
    import yfinance as yf

    try:
        import asyncio
        from src.agents.trading_research.nodes.data_gathering.utils.stockstats_utils import (
            load_ohlcv,
        )

        # Wrap in asyncio.to_thread because load_ohlcv makes blocking os.getcwd() calls
        df = await asyncio.to_thread(load_ohlcv, yf_ticker, trade_date)
        if not df.empty:
            current_price = float(df["Close"].iloc[-1])
        else:
            current_price = 0.0
            logger.warning(
                f"Could not fetch current price from load_ohlcv for {yf_ticker}"
            )
    except Exception as e:
        logger.error(f"Error fetching current price: {e}")
        current_price = 0.0

    # Return the report and the hard data to update the TradingAnalysisState
    return {"market_report": final_report, "current_price": current_price}
