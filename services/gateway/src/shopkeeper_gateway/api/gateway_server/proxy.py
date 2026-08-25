"""HTTP / SSE 流式反向代理。"""
import httpx
from fastapi import Request
from fastapi.responses import StreamingResponse
from shopkeeper_common.web.errors import NotFoundError

# 逐跳头不转发（由 httpx / StreamingResponse 重建）
_HOP_BY_HOP = {
    "host",
    "content-length",
    "transfer-encoding",
    "connection",
    "keep-alive",
    "upgrade",
    "te",
    "trailer",
}


def _filter_headers(headers, *, extra: dict[str, str] | None = None) -> dict[str, str]:
    """过滤逐跳头，并追加额外头（如 X-Forwarded-*）。"""
    out: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in _HOP_BY_HOP:
            continue
        out[key] = value
    for key, value in (extra or {}).items():
        if value:
            out[key] = value
    return out


class GatewayProxy:
    """流式反向代理：透传任意方法与请求体，SSE 逐块转发。"""

    def __init__(self, routes: dict[str, str], client: httpx.AsyncClient | None = None):
        self.routes = {prefix.rstrip("/"): url.rstrip("/") for prefix, url in routes.items()}
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(600.0, connect=5.0),
            follow_redirects=False,
        )

    def match(self, path: str) -> tuple[str, str] | None:
        """返回 (匹配前缀, 后端基础 URL)；命中多个前缀时取最长。"""
        best: tuple[str, str] | None = None
        for prefix, url in self.routes.items():
            if path == prefix or path.startswith(prefix + "/"):
                if best is None or len(prefix) > len(best[0]):
                    best = (prefix, url)
        return best

    async def forward(self, request: Request) -> StreamingResponse:
        """转发请求到后端服务，流式返回响应。"""
        path = request.url.path
        matched = self.match(path)
        if matched is None:
            raise NotFoundError(f"未知路由: {path}")
        prefix, base_url = matched
        target = f"{base_url}{path[len(prefix):]}"
        if request.url.query:
            target += "?" + request.url.query

        body = await request.body()
        client_host = request.client.host if request.client else ""
        headers = _filter_headers(
            request.headers,
            extra={
                "X-Forwarded-For": client_host,
                "X-Forwarded-Host": request.headers.get("host", ""),
                "X-Forwarded-Proto": request.url.scheme,
            },
        )
        req = self.client.build_request(request.method, target, headers=headers, content=body)
        resp = await self.client.send(req, stream=True)
        resp_headers = _filter_headers(resp.headers)
        resp_headers.setdefault("Cache-Control", "no-cache")
        return StreamingResponse(
            resp.aiter_bytes(),
            status_code=resp.status_code,
            headers=resp_headers,
        )
