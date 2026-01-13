"""
FastAPI 서버 - 천기문 사주풀이 API (배포용)
실행: uvicorn api_server:app --host 0.0.0.0 --port 8001
"""

import sys
import os
import re
import yaml
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
import asyncio
from typing import Optional, List
import json
from dotenv import load_dotenv
from datetime import datetime
import httpx
import secrets
import string
import asyncpg

# .env 파일 로드 (현재 디렉토리)
load_dotenv()

# Supabase 연결 정보
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres.jlutbjmjpreauyanjzdd:cjsrlans1234@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres")

# 현재 디렉토리 기준 경로 설정
BASE_DIR = Path(__file__).parent

# LLM_모듈 경로 추가
sys.path.insert(0, str(BASE_DIR))
from client import LLMClient

# FastAPI 앱 생성
app = FastAPI(title="천기문 사주풀이 API", version="1.0.0")

# CORS 설정 (Framer에서 호출 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 변수
llm_client = LLMClient()
db_pool: Optional[asyncpg.Pool] = None

# 서버 시작/종료 이벤트
@app.on_event("startup")
async def startup():
    """서버 시작 시 DB 연결 풀 생성"""
    global db_pool
    print("[INFO] Connecting to Supabase...")
    try:
        db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            command_timeout=60,
            statement_cache_size=0  # Supabase pgbouncer compatibility
        )
        print("[OK] Supabase connection pool created")
    except Exception as e:
        print(f"[ERROR] Failed to create DB pool: {e}")

@app.on_event("shutdown")
async def shutdown():
    """서버 종료 시 DB 연결 풀 닫기"""
    global db_pool
    if db_pool:
        await db_pool.close()
        print("[INFO] Supabase connection pool closed")

# 사주 데이터 디렉토리 (배포 환경용)
SAJU_DATA_DIR = BASE_DIR / "saju_data"

# 무료 사주 저장소 (비동기 만세력 API 통합용)
STORAGE_DIR = BASE_DIR / "saju_data"
STORAGE_DIR.mkdir(exist_ok=True)

# 만세력 API URL
MANSERYUK_API_URL = "https://api.cheongimun.com/api/v1/manseryuk/calculate-enriched"

# 기본 테스트 데이터 로드 (비활성화 - 실제 데이터만 사용)
DEFAULT_SAJU_DATA = None
DEFAULT_USER_NAME = "테스트"
# try:
#     default_file = SAJU_DATA_DIR / "default.json"
#     if default_file.exists():
#         with open(default_file, "r", encoding="utf-8") as f:
#             DEFAULT_SAJU_DATA = json.load(f)
#         DEFAULT_USER_NAME = DEFAULT_SAJU_DATA.get("meta", {}).get("이름", "테스트")
#         print(f"[OK] Default saju data loaded: {DEFAULT_USER_NAME}")
# except Exception as e:
#     print(f"[WARN] Default saju data load failed: {e}")
#     DEFAULT_USER_NAME = "테스트"
print("[INFO] Default saju data disabled - using request data only")

# v9.1 프롬프트 경로 (배포용 - prompts 폴더)
V9_PROMPT_PATH = BASE_DIR / "prompts" / "v9.1_with_buttons.yaml"


def load_v8_prompts():
    """v9.1 프롬프트 실시간 로드 (yaml 수정 즉시 반영)"""
    try:
        if V9_PROMPT_PATH.exists():
            with open(V9_PROMPT_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                import datetime
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] v9.1 prompts loaded from disk")
                return data
    except Exception as e:
        print(f"[WARN] v9.1 prompts load failed: {e}")
    return None


# v10.2 프롬프트 경로 (배포용 - prompts 폴더)
V10_PROMPT_PATH = BASE_DIR / "prompts" / "v10.2_parallel.yaml"


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


