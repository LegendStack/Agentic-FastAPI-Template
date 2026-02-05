import sys
import os

def trace_import(module_name):
    print(f"DEBUG: Importing {module_name}...", flush=True)
    try:
        __import__(module_name)
        print(f"DEBUG: Successfully imported {module_name}", flush=True)
    except Exception as e:
        print(f"DEBUG: ERROR importing {module_name}: {e}", flush=True)

print("STEP 1: Starting granular trace...", flush=True)
trace_import("typing")
trace_import("logging")
trace_import("uuid")
trace_import("langgraph.checkpoint.base")
trace_import("langgraph.graph")
trace_import("src.app.agents.backlog.config")
trace_import("src.app.agents.backlog.schemas")
trace_import("src.app.agents.backlog.nodes.input_node")
trace_import("src.app.agents.backlog.nodes.decompose_node")
trace_import("src.app.agents.backlog.nodes.refine_node")
trace_import("src.app.agents.backlog.nodes.format_node")
trace_import("src.app.agents.backlog.nodes.export_node")
trace_import("src.app.agents.backlog.backlog_agent")

print("STEP 2: Finished granular trace", flush=True)
