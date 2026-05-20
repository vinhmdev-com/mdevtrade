import datetime

import yfinance as yf
from langchain_core.tools import tool


def _parse_pub_date(raw: str | None) -> str:
    if not raw:
        return "Unknown Date"
    try:
        # yfinance returns ISO 8601 like "2026-05-19T10:54:00Z"
        return datetime.datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except (TypeError, ValueError):
        return str(raw)


@tool
def get_financial_news(ticker: str) -> str:
    """
    Retrieve the latest financial news for a given ticker symbol.
    Uses yfinance to fetch news articles related to the ticker.
    Args:
        ticker (str): The ticker symbol (e.g., 'AAPL', 'MSFT', 'GC=F' for Gold).
    Returns:
        str: A formatted string containing the titles, publishers, and summaries of the news.
    """
    try:
        stock = yf.Ticker(ticker)
        news_items = stock.news
        if not news_items:
            return f"No news found for ticker {ticker}."

        report = f"--- LATEST NEWS FOR {ticker} ---\n\n"

        for item in news_items[:10]:
            # yfinance >= 0.2.x wraps each item as {"id": ..., "content": {...}}.
            content = item.get("content") or item
            title = content.get("title") or "No Title"
            summary = content.get("summary") or content.get("description") or "No summary available."
            provider = content.get("provider") or {}
            publisher = provider.get("displayName") or "Unknown Publisher"
            date_str = _parse_pub_date(content.get("pubDate") or content.get("displayTime"))

            report += f"Date: {date_str}\n"
            report += f"Title: {title}\n"
            report += f"Publisher: {publisher}\n"
            report += f"Summary: {summary}\n"
            report += "-" * 50 + "\n"

        return report
    except Exception as e:
        return f"Error fetching news for {ticker}: {str(e)}"
