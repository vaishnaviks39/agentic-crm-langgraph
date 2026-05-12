import os
import time
from fastapi import FastAPI, Request
from tools.hubspot_tools import get_deal, get_all_deals, add_note_to_deal
from graph.workflow import build_graph
from langchain_core.messages import HumanMessage
import uvicorn
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver

load_dotenv()
print("TOKEN:", os.getenv("HUBSPOT_ACCESS_TOKEN"))

app = FastAPI()

# SQLite connection stays open for entire server lifetime
with SqliteSaver.from_conn_string("crm_memory.db") as memory:
    graph = build_graph(memory)

    @app.get("/")
    def home():
        return {"message": "CRM Autopilot API is running"}

    @app.post("/webhook")
    async def hubspot_webhook(request: Request):
        """Receives real HubSpot webhook events."""
        body = await request.json()

        for event in body:
            deal_id = str(event.get("objectId", ""))
            if not deal_id:
                continue

            # Fetch full deal data from HubSpot
            deal_data = get_deal.invoke({"deal_id": deal_id})

            # unique thread ID every run — prevents conflicts with old saved state
            thread_id = f"{deal_id}_{int(time.time())}"
            config = {"configurable": {"thread_id": thread_id}}

            # Build initial state
            initial_state = {
                "messages": [HumanMessage(content=f"New deal event for deal {deal_id}")],
                "deal_id": deal_id,
                "deal_data": deal_data,
                "risk_analysis": "",
                "draft_action": "",
                "contact_email": "",
                "owner_name": "",
                "owner_email": "",
                "thread_id": thread_id,
                "route": "",
                "awaiting_approval": False,
                "approved": False
            }

            result = graph.invoke(initial_state, config=config)

            print(f"\n[CRM Autopilot] Deal {deal_id} processed")
            print(f"Risk: {result.get('risk_analysis', 'none')}")
            if result.get('draft_action'):
                print(f"\n--- DRAFT (awaiting approval) ---")
                print(result['draft_action'])
                print(f"\n--- Run GET /approve/{thread_id} to approve ---\n")

        return {"status": "ok"}

    @app.get("/approve/{thread_id}")
    async def approve_action(thread_id: str):
        """Human approves via email link — browser sends GET request."""
        config = {"configurable": {"thread_id": thread_id}}

        # resume graph from where it paused
        graph.invoke(None, config=config)

        # fetch latest state AFTER graph finishes
        latest_state = graph.get_state(config)
        deal_name = latest_state.values.get("deal_data", {}).get("properties", {}).get("dealname", "")

        return {
            "status": "Approved! Recovery email sent to contact.",
            "deal": deal_name,
            "approved": latest_state.values.get("approved"),
            "awaiting_approval": latest_state.values.get("awaiting_approval")
        }

    @app.get("/reject/{thread_id}")
    async def reject_action(thread_id: str, reason: str = "No reason provided"):
        """Human rejects via email link — browser sends GET request."""
        config = {"configurable": {"thread_id": thread_id}}

        # get current state to find deal_id
        current_state = graph.get_state(config)
        deal_id = current_state.values.get("deal_id")
        deal_name = current_state.values.get("deal_data", {}).get("properties", {}).get("dealname", "")

        # log rejection to HubSpot
        add_note_to_deal.invoke({
            "deal_id": deal_id,
            "note": f"[AI Draft Rejected] Reason: {reason}. Sales rep will follow up manually."
        })

        print(f"\nDraft rejected for deal {deal_id} — Reason: {reason}\n")

        return {
            "status": "Rejected. Note logged to HubSpot.",
            "deal": deal_name
        }

    @app.get("/pipeline")
    async def get_pipeline():
        """Quick endpoint to check all deals."""
        deals = get_all_deals.invoke({})
        return {"deals": deals, "count": len(deals)}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8000)