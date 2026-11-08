"""Refuse an oversized body from its declared size, before anything is parsed (G3)."""
import re

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.domain.monitoring_limits import LIMITS as F3_LIMITS
from app.domain.operation_limits import LIMITS

_F6 = re.compile(r"^/v1/farms/[^/]+/(operations|registry|phyto-products)(/|$)")
_F3 = re.compile(r"^/v1/farms/[^/]+/(zones|summary)(/|$)")
_F4 = re.compile(r"^/v1/farms/[^/]+/parcels/[^/]+/(irrigation|irrigation-system|water-analyses)(/|$)")
_PHOTO = re.compile(r"^/v1/farms/[^/]+/zones/[^/]+/observations/photo$")
_LABEL = re.compile(r"^/v1/farms/[^/]+/operations/label$")
_MULTIPART_OVERHEAD = 1024 * 1024


class BodyLimitMiddleware:
    """413 on F6 routes: JSON bodies are small, the label photo is bounded (plus the multipart envelope)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in ("POST", "PATCH", "PUT") or not (_F6.match(scope["path"]) or _F3.match(scope["path"]) or _F4.match(scope["path"])):
            await self.app(scope, receive, send)
            return
        if _PHOTO.match(scope["path"]):
            limit = F3_LIMITS["photo_bytes"] + _MULTIPART_OVERHEAD
        elif _F3.match(scope["path"]) or _F4.match(scope["path"]):
            limit = F3_LIMITS["body_bytes"]
        else:
            limit = LIMITS["label_bytes"] + _MULTIPART_OVERHEAD if _LABEL.match(scope["path"]) else LIMITS["body_bytes"]
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await self._refuse(scope, receive, send)
            return
        seen = 0
        refused = False

        async def counting() -> Message:
            nonlocal seen, refused
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    refused = True
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        started = False

        async def guarded_send(message: Message) -> None:
            nonlocal started
            if refused and not started:
                started = True
                await self._refuse(scope, receive, send)
                return
            if refused:
                return
            await send(message)

        await self.app(scope, counting, guarded_send)

    @staticmethod
    async def _refuse(scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse({"detail": {"code": "payload_too_large"}}, status_code=413)
        await response(scope, receive, send)
