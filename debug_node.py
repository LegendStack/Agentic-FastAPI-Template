
from src.app.agents.backlog.nodes.decompose_node import DecomposeNode
from src.app.agents.backlog.config import BacklogAgentConfig

node = DecomposeNode(config=BacklogAgentConfig())
print(f"Attributes: {dir(node)}")
print(f"jira_service exists: {hasattr(node, 'jira_service')}")
print(f"jira_service value: {node.jira_service}")
