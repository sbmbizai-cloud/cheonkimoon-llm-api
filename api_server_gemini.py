"""
FastAPI 서버 - 천기문 사주풀이 API (Gemini 3 Flash Preview 버전)
실행: uvicorn api_server_gemini:app --host 0.0.0.0 --port 8002
"""

import sys
import os
import re
import yaml
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
import asyncio
from typing import Optional, List
import json
from dotenv import load_dotenv

# .env 파일 로드 (현재 디렉토리)
load_dotenv()

# 현재 디렉토리 기준 경로 설정
BASE_DIR = Path(__file__).parent

# LLM_모듈 경로 추가
sys.path.insert(0, str(BASE_DIR))
from client_gemini import LLMClient

# FastAPI 앱 생성
app = FastAPI(title="천기문 사주풀이 API (Gemini)", version="4.0.0")

# CORS 설정 (Framer에서 호출 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 클라이언트
llm_client = LLMClient()

# 사주 데이터 디렉토리 (배포 환경용)
SAJU_DATA_DIR = BASE_DIR / "saju_data"

# 기본 테스트 데이터 로드
DEFAULT_SAJU_DATA = None
DEFAULT_USER_NAME = None
try:
    default_file = SAJU_DATA_DIR / "default.json"
    if default_file.exists():
        with open(default_file, "r", encoding="utf-8") as f:
            DEFAULT_SAJU_DATA = json.load(f)
        DEFAULT_USER_NAME = DEFAULT_SAJU_DATA.get("meta", {}).get("이름", "테스트")
        print(f"[OK] Default saju data loaded: {DEFAULT_USER_NAME}")
except Exception as e:
    print(f"[WARN] Default saju data load failed: {e}")
    DEFAULT_USER_NAME = "테스트"

# v4.0 프롬프트 경로 (Gemini용)
V4_PROMPT_PATH = BASE_DIR / "prompts" / "v4.0_with_buttons.yaml"


def load_v4_prompts():
    """v4.0 프롬프트 실시간 로드 (yaml 수정 즉시 반영)"""
    try:
        if V4_PROMPT_PATH.exists():
            with open(V4_PROMPT_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                import datetime
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] v4.0 prompts loaded from disk")
                return data
    except Exception as e:
        print(f"[WARN] v4.0 prompts load failed: {e}")
    return None


# v10.0 프롬프트 경로 (배포용 - prompts 폴더)
V10_PROMPT_PATH = BASE_DIR / "prompts" / "v10.0_parallel.yaml"


def load_v10_prompts():
    """v10.0 프롬프트 실시간 로드 (yaml 수정 즉시 반영)"""
    try:
        if V10_PROMPT_PATH.exists():
            with open(V10_PROMPT_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                import datetime
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] v10.0 prompts loaded from disk")
                return data
    except Exception as e:
        print(f"[WARN] v10.0 prompts load failed: {e}")
    return None


# 서버 시작 시 확인
if V4_PROMPT_PATH.exists():
    print("[OK] v4.0 prompts file found (will load on each request)")
else:
    print(f"[WARN] v4.0 prompts file not found at {V4_PROMPT_PATH}")

if V10_PROMPT_PATH.exists():
    print("[OK] v10.0 prompts file found (will load on each request)")
else:
    print(f"[WARN] v10.0 prompts file not found at {V10_PROMPT_PATH}")


# ============ v8 헬퍼 함수 ============

