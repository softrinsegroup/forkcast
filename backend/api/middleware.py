"""
Request logging middleware.

Written as raw ASGI (not Starlette's ``BaseHTTPMiddleware``) on purpose:
``BaseHTTPMiddleware`` runs the endpoint in a separate task, so contextvars
bound here would not propagate into route handlers or the agent. Raw ASGI keeps
the whole request in one task, so the bound ``request_id`` flows everywhere.
"""

import time
import uuid

import structlog

log = structlog.get_logger()


class RequestLoggingMiddleware:
    """Bind a ``request_id`` to the logging context and log each HTTP request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=str(uuid.uuid4()),
            method=scope["method"],
            path=scope["path"],
        )

        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        log.info("request_started")
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            log.exception("request_failed")
            raise
        finally:
            log.info(
                "request_finished",
                status_code=status_code,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
            )
