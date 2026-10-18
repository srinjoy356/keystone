"""Optional OpenTelemetry tracing: one trace per question (LLM calls with token counts, tool calls, Cypher queries).
Off unless OTEL_EXPORTER_OTLP_ENDPOINT is set (for example http://localhost:4318 for a local SigNoz). Needs
`pip install -r requirements-otel.txt`; without the packages it is a silent no-op, so the deployed app is unaffected."""
import contextlib, os
from . import config  # noqa: F401  (loads .env before the endpoint is read)

_tracer = _provider = None
_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
if _endpoint:
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        _provider = TracerProvider(resource=Resource.create({"service.name": os.environ.get("OTEL_SERVICE_NAME", "keystone")}))
        _provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=_endpoint.rstrip("/") + "/v1/traces")))
        trace.set_tracer_provider(_provider)
        _tracer = trace.get_tracer("keystone")
    except ImportError:
        pass


@contextlib.contextmanager
def span(name: str, **attrs):
    if _tracer is None:
        yield None
        return
    with _tracer.start_as_current_span(name, attributes=attrs) as s:
        yield s


def flush():
    """Send buffered spans now (short-lived scripts call this before exiting)."""
    if _provider is not None:
        _provider.force_flush()
