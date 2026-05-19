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
        # Inline import intentional: opentelemetry-exporter-otlp-proto-grpc
        # depends on opentelemetry-proto which requires protobuf>=5.0,<7.0.
        # This project uses protobuf>=7.34.1 (required by the generated
        # scheduling_pb2.py which uses runtime_version.ValidateProtobufRuntimeVersion).
        # The OTLP gRPC exporter cannot be a hard dependency until
        # opentelemetry-proto supports protobuf>=7.  When that happens:
        #   1. Add "opentelemetry-exporter-otlp-proto-grpc>=..." to pyproject.toml
        #   2. Move this import to the top of this file (after
        #      opentelemetry.sdk.trace.export imports)
        #   3. Remove this try/except ImportError guard
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
