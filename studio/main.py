import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="LegendStack Studio",
    page_icon="🤖",
    layout="wide",
)

st.sidebar.title("LegendStack Studio")
st.sidebar.image(
    "https://github.com/LegendStack/agentic-fastapi-template/raw/main/docs/assets/sidebar_logo.png", width=100
)

menu = st.sidebar.selectbox(
    "Navigation", ["Trace Visualizer", "Evaluation Hub", "Safety Guardrails", "HITL Approvals", "Connectors"]
)

if menu == "Trace Visualizer":
    st.title("🛡️ Agent Trace Visualizer")
    st.write("Monitor agent decision-making in real-time.")

    # Mock trace data
    data = pd.DataFrame(
        [
            {
                "Step": 1,
                "Agent": "Supervisor",
                "Action": "Route to Researcher",
                "Status": "Complete",
                "Latency": "1.2s",
            },
            {"Step": 2, "Agent": "Researcher", "Action": "Search Jira", "Status": "Complete", "Latency": "2.5s"},
            {"Step": 3, "Agent": "Supervisor", "Action": "Review Results", "Status": "Running", "Latency": "0.1s"},
        ]
    )
    st.table(data)

    if st.button("Refresh Traces"):
        st.toast("Updating traces...")

elif menu == "Evaluation Hub":
    st.title("🧪 RAG Evaluation Hub")
    st.write("Quality metrics from Ragas.")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Faithfulness", "0.89", "+2%")
    col2.metric("Relevancy", "0.92", "+5%")
    col3.metric("Precision", "0.85", "-1%")
    col4.metric("Recall", "0.94", "0%")

    st.line_chart(pd.DataFrame({"Faithfulness": [0.8, 0.85, 0.89], "Relevancy": [0.7, 0.82, 0.92]}))

elif menu == "Safety Guardrails":
    st.title("🛡️ Safety & Guardrails")
    st.write("PII Masking and Moderation summaries.")
    st.info("Currently monitoring for: Email, Phone, Credit Card, IP Address.")

    st.success("0 critical safety violations in the last 24h.")
    st.warning("12 minor PII items masked automatically.")

elif menu == "HITL Approvals":
    st.title("🤝 HITL Approvals")
    st.write("Human-in-the-loop intervention queue.")

    st.warning("Pending Action: Researcher wants to delete a Jira issue.")
    if st.button("Approve"):
        st.success("Action Approved.")
    if st.button("Reject"):
        st.error("Action Rejected.")

elif menu == "Connectors":
    st.title("🔌 Connector Marketplace")
    st.write("Dynamic ingestion connectors.")

    connectors = ["Jira", "SharePoint", "Confluence", "Slack (Coming Soon)", "Zendesk (Coming Soon)"]
    for c in connectors:
        st.checkbox(c, value=True if "Soon" not in c else False)
