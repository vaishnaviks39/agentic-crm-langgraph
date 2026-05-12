from typing import TypedDict, Annotated, Literal
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class CRMState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    deal_id: str
    deal_data: dict
    risk_analysis: str
    draft_action: str
    contact_email: str
    owner_name: str
    owner_email: str
    thread_id: str 
    route: Literal["deal_risk", "recovery", "pipeline", "end"]
    awaiting_approval: bool
    approved: bool