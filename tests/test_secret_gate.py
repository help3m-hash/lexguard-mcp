"""src/secret_gate.py — 비밀 경로 게이트 동작 테스트"""
import importlib
import os

import pytest
from starlette.testclient import TestClient

SECRET = "test_secret_value_1234567890"


@pytest.fixture(scope="module")
def client():
    os.environ["MCP_SECRET"] = SECRET
    import src.secret_gate as gate
    importlib.reload(gate)
    with TestClient(gate.app) as c:
        yield c


def test_healthz_is_public_and_minimal(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.parametrize("path", ["/", "/health", "/mcp", "/tools", "/check-ip",
                                  f"/{SECRET[:-1]}/mcp", f"/{SECRET}x/mcp"])
def test_paths_without_secret_are_hidden(client, path):
    assert client.get(path).status_code == 404


def test_secret_prefix_reaches_app(client):
    assert client.get(f"/{SECRET}/health").status_code == 200


def test_mcp_initialize_through_gate(client):
    r = client.post(
        f"/{SECRET}/mcp",
        headers={"Accept": "application/json, text/event-stream"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                         "clientInfo": {"name": "t", "version": "1"}}},
    )
    assert r.status_code == 200
    assert "lexguard-mcp" in r.text


def test_refuses_to_start_without_secret(monkeypatch):
    import src.secret_gate as gate
    monkeypatch.setenv("MCP_SECRET", "short")
    with pytest.raises(RuntimeError):
        gate._secret()
