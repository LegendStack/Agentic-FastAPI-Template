"""
Supervisor Agent Orchestrator.
==============================
Implements the Supervisor pattern from LangGraph to coordinate
multiple specialized agents.
"""

import logging
from typing import Any, Dict, List, Literal

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from .azure_openai import get_azure_openai_chat

logger = logging.getLogger(__name__)


# Define the state of our team graph
class TeamState(TypedDict):
    messages: List[BaseMessage]
    next: str


class SupervisorAgent:
    """
    Orchestrator that delegates tasks to specialized workers.

    The supervisor analyzes the conversation and decides which worker
    should act next (e.g., Researcher, DocumentExpert, or Finish).
    """

    def __init__(self, workers: List[str], checkpointer: BaseCheckpointSaver | None = None):
        self.llm = get_azure_openai_chat()
        self.workers = workers
        self.checkpointer = checkpointer
        self.graph = self._build_graph()

    def _build_graph(self):
        """Constructs the multi-agent orchestration graph."""
        options = ["FINISH"] + self.workers

        # System prompt for the supervisor
        system_prompt = (
            "You are a supervisor tasked with managing a conversation between the"
            f" following workers: {self.workers}. Given the following user request,"
            " respond with the worker to act next. Each worker will perform a"
            " task and respond with their results and status. When finished,"
            " respond with FINISH."
        )

        class Router(TypedDict):
            """Worker to route to next."""

            next: Literal[*options]  # type: ignore

        def supervisor_node(state: TeamState) -> Dict[str, Any]:
            """The router node that decides who goes next."""
            # In a real implementation, we'd use structured output to get the 'next' worker
            # For the template, we show the logic
            messages = [{"role": "system", "content": system_prompt}] + state["messages"]
            # Mocking the decision for now or using LLM
            return {"next": self.workers[0] if len(state["messages"]) < 3 else "FINISH"}

        workflow = StateGraph(TeamState)
        workflow.add_node("supervisor", supervisor_node)

        # Add dummy nodes for workers to allow edges to be valid in the template
        for worker in self.workers:
            workflow.add_node(worker, lambda x: x)

        workflow.add_edge(START, "supervisor")

        # Conditional edges from supervisor to workers or END
        for worker in self.workers:
            workflow.add_edge(worker, "supervisor")

        conditional_map = {k: k for k in self.workers}
        conditional_map["FINISH"] = END

        workflow.add_conditional_edges(
            "supervisor",
            lambda x: x["next"],
            conditional_map,
        )

        return workflow.compile(checkpointer=self.checkpointer)

    async def run(self, user_input: str, thread_id: str):
        """Executes the multi-agent team workflow."""
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = {"messages": [HumanMessage(content=user_input)], "next": ""}

        async for chunk in self.graph.astream(initial_state, config=config):
            # Process streaming output from all agents
            pass

        final_state = await self.graph.aget_state(config)
        return final_state.values["messages"][-1]
