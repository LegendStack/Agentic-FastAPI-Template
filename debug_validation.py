
from pydantic import BaseModel, Field
from typing import Literal
from src.app.agents.backlog.schemas import DecompositionResult, Epic, UserStory, AcceptanceCriteria

class StoryResponse(BaseModel):
    id: str
    title: str
    description: str
    acceptance_criteria: list[dict]
    edge_cases: list[str] = []
    technical_notes: list[str] = []
    dependencies: list[str] = []
    estimated_complexity: str | None = None
    tags: list[str] = []

try:
    shell_epic = Epic(
        title="Imported stories", 
        description="Refining pre-populated stories"
    )
    # Simulate list of StoryResponse objects from API
    existing_stories = [
        StoryResponse(
            id="OLD-01",
            title="Existing Story",
            description="This already exists",
            acceptance_criteria=[],
        )
    ]
    
    # This is what happens in InputNode
    shell_result = DecompositionResult(
        epic=shell_epic,
        stories=existing_stories,
        summary="Imported stories for refinement",
    )
    print("Success!")
except Exception as e:
    print(f"Error: {e}")
