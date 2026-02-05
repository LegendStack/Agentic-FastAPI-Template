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

print("STEP 1: Starting OTEL trace...", flush=True)
trace_import("opentelemetry")
trace_import("opentelemetry.trace")
trace_import("opentelemetry.sdk.trace")
trace_import("opentelemetry.exporter.otlp.proto.grpc.trace_exporter")
print("STEP 2: Finished OTEL trace", flush=True)