def get_template_variables(saju_data: dict, user_name: str) -> dict:
    """사주 데이터에서 모든 템플릿 변수 추출"""
    if not saju_data:
        return {"name": user_name, "saju_data": "{}"}

    # 다양한 JSON 구조 지원
    meta = saju_data.get("meta", {})
    core = saju_data.get("핵심요소", saju_data.get("사주", {}))
    ohang = saju_data.get("오행", saju_data.get("오행분석", {}))
    sipsung = saju_data.get("십성", saju_data.get("십성분석", {}))
    daewoon = saju_data.get("대운", {})
    sewoon = saju_data.get("세운", {})
    sinsal = saju_data.get("신살", {})
    gisin = saju_data.get("기신", {})

    # 십성 개수 계산
    sipsung_detail = sipsung.get("상세", {})
    jaesong_count = sipsung_detail.get("정재", 0) + sipsung_detail.get("편재", 0)
    gwansung_count = sipsung_detail.get("정관", 0) + sipsung_detail.get("편관", 0)
    siksang_count = sipsung_detail.get("식신", 0) + sipsung_detail.get("상관", 0)
    insung_count = sipsung_detail.get("정인", 0) + sipsung_detail.get("편인", 0)
    bigeop_count = sipsung_detail.get("비견", 0) + sipsung_detail.get("겁재", 0)

    # 일주에서 일지 추출 (두 번째 글자)
    ilju = core.get("일주", "")
    ilji = ilju[1] if len(ilju) >= 2 else ""

    return {
        "name": user_name,
        "gender": meta.get("성별", ""),
        "ilju": ilju,
        "ilgan": core.get("일간", ""),
        "ilji": ilji,
        "ohang_gwada": str(ohang.get("과다", [])),
        "ohang_gyeolpip": str(ohang.get("결핍", [])),
        "sipsung_gwada": str(sipsung.get("과다", [])),
        "sipsung_gyeolpip": str(sipsung.get("결핍", [])),
        "jaesong_count": jaesong_count,
        "gwansung_count": gwansung_count,
        "siksang_count": siksang_count,
        "insung_count": insung_count,
        "bigeop_count": bigeop_count,
        "current_daewoon": daewoon.get("현재", {}).get("간지", ""),
        "sewoon_2026": sewoon.get("분석대상", {}).get("간지", ""),
        "sinsal": str(sinsal),
        "dohwasal": "있음" if sinsal.get("특수", {}).get("도화살") else "없음",
        "mbti": meta.get("mbti", "알 수 없음"),
        "gisin": str(gisin.get("오행", [])),
        "saju_data": json.dumps(saju_data, ensure_ascii=False, indent=2)
    }


def render_template(template: str, variables: dict) -> str:
    """템플릿 변수 치환"""
    result = template
    for key, value in variables.items():
        result = result.replace(f"{{{key}}}", str(value))
    return result


def parse_v8_response(text: str) -> List[str]:
    """v8 형식 응답을 말풍선 + 버튼으로 분리"""
    parts = text.split("---")
    bubbles = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        button_match = re.search(r'\[BUTTON:\s*([^\]]+)\]', part)
        button_text = None

        if button_match:
            button_text = button_match.group(1)
            part = re.sub(r'\[BUTTON:\s*[^\]]+\]', '', part).strip()

        sentences = [s.strip() for s in part.split("\n") if s.strip()]

        for sentence in sentences:
            bubbles.append(sentence)

        if button_text:
            bubbles.append(f"[BUTTON]{button_text}")

    return bubbles


# ============ 요청/응답 모델 ============

class FirstImpressionRequest(BaseModel):
    """첫인상 풀이 요청"""
    topic_id: Optional[str] = None
    user_name: str = "사용자"
    saju_data: Optional[dict] = None


class FullReadingRequest(BaseModel):
    """전체 풀이 요청"""
    user_name: str = "사용자"
    saju_data: Optional[dict] = None


class StepRequest(BaseModel):
    """특정 스텝 풀이 요청"""
    step_name: str
    user_name: str = "사용자"
    saju_data: Optional[dict] = None


class SectionRequest(BaseModel):
    """특정 섹션 풀이 요청 (v10.0 병렬 처리용)"""
    section_name: str  # "first-impression", "강점", "yearly", "재물운", "진로운", "성격", "연애운", "하반기경고"
    user_name: str = "사용자"
    saju_data: Optional[dict] = None


class ApiResponse(BaseModel):
    """API 응답"""
    success: bool
    messages: List[str]
    raw_text: Optional[str] = None
    model: Optional[str] = None
    response_time: Optional[float] = None


# ============ API 엔드포인트 ============

