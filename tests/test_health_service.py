"""
HealthService — API 키 마스킹 등 순수/경량 검증 + deep API 연결 검사
"""
import httpx
import pytest

import src.services.health_service as health_module
from src.services.health_service import HealthService


class _FakeResponse:
    def __init__(self, text, content_type="application/json", status_code=200):
        self.text = text
        self.headers = {"Content-Type": content_type}
        self.status_code = status_code
        self.url = "http://test.local/DRF/lawSearch.do"


@pytest.mark.asyncio
async def test_health_never_exposes_raw_api_key(monkeypatch):
    raw = "abcdefghijklmnopqr_stuvwxyz"
    monkeypatch.setenv("LAW_API_KEY", raw)
    out = await HealthService.check_health()
    preview = out["environment"]["law_api_key"]["preview"]
    assert preview is not None
    assert raw not in preview
    nested = out["environment"]["env_vars"]["LAW_API_KEY"]["preview"]
    assert nested is not None
    assert raw not in nested


@pytest.mark.asyncio
async def test_health_without_key_no_preview(monkeypatch):
    monkeypatch.delenv("LAW_API_KEY", raising=False)
    out = await HealthService.check_health()
    assert out["environment"]["law_api_key"]["preview"] is None


@pytest.mark.asyncio
async def test_health_shallow_has_no_api_connection(monkeypatch):
    monkeypatch.setenv("LAW_API_KEY", "realkey1234")
    out = await HealthService.check_health()
    assert "api_connection" not in out


@pytest.mark.asyncio
async def test_health_deep_ok(monkeypatch):
    monkeypatch.setenv("LAW_API_KEY", "realkey1234")

    async def fake_aget(url, params=None, timeout=None):
        return _FakeResponse('{"법령": {"기본정보": {"법령명_한글": "근로기준법"}}}')

    monkeypatch.setattr(health_module, "aget", fake_aget)
    out = await HealthService.check_health(deep=True)
    assert out["api_connection"]["status"] == "ok"
    assert out["api_connection"]["checked"] is True
    assert out["status"] == "ok"


@pytest.mark.asyncio
async def test_health_deep_unregistered_ip_json(monkeypatch):
    """미등록 IP/잘못된 키: HTTP 200 + JSON 본문으로 오는 검증 실패를 감지해야 함."""
    monkeypatch.setenv("LAW_API_KEY", "realkey1234")

    async def fake_aget(url, params=None, timeout=None):
        return _FakeResponse(
            '{"result": "사용자 정보 검증에 실패하였습니다.",'
            ' "msg": "OPEN API 호출 시 사용자 검증을 위하여 정확한 서버장비의'
            ' IP주소 및 도메인주소를 등록해 주세요."}'
        )

    monkeypatch.setattr(health_module, "aget", fake_aget)
    out = await HealthService.check_health(deep=True)
    conn = out["api_connection"]
    assert conn["status"] == "failed"
    assert conn["error_code"] == "API_ERROR_AUTH"
    assert "IP" in conn["guide"]
    assert out["status"] == "warning"


@pytest.mark.asyncio
async def test_health_deep_unregistered_ip_html(monkeypatch):
    monkeypatch.setenv("LAW_API_KEY", "realkey1234")

    async def fake_aget(url, params=None, timeout=None):
        return _FakeResponse(
            "<html><body>사용자 정보 검증에 실패하였습니다.</body></html>",
            content_type="text/html",
        )

    monkeypatch.setattr(health_module, "aget", fake_aget)
    out = await HealthService.check_health(deep=True)
    conn = out["api_connection"]
    assert conn["status"] == "failed"
    # HTML 안내 페이지라도 인증 실패 문구가 있으면 인증 오류로 분류한다.
    assert conn["error_code"] == "API_ERROR_AUTH"
    assert "IP" in conn["guide"]
    assert out["status"] == "warning"


@pytest.mark.asyncio
async def test_health_deep_timeout(monkeypatch):
    monkeypatch.setenv("LAW_API_KEY", "realkey1234")

    async def fake_aget(url, params=None, timeout=None):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(health_module, "aget", fake_aget)
    out = await HealthService.check_health(deep=True)
    assert out["api_connection"]["status"] == "failed"
    assert "error_code" not in out["api_connection"]
    assert out["status"] == "warning"


@pytest.mark.asyncio
async def test_health_deep_without_key(monkeypatch):
    monkeypatch.delenv("LAW_API_KEY", raising=False)
    monkeypatch.delenv("LAWGOKR_OC", raising=False)

    async def fail_aget(url, params=None, timeout=None):
        raise AssertionError("키가 없으면 실제 호출을 하지 않아야 함")

    monkeypatch.setattr(health_module, "aget", fail_aget)
    out = await HealthService.check_health(deep=True)
    conn = out["api_connection"]
    assert conn["status"] == "failed"
    assert conn["error_code"] == "API_ERROR_AUTH"


@pytest.mark.asyncio
async def test_health_deep_failure_marks_api_not_ready(monkeypatch):
    """연결 실패 시 api_ready가 True로 남아 '사용 가능'처럼 보이면 안 된다."""
    monkeypatch.setenv("LAW_API_KEY", "realkey1234")

    async def fake_aget(url, params=None, timeout=None):
        return _FakeResponse('{"result": "사용자 정보 검증에 실패하였습니다."}')

    monkeypatch.setattr(health_module, "aget", fake_aget)
    out = await HealthService.check_health(deep=True)
    env = out["environment"]
    assert env["api_ready"] is False
    assert env["api_status"] == "connection_failed"


@pytest.mark.asyncio
async def test_health_key_source_without_env_file(monkeypatch, tmp_path):
    """.env 파일이 없으면 출처를 '.env 파일'로 표시하지 않는다."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LAW_API_KEY", "realkey1234")
    out = await HealthService.check_health()
    source = out["environment"]["law_api_key"]["source"]
    assert ".env 파일에서 로드됨" not in source
    assert "호스팅 환경변수" in source


@pytest.mark.asyncio
async def test_health_reports_stripped_key_and_whitespace_warning(monkeypatch):
    """미리보기·길이는 실제 전송되는 값(strip)을 기준으로 하고 공백은 경고한다."""
    monkeypatch.setenv("LAW_API_KEY", " realkey12345 ")
    out = await HealthService.check_health()
    info = out["environment"]["law_api_key"]
    assert info["length"] == 12
    assert info["preview"] == "real****2345"
    assert "warning" in info


@pytest.mark.asyncio
async def test_health_uses_lawgokr_oc_fallback(monkeypatch):
    """요청 경로(get_api_key)와 같이 LAWGOKR_OC도 키로 인정한다."""
    monkeypatch.delenv("LAW_API_KEY", raising=False)
    monkeypatch.setenv("LAWGOKR_OC", "fallbackkey1")
    out = await HealthService.check_health()
    info = out["environment"]["law_api_key"]
    assert info["configured"] is True
    assert "LAWGOKR_OC" in info["source"]
