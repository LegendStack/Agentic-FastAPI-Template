from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import TypedDict

from ..core.graph_db import GraphDBClient
from .azure_openai import get_azure_openai_chat
from .graph_retriever import GraphRetriever
from .nodes.entity_node import EntityNode
from .vector_stores import VectorStoreFactory


class AgentState(TypedDict):
    """The state of our conversation graph."""

    messages: list[dict[str, Any]]
    context: str
    tenant_id: str | None


class DocAssistantAgent:
    """A sample RAG agent that uses LangGraph."""

    def __init__(self, db: AsyncSession, checkpointer: BaseCheckpointSaver | None = None):
        self.db = db
        self.llm = get_azure_openai_chat()
        self.vector_store = VectorStoreFactory.get_store(db)
        self.graph_client = GraphDBClient()
        self.retriever = GraphRetriever(self.vector_store, self.graph_client)
        self.entity_node = EntityNode(self.graph_client)
        self.checkpointer = checkpointer
        self.graph = self._build_graph()

    def _build_graph(self):
        """Constructs a hybrid RAG graph with entity memory."""
        workflow = StateGraph(AgentState)

        # Define nodes
        workflow.add_node("remember", self.entity_node)
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("generate", self._generate_node)

        # Define edges
        workflow.add_edge(START, "remember")
        workflow.add_edge("remember", "retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)

        return workflow.compile(checkpointer=self.checkpointer)

    async def _retrieve_node(self, state: AgentState):
        """Retrieves context from hybrid vector-graph store."""
        user_msg = state["messages"][-1]["content"]

        # In a real scenario, we'd get embeddings for the user_msg
        # Assuming our LLMService/Retriever handles simple cases or we mock it
        try:
            from .azure_openai import LLMService

            llm_service = LLMService()
            query_vector = await llm_service.get_embeddings(user_msg)
            results = await self.retriever.retrieve(query_text=user_msg, query_vector=query_vector)
            context = "\n\n".join([res["content"] for res in results])
        except Exception:
            context = "Memory/Retrieval active but no results found."

        return {"context": context}

    async def _generate_node(self, state: AgentState):
        """Generates a response using the LLM."""
        prompt = f"Context: {state['context']}\nUser: {state['messages'][-1]['content']}"
        response = await self.llm.ainvoke(prompt)
        return {"messages": [{"role": "assistant", "content": response.content}]}

    async def chat(self, user_input: str, thread_id: str, tenant_id: str | None = None):
        """Executes the graph with cross-thread entity memory support."""
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = {"messages": [{"role": "user", "content": user_input}], "tenant_id": tenant_id}

        async for event in self.graph.astream(initial_state, config=config, stream_mode="values"):
            pass

        final_state = await self.graph.aget_state(config)
        return final_state.values["messages"][-1]
