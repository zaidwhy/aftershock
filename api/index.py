"""Vercel entrypoint. vercel.json rewrites every API path to /api/index and passes the original
path in the __path query parameter, because the function otherwise sees only /api/index."""
from urllib.parse import parse_qsl, urlencode

from aftershock.api import app as fastapi_app


async def app(scope, receive, send):
    if scope["type"] == "http":
        query = parse_qsl(scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True)
        original = next((v for k, v in query if k == "__path"), None)
        if original:
            rest = [(k, v) for k, v in query if k != "__path"]
            scope = dict(scope, path=original, raw_path=original.encode("latin-1"),
                         query_string=urlencode(rest).encode("latin-1"))
    await fastapi_app(scope, receive, send)
