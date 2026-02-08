"""
LegendStack Tutorial App
========================
An interactive Streamlit application for learning the LegendStack framework.

Features:
- Step-by-step guided walkthrough
- Live agent interaction
- Real-time feature visualization
- Code snippets with explanations

Run with:
    streamlit run studio/tutorial_app.py
"""

import asyncio
import sys
from pathlib import Path

import streamlit as st

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.agents.demo import DemoAgentConfig, LegendDemoAgent

# === Page Config ===
st.set_page_config(
    page_title="LegendStack Tutorial",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# === Custom CSS ===
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    .feature-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 4px solid #667eea;
    }
    .code-block {
        background: #1e1e1e;
        border-radius: 8px;
        padding: 1rem;
        font-family: 'Fira Code', monospace;
    }
    .step-indicator {
        display: flex;
        justify-content: center;
        margin: 1rem 0;
    }
    .step-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: #333;
        margin: 0 5px;
    }
    .step-dot.active {
        background: #667eea;
    }
</style>
""",
    unsafe_allow_html=True,
)

# === Session State ===
if "agent" not in st.session_state:
    st.session_state.agent = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_step" not in st.session_state:
    st.session_state.current_step = 0
if "config" not in st.session_state:
    st.session_state.config = DemoAgentConfig()

# === Sidebar ===
with st.sidebar:
    st.markdown("## 🎛️ Feature Toggles")
    st.caption("Enable/disable features to see how the agent changes.")

    st.session_state.config.ENABLE_PII_GUARD = st.toggle("🛡️ PII Guard", value=True, help="Mask sensitive information")
    st.session_state.config.ENABLE_MODERATION = st.toggle(
        "⚖️ Content Moderation", value=True, help="Filter harmful content"
    )
    st.session_state.config.ENABLE_RAG = st.toggle("📚 RAG Retrieval", value=True, help="Vector-based document search")
    st.session_state.config.ENABLE_GRAPH_RAG = st.toggle(
        "🔗 Graph-RAG", value=True, help="Knowledge graph relationships"
    )
    st.session_state.config.ENABLE_SEMANTIC_CACHE = st.toggle(
        "⚡ Semantic Cache", value=True, help="Cache similar queries"
    )
    st.session_state.config.ENABLE_ENTITY_MEMORY = st.toggle(
        "🧠 Entity Memory", value=True, help="Extract and remember entities"
    )
    st.session_state.config.ENABLE_REFLECTOR = st.toggle(
        "🔄 Self-Correction", value=True, help="Auto-improve low-quality responses"
    )
    st.session_state.config.ENABLE_HITL = st.toggle(
        "👤 Human-in-the-Loop", value=False, help="Require approval for actions"
    )
    st.session_state.config.ENABLE_COST_TRACKING = st.toggle("💰 Cost Tracking", value=True, help="Monitor token usage")

    st.divider()

    if st.button("🔄 Reset Agent", use_container_width=True):
        st.session_state.agent = None
        st.session_state.messages = []
        st.rerun()

# === Tutorial Steps ===
STEPS = [
    {
        "title": "Welcome to LegendStack",
        "icon": "🚀",
        "content": """
Welcome to the **LegendStack Agentic AI Framework** interactive tutorial!

This app will guide you through building production-ready AI agents step by step.

### What You'll Learn

1. **Agent Basics** - Create and chat with an AI agent
2. **Safety First** - PII masking and content moderation
3. **RAG Power** - Ground responses in your data
4. **Knowledge Graphs** - Discover entity relationships
5. **Memory & Entities** - Cross-conversation persistence
6. **Self-Correction** - Quality assurance loops

Click **Next** to begin your journey!
        """,
    },
    {
        "title": "Create Your First Agent",
        "icon": "🤖",
        "content": """
Let's create your first LegendStack agent!

The Demo Agent runs with **zero external dependencies** using mock services.
This means you can experiment without any cloud credentials.

### Code

```python
from app.agents.demo import LegendDemoAgent

# Create agent with all features enabled
agent = LegendDemoAgent()

# Chat!
result = await agent.chat("What is LegendStack?")
print(result["response"])
```

**Try it below!** Type a message and see the agent respond.
        """,
        "interactive": True,
    },
    {
        "title": "Safety Guardrails",
        "icon": "🛡️",
        "content": """
LegendStack protects sensitive data automatically.

### PII Types Detected

| Type | Example | Masked As |
|------|---------|-----------|
| Email | user@example.com | [EMAIL_MASKED] |
| Phone | 555-123-4567 | [PHONE_MASKED] |
| IP Address | 192.168.1.1 | [IP_MASKED] |

### Try It!

Send a message with an email or phone number and see it get masked.

Example: *"My email is secret@company.com"*
        """,
        "interactive": True,
    },
    {
        "title": "RAG: Retrieval-Augmented Generation",
        "icon": "📚",
        "content": """
RAG grounds AI responses in **your actual data**.

Instead of hallucinating, the agent retrieves relevant documents
and uses them as context for its response.

### How It Works

```
User Query → Embed → Vector Search → Context → LLM → Response
```

### The Demo Agent's Knowledge Base

The mock vector store contains documentation about:
- LegendStack features
- RAG concepts
- Graph databases
- Security best practices

