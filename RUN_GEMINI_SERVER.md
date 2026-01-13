# Gemini 서버 실행 가이드

> 기존 Claude 서버와 별도로 Gemini 서버를 포트 8002에서 실행

---

## 🚀 빠른 시작 (3단계)

### 1. 의존성 설치
```bash
cd "C:\Users\A2\Documents\커서\천기문_LLM_챗봇_개발\deploy"
pip install -r requirements_gemini.txt
```

### 2. 환경변수 설정
`.env` 파일에 Google API 키 추가:
```bash
echo GOOGLE_API_KEY=your_api_key_here >> .env
```

### 3. 서버 실행
```bash
python -m uvicorn api_server_gemini:app --host 0.0.0.0 --port 8002 --reload
```

---

## ✅ 실행 확인

서버가 정상 실행되면 다음 메시지가 표시됩니다:

```
[OK] Default saju data loaded: 앤드류
[OK] v4.0 prompts file found (will load on each request)
INFO:     Uvicorn running on http://0.0.0.0:8002 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

---

## 🧪 테스트

### 헬스 체크
```bash
curl http://localhost:8002/
```

**예상 응답:**
```json
{
  "status": "ok",
  "message": "천기문 사주풀이 API (Gemini)",
  "version": "4.0.0",
  "model": "gemini-3-flash-preview"
}
```

### 전체 풀이 테스트
```bash
curl -X POST http://localhost:8002/full-reading-stream \
  -H "Content-Type: application/json" \
  -d "{\"user_name\":\"테스트\"}"
```

**확인사항:**
- ✅ 스트리밍 응답 (실시간 토큰 전송)
- ✅ 8개 섹션 생성 (`[SECTION:first-impression]` ~ `[SECTION:하반기경고]`)
- ✅ 도사 말투 ("자네", "~구만")
- ✅ 응답 끊김 없음

---

## 🔄 Claude vs Gemini 동시 실행

### 포트 구분
- **포트 8001**: Claude (기존)
- **포트 8002**: Gemini (신규)

### 터미널 2개 사용

**터미널 1 (Claude - 기존 작업):**
```bash
cd deploy
python -m uvicorn api_server:app --host 0.0.0.0 --port 8001 --reload
```

**터미널 2 (Gemini - 테스트):**
```bash
cd deploy
python -m uvicorn api_server_gemini:app --host 0.0.0.0 --port 8002 --reload
```

---

## 🌐 Framer 테스트

### API URL 변경

```typescript
// Gemini 테스트 (로컬)
const apiUrl = "http://localhost:8002/full-reading-stream";

// Claude 기존 (Railway)
const apiUrl = "https://web-production-2d723.up.railway.app/full-reading-stream";
```

---

## ❌ 서버 종료

```
터미널에서 Ctrl + C
```

---

## 🔧 문제 해결

### 문제: "GOOGLE_API_KEY not found"
```bash
# .env 파일 확인
cat .env

# API 키 추가
echo GOOGLE_API_KEY=your_key >> .env
```

### 문제: "port 8002 is already in use"
```bash
# 포트 8002 사용 중인 프로세스 확인 (Windows)
netstat -ano | findstr :8002

# 프로세스 종료 (PID 확인 후)
taskkill /PID [PID번호] /F
```

### 문제: "module 'google.generativeai' not found"
```bash
pip install google-generativeai==0.8.0
```

### 문제: "v4.0 prompts file not found"
```bash
# 프롬프트 파일 확인
ls -l prompts/v4.0_with_buttons.yaml

# 없으면 생성
cp prompts/v9.1_with_buttons.yaml prompts/v4.0_with_buttons.yaml
```

---

## 📊 로그 확인

서버 실행 중 터미널에 다음과 같은 로그가 출력됩니다:

```
============================================================
[15:30:45] /full-reading-stream 호출 (Gemini)
  - user_name: 테스트
============================================================
[OK] 프롬프트 준비 완료 (system: 2500자, user: 1200자)
[15:30:45] LLM 스트리밍 시작 (Gemini)...
[15:30:48] 스트리밍 완료 (Gemini)
```

---

## 🎯 다음 단계

로컬 테스트 성공 후:

1. **품질 비교**: Claude vs Gemini 응답 품질 비교
2. **성능 측정**: 첫 토큰 시간, 전체 응답 시간
3. **Railway 배포**: 테스트 성공 시 Railway 새 프로젝트 생성

---

**작성일**: 2026-01-12
**포트**: 8002
**모델**: gemini-3-flash-preview
