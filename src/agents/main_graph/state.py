from src.agents.trading_binance.states.execution_state import ExecutionState
from src.agents.trading_research.states.trading_analysis_state import (
    TradingAnalysisState,
)


class MainState(TradingAnalysisState):
    """
    Unified state for the Main Orchestrator Graph.
    Inherits fields from Research and explicitly adds Execution fields.
    """

    # Fields from ExecutionState
    macro_trend: str
    signal_id: int
    entry_price: float

    usdt_balance: float
    xaut_balance: float

    portfolio_value: float
    peak_portfolio_value: float
    drawdown_pct: float

    action_taken: str
    action_amount: float
    action_message: str