def load_prompts_by_variant(variant: Optional[str] = None):
    """variant에 따라 다른 프롬프트 로드 (v4.0/v4.1 분기)

    Args:
        variant: "v4.0" (소프트 유도), "v4.1" (빠른 후킹), None (기본 v3.0)

    Returns:
        프롬프트 데이터 (dict) 또는 None
    """
    import datetime
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")

    try:
        # variant에 따라 파일 경로 선택
        if variant == "v4.0":
            yaml_path = BASE_DIR / "prompts" / "v10.0_v4.0.yaml"
            print(f"[{timestamp}] ✅ v4.0 variant selected (소프트 유도)")
        elif variant == "v4.0.1":
            yaml_path = BASE_DIR / "prompts" / "v10.0_v4.0.1.yaml"
            print(f"[{timestamp}] ✅ v4.0.1 variant selected (채팅 UX 최적화)")
        elif variant == "v4.1":
            yaml_path = BASE_DIR / "prompts" / "v10.0_v4.1.yaml"
            print(f"[{timestamp}] ✅ v4.1 variant selected (빠른 후킹)")
        else:
            # None 또는 기타 값이면 기본 v4.0.1 (채팅 UX 최적화)
            yaml_path = BASE_DIR / "prompts" / "v10.0_v4.0.1.yaml"
            print(f"[{timestamp}] ✅ v4.0.1 variant selected (기본 - 채팅 UX 최적화)")

        # 파일 존재 확인 및 로드
        if yaml_path.exists():
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                print(f"[{timestamp}] Prompts loaded from: {yaml_path.name}")
                return data
        else:
            print(f"[{timestamp}] ⚠️  Prompt file not found: {yaml_path}")
            return None

    except Exception as e:
        print(f"[{timestamp}] ❌ Prompt load failed: {e}")
        return None


# 서버 시작 시 확인
if V9_PROMPT_PATH.exists():
    print("[OK] v9.1 prompts file found (will load on each request)")
else:
    print(f"[WARN] v9.1 prompts file not found at {V9_PROMPT_PATH}")

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


# ============ 만세력 API 통합 헬퍼 함수 ============

async def save_to_db(form_data: dict) -> int:
    """
    Supabase에 초기 레코드 저장 (status: "processing")
    Returns: 생성된 순차 ID (SERIAL)
    """
    global db_pool
    if not db_pool:
        raise Exception("DB pool not initialized")

    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            INSERT INTO free_saju_records (status, form_data, saju_data, error)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            "processing",
            json.dumps(form_data),
            None,
            None
        )
        saju_id = result['id']
        print(f"[OK] Saved record to Supabase: ID={saju_id}")
        return saju_id


async def load_from_db(saju_id: int) -> Optional[dict]:
    """Supabase에서 레코드 로드"""
    global db_pool
    if not db_pool:
        raise Exception("DB pool not initialized")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, created_at, status, form_data, saju_data, error
            FROM free_saju_records
            WHERE id = $1
            """,
            saju_id
        )

        if not row:
            return None

        return {
            "id": row['id'],
            "created_at": row['created_at'].isoformat(),
            "status": row['status'],
            "form_data": json.loads(row['form_data']),
            "saju_data": json.loads(row['saju_data']) if row['saju_data'] else None,
            "error": row['error']
        }


async def update_saju_status(saju_id: int, status: str, saju_data: Optional[dict] = None, error: Optional[str] = None):
    """Supabase에서 사주 상태 업데이트"""
    global db_pool
    if not db_pool:
        raise Exception("DB pool not initialized")

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE free_saju_records
            SET status = $1, saju_data = $2, error = $3
            WHERE id = $4
            """,
            status,
            json.dumps(saju_data) if saju_data else None,
            error,
            saju_id
        )
        print(f"[OK] Updated status to '{status}': ID={saju_id}")


async def call_manseryuk_api(
    name: str,
    year: int,
    month: int,
    day: int,
    hour: Optional[int],
    minute: Optional[int],
    gender: str,
    is_lunar: bool,
    mbti: Optional[str],
    birth_place: Optional[str]
) -> dict:
    """만세력 API 호출하여 사주 데이터 계산"""

    payload = {
        "name": name,
        "year": year,
        "month": month,
        "day": day,
        "hour": hour,
        "minute": minute,
        "gender": gender,
        "is_lunar": is_lunar,
        "mbti": mbti,
        "birth_place": birth_place or "미상"
    }

    print(f"[INFO] 만세력 API 호출 시작: {name}, {year}-{month}-{day}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            MANSERYUK_API_URL,
            json=payload
        )
        response.raise_for_status()

        print(f"[OK] 만세력 API 호출 성공: {response.status_code}")
        return response.json()


