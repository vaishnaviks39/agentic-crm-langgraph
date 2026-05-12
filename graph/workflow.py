from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from agents.supervisor import supervisor, route_decision
from agents.deal_risk_agent import deal_risk_agent
from agents.recovery_agent import recovery_agent, send_action
from graph.state import CRMState

def build_graph(memory):
    g = StateGraph(CRMState)

    g.add_node("supervisor", supervisor)
    g.add_node("deal_risk", deal_risk_agent)
    g.add_node("recovery", recovery_agent)
    g.add_node("send_action", send_action)

    g.set_entry_point("supervisor")

    # Supervisor routes to sub-agents based on its decision
    g.add_conditional_edges("supervisor", route_decision, {
        "deal_risk": "deal_risk",
        "recovery":  "recovery",
        "pipeline":  END,
        "end":       END
    })

    # Deal risk agent can trigger recovery agent
    g.add_conditional_edges("deal_risk", route_decision, {
        "recovery": "recovery",
        "end":      END
    })

    # recovery drafts email -> send_action logs after approval
    g.add_edge("recovery", "send_action") 
    g.add_edge("send_action", END)

    return g.compile(
        checkpointer=memory,
        interrupt_before=["send_action"] 
    )