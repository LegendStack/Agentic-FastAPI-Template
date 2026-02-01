from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import TypedDict

from .azure_openai import get_azure_openai_chat
from .vector_stores import VectorStoreFactory


class AgentState(TypedDict):
    """The state of our conversation graph."""

    messages: list[dict[str, Any]]
    context: str


class DocAssistantAgent:
    """A sample RAG agent that uses LangGraph."""

    def __init__(self, db: AsyncSession, checkpointer: BaseCheckpointSaver | None = None):
        self.db = db
        self.llm = get_azure_openai_chat()
        self.vector_store = VectorStoreFactory.get_store(db)
        self.checkpointer = checkpointer
        self.graph = self._build_graph()

    def _build_graph(self):
        """Constructs a simple RAG graph."""
        workflow = StateGraph(AgentState)

        # Define nodes
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("generate", self._generate_node)

        # Define edges
        workflow.add_edge(START, "retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)

        return workflow.compile(checkpointer=self.checkpointer)

    async def _retrieve_node(self, state: AgentState):
        """Retrieves context from pgvector."""
        state["messages"][-1]["content"]
        # In a real scenario, we'd embed the query first
        # For simplicity in this boilerplate sample, we'll assume a search method
        # that handles embedding or just use a mock for now
        # results = await self.vector_store.similarity_search(...)
        context = "Sample context from RAG foundation."
        return {"context": context}

    async def _generate_node(self, state: AgentState):
        """Generates a response using the LLM."""
        prompt = f"Context: {state['context']}\nUser: {state['messages'][-1]['content']}"
        response = await self.llm.ainvoke(prompt)
        return {"messages": [{"role": "assistant", "content": response.content}]}

    async def chat(self, user_input: str, thread_id: str):
        """Executes the graph with a thread_id for persistence."""
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = {"messages": [{"role": "user", "content": user_input}]}

        async for event in self.graph.astream(initial_state, config=config, stream_mode="values"):
            # This can be used for streaming token-by-token or node-by-node
            pass

        final_state = await self.graph.aget_state(config)
        return final_state.values["messages"][-1]