async def process_saju_calculation(saju_id: int, form_data: dict):
    """백그라운드에서 만세력 API 호출 및 DB 업데이트"""
    try:
        print(f"[BG] 사주 계산 시작: {saju_id}")

        # 1. 만세력 API 호출 (0.6~3.5초 소요)
        manseryuk_response = await call_manseryuk_api(
            name=form_data["name"],
            year=form_data["birth_year"],
            month=form_data["birth_month"],
            day=form_data["birth_day"],
            hour=form_data.get("birth_hour"),
            minute=form_data.get("birth_minute"),
            gender=form_data["gender"],
            is_lunar=form_data.get("is_lunar", False),
            mbti=form_data.get("mbti"),
            birth_place=form_data.get("birth_place", "미상")
        )

        # 2. enrichment 데이터 추출
        saju_data = manseryuk_response.get("enrichment")
        if not saju_data:
            raise ValueError("enrichment 데이터가 없습니다")

        # 3. DB 업데이트 (status: "completed")
        await update_saju_status(saju_id, "completed", saju_data=saju_data)
        print(f"[BG] 사주 계산 완료: {saju_id}")

    except Exception as e:
        # 4. 에러 발생 시 상태 업데이트
        await update_saju_status(saju_id, "error", error=str(e))
        print(f"[ERROR] 만세력 API 호출 실패: {saju_id}, {e}")


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
    variant: Optional[str] = None  # "v4.0" (소프트 유도), "v4.1" (빠른 후킹), None (기본 v3.0)


