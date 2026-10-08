# 법령검색 MCP — Render 무료 배포 가이드

GitHub 저장소(`help3m-hash/lexguard-mcp`)를 Render에 연결하면 Render가 알아서 빌드·실행하고 HTTPS 주소를 줍니다.
서버를 직접 관리할 필요가 없고, push하면 자동으로 다시 배포됩니다.

```
Claude (PC·웹·모바일)
   │ https://<서비스>.onrender.com/<비밀경로>/mcp
   ▼
Render 무료 서버 ─ 비밀 경로 확인(src/secret_gate.py) ─ lexguard-mcp
   │ Render 나가는 IP
   ▼
국가법령정보센터 OPEN API
```

| 파일 | 역할 |
| --- | --- |
| `src/secret_gate.py` | 비밀 경로로 온 요청만 통과. 그 외는 404. `/healthz`만 공개(정보 노출 없음). 원본 코드는 건드리지 않음 |
| `.github/workflows/keepalive.yml` | 10분마다 서버를 깨워서 첫 질문 지연(약 1분)을 막음 |

---

## 1단계. 비밀 경로 만들기

Windows PowerShell(시작 메뉴에서 `PowerShell` 검색)에서 아래를 실행하고, 나온 32자를 **메모**합니다.

```powershell
[guid]::NewGuid().ToString("N")
```

이 값이 `MCP_SECRET`입니다. **URL의 비밀번호 역할**을 하므로 다른 사람에게 보여 주지 마세요.

## 2단계. Render 가입

1. https://render.com 접속 → 오른쪽 위 **Get Started**
2. **GitHub** 버튼으로 가입(help3m-hash 계정으로 로그인 → **Authorize Render**)
3. 이름이나 용도를 묻는 질문은 아무거나 고르고 넘어가면 됩니다.

카드 등록은 필요 없습니다.

## 3단계. 웹 서비스 만들기

1. Render 대시보드 오른쪽 위 **+ New → Web Service**
2. **Git Provider → GitHub**에서 `help3m-hash/lexguard-mcp` 선택
   (목록에 없으면 **Configure GitHub** → 이 저장소 접근 허용)
3. 설정 입력

| 항목 | 입력값 |
| --- | --- |
| Name | `lexguard-mcp` (주소가 `lexguard-mcp-xxxx.onrender.com`처럼 정해짐) |
| Region | **Singapore** (한국에서 가장 가까움) |
| Branch | `main` |
| Language(Runtime) | **Python 3** |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn src.secret_gate:app --host 0.0.0.0 --port $PORT` |
| Instance Type | **Free** |

4. **Environment Variables** 칸에서 **Add Environment Variable**로 추가

| Key | Value |
| --- | --- |
| `MCP_SECRET` | 1단계에서 만든 32자 |
| `LAW_API_KEY` | 일단 `pending` (4단계에서 진짜 값으로 바꿈) |

5. **Advanced** 펼치기 → **Health Check Path**에 `/healthz`
6. 맨 아래 **Deploy Web Service**
7. 로그 창에 `Your service is live` 가 나오면 완료(첫 배포 3~5분)
8. 화면 위쪽의 주소(`https://lexguard-mcp-xxxx.onrender.com`)를 **메모**

확인: 브라우저에서 `주소/healthz`를 열면 `{"status":"ok"}`, 그냥 `주소`를 열면 `Not Found`가 나오면 정상입니다.

## 4단계. 국가법령정보센터 API 신청

1. Render 서비스 화면 오른쪽 위 **Connect** → **Outbound** 탭 → 나오는 **IP 범위들을 모두 메모**
   - `1.2.3.4/32`처럼 끝이 `/32`이면 IP 한 개라는 뜻입니다. `/32`를 뺀 IP만 쓰면 됩니다.
   - `/24`처럼 넓은 범위로 나오면 IP를 하나씩 등록할 수 없습니다. 이때는 브라우저에서
     `주소/<MCP_SECRET>/check-ip`를 몇 번 열어서 실제로 나오는 IP를 등록하고, 이 상황을 Claude에게 알려 주세요.
2. https://open.law.go.kr 회원가입 → 로그인 → **OPEN API → OPEN API 신청**
3. 서버 IP 입력 칸에 1번의 IP들을 모두 입력
4. 승인 대기(보통 1~2일)
5. 승인되면 **OC 값** = 가입한 이메일의 `@` 앞부분 (예: `help3m@gmail.com` → `help3m`)
6. Render 서비스 → **Environment** → `LAW_API_KEY` 값을 OC 값으로 수정 → **Save, rebuild, and deploy**

## 5단계. 깨우기 설정 (GitHub)

1. https://github.com/help3m-hash/lexguard-mcp → **Settings**
2. 왼쪽 **Secrets and variables → Actions** → **Variables** 탭 → **New repository variable**
   - Name: `RENDER_URL`
   - Value: 3단계에서 메모한 주소(예: `https://lexguard-mcp-xxxx.onrender.com`) — **비밀 경로는 넣지 않음**
3. **Actions** 탭 → 왼쪽 **Keep Render awake** → **Run workflow**로 한 번 실행해 초록색 체크 확인

이후 10분마다 자동 실행됩니다. (GitHub 일정 실행은 몇 분씩 늦어질 수 있습니다.)

## 6단계. Claude에 연결

claude.ai → **설정 → 커넥터 → 맞춤 커넥터 추가**

- 이름: `법령검색`
- URL: `https://lexguard-mcp-xxxx.onrender.com/<MCP_SECRET>/mcp`

새 대화에서 테스트: `개인정보 보호법 제29조 조문 찾아줘`

---

## 운영

| 상황 | 방법 |
| --- | --- |
| 원본 업데이트 반영 | GitHub 저장소 첫 화면 **Sync fork → Update branch** → Render가 자동 재배포 |
| URL이 유출됐을 때 | Render Environment에서 `MCP_SECRET`을 새 값으로 바꾸고 저장 → Claude 커넥터 URL도 수정 |
| "사용자 정보 검증에 실패하였습니다" | API 미승인 또는 IP 불일치. Render **Connect → Outbound**의 IP가 open.law.go.kr에 모두 등록됐는지 확인 |
| 서버가 실제로 쓰는 IP 확인 | 브라우저에서 `주소/<MCP_SECRET>/check-ip` |
| 깨우기가 멈춤 | GitHub는 저장소에 60일간 활동이 없으면 일정 실행을 끕니다. Actions 탭에서 다시 켜기(Enable) |

## 알아둘 점

- Render 무료 플랜은 월 750시간입니다. 이 서비스 하나만 계속 켜 두면 충분하지만, **다른 무료 서비스를 추가로 만들면 시간이 모자랄 수 있습니다.**
- Render는 무료 플랜을 운영용으로 쓰지 말라고 안내합니다. 개인 업무 보조용으로 쓰는 데는 문제없지만, 가끔 재시작될 수 있습니다.
- 질의 내용은 법령명·조문 같은 공개 정보지만, 고객사 이름 같은 민감한 내용을 질의에 넣지 않는 습관을 권장합니다.
