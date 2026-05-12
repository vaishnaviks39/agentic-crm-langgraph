# Agentic CRM System Using LangGraph

An event-driven multi-agent AI system that monitors HubSpot deals in real time, detects at-risk opportunities, drafts personalized recovery emails, and routes them for human approval — all triggered automatically via webhooks.

---

## What It Does

When a deal changes in HubSpot, a webhook fires and the system kicks off automatically:

1. The **Supervisor agent** reads the deal data and routes to the deal risk agent
2. The **Deal Risk agent** analyzes the deal, flags it as HIGH RISK if closing in under 7 days or inactive for over 14 days, and logs a note to HubSpot
3. The **Recovery agent** fetches the contact details, drafts a personalized recovery email signed with the owner's real name
4. An **approval email is sent to the deal owner** with Approve and Reject links
5. If the owner clicks Approve, the email is sent to the contact via Gmail and the activity is logged to the HubSpot deal timeline
6. If the owner clicks Reject, a rejection note is logged to HubSpot instead

---

## Architecture

```
HubSpot Webhook
      ↓
Supervisor Agent       (LangGraph StateGraph, routes by intent)
      ↓
Deal Risk Agent        (LLM analyzes risk, logs note to HubSpot)
      ↓
Recovery Agent         (LLM fetches contact, drafts recovery email)
      ↓
    PAUSE              (Human-in-the-loop via interrupt_before)
      ↓
Owner clicks Approve
      ↓
Send Action            (Gmail sends email, HubSpot note logged)
```

Multi-agent pattern: Supervisor architecture with three specialist sub-agents.

---

## Tech Stack

| Layer | Tech |
|---|---|
| Agent orchestration | LangGraph (StateGraph, conditional edges, checkpointing) |
| LLM | Groq (llama-3.3-70b-versatile) |
| LLM framework | LangChain |
| CRM integration | HubSpot REST API |
| Email | Gmail API |
| Persistence | SQLite (LangGraph checkpointer) |
| API server | FastAPI |
| Webhook tunnel | ngrok |

---

## Key Features

- Real HubSpot webhooks so the system is event-driven, not polling
- Truly agentic tool calling where the LLM autonomously decides when to call tools like `get_contact_for_deal`
- Human-in-the-loop approval where the agent pauses before sending and the owner approves via a simple email link
- Persistent SQLite state so pending approvals survive server restarts
- Real Gmail sending so approved emails actually land in the contact's inbox
- Full CRM audit trail with every AI action logged as a note on the HubSpot deal timeline

---

## Project Structure

```
agentic-crm-langgraph/
├── agents/
│   ├── supervisor.py          # Routes webhook events to correct agent
│   ├── deal_risk_agent.py     # Analyzes deal risk, logs to HubSpot
│   └── recovery_agent.py      # Drafts email, sends approval request, handles send
├── tools/
│   ├── hubspot_tools.py       # HubSpot REST API tools
│   └── gmail_tools.py         # Gmail send tool
├── graph/
│   ├── workflow.py            # LangGraph StateGraph definition
│   └── state.py               # Shared CRMState TypedDict
├── main.py                    # FastAPI server with webhook, approve, reject endpoints
├── requirements.txt
└── .env.example
```

---

## Setup

**1. Clone and install**

```bash
git clone https://github.com/yourusername/agentic-crm-langgraph.git
cd agentic-crm-langgraph
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**2. Configure environment variables**

```bash
cp .env.example .env
```

Fill in `.env`:

```
HUBSPOT_ACCESS_TOKEN=your_hubspot_private_app_token
GROQ_API_KEY=your_groq_api_key
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=agentic-crm-langgraph
BASE_URL=http://localhost:8000
```

**3. Set up Gmail**

Create a Google Cloud project, enable the Gmail API, download `credentials.json` and place it in the project root. Then run this once to authenticate:

```bash
python tools/gmail_tools.py
```

**4. Set up HubSpot**

Create a free HubSpot account and a Private App with these scopes: `crm.objects.deals.read/write`, `crm.objects.contacts.read`, `crm.objects.notes.write`, `crm.objects.owners.read`. Copy the access token to `.env`.

**5. Run the server**

```bash
python main.py
```

**6. Expose via ngrok**

```bash
ngrok http 8000
```

Copy the ngrok URL and set it as your HubSpot webhook target:

```
https://your-ngrok-url.ngrok-free.app/webhook
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/webhook` | Receives HubSpot deal events |
| GET | `/approve/{thread_id}` | Approves draft and sends email to contact |
| GET | `/reject/{thread_id}` | Rejects draft and logs note to HubSpot |
| GET | `/pipeline` | Returns all deals from HubSpot |

---

## How Human-in-the-Loop Works

When a deal is flagged HIGH RISK the agent pauses using LangGraph's `interrupt_before` and saves the graph state to SQLite. The deal owner then receives an approval email with two clickable links. Clicking Approve resumes the graph and sends the email. Clicking Reject logs the rejection to HubSpot. Because state is persisted in SQLite, the server can be restarted without losing any pending approvals.

---

## Environment Variables

| Variable | Description |
|---|---|
| `HUBSPOT_ACCESS_TOKEN` | HubSpot Private App token |
| `GROQ_API_KEY` | Groq API key (free tier works) |
| `LANGSMITH_API_KEY` | LangSmith for tracing (optional) |
| `BASE_URL` | Server URL used in approve and reject links |
