"""
Supabase Migration 실행 스크립트
"""
import asyncio
import asyncpg
from pathlib import Path

DATABASE_URL = "postgresql://postgres.jlutbjmjpreauyanjzdd:cjsrlans1234@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres"

async def run_migration():
    """Migration SQL 파일 실행"""

    # SQL 파일 읽기
    sql_file = Path("supabase/migrations/20260113_free_saju_records.sql")

    if not sql_file.exists():
        print(f"❌ SQL 파일을 찾을 수 없습니다: {sql_file}")
        return

    with open(sql_file, "r", encoding="utf-8") as f:
        sql = f.read()

    print("[INFO] SQL file loaded")
    print(f"   File: {sql_file}")
    print(f"   Size: {len(sql)} bytes\n")

    # Supabase 연결
    print("[INFO] Connecting to Supabase...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("[SUCCESS] Supabase connected\n")
    except Exception as e:
        print(f"[ERROR] Supabase connection failed: {e}")
        return

    try:
        # Migration 실행
        print("[INFO] Running migration...")
        await conn.execute(sql)
        print("[SUCCESS] Migration completed!\n")

        # 테이블 확인
        print("[INFO] Verifying table...")
        result = await conn.fetch("""
            SELECT
                table_name,
                column_name,
                data_type
            FROM information_schema.columns
            WHERE table_name = 'free_saju_records'
            ORDER BY ordinal_position
        """)

        if result:
            print("[SUCCESS] free_saju_records table created:")
            for row in result:
                print(f"   - {row['column_name']}: {row['data_type']}")
        else:
            print("[WARNING] Table not found")

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
    finally:
        await conn.close()
        print("\n[INFO] Supabase connection closed")

if __name__ == "__main__":
    asyncio.run(run_migration())