@app.get("/")
async def root():
    """헬스 체크"""
    return {"status": "ok", "message": "천기문 사주풀이 API (Gemini)", "version": "4.0.0", "model": "gemini-3-flash-preview"}


@app.get("/health")
async def health_check():
    """상세 헬스 체크"""
    return {
        "status": "ok",
        "model": "gemini-3-flash-preview",
        "prompts_loaded": V4_PROMPT_PATH.exists(),
        "default_data_loaded": DEFAULT_SAJU_DATA is not None
    }


@app.post("/full-reading-stream")
async def get_full_reading_stream(request: FullReadingRequest):
    """전체 풀이 - 통합 프롬프트로 8개 섹션을 한번에 생성 (스트리밍)"""
    import datetime

    print("\n" + "="*60)
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] /full-reading-stream 호출 (Gemini)")
    print(f"  - user_name: {request.user_name}")
    print("="*60)

    v4_prompts = load_v4_prompts()
    if not v4_prompts:
        raise HTTPException(status_code=500, detail="v4.0 prompts not loaded")

    unified_prompt = v4_prompts.get("unified_prompt", {})
    if not unified_prompt:
        raise HTTPException(status_code=500, detail="unified_prompt not found in yaml")

    # 사주 데이터 결정
    saju_data = request.saju_data if request.saju_data else DEFAULT_SAJU_DATA
    user_name = request.user_name if request.user_name != "사용자" else DEFAULT_USER_NAME

    # 변수 추출
    variables = get_template_variables(saju_data, user_name)
    timestamp = datetime.datetime.now().isoformat()

    # 프롬프트 준비
    system_prompt = unified_prompt.get("system", "") + f"\n\n[Internal timestamp: {timestamp}]"
    user_message = render_template(unified_prompt.get("user_template", ""), variables)

    print(f"[OK] 프롬프트 준비 완료 (system: {len(system_prompt)}자, user: {len(user_message)}자)")

    async def event_generator():
        try:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] LLM 스트리밍 시작 (Gemini)...")
            # 동기 generator를 별도 스레드에서 실행
            loop = asyncio.get_event_loop()
            stream_iter = iter(llm_client.stream(system_prompt, user_message))

            while True:
                try:
                    chunk = await loop.run_in_executor(None, next, stream_iter)
                    yield {"event": "message", "data": json.dumps({"token": chunk})}
                except StopIteration:
                    break

            yield {"event": "message", "data": json.dumps({"done": True})}
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 스트리밍 완료 (Gemini)")
        except Exception as e:
            print(f"[ERROR] 스트리밍 실패 (Gemini): {str(e)}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())


@app.post("/first-impression-stream")
async def get_first_impression_stream(request: FirstImpressionRequest):
    """첫인상 풀이 - 스트리밍 (레거시 호환)"""
    import datetime

    v4_prompts = load_v4_prompts()
    if not v4_prompts:
        raise HTTPException(status_code=500, detail="v4.0 prompts not loaded")

    saju_data = request.saju_data if request.saju_data else DEFAULT_SAJU_DATA
    user_name = request.user_name if request.user_name != "사용자" else DEFAULT_USER_NAME

    step_prompt = v4_prompts.get("step_prompts", {}).get("step_2_first_impression", {})
    if not step_prompt:
        raise HTTPException(status_code=500, detail="step_2 prompt not found")

    system_prompt = step_prompt.get("system", "")
    user_template = step_prompt.get("user_template", "")

    timestamp = datetime.datetime.now().isoformat()
    system_prompt = f"{system_prompt}\n\n[Internal timestamp: {timestamp}]"

    variables = get_template_variables(saju_data, user_name)
    user_message = render_template(user_template, variables)

    async def event_generator():
        try:
            loop = asyncio.get_event_loop()
            stream_iter = iter(llm_client.stream(system_prompt, user_message))

            while True:
                try:
                    chunk = await loop.run_in_executor(None, next, stream_iter)
                    yield {"event": "message", "data": json.dumps({"token": chunk})}
                except StopIteration:
                    break

            yield {"event": "message", "data": json.dumps({"done": True})}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())


