import os
from pathlib import Path

from typer.testing import CliRunner

from src.app.cli.main import app

runner = CliRunner()


def test_create_agent_command():
    agent_name = "TestScaffolded"
    # Ensure it doesn't exist
    file_path = Path("src/app/agents") / f"{agent_name.lower()}_agent.py"
    if file_path.exists():
        os.remove(file_path)

    result = runner.invoke(app, ["create-agent", agent_name])

    assert result.exit_code == 0
    assert "Creating agent" in result.stdout
    assert "created at" in result.stdout
    assert file_path.exists()

    # Clean up
    os.remove(file_path)


def test_create_connector_command():
    conn_name = "TestConn"
    file_path = Path("src/app/agents/connectors") / f"{conn_name.lower()}.py"
    if file_path.exists():
        os.remove(file_path)

    result = runner.invoke(app, ["create-connector", conn_name])

    assert result.exit_code == 0
    assert "Creating connector" in result.stdout
    assert "created at" in result.stdout
    assert file_path.exists()

    # Clean up
    os.remove(file_path)


def test_evaluate_rag_command():
    result = runner.invoke(app, ["evaluate-rag"])

    assert result.exit_code == 0
    assert "Initializing RAG Evaluation" in result.stdout
    assert "Evaluation complete" in result.stdout
