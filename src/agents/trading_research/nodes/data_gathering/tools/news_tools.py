import yfinance as yf
from langchain_core.tools import tool


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
        import datetime

        for item in news_items[
            :10
        ]:  # Tăng lên 10 tin để lấy được bức tranh toàn cảnh hơn
            title = item.get("title", "No Title")
            publisher = item.get("publisher", "Unknown Publisher")

            # Lấy thời gian đăng bài để AI biết tin này là cũ hay mới
            publish_time = item.get("providerPublishTime")
            if publish_time:
                date_str = datetime.datetime.fromtimestamp(publish_time).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            else:
                date_str = "Unknown Date"

            # Lấy summary để AI có nội dung phân tích thay vì chỉ đọc mỗi cái Title
            summary = item.get("summary", "No summary available.")

            report += f"Date: {date_str}\n"
            report += f"Title: {title}\n"
            report += f"Publisher: {publisher}\n"
            report += f"Summary: {summary}\n"
            report += "-" * 50 + "\n"

        return report
    except Exception as e:
        return f"Error fetching news for {ticker}: {str(e)}"