class FreeSajuCreateRequest(BaseModel):
    """무료 사주 생성 요청 (비동기 만세력 API 통합)"""
    session_id: Optional[str] = None
    name: str
    phone: Optional[str] = None
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: Optional[int] = None
    birth_minute: Optional[int] = None
    gender: str  # "male" or "female"
    is_lunar: bool = False
    mbti: Optional[str] = None
    birth_place: Optional[str] = "미상"
    # UTM 파라미터
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_term: Optional[str] = None
    utm_content: Optional[str] = None
    referred_share_id: Optional[str] = None


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
    return {"status": "ok", "message": "천기문 사주풀이 API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """상세 헬스 체크"""
    return {
        "status": "ok",
        "prompts_loaded": V9_PROMPT_PATH.exists(),
        "default_data_loaded": DEFAULT_SAJU_DATA is not None
    }


@app.post("/full-reading-stream")
async def get_full_reading_stream(request: FullReadingRequest):
    """전체 풀이 - 통합 프롬프트로 8개 섹션을 한번에 생성 (스트리밍)"""
    import datetime

    print("\n" + "="*60)
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] /full-reading-stream 호출")
    print(f"  - user_name: {request.user_name}")
    print("="*60)

    v8_prompts = load_v8_prompts()
    if not v8_prompts:
        raise HTTPException(status_code=500, detail="v9.1 prompts not loaded")

    unified_prompt = v8_prompts.get("unified_prompt", {})
    if not unified_prompt:
        raise HTTPException(status_code=500, detail="unified_prompt not found in yaml")

    # 사주 데이터 검증 (더미 데이터 사용 안 함)
    if not request.saju_data:
        raise HTTPException(status_code=400, detail="saju_data is required")

    saju_data = request.saju_data
    user_name = request.user_name if request.user_name and request.user_name != "사용자" else DEFAULT_USER_NAME

    # 변수 추출
    variables = get_template_variables(saju_data, user_name)
    timestamp = datetime.datetime.now().isoformat()

    # 프롬프트 준비
    system_prompt = unified_prompt.get("system", "") + f"\n\n[Internal timestamp: {timestamp}]"
    user_message = render_template(unified_prompt.get("user_template", ""), variables)

    print(f"[OK] 프롬프트 준비 완료 (system: {len(system_prompt)}자, user: {len(user_message)}자)")

    async def event_generator():
        try:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] LLM 스트리밍 시작...")
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
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 스트리밍 완료")
        except Exception as e:
            print(f"[ERROR] 스트리밍 실패: {str(e)}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())


@app.post("/first-impression-stream")
async def get_first_impression_stream(request: FirstImpressionRequest):
    """첫인상 풀이 - 스트리밍 (레거시 호환)"""
    import datetime

    v8_prompts = load_v8_prompts()
    if not v8_prompts:
        raise HTTPException(status_code=500, detail="v9.1 prompts not loaded")

    # 사주 데이터 검증 (더미 데이터 사용 안 함)
    if not request.saju_data:
        raise HTTPException(status_code=400, detail="saju_data is required")

    saju_data = request.saju_data
    user_name = request.user_name if request.user_name and request.user_name != "사용자" else DEFAULT_USER_NAME

    step_prompt = v8_prompts.get("step_prompts", {}).get("step_2_first_impression", {})
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

    v8_prompts = load_v8_prompts()
    if not v8_prompts:
        raise HTTPException(status_code=500, detail="v9.1 prompts not loaded")

    # 사주 데이터 검증 (더미 데이터 사용 안 함)
    if not request.saju_data:
        raise HTTPException(status_code=400, detail="saju_data is required")

    saju_data = request.saju_data
    user_name = request.user_name if request.user_name and request.user_name != "사용자" else DEFAULT_USER_NAME

    step_prompt = v8_prompts.get("step_prompts", {}).get(request.step_name, {})
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
@app.post("/api/v1/section-stream")  # 별칭 추가 (프론트엔드 호환성)
async def get_section_stream(request: SectionRequest):
    """특정 섹션 풀이 - 스트리밍 (v10.0 병렬 처리용)"""
    import datetime

    print(f"\n{'='*60}")
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] /section-stream 호출: {request.section_name}")
    print(f"  - user_name: {request.user_name}")
    print(f"  - variant: {request.variant if request.variant else 'None (기본 v3.0)'}")
    print('='*60)

    # variant에 따라 프롬프트 로드
    v10_prompts = load_prompts_by_variant(request.variant)
    if not v10_prompts:
        raise HTTPException(status_code=500, detail="prompts not loaded")

    section_prompt = v10_prompts.get("section_prompts", {}).get(request.section_name, {})
    if not section_prompt:
        raise HTTPException(status_code=404, detail=f"section not found: {request.section_name}")

    # 사주 데이터 검증 (더미 데이터 사용 안 함)
    if not request.saju_data:
        raise HTTPException(status_code=400, detail="saju_data is required")

    saju_data = request.saju_data
    user_name = request.user_name if request.user_name and request.user_name != "사용자" else DEFAULT_USER_NAME

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
            full_text = ""  # 전체 텍스트 수집용
            loop = asyncio.get_event_loop()
            stream_iter = iter(llm_client.stream(system_prompt, user_message))

            while True:
                try:
                    chunk = await loop.run_in_executor(None, next, stream_iter)
                    full_text += chunk  # 텍스트 수집
                    yield {"event": "message", "data": json.dumps({"token": chunk})}
                except StopIteration:
                    break

            # done 이벤트 단순화 (클라이언트에서 buffer로 파싱)
            yield {"event": "message", "data": json.dumps({"done": True})}
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 섹션 스트리밍 완료: {request.section_name} ({len(full_text)}자)")
        except Exception as e:
            print(f"[ERROR] 섹션 스트리밍 실패 ({request.section_name}): {str(e)}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())


@app.post("/free-saju/create")  # v3.0 호환 별칭
@app.post("/api/v1/free-saju/create")
async def create_free_saju(
    request: FreeSajuCreateRequest,
    background_tasks: BackgroundTasks
):
    """
    무료 사주 생성 (비동기 방식 - Supabase + 순차 ID)
    - 폼 데이터만 저장하고 즉시 ID 반환 (0.1초)
    - 백그라운드에서 만세력 API 호출 시작
    """
    print(f"\n{'='*60}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] /free-saju/create 호출")
    print(f"  - name: {request.name}")
    print(f"  - birth: {request.birth_year}-{request.birth_month}-{request.birth_day}")
    print('='*60)

    # 1. Supabase에 저장 (순차 ID 자동 생성)
    saju_id = await save_to_db(request.dict())
    print(f"[OK] ID 생성 (SERIAL): {saju_id}")

    # 2. 백그라운드 태스크로 만세력 API 호출
    background_tasks.add_task(
        process_saju_calculation,
        saju_id=saju_id,
        form_data=request.dict()
    )
    print(f"[OK] 백그라운드 태스크 등록: {saju_id}")

    # 3. 즉시 응답 반환 (0.1초 이내)
    return {
        "id": saju_id,
        "redirect_url": f"/result/saju/{saju_id}"
    }


@app.get("/free-saju/{saju_id}")  # v3.0 호환 별칭
@app.get("/api/v1/free-saju/{saju_id}")
async def get_free_saju(saju_id: int):
    """
    무료 사주 조회 (상태 포함 - Supabase)
    - processing: 계산 중
    - completed: 계산 완료
    - error: 에러 발생
    """
    print(f"[INFO] GET /free-saju/{saju_id}")

    # 1. Supabase에서 조회
    record = await load_from_db(saju_id)

    # 2. 존재하지 않으면 404
    if not record:
        raise HTTPException(status_code=404, detail="사주 데이터를 찾을 수 없습니다")

    # 3. 응답 반환 (status에 따라 다른 데이터)
    response = {
        "id": record["id"],
        "status": record["status"],
        "created_at": record["created_at"],
        "user_name": record["form_data"]["name"],
        "saju_data": record.get("saju_data")
    }

    if record["status"] == "error":
        response["error"] = record.get("error", "알 수 없는 오류")

    print(f"[OK] 상태 응답: {record['status']}")
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run("api_server:app", host="0.0.0.0", port=port, reload=True)