@app.post("/step-stream")
async def get_step_stream(request: StepRequest):
    """특정 스텝 풀이 - 스트리밍"""
    import datetime

    v4_prompts = load_v4_prompts()
    if not v4_prompts:
        raise HTTPException(status_code=500, detail="v4.0 prompts not loaded")

    saju_data = request.saju_data if request.saju_data else DEFAULT_SAJU_DATA
    user_name = request.user_name if request.user_name != "사용자" else DEFAULT_USER_NAME

    step_prompt = v4_prompts.get("step_prompts", {}).get(request.step_name, {})
    if not step_prompt:
        raise HTTPException(status_code=404, detail=f"step not found: {request.step_name}")

    system_prompt = step_prompt.get("system", "")
    user_template = step_prompt.get("user_template", "")

    timestamp = datetime.datetime.now().isoformat()
    system_prompt = f"{system_prompt}\n\n[Internal timestamp: {timestamp}]"

    variables = get_template_variables(saju_data, user_name)
    user_message = render_template(user_template, variables)

    async def event_generator():
        try:
            loop = asyncio.get_event_loop()
            stream_iter = iter(llm_client.stream(system_prompt, user_message))

            while True:
                try:
                    chunk = await loop.run_in_executor(None, next, stream_iter)
                    yield {"event": "message", "data": json.dumps({"token": chunk})}
                except StopIteration:
                    break

            yield {"event": "message", "data": json.dumps({"done": True})}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())


@app.post("/section-stream")
async def get_section_stream(request: SectionRequest):
    """특정 섹션 풀이 - 스트리밍 (v10.0 병렬 처리용)"""
    import datetime

    print(f"\n{'='*60}")
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] /section-stream 호출: {request.section_name}")
    print(f"  - user_name: {request.user_name}")
    print('='*60)

    v10_prompts = load_v10_prompts()
    if not v10_prompts:
        raise HTTPException(status_code=500, detail="v10.0 prompts not loaded")

    section_prompt = v10_prompts.get("section_prompts", {}).get(request.section_name, {})
    if not section_prompt:
        raise HTTPException(status_code=404, detail=f"section not found: {request.section_name}")

    # 사주 데이터 결정
    saju_data = request.saju_data if request.saju_data else DEFAULT_SAJU_DATA
    user_name = request.user_name if request.user_name != "사용자" else DEFAULT_USER_NAME

    # 변수 추출
    variables = get_template_variables(saju_data, user_name)
    timestamp = datetime.datetime.now().isoformat()

    # 공통 시스템 + 섹션별 시스템 결합
    common_system = v10_prompts.get("common_system", "")
    section_system = section_prompt.get("system", "")
    system_prompt = section_system.replace("{common_system}", common_system)
    system_prompt = f"{system_prompt}\n\n[Internal timestamp: {timestamp}]"

    # 공통 데이터 + 섹션별 템플릿 결합
    common_data = v10_prompts.get("common_data_template", "")
    section_user = section_prompt.get("user_template", "")
    user_message = section_user.replace("{common_data_template}", common_data)
    user_message = render_template(user_message, variables)

    print(f"[OK] 섹션 프롬프트 준비 완료: {request.section_name}")
    print(f"  - system_prompt 길이: {len(system_prompt)}자")
    print(f"  - user_message 길이: {len(user_message)}자")

    async def event_generator():
        try:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 섹션 스트리밍 시작: {request.section_name}")
            loop = asyncio.get_event_loop()
            stream_iter = iter(llm_client.stream(system_prompt, user_message))

            while True:
                try:
                    chunk = await loop.run_in_executor(None, next, stream_iter)
                    yield {"event": "message", "data": json.dumps({"token": chunk})}
                except StopIteration:
                    break

            yield {"event": "message", "data": json.dumps({"done": True})}
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 섹션 스트리밍 완료: {request.section_name}")
        except Exception as e:
            print(f"[ERROR] 섹션 스트리밍 실패 ({request.section_name}): {str(e)}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8002))
    uvicorn.run("api_server_gemini:app", host="0.0.0.0", port=port, reload=True)
