# Gemini 3 Flash Preview 마이그레이션 가이드

> 기존 Claude 파일을 건드리지 않고 Gemini로 전환하는 방법

---

## 📦 생성된 파일 목록

### 1. Gemini 클라이언트
- `deploy/client_gemini.py` ✅ 생성 완료
- `02_개발/LLM_모듈/client_gemini.py` ✅ 생성 완료

### 2. 의존성 파일
- `deploy/requirements_gemini.txt` ✅ 생성 완료

### 3. 프롬프트 파일 (v4.0)
- `deploy/prompts/v4.0_with_buttons.yaml` ✅ 생성 완료
- `framer/system_prompts/v4.0_with_buttons.yaml` ✅ 생성 완료

---

## 🔧 api_server.py 수정 방법

### 방법 1: 기존 파일 수정 (권장)

**수정 위치 4곳:**

#### 1) 프롬프트 경로 변경 (64번 줄)
```python
# Before
V9_PROMPT_PATH = BASE_DIR / "prompts" / "v9.1_with_buttons.yaml"

# After
V4_PROMPT_PATH = BASE_DIR / "prompts" / "v4.0_with_buttons.yaml"
```

#### 2) 함수명 변경 (67번 줄)
```python
# Before
def load_v8_prompts():
    """v9.1 프롬프트 실시간 로드 (yaml 수정 즉시 반영)"""
    try:
        if V9_PROMPT_PATH.exists():
            with open(V9_PROMPT_PATH, "r", encoding="utf-8") as f:

# After
def load_v4_prompts():
    """v4.0 프롬프트 실시간 로드 (yaml 수정 즉시 반영)"""
    try:
        if V4_PROMPT_PATH.exists():
            with open(V4_PROMPT_PATH, "r", encoding="utf-8") as f:
```

#### 3) 함수 호출 변경 (3곳)
**위치:**
- 238번 줄: `/full-reading-stream` 엔드포인트
- 288번 줄: `/first-impression-stream` 엔드포인트
- 332번 줄: `/step-stream` 엔드포인트

```python
# Before
prompts_data = load_v8_prompts()

# After
prompts_data = load_v4_prompts()
```

#### 4) 시작 메시지 변경 (83번 줄)
```python
# Before
if V9_PROMPT_PATH.exists():
    print("[OK] v9.1 prompts file found (will load on each request)")
else:
    print(f"[WARN] v9.1 prompts file not found at {V9_PROMPT_PATH}")

# After
if V4_PROMPT_PATH.exists():
    print("[OK] v4.0 prompts file found (will load on each request)")
else:
    print(f"[WARN] v4.0 prompts file not found at {V4_PROMPT_PATH}")
```

#### 5) import 변경 (29번 줄)
```python
# Before
from client import LLMClient

# After
from client_gemini import LLMClient
```

---

### 방법 2: 별도 파일 생성 (충돌 방지)

기존 `api_server.py`를 유지하고 `api_server_gemini.py` 생성:

```bash
cp deploy/api_server.py deploy/api_server_gemini.py
```

그 다음 `api_server_gemini.py`에서 위 5곳 수정.

**서버 실행 시:**
```bash
# Claude 버전
python -m uvicorn api_server:app --host 0.0.0.0 --port 8001

# Gemini 버전
python -m uvicorn api_server_gemini:app --host 0.0.0.0 --port 8002
```

---

## 🚀 로컬 테스트 방법

### 1. 의존성 설치
```bash
cd deploy
pip install -r requirements_gemini.txt
```

### 2. 환경변수 설정
```bash
# .env 파일에 추가
echo GOOGLE_API_KEY=your_api_key_here >> .env
```

### 3. 단위 테스트
```python
# test_gemini.py
from client_gemini import LLMClient

client = LLMClient()

# 스트리밍 테스트
print("=== 스트리밍 테스트 ===")
for chunk in client.stream(
    system_prompt="당신은 도움이 되는 AI입니다.",
    user_message="1부터 5까지 세어주세요."
):
    print(chunk, end="", flush=True)
print("\n✅ 완료")
```

### 4. 서버 실행 (방법 선택)

**방법 1: 기존 파일 수정 후**
```bash
cd deploy
python -m uvicorn api_server:app --host 0.0.0.0 --port 8001 --reload
```

**방법 2: 별도 파일 사용**
```bash
cd deploy
python -m uvicorn api_server_gemini:app --host 0.0.0.0 --port 8002 --reload
```

### 5. API 테스트
```bash
# 헬스 체크
curl http://localhost:8001/  # 또는 8002

# 전체 풀이 테스트
curl -X POST http://localhost:8001/full-reading-stream \
  -H "Content-Type: application/json" \
  -d '{"user_name":"테스트"}'
```

---

## ✅ 검증 체크리스트

- [ ] `google-generativeai` 설치 완료
- [ ] `GOOGLE_API_KEY` 환경변수 설정
- [ ] client_gemini.py 정상 작동 확인
- [ ] api_server.py 수정 완료 (또는 api_server_gemini.py 생성)
- [ ] 서버 시작 성공 (에러 없음)
- [ ] 헬스 체크 응답: `{"status":"ok"...}`
- [ ] 스트리밍 응답 수신
- [ ] 8개 섹션 생성 확인
- [ ] 도사 말투 유지 확인

---

## ⚠️ 주의사항

### 1. 토큰 제한
- Gemini 3 Flash Preview: max_output_tokens 불확실 (현재 8192 설정)
- 응답이 끊기면 `client_gemini.py`의 `max_output_tokens` 증가

### 2. 안전 필터
- 사주 용어가 차단될 경우 `client_gemini.py`에 safety_settings 추가 필요

### 3. 모델 코드
- 현재: `gemini-3-flash-preview`
- 최신 모델이라 공식 문서 제한적
- 에러 발생 시 로그 상세 확인 필요

---

## 🔄 롤백 방법

문제 발생 시 기존 Claude 버전으로 즉시 복구 가능:

### 방법 1 사용 시
```bash
cd deploy
# api_server.py 수정사항 되돌리기
git checkout api_server.py

# 또는 백업에서 복구
cp api_server_backup.py api_server.py
```

### 방법 2 사용 시
```bash
# 그냥 Claude 버전 서버 재시작
python -m uvicorn api_server:app --host 0.0.0.0 --port 8001 --reload
```

---

## 📞 문제 해결

### 문제: "GOOGLE_API_KEY not found"
**해결:** `.env` 파일에 API 키 추가
```bash
echo GOOGLE_API_KEY=your_key >> deploy/.env
```

### 문제: "모듈을 찾을 수 없음: google.generativeai"
**해결:** 의존성 설치
```bash
pip install google-generativeai==0.8.0
```

### 문제: "응답이 끊김"
**해결:** `client_gemini.py`의 `max_output_tokens` 증가
```python
self.max_output_tokens = 16384  # 8192 → 16384
```

### 문제: "안전 필터 차단"
**해결:** `client_gemini.py`에 safety_settings 추가
```python
from google.generativeai.types import HarmCategory, HarmBlockThreshold

safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

response = model.generate_content(
    user_message,
    safety_settings=safety_settings,
    stream=True
)
```

---

**작성일**: 2026-01-12
**버전**: v4.0 (Gemini 3 Flash Preview)
