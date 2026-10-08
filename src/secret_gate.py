"""
비밀 경로 게이트 (클라우드 배포용 진입점)

lexguard-mcp 자체에는 인증 기능이 없으므로, 인터넷에 공개 배포할 때
URL 앞에 추측할 수 없는 비밀 경로를 붙여야만 접근할 수 있게 감싼다.

    https://<서비스>.onrender.com/<MCP_SECRET>/mcp   → 내부의 /mcp 로 전달
    https://<서비스>.onrender.com/healthz            → {"status":"ok"} (깨우기/헬스체크용, 정보 노출 없음)
    그 밖의 모든 경로                                  → 404

원본 코드는 수정하지 않는다(업스트림 Sync fork 시 충돌 방지).
실행: uvicorn src.secret_gate:app --host 0.0.0.0 --port $PORT
"""
import hmac
import os

from .main import api

HEALTHZ_PATH = "/healthz"


def _secret() -> str:
    value = (os.environ.get("MCP_SECRET") or "").strip().strip("/")
    if len(value) < 16:
        raise RuntimeError(
            "MCP_SECRET 환경변수가 없거나 너무 짧습니다(16자 이상). "
            "공개 배포 시 비밀 경로 없이 실행하지 않도록 중단합니다."
        )
    return value


class SecretPathGate:
    def __init__(self, inner, secret: str):
        self.inner = inner
        self.prefix = "/" + secret
        self.prefix_b = self.prefix.encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            # 이 서버는 웹소켓을 쓰지 않으므로 모두 거부
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] != "http":
            # lifespan 등은 그대로 전달
            await self.inner(scope, receive, send)
            return

        path = scope.get("path", "")

        if scope["type"] == "http" and path == HEALTHZ_PATH:
            await _respond(send, 200, b'{"status":"ok"}', b"application/json")
            return

        head, sep, rest = path[1:].partition("/")
        if not hmac.compare_digest(("/" + head).encode(), self.prefix_b):
            await _respond(send, 404, b"Not Found", b"text/plain")
            return

        new_path = "/" + rest if sep else "/"
        scope = dict(scope)
        scope["path"] = new_path
        raw = scope.get("raw_path")
        if raw:
            scope["raw_path"] = new_path.encode()
        await self.inner(scope, receive, send)


async def _respond(send, status: int, body: bytes, content_type: bytes):
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", content_type), (b"content-length", str(len(body)).encode())],
    })
    await send({"type": "http.response.body", "body": body})


app = SecretPathGate(api, _secret())
