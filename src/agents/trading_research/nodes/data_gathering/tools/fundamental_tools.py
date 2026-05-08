import yfinance as yf
from langchain_core.tools import tool


@tool
def get_company_fundamentals(ticker: str) -> str:
    """
    Retrieve key fundamental metrics for a given ticker symbol (e.g. Market Cap, P/E Ratio, Margins, ROE).
    Args:
        ticker (str): The ticker symbol (e.g., 'AAPL', 'MSFT').
    Returns:
        str: A formatted string containing the fundamental metrics.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Determine if it's a valid stock by checking for typical fundamental keys
        if (
            "marketCap" not in info
            and "trailingPE" not in info
            and "revenueGrowth" not in info
        ):
            return f"Fundamentals not available for ticker {ticker}. It might be a commodity, index, or cryptocurrency."

        report = f"--- FUNDAMENTAL METRICS FOR {ticker} ---\n\n"

        # Valuation Metrics
        report += "== Valuation ==\n"
        report += f"Market Cap: {info.get('marketCap', 'N/A')}\n"
        report += f"Trailing P/E: {info.get('trailingPE', 'N/A')}\n"
        report += f"Forward P/E: {info.get('forwardPE', 'N/A')}\n"
        report += f"PEG Ratio: {info.get('pegRatio', 'N/A')}\n"
        report += f"Price to Book (P/B): {info.get('priceToBook', 'N/A')}\n\n"

        # Profitability & Growth
        report += "== Profitability & Growth ==\n"
        report += f"Profit Margin: {info.get('profitMargins', 'N/A')}\n"
        report += f"Operating Margin: {info.get('operatingMargins', 'N/A')}\n"
        report += f"Return on Equity (ROE): {info.get('returnOnEquity', 'N/A')}\n"
        report += f"Return on Assets (ROA): {info.get('returnOnAssets', 'N/A')}\n"
        report += f"Revenue Growth (YoY): {info.get('revenueGrowth', 'N/A')}\n"
        report += f"Earnings Growth (YoY): {info.get('earningsGrowth', 'N/A')}\n\n"

        # Financial Health
        report += "== Financial Health ==\n"
        report += f"Debt to Equity: {info.get('debtToEquity', 'N/A')}\n"
        report += f"Current Ratio: {info.get('currentRatio', 'N/A')}\n"

        return report

    except Exception as e:
        return f"Error fetching fundamental data for {ticker}: {str(e)}"
