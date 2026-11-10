"""DecisionSpec: what the LLM extracts; Python evaluates it. The LLM never decides eligibility."""
from typing import Any, Literal

from pydantic import BaseModel, Field

Operator = Literal[">=", "<=", ">", "<", "==", "!=", "in", "not_in"]
ValueType = Literal["number", "inr", "cgpa", "percentage", "year", "category", "bool", "days", "text"]
Result = Literal["TRUE", "FALSE", "UNKNOWN"]


class Source(BaseModel):
    filename: str
    page: int


class Condition(BaseModel):
    id: str
    label: str
    field: str  # key into DecisionSpec.user_facts
    operator: Operator
    value: Any
    value_type: ValueType
    source: Source | None = None
    required: bool = True
    weight: float = 1.0


class Choice(BaseModel):
    id: str
    label: str
    criteria: list[Condition]


class Conversions(BaseModel):
    cgpa_to_percentage: float | None = None  # only if the document states it (e.g. 9.5)
    source: Source | None = None


class DecisionSpec(BaseModel):
    user_facts: dict[str, Any] = Field(default_factory=dict)
    conditions: list[Condition] = Field(default_factory=list)
    choices: list[Choice] = Field(default_factory=list)
    combine: Literal["ALL", "ANY"] = "ALL"
    conversions: Conversions | None = None