**Ask about these topics and watch RAG in action!**
        """,
        "interactive": True,
    },
    {
        "title": "Graph-RAG: Relationship Discovery",
        "icon": "🔗",
        "content": """
Graph-RAG enhances context with **relationships**.

While vector search finds similar documents, Graph-RAG discovers:
- Entity connections
- Hierarchies
- Dependencies

### Example Relationships

```
LegendStack → USES → FastAPI
LegendStack → USES → LangGraph
LegendStack → STORES_IN → Neo4j
FastAPI → DEPENDS_ON → Python
```

**Mention "LegendStack" in your query to see graph context!**
        """,
        "interactive": True,
    },
    {
        "title": "Configuration & Customization",
        "icon": "⚙️",
        "content": """
Every feature can be toggled on/off via configuration.

### Minimal Agent

```python
config = DemoAgentConfig(
    ENABLE_RAG=False,
    ENABLE_GRAPH_RAG=False,
    ENABLE_REFLECTOR=False,
)
agent = LegendDemoAgent(config=config)
```

### Enterprise Agent

```python
config = DemoAgentConfig(
    ENABLE_HITL=True,  # Human approval required
    ENABLE_COST_TRACKING=True,
    REFLECTOR_THRESHOLD=0.8,  # High quality bar
)
agent = LegendDemoAgent(config=config)
```

**Use the sidebar toggles to experiment with different configurations!**
        """,
        "interactive": True,
    },
    {
        "title": "You Did It! 🎉",
        "icon": "🏆",
        "content": """
Congratulations on completing the LegendStack tutorial!

### What You Learned

✅ Created an AI agent with zero dependencies  
✅ Explored safety guardrails (PII, moderation)  
✅ Understood RAG retrieval  
✅ Discovered Graph-RAG relationships  
✅ Customized agent configuration  

### Next Steps

- 📓 **Jupyter Notebook**: `notebooks/tutorial.ipynb` for deeper exploration
- 📖 **Documentation**: Full API reference and guides
- 💬 **Community**: Join our Discord for support
- ⭐ **GitHub**: Star the repo and contribute!

### Quick Reference

```python
from app.agents.demo import LegendDemoAgent, DemoAgentConfig

# Create with custom config
config = DemoAgentConfig(
    ENABLE_RAG=True,
    ENABLE_GRAPH_RAG=True,
    ENABLE_SEMANTIC_CACHE=True,
)
agent = LegendDemoAgent(config=config)

# Chat with the agent
result = await agent.chat(
    "Your question here",
    thread_id="unique-thread-id",
    tenant_id="optional-tenant-id",
)

print(result["response"])
print(result["features_used"])
```
        """,
    },
]

# === Main Content ===
st.markdown('<h1 class="main-header">🚀 LegendStack Tutorial</h1>', unsafe_allow_html=True)

# Step navigation
cols = st.columns([1, 4, 1])
with cols[0]:
    if st.button("◀ Back", disabled=st.session_state.current_step == 0):
        st.session_state.current_step -= 1
        st.rerun()

with cols[1]:
    # Progress indicator
    progress = (st.session_state.current_step + 1) / len(STEPS)
    st.progress(progress)
    st.caption(f"Step {st.session_state.current_step + 1} of {len(STEPS)}")

with cols[2]:
    if st.button("Next ▶", disabled=st.session_state.current_step == len(STEPS) - 1):
        st.session_state.current_step += 1
        st.rerun()

# Current step content
current = STEPS[st.session_state.current_step]
st.markdown(f"## {current['icon']} {current['title']}")
st.markdown(current["content"])

# Interactive chat section
if current.get("interactive", False):
    st.divider()
    st.markdown("### 💬 Try It")

    # Initialize agent if needed
    if st.session_state.agent is None:
        st.session_state.agent = LegendDemoAgent(config=st.session_state.config)

    # Chat input
    user_input = st.chat_input("Type your message...")

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("features"):
                st.caption(f"📊 Features: {', '.join(msg['features'])}")

    if user_input:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})

        with st.chat_message("user"):
            st.markdown(user_input)

        # Get agent response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # Recreate agent with current config
                st.session_state.agent = LegendDemoAgent(config=st.session_state.config)

                # Run async
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(
                        st.session_state.agent.chat(user_input, thread_id="tutorial-session")
                    )
                finally:
                    loop.close()

                st.markdown(result["response"])

                features = result.get("features_used", [])
                if features:
                    st.caption(f"📊 Features: {', '.join(features)}")

                if result.get("cache_hit"):
                    st.info("⚡ Served from semantic cache!")

                # Show cost info
                cost_info = result.get("cost_info", {})
                if cost_info.get("estimated_cost_usd"):
                    st.caption(f"💰 Est. Cost: ${cost_info['estimated_cost_usd']:.6f}")

                # Save to history
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": result["response"],
                        "features": features,
                    }
                )

# === Footer ===
st.divider()
st.markdown(
    """
<div style="text-align: center; color: #666; font-size: 0.8rem;">
    LegendStack Agentic AI Framework | 
    <a href="https://github.com/LegendStack/agentic-fastapi-template" target="_blank">GitHub</a> | 
    <a href="https://legendstack.github.io/agentic-fastapi-template/" target="_blank">Documentation</a>
</div>
""",
    unsafe_allow_html=True,
)
