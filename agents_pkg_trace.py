import sys
import time

def trace_import(module_name):
    print(f"DEBUG: Importing {module_name}...", flush=True)
    start = time.time()
    try:
        __import__(module_name)
        print(f"DEBUG: Successfully imported {module_name} in {time.time() - start:.2f}s", flush=True)
    except Exception as e:
        print(f"DEBUG: ERROR importing {module_name}: {e}", flush=True)

print("STEP 1: Starting agents pkg trace...", flush=True)
trace_import("src.app.agents.azure_openai")
trace_import("src.app.agents.base")
trace_import("src.app.agents.vector_stores")
trace_import("src.app.agents.indexers")
trace_import("src.app.agents.background")
trace_import("src.app.agents.conversations")
trace_import("src.app.agents.cost_tracking")
trace_import("src.app.agents.hitl")
trace_import("src.app.agents.memory")
trace_import("src.app.agents.multi_tenant")
trace_import("src.app.agents.observability")
trace_import("src.app.agents.persistence")
trace_import("src.app.agents.prompts")
trace_import("src.app.agents.rate_limiting")
trace_import("src.app.agents.reranking")
trace_import("src.app.agents.resilience")
trace_import("src.app.agents.sample_agent")
trace_import("src.app.agents.backlog")
print("STEP 2: Finished agents pkg trace", flush=True)
