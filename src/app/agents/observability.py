"""
OpenTelemetry observability for the Agentic Boilerplate.
Configured for Datadog integration via OTLP in AKS deployments.

In AKS, the Datadog Agent automatically receives OTLP traces when configured.
Local development can use Jaeger or a local Datadog agent.
"""

import functools
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)

# Global tracer instance
_tracer: trace.Tracer | None = None


def get_tracer() -> trace.Tracer:
    """Get the configured OpenTelemetry tracer."""
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer("agentic-boilerplate")
    return _tracer


def setup_telemetry(app=None, engine=None) -> None:
    """
    Initialize OpenTelemetry with Datadog-compatible configuration.

    In AKS with Datadog Agent, set these environment variables:
    - OTEL_EXPORTER_OTLP_ENDPOINT=http://datadog-agent:4317
    - OTEL_SERVICE_NAME=your-service-name
    - DD_ENV, DD_VERSION, DD_SERVICE for Datadog unified tagging

    Args:
        app: FastAPI application instance for auto-instrumentation
        engine: SQLAlchemy engine for database tracing
    """
    import os

    # Build resource with Datadog unified service tags
    resource = Resource.create(
        {
            "service.name": os.getenv("DD_SERVICE", os.getenv("OTEL_SERVICE_NAME", "agentic-boilerplate")),
            "service.version": os.getenv("DD_VERSION", "1.0.0"),
            "deployment.environment": os.getenv("DD_ENV", "development"),
            # Kubernetes-specific attributes (auto-populated in AKS)
            "k8s.namespace.name": os.getenv("K8S_NAMESPACE", "default"),
            "k8s.pod.name": os.getenv("K8S_POD_NAME", "local"),
        }
    )

    # Create tracer provider with resource
    provider = TracerProvider(resource=resource)

    # Configure OTLP exporter for Datadog Agent
    # In AKS: Datadog Agent listens on port 4317 for OTLP/gRPC
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    try:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info(f"OpenTelemetry configured with OTLP exporter: {otlp_endpoint}")
    except Exception as e:
        logger.warning(f"Failed to configure OTLP exporter: {e}. Tracing disabled.")

    # Set global tracer provider
    trace.set_tracer_provider(provider)

    # Auto-instrument FastAPI
    if app:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented for tracing")

    # Auto-instrument SQLAlchemy
    if engine:
        SQLAlchemyInstrumentor().instrument(engine=engine)
        logger.info("SQLAlchemy instrumented for tracing")

    # Instrument HTTP clients (for Azure OpenAI calls)
    HTTPXClientInstrumentor().instrument()

    # Instrument Redis (for session/cache operations)
    RedisInstrumentor().instrument()

    logger.info("OpenTelemetry setup complete for Datadog integration")


def trace_llm_call(operation_name: str = "llm_call"):
    """
    Decorator to trace LLM calls with token and cost metrics.

    Usage:
        @trace_llm_call("chat_completion")
        async def call_openai(prompt):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(
                operation_name,
                attributes={
                    "llm.provider": "azure_openai",
                    "llm.model": kwargs.get("model", "gpt-4"),
                },
            ) as span:
                try:
                    result = await func(*args, **kwargs)

                    # Extract token usage if available
                    if hasattr(result, "usage_metadata"):
                        usage = result.usage_metadata
                        span.set_attribute("llm.input_tokens", usage.get("input_tokens", 0))
                        span.set_attribute("llm.output_tokens", usage.get("output_tokens", 0))
                        span.set_attribute("llm.total_tokens", usage.get("total_tokens", 0))

                    return result
                except Exception as e:
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", str(e))
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(operation_name) as span:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", str(e))
                    raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def trace_vector_operation(operation_name: str = "vector_operation"):
    """
    Decorator to trace vector store operations.

    Usage:
        @trace_vector_operation("similarity_search")
        async def search(query_vec, k=4):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(
                operation_name,
                attributes={
                    "vector.operation": operation_name,
                    "vector.k": kwargs.get("k", 4),
                },
            ) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("vector.result_count", len(result) if result else 0)
                    return result
                except Exception as e:
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", str(e))
                    raise

        return wrapper

    return decorator


@asynccontextmanager
async def trace_agent_execution(agent_name: str, thread_id: str):
    """
    Context manager for tracing complete agent executions.

    Usage:
        async with trace_agent_execution("doc_assistant", "thread-123"):
            result = await agent.chat(message)
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(
        f"agent.{agent_name}",
        attributes={
            "agent.name": agent_name,
            "agent.thread_id": thread_id,
        },
    ) as span:
        try:
            yield span
            span.set_attribute("agent.status", "success")
        except Exception as e:
            span.set_attribute("agent.status", "error")
            span.set_attribute("error.message", str(e))
            raise
