"""Reject non-HTTPS requests when ENFORCE_HTTPS=true.

The backend sits behind IIS, which terminates TLS and forwards
X-Forwarded-Proto. We trust that header (IIS strips it from inbound client
requests; the backend isn't reachable from outside the VM).

Default behavior (ENFORCE_HTTPS unset or any value other than "true") is
permissive — Phase 2 ships this dormant so it can be activated at the
Phase 3 cutover without a code release.
"""
import logging
import os
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# Paths that bypass HTTPS enforcement even when enabled. Health checks need
# to remain callable from inside the VM (IIS health probe, monitoring).
_BYPASS_PATHS = {"/health"}


class EnforceHttpsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if os.environ.get("ENFORCE_HTTPS") != "true":
            return await call_next(request)
        if request.url.path in _BYPASS_PATHS:
            return await call_next(request)

        proto = request.headers.get("x-forwarded-proto", "").lower()
        if proto != "https":
            logger.warning(
                "Rejecting non-HTTPS request: path=%s proto=%s client=%s",
                request.url.path, proto or "(none)", request.client.host if request.client else "?",
            )
            return JSONResponse(
                status_code=400,
                content={"detail": "HTTPS required"},
            )
        return await call_next(request)
