from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from tools.hubspot_tools import add_note_to_deal, get_owner
from graph.state import CRMState
from datetime import datetime

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

# tool binding
tools = [add_note_to_deal]
llm_with_tools = llm.bind_tools(tools)

def deal_risk_agent(state: CRMState) -> CRMState:
    """
    Analyzes deal risk.
    LLM decides when to call add_note_to_deal tool.
    Fetches owner name and email for approval email later.
    """
    deal = state.get("deal_data", {})
    props = deal.get("properties", {})

    deal_name = props.get("dealname", "Unknown")
    close_date = props.get("closedate", "")
    last_modified = props.get("hs_lastmodifieddate", "")
    amount = props.get("amount", "0")
    stage = props.get("dealstage", "")
    owner_id = props.get("hubspot_owner_id", "")

    # calculate days since last activity
    days_stale = 0
    if last_modified:
        last = datetime.fromisoformat(last_modified.replace("Z", "+00:00"))
        days_stale = (datetime.now(last.tzinfo) - last).days

    # calculate days until close date
    days_to_close = None
    if close_date:
        close = datetime.fromisoformat(close_date.replace("Z", "+00:00"))
        days_to_close = (close - datetime.now(close.tzinfo)).days

    # fetch owner name and email from HubSpot
    owner_name = ""
    owner_email = ""
    if owner_id:
        owner_data = get_owner.invoke({"owner_id": owner_id})
        owner_name = f"{owner_data.get('firstname', '')} {owner_data.get('lastname', '')}".strip()
        owner_email = owner_data.get("email", "")

    deal_id = state.get("deal_id")

    is_closing_soon = days_to_close is not None and days_to_close < 7
    is_stale = days_stale > 14
    risk_level = "HIGH RISK" if (is_closing_soon or is_stale) else "LOW RISK"
    risk_reason = []
    if is_closing_soon:
        days_text = "day" if days_to_close == 1 else "days"  # ← fix grammar
        risk_reason.append(f"closing in {days_to_close} {days_text}")
    if is_stale:
        days_text = "day" if days_stale == 1 else "days"  # ← fix grammar
        risk_reason.append(f"no activity for {days_stale} {days_text}")
    risk_summary = f"{risk_level}: {', '.join(risk_reason) if risk_reason else 'deal is healthy'}"

    note_logged = False

    messages = [
        SystemMessage(content=f"""You are a CRM deal risk analyst.

    Deal: {deal_name} | Amount: ${amount} | Owner: {owner_name}
    Risk assessment: {risk_summary}

    Your only job: call add_note_to_deal with:
    - deal_id: "{deal_id}"  
    - note: "[AI Risk Analysis] {risk_summary}. Deal: {deal_name}, Amount: ${amount}, Stage: {stage}, Days until close: {days_to_close}, Days since last activity: {days_stale}. Recommendation: immediate follow-up required to prevent deal loss."

    Then respond with a 3-4 sentence analysis covering: risk level, why it's at risk, deal details, and recommended action.
    """),
        HumanMessage(content="Log the risk assessment note now and give me a detailed analysis.")
    ]

    # agentic loop - LLM decides when to call tools
    while True:
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if response.tool_calls:
            for tool_call in response.tool_calls:
                if tool_call["name"] == "add_note_to_deal":
                    if not note_logged:
                        result = add_note_to_deal.invoke(tool_call["args"])
                        note_logged = True
                        print(f"Note logged to HubSpot")
                    else:
                        result = {"status": "note already logged, skipping"}
                else:
                    result = {"error": "unknown tool"}

                messages.append(ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call["id"]
                ))
        else:
            if response.content.strip():
                break
            else:
                messages.append(HumanMessage(
                    content=f"Respond with exactly: {risk_summary}"
                ))

    # fallback — if LLM returns empty use pre-computed analysis
    analysis = response.content.strip() if response.content.strip() else risk_summary

    print(f"\nAnalysis: {analysis}")
    print(f"HIGH RISK detected: {'high risk' in analysis.lower()}")

    return {
        **state,
        "risk_analysis": analysis,
        "owner_name": owner_name,
        "owner_email": owner_email,
        "route": "recovery" if "high risk" in analysis.lower() else "end"
    }