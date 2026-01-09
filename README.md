# 천기문 사주풀이 API

FastAPI 기반 사주풀이 API 서버입니다.

## 기능

- `/full-reading-stream`: 8개 섹션 전체 풀이 (스트리밍)
- `/first-impression-stream`: 첫인상 풀이 (스트리밍)
- `/step-stream`: 개별 스텝 풀이 (스트리밍)
- `/health`: 서버 상태 확인

## 환경 변수

Railway에서 설정해야 할 환경 변수:

```
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
```

## 로컬 실행

```bash
pip install -r requirements.txt
uvicorn api_server:app --host 0.0.0.0 --port 8001
```

## 배포

Railway에서 자동 배포됩니다.

## 기술 스택

- Python 3.9+
- FastAPI
- Claude Sonnet 4 (Anthropic API)
- SSE Streaming
