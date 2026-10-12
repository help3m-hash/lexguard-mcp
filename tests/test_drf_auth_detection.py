"""
DRF 인증 실패 응답(미등록 IP·잘못된 OC)이 모든 도구에서 API_ERROR_AUTH로 드러나는지 검증.

DRF는 인증 실패를 HTTP 200 + 짧은 안내문으로 돌려준다. 이를 놓치면 법령 조회는
"법령 ID를 찾을 수 없습니다", 검색은 "결과 0건"으로 보여 원인 진단이 어려워진다.
"""
from src.repositories.base import BaseLawRepository


class _Resp:
    def __init__(self, text, content_type="application/json", status_code=200):
        self.text = text
        self.headers = {"Content-Type": content_type}
        self.status_code = status_code
        self.url = "https://www.law.go.kr/DRF/lawSearch.do?OC=secretkey1234&query=x"


AUTH_JSON = (
    '{"result": "사용자 정보 검증에 실패하였습니다.",'
    ' "msg": "OPEN API 호출 시 사용자 검증을 위하여 정확한 서버장비의'
    ' IP주소 및 도메인주소를 등록해 주세요."}'
)


def test_auth_failure_json_is_reported_as_auth_error():
    err = BaseLawRepository.validate_drf_response(_Resp(AUTH_JSON))
    assert err is not None
    assert err["error_code"] == "API_ERROR_AUTH"
    assert "IP" in err["recovery_guide"]


def test_auth_failure_xml_is_reported_as_auth_error():
    body = "<?xml version='1.0'?><result>사용자 정보 검증에 실패하였습니다.</result>"
    err = BaseLawRepository.validate_drf_response(_Resp(body, "text/xml"))
    assert err["error_code"] == "API_ERROR_AUTH"


def test_auth_failure_html_is_reported_as_auth_error():
    body = "<html><body>사용자 정보 검증에 실패하였습니다.</body></html>"
    err = BaseLawRepository.validate_drf_response(_Resp(body, "text/html"))
    assert err["error_code"] == "API_ERROR_AUTH"


def test_auth_error_never_exposes_raw_key():
    err = BaseLawRepository.validate_drf_response(_Resp(AUTH_JSON))
    assert "secretkey1234" not in str(err)


def test_normal_response_passes():
    body = '{"LawSearch": {"totalCnt": "1", "law": [{"법령명한글": "민법"}]}}'
    assert BaseLawRepository.validate_drf_response(_Resp(body)) is None


def test_long_legitimate_body_mentioning_phrase_is_not_auth_error():
    """판례 본문 등에 같은 문구가 우연히 들어 있어도 인증 오류로 오판하지 않는다."""
    body = '{"판례": "' + ("가" * 3000) + ' 사용자 정보 검증에 실패하였다고 주장한다."}'
    assert BaseLawRepository.validate_drf_response(_Resp(body)) is None
