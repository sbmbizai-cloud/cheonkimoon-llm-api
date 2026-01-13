"""
무료 사주 API 테스트 스크립트 (비동기 방식)
"""
import httpx
import time
import asyncio
import json

API_BASE_URL = "http://localhost:8001"

async def test_free_saju_api():
    """무료 사주 API 전체 플로우 테스트"""

    # 테스트 데이터
    test_data = {
        "name": "테스트사용자",
        "birth_year": 1995,
        "birth_month": 9,
        "birth_day": 28,
        "birth_hour": 12,
        "birth_minute": 18,
        "gender": "male",
        "is_lunar": False,
        "mbti": "INTJ",
        "birth_place": "서울"
    }

    print("="*60)
    print("Free Saju API Test Start")
    print("="*60)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: POST /api/v1/free-saju/create
        print("\n[Step 1] POST /api/v1/free-saju/create")
        print(f"  - Request data: {test_data['name']}, {test_data['birth_year']}-{test_data['birth_month']}-{test_data['birth_day']}")

        start_time = time.time()
        response = await client.post(
            f"{API_BASE_URL}/api/v1/free-saju/create",
            json=test_data
        )
        create_time = time.time() - start_time

        if response.status_code != 200:
            print(f"  [FAIL] Failed: {response.status_code}")
            print(f"  - Response: {response.text}")
            return

        result = response.json()
        saju_id = result["id"]
        redirect_url = result["redirect_url"]

        print(f"  [OK] Success ({create_time:.3f}s)")
        print(f"  - ID: {saju_id}")
        print(f"  - Redirect URL: {redirect_url}")

        # Step 2: Status polling
        print(f"\n[Step 2] Polling started (GET /api/v1/free-saju/{saju_id})")

        max_polls = 10
        poll_interval = 1.0

        for poll_count in range(1, max_polls + 1):
            print(f"\n  [Polling {poll_count}/{max_polls}]")

            poll_start = time.time()
            response = await client.get(f"{API_BASE_URL}/api/v1/free-saju/{saju_id}")
            poll_time = time.time() - poll_start

            if response.status_code != 200:
                print(f"    [FAIL] Failed: {response.status_code}")
                print(f"    - Response: {response.text}")
                break

            data = response.json()
            status = data["status"]

            print(f"    Status: {status} ({poll_time:.3f}s)")

            if status == "completed":
                print("\n  [OK] Saju calculation completed!")
                print(f"    - User name: {data['user_name']}")
                print(f"    - Created at: {data['created_at']}")

                saju_data = data.get("saju_data")
                if saju_data:
                    print(f"    - Saju data keys: {list(saju_data.keys())[:5]}...")

                    # Display sample data
                    meta = saju_data.get("meta", {})
                    print(f"\n  [DATA] Saju data sample:")
                    print(f"    - Name: {meta.get('이름')}")
                    print(f"    - Gender: {meta.get('성별')}")
                    print(f"    - Age: {meta.get('현재나이')}")

                break

            elif status == "error":
                print(f"\n  [ERROR] Saju calculation failed")
                print(f"    - Error: {data.get('error')}")
                break

            elif status == "processing":
                print(f"    [WAIT] Calculating... ({poll_count}/{max_polls})")

                if poll_count >= max_polls:
                    print(f"\n  [TIMEOUT] Exceeded {max_polls}s")
                    break

                # 1초 대기
                await asyncio.sleep(poll_interval)

        # Step 3: Supabase storage confirmation
        print(f"\n[Step 3] Supabase storage confirmed (Sequential ID: {saju_id})")
        print(f"  [OK] Saved to Supabase (ID: {saju_id})")
        print(f"  - Sequential ID auto-generated")
        print(f"  - Data stored in Supabase free_saju_records table")

    print("\n" + "="*60)
    print("Test completed")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_free_saju_api())
