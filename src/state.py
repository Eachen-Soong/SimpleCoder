from typing import List, Literal, Optional

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


class Step(BaseModel):
    title: str = ""
    description: str = ""
    status: Literal["pending", "completed"] = "pending"


class Plan(BaseModel):
    goal: str = ""
    thought: str = ""
    steps: List[Step] = Field(default_factory=list)


class State(MessagesState):
    user_message: str = ""
    plan: Optional[Plan] = None
    observations: List = Field(default_factory=list)
    final_report: str = ""
