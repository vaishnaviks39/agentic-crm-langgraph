import os
import requests
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

BASE = "https://api.hubapi.com"

def get_headers():
    """Build headers fresh every time — ensures token is always loaded."""
    return {
        "Authorization": f"Bearer {os.getenv('HUBSPOT_ACCESS_TOKEN')}",
        "Content-Type": "application/json"
    }

@tool
def get_all_deals() -> list:
    """Fetch all deals from HubSpot pipeline."""
    r = requests.get(
        f"{BASE}/crm/v3/objects/deals",
        headers=get_headers(),
        params={"properties": "dealname,amount,dealstage,closedate", "limit": 50}
    )
    return r.json().get("results", [])

@tool
def get_deal(deal_id: str) -> dict:
    """Fetch full deal details from HubSpot by deal ID."""
    r = requests.get(
        f"{BASE}/crm/v3/objects/deals/{deal_id}",
        headers=get_headers(),
        params={"properties": "dealname,amount,dealstage,closedate,hs_lastmodifieddate,hubspot_owner_id"}
    )
    return r.json()

@tool
def update_deal_stage(deal_id: str, new_stage: str) -> dict:
    """Update a deal's stage in HubSpot."""
    r = requests.patch(
        f"{BASE}/crm/v3/objects/deals/{deal_id}",
        headers=get_headers(),
        json={"properties": {"dealstage": new_stage}}
    )
    return r.json()

@tool
def get_contact_for_deal(deal_id: str) -> dict:
    """Get the contact associated with a deal."""
    r = requests.get(
        f"{BASE}/crm/v3/objects/deals/{deal_id}/associations/contacts",
        headers=get_headers()
    )
    contacts = r.json().get("results", [])
    if not contacts:
        return {"error": "No contact found"}
    contact_id = contacts[0]["id"]
    cr = requests.get(
        f"{BASE}/crm/v3/objects/contacts/{contact_id}",
        headers=get_headers(),
        params={"properties": "firstname,lastname,email,company"}
    )
    return cr.json()

@tool
def add_note_to_deal(deal_id: str, note: str) -> dict:
    """Add a note to a deal in HubSpot."""
    import time
    r = requests.post(
        f"{BASE}/crm/v3/objects/notes",
        headers=get_headers(),
        json={
            "properties": {
                "hs_timestamp": str(int(time.time() * 1000)),
                "hs_note_body": note
            },
            "associations": [
                {
                    "to": {"id": deal_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 214
                        }
                    ]
                }
            ]
        }
    )
    return r.json()

@tool
def get_owner(owner_id: str) -> dict:
    """Fetch HubSpot owner/sales rep details by owner ID."""
    r = requests.get(
        f"{BASE}/crm/v3/owners/{owner_id}",
        headers=get_headers()
    )
    data = r.json()
    return {
        "id": data.get("id"),
        "firstname": data.get("firstName", ""),
        "lastname": data.get("lastName", ""),
        "email": data.get("email", "")
    }