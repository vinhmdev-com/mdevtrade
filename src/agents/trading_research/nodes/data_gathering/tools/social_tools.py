import requests
from langchain_core.tools import tool

from ..utils.stockstats_utils import format_ticker_for_social


@tool
def get_stocktwits_sentiment(ticker: str) -> str:
    """
    Retrieve the latest social sentiment and discussions from StockTwits for a given ticker symbol.
    Args:
        ticker (str): The ticker symbol (e.g., 'AAPL', 'MSFT', 'GC=F' for Gold).
    Returns:
        str: A formatted string containing the recent messages and their sentiment (Bullish/Bearish).
    """
    try:
        # Use the utility function to format the ticker for StockTwits
        formatted_ticker = format_ticker_for_social(ticker)
        url = f"https://api.stocktwits.com/api/2/streams/symbol/{formatted_ticker}.json"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        messages = data.get("messages", [])
        if not messages:
            return f"No recent StockTwits messages found for ticker {ticker}."

        report = f"--- LATEST STOCKTWITS SOCIAL SENTIMENT FOR {ticker} ---\n\n"

        # Count sentiment explicitly to give a quick overview to the LLM
        bullish = 0
        bearish = 0

        for msg in messages[:20]:  # Get top 20 latest posts
            body = msg.get("body", "")
            created_at = msg.get("created_at", "Unknown Date")

            entities = msg.get("entities", {})
            sentiment_obj = entities.get("sentiment")
            sentiment = "None"
            if sentiment_obj and sentiment_obj.get("basic"):
                sentiment = sentiment_obj.get("basic")
                if sentiment == "Bullish":
                    bullish += 1
                if sentiment == "Bearish":
                    bearish += 1

            report += f"Date: {created_at}\n"
            report += f"Sentiment Tag: {sentiment}\n"
            report += f"Message: {body}\n"
            report += "-" * 50 + "\n"

        summary = (
            f"QUICK STATS FROM TOP 20 POSTS: {bullish} Bullish, {bearish} Bearish.\n\n"
        )
        return summary + report

    except Exception as e:
        return f"Error fetching StockTwits data for {ticker}. It's possible the ticker is not supported or API is rate-limited. Details: {str(e)}"
