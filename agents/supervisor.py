from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage
from graph.state import CRMState
from datetime import datetime

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

def supervisor(state: CRMState) -> CRMState:
    """
    Reads deal data and routes to correct agent.
    Extracts key fields first so LLM can make accurate routing decision.
    """
    deal = state.get("deal_data", {})
    props = deal.get("properties", {})

    deal_name = props.get("dealname", "Unknown")
    stage = props.get("dealstage", "Unknown")
    close_date = props.get("closedate", "None")
    last_modified = props.get("hs_lastmodifieddate", "None")

    days_to_close = None
    if close_date and close_date != "None":
        try:
            close = datetime.fromisoformat(close_date.replace("Z", "+00:00"))
            days_to_close = (close - datetime.now(close.tzinfo)).days
        except:
            pass

    days_stale = 0
    if last_modified and last_modified != "None":
        try:
            last = datetime.fromisoformat(last_modified.replace("Z", "+00:00"))
            days_stale = (datetime.now(last.tzinfo) - last).days
        except:
            pass

    prompt = f"""You are a CRM supervisor. A HubSpot deal event came in.

    Deal: {deal_name}
    Stage: {stage}
    Days until close: {days_to_close}
    Days since last activity: {days_stale}

    Routing rules:
    - "deal_risk": if days until close <= 7 OR days since last activity >= 14
    - "end": if deal is healthy (close date far away AND recently active)

    Reply with ONLY one word: deal_risk or end.
    """
    response = llm.invoke([SystemMessage(content=prompt)])
    route = response.content.strip().lower()

    # safety fallback - if LLM returns unexpected value default to deal_risk
    if route not in ["deal_risk", "end"]:
        route = "deal_risk"

    print(f"Supervisor routed to: {route}")
    return {**state, "route": route}

def route_decision(state: CRMState) -> str:
    return state.get("route", "end")