import os
from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from tools.hubspot_tools import get_contact_for_deal, add_note_to_deal
from tools.gmail_tools import send_email
from graph.state import CRMState

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

# tool binding
tools = [get_contact_for_deal, add_note_to_deal]
llm_with_tools = llm.bind_tools(tools)


def recovery_agent(state: CRMState) -> CRMState:
    """
    RUNS BEFORE APPROVAL.
    LLM fetches contact and drafts recovery email.
    Then sends approval email to deal owner with approve/reject links.
    """
    deal = state.get("deal_data", {})
    risk = state.get("risk_analysis", "")
    deal_id = state.get("deal_id")
    owner_name = state.get("owner_name", "Sales Team")
    owner_email = state.get("owner_email", "")
    thread_id = state.get("thread_id", deal_id)
    deal_name = deal.get("properties", {}).get("dealname", "")

    messages = [
        SystemMessage(content=f"""You are a CRM recovery specialist.
        Your job is to draft a recovery email for an at-risk deal.
        
        Deal ID: {deal_id}
        Deal: {deal_name}
        Risk: {risk}
        Sender name: {owner_name}
        
        Instructions:
        1. Call get_contact_for_deal to fetch contact details
        2. Draft a short warm professional email under 100 words
        3. Sign it with sender name: {owner_name}
        4. Return ONLY:
        Subject: <subject line>

        <email body>
        """),
        HumanMessage(content="Fetch the contact and draft the recovery email.")
    ]

    contact_email = ""

    # agentic loop — LLM fetches contact and drafts email
    while True:
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if response.tool_calls:
            for tool_call in response.tool_calls:
                if tool_call["name"] == "get_contact_for_deal":
                    result = get_contact_for_deal.invoke(tool_call["args"])
                    # extract contact email for sending later
                    contact_email = result.get("properties", {}).get("email", "")
                elif tool_call["name"] == "add_note_to_deal":
                    result = add_note_to_deal.invoke(tool_call["args"])
                else:
                    result = {"error": "unknown tool"}

                messages.append(ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call["id"]
                ))
        else:
            break

    draft = response.content

    print(f"\n--- DRAFT EMAIL (awaiting approval) ---")
    print(draft)

    # build approve and reject URLs
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    approve_url = f"{base_url}/approve/{thread_id}"
    reject_url = f"{base_url}/reject/{thread_id}"

    # send approval email to deal owner
    if owner_email:
        approval_body = f"""Hi {owner_name},

A recovery email draft is ready for your approval.

DEAL: {deal_name}
RISK: {risk}

DRAFT EMAIL TO SEND TO CONTACT:
{draft}

---
Click to APPROVE and send this email:
{approve_url}

Click to REJECT (no email will be sent):
{reject_url}
---

CRM Autopilot
"""
        send_email.invoke({
            "to": owner_email,
            "subject": f"[Action Required] Approve recovery email for: {deal_name}",
            "body": approval_body
        })
        print(f"\n Approval email sent to {owner_email}")
        print(f"Approve: {approve_url}")
        print(f"Reject: {reject_url}\n")
    else:
        print("\n No owner email found — skipping approval email\n")

    return {
        **state,
        "draft_action": draft,
        "contact_email": contact_email,
        "awaiting_approval": True
    }


def send_action(state: CRMState) -> CRMState:
    """
    RUNS AFTER APPROVAL.
    Sends real email to contact via Gmail and logs to HubSpot.
    """
    deal_id = state.get("deal_id")
    draft = state.get("draft_action", "")
    contact_email = state.get("contact_email", "")

    # parse subject and body from draft
    lines = draft.split("\n\n", 1)
    subject = lines[0].replace("Subject: ", "").strip()
    body = lines[1].replace("Body:", "").strip() if len(lines) > 1 else draft
    body = body.replace("\\n", "\n").strip()

    print(f"\nsend_action running for deal {deal_id}")
    print(f"Sending email to: {contact_email}")

    # send real email to contact via Gmail
    if contact_email:
        email_result = send_email.invoke({
            "to": contact_email,
            "subject": subject,
            "body": body
        })
        print(f"Email result: {email_result}")
    else:
        print("No contact email found — skipping email send")

    # log to HubSpot deal timeline
    note_result = add_note_to_deal.invoke({
        "deal_id": deal_id,
        "note": f"[AI Email Sent to {contact_email}]\n{draft}"
    })
    print(f"HubSpot note result: {note_result.get('id', 'error')}")

    print(f"\n Email sent and logged to HubSpot for deal {deal_id}\n")

    return {
        **state,
        "approved": True,
        "awaiting_approval": False
    }