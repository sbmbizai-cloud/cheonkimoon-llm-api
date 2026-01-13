# Gemini 로컬 테스트 가이드

> Railway 건드리지 않고 로컬에서 Claude와 Gemini 동시 실행

---

## 🎯 목표

- 포트 8001: Claude (기존 작업 계속)
- 포트 8002: Gemini (테스트)

---

## 📋 단계별 실행

### Step 1: api_server_gemini.py 생성 (1분)

```bash
cd "C:\Users\A2\Documents\커서\천기문_LLM_챗봇_개발\deploy"
cp api_server.py api_server_gemini.py
```

### Step 2: api_server_gemini.py 수정 (5곳)

#### 1) 라인 29: import 변경
```python
# Before
from client import LLMClient

# After
from client_gemini import LLMClient
```

#### 2) 라인 64: 프롬프트 경로 변경
```python
# Before
V9_PROMPT_PATH = BASE_DIR / "prompts" / "v9.1_with_buttons.yaml"

# After
V4_PROMPT_PATH = BASE_DIR / "prompts" / "v4.0_with_buttons.yaml"
```

#### 3) 라인 67-79: 함수명 변경
```python
# Before
def load_v8_prompts():
    """v9.1 프롬프트 실시간 로드"""
    try:
        if V9_PROMPT_PATH.exists():
            with open(V9_PROMPT_PATH, "r", encoding="utf-8") as f:

# After
def load_v4_prompts():
    """v4.0 프롬프트 실시간 로드"""
    try:
        if V4_PROMPT_PATH.exists():
            with open(V4_PROMPT_PATH, "r", encoding="utf-8") as f:
```

#### 4) 라인 83-86: 시작 메시지
```python
# Before
if V9_PROMPT_PATH.exists():
    print("[OK] v9.1 prompts file found")
else:
    print(f"[WARN] v9.1 prompts file not found at {V9_PROMPT_PATH}")

# After
if V4_PROMPT_PATH.exists():
    print("[OK] v4.0 prompts file found")
else:
    print(f"[WARN] v4.0 prompts file not found at {V4_PROMPT_PATH}")
```

#### 5) 라인 238, 288, 332: 함수 호출 변경 (3곳)
```python
# Before
prompts_data = load_v8_prompts()

# After
prompts_data = load_v4_prompts()
```

### Step 3: 의존성 설치
```bash
pip install -r requirements_gemini.txt
```

### Step 4: 환경변수 설정
```bash
# .env 파일에 추가
echo GOOGLE_API_KEY=your_api_key_here >> .env
```

### Step 5: Gemini 서버 실행
```bash
python -m uvicorn api_server_gemini:app --host 0.0.0.0 --port 8002 --reload
```

### Step 6: 테스트
```bash
# 터미널 1: Gemini 서버 (포트 8002)
curl http://localhost:8002/

# 터미널 2: Claude 서버 (포트 8001, 기존 작업)
curl http://localhost:8001/
```

---

## ✅ 확인사항

서버 실행 시 다음 메시지 확인:
```
[OK] GOOGLE_API_KEY loaded
[OK] v4.0 prompts file found
INFO:     Uvicorn running on http://0.0.0.0:8002
```

---

## 🔧 전체 풀이 테스트

```bash
curl -X POST http://localhost:8002/full-reading-stream \
  -H "Content-Type: application/json" \
  -d '{"user_name":"테스트"}'
```

**확인사항:**
- ✅ 스트리밍 응답
- ✅ 8개 섹션 (`[SECTION:first-impression]` ~ `[SECTION:하반기경고]`)
- ✅ 도사 말투
- ✅ 응답 끊김 없음

---

## 🌐 Framer 테스트

Framer 컴포넌트에서 API URL 변경:

```typescript
// 로컬 Gemini 테스트
const apiUrl = "http://localhost:8002/full-reading-stream";

// Railway Claude (기존)
const apiUrl = "https://web-production-2d723.up.railway.app/full-reading-stream";
```

---

## 🚫 주의사항

- 포트 8001은 기존 작업용이니 건드리지 마세요
- 포트 8002만 Gemini 테스트용
- Railway는 전혀 건드리지 않음
- 테스트 끝나면 포트 8002 서버 종료하면 됨

---

**작성일**: 2026-01-12
