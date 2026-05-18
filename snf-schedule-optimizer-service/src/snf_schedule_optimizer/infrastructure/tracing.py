"""OpenTelemetry tracing setup."""
import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

_SERVICE_NAME = "snf-schedule-optimizer"
logger = logging.getLogger(__name__)


def setup_tracing() -> None:
    resource = Resource.create({"service.name": _SERVICE_NAME})
    provider = TracerProvider(resource=resource)

    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # type: ignore[import-not-found]
                OTLPSpanExporter,
            )
        except ImportError:
            logger.warning(
                "OTLP exporter not available, falling back to console exporter"
            )
            exporter = ConsoleSpanExporter()
        else:
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    else:
        exporter = ConsoleSpanExporter()

    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)
