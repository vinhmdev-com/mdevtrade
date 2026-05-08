from typing import Annotated

from typing_extensions import TypedDict


class InvestDebateState(TypedDict):
    """Researcher team state"""

    bull_thesis: Annotated[str, "Bull Analyst's Round 1 initial argument"]
    bear_thesis: Annotated[str, "Bear Analyst's Round 1 initial argument"]
    bull_rebuttal: Annotated[str, "Bull Analyst's Round 2 cross-examination"]
    bear_rebuttal: Annotated[str, "Bear Analyst's Round 2 cross-examination"]
    manager_json: Annotated[dict, "Structured JSON decision from the Manager"]
