"""Bound the HTTP body before multipart parsing can spool an arbitrary upload."""
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    def __init__(self, app, maximum: int):
        self.app, self.maximum = app, maximum

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        length = headers.get(b"content-length")
        if length:
            try:
                oversized = int(length) > self.maximum
            except ValueError:
                response = JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)
                return await response(scope, receive, send)
            if oversized:
                response = JSONResponse({"detail": "Request body exceeds limit"}, status_code=413)
                return await response(scope, receive, send)
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.maximum:
                    raise HTTPException(413, "Request body exceeds limit")
            return message

        return await self.app(scope, bounded_receive, send)
