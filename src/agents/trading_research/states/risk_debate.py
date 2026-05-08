from typing import Annotated

from typing_extensions import TypedDict


class RiskDebateState(TypedDict):
    """Risk management team state"""

    aggressive_evaluation: Annotated[
        str, "Aggressive Analyst's evaluation of the Trader's proposal"
    ]
    conservative_evaluation: Annotated[
        str, "Conservative Analyst's evaluation of the Trader's proposal"
    ]
    neutral_evaluation: Annotated[
        str, "Neutral Analyst's evaluation of the Trader's proposal"
    ]
