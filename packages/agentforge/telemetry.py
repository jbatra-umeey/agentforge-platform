import os
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CollectorRegistry, Counter, Histogram

registry = CollectorRegistry()
runs = Counter("agentforge_runs_total", "Terminal runs", ["scenario", "status"], registry=registry)
latency = Histogram("agentforge_stage_seconds", "Stage latency", ["stage"], registry=registry)
provider = TracerProvider(resource=Resource.create({"service.name": "agentforge-api"}))
if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
tracer = provider.get_tracer("agentforge")
