-- ============================================
-- 무료 사주 결과 저장 테이블
-- ============================================
-- 작성일: 2026-01-13
-- 목적: 무료 랜딩페이지에서 생성된 사주 결과를 저장
-- ============================================

CREATE TABLE IF NOT EXISTS free_saju_records (
    id SERIAL PRIMARY KEY,                      -- 순차 ID (자동 생성)
    created_at TIMESTAMPTZ DEFAULT NOW(),       -- 생성 시각
    status TEXT NOT NULL DEFAULT 'processing',  -- processing, completed, error

    -- 폼 입력 데이터 (JSONB)
    form_data JSONB NOT NULL,

    -- 계산된 사주 데이터 (JSONB)
    saju_data JSONB,

    -- 에러 메시지
    error TEXT
);

-- 인덱스 추가 (성능 최적화)
CREATE INDEX IF NOT EXISTS idx_free_saju_status ON free_saju_records(status);
CREATE INDEX IF NOT EXISTS idx_free_saju_created_at ON free_saju_records(created_at DESC);

-- 코멘트 추가
COMMENT ON TABLE free_saju_records IS '무료 사주 결과 저장 테이블 (천기문 LLM 챗봇)';
COMMENT ON COLUMN free_saju_records.id IS '순차 ID (자동 생성, 1부터 시작)';
COMMENT ON COLUMN free_saju_records.status IS '처리 상태: processing(계산중), completed(완료), error(에러)';
COMMENT ON COLUMN free_saju_records.form_data IS '사용자 입력 폼 데이터 (name, birth_year, gender 등)';
COMMENT ON COLUMN free_saju_records.saju_data IS '만세력 API에서 계산된 사주 데이터 (enrichment)';
COMMENT ON COLUMN free_saju_records.error IS '에러 발생 시 에러 메시지';
