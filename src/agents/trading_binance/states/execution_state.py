from typing import Any, Dict, Literal, TypedDict


class ExecutionState(TypedDict):
    """
    State for the Binance Execution Graph.
    """

    # Signal from Research AI
    macro_trend: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    signal_id: int
    entry_price: float

    # Wallet balances fetched from Binance
    usdt_balance: float
    xaut_balance: float

    # Portfolio tracking for Circuit Breaker
    current_price: float
    portfolio_value: float
    peak_portfolio_value: float
    drawdown_pct: float

    # Execution decision
    action_taken: Literal["BUY", "SELL", "PAUSE", "SKIP", "NONE"]
    action_amount: float
    action_message: str
