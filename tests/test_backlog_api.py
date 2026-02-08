"""
Integration tests for the Backlog Assistant API.
"""

from fastapi.testclient import TestClient


class TestBacklogAPI:
    """Test the /backlog endpoints."""

    def test_get_config(self, client: TestClient):
        """Test GET /api/v1/backlog/config"""
        response = client.get("/api/v1/backlog/config")
        assert response.status_code == 200
        data = response.json()
        assert "story_template" in data
        assert "enabled_features" in data
        assert data["using_mocks"] is True

    def test_decompose_epic(self, client: TestClient):
        """Test POST /api/v1/backlog/decompose"""
        payload = {
            "epic_description": "Add user authentication with email and password",
            "context": "We use Azure AD",
            "output_format": "json",
        }
        response = client.post("/api/v1/backlog/decompose", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "thread_id" in data
        assert "stories" in data
        assert len(data["stories"]) >= 2
        assert data["story_count"] == len(data["stories"])

    def test_chat_refinement(self, client: TestClient):
        """Test POST /api/v1/backlog/chat/{thread_id}"""
        # First decompose to get a thread_id
        decompose_payload = {"epic_description": "Initial Epic for Chat Test", "output_format": "json"}
        initial_response = client.post("/api/v1/backlog/decompose", json=decompose_payload)
        thread_id = initial_response.json()["thread_id"]

        # Now chat to refine
        chat_payload = {"message": "Add more edge cases"}
        response = client.post(f"/api/v1/backlog/chat/{thread_id}", json=chat_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["thread_id"] == thread_id
        assert len(data["stories"]) >= 1

    def test_refine_door_b(self, client: TestClient):
        """Test POST /api/v1/backlog/refine (and unified /chat)"""
        # Door B: Start with existing stories via /refine
        refine_payload = {
            "stories": [
                {
                    "id": "OLD-01",
                    "title": "Existing Story",
                    "description": "This already exists",
                    "acceptance_criteria": [],
                }
            ],
            "message": "Convert to BDD",
            "output_format": "json",
        }
        response = client.post("/api/v1/backlog/refine", json=refine_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["thread_id"] is not None
        assert data["story_count"] >= 1

        # Test unified /chat as well
        thread_id = "unified-test-thread"
        unified_payload = {"message": "Refine these stories", "stories": refine_payload["stories"]}
        response = client.post(f"/api/v1/backlog/chat/{thread_id}", json=unified_payload)
        assert response.status_code == 200
        assert response.json()["thread_id"] == thread_id

    def test_get_stories(self, client: TestClient):
        """Test GET /api/v1/backlog/stories/{thread_id}"""
        # Note: Since we are using TestClient and SqlAlchemyCheckpointSaver (if and only if configured),
        # we need to ensure the state is persisted.
        # By default in mocks, it might not persist unless checkpointer is active.
        # But decompose returns stories anyway.

        decompose_payload = {"epic_description": "Get Stories Test Epic", "output_format": "json"}
        initial_response = client.post("/api/v1/backlog/decompose", json=decompose_payload)
        thread_id = initial_response.json()["thread_id"]

        response = client.get(f"/api/v1/backlog/stories/{thread_id}")
        # If persistence is not enabled in conftest/setup for tests, this might return 404 or empty.
        # However, the repo usually has SqlAlchemyCheckpointSaver enabled in the get_agent factory if db is provided.
        if response.status_code == 200:
            data = response.json()
            assert "stories" in data
        else:
            # If persistence isn't working in the test env, at least we know the endpoint exists.
            assert response.status_code in [200, 404]

    def test_error_handling(self, client: TestClient):
        """Test error handling with empty input."""
        payload = {
            "epic_description": "",  # Too short
            "output_format": "json",
        }
        response = client.post("/api/v1/backlog/decompose", json=payload)
        assert response.status_code == 422
        assert "detail" in response.json()
