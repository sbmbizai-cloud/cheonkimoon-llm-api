"""
Railway 배포 API 테스트 (무료 사주)
"""
import httpx
import time
import asyncio

API_BASE_URL = "https://web-production-2d723.up.railway.app"

async def test_railway_free_saju():
    """Railway 배포된 무료 사주 API 테스트"""

    test_data = {
        "name": "Railway테스트",
        "birth_year": 1990,
        "birth_month": 5,
        "birth_day": 15,
        "birth_hour": 10,
        "birth_minute": 30,
        "gender": "female",
        "is_lunar": False,
        "mbti": "ENFP",
        "birth_place": "부산"
    }

    print("="*60)
    print("Railway Free Saju API Test")
    print("="*60)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: POST /api/v1/free-saju/create
        print("\n[Step 1] POST /api/v1/free-saju/create")
        print(f"  - Request: {test_data['name']}, {test_data['birth_year']}-{test_data['birth_month']}-{test_data['birth_day']}")

        start = time.time()
        response = await client.post(
            f"{API_BASE_URL}/api/v1/free-saju/create",
            json=test_data
        )
        elapsed = time.time() - start

        if response.status_code != 200:
            print(f"  [FAIL] {response.status_code}")
            print(f"  Response: {response.text}")
            return

        result = response.json()
        saju_id = result["id"]

        print(f"  [OK] Success ({elapsed:.3f}s)")
        print(f"  - ID: {saju_id}")
        print(f"  - Redirect URL: {result['redirect_url']}")

        # Step 2: Polling
        print(f"\n[Step 2] Polling (GET /api/v1/free-saju/{saju_id})")

        for i in range(1, 11):
            print(f"\n  [Poll {i}/10]")

            start = time.time()
            response = await client.get(f"{API_BASE_URL}/api/v1/free-saju/{saju_id}")
            elapsed = time.time() - start

            if response.status_code != 200:
                print(f"    [FAIL] {response.status_code}")
                break

            data = response.json()
            status = data["status"]

            print(f"    Status: {status} ({elapsed:.3f}s)")

            if status == "completed":
                print("\n  [OK] Calculation completed!")
                print(f"    - User: {data['user_name']}")
                print(f"    - Created: {data['created_at']}")

                if data.get("saju_data"):
                    keys = list(data['saju_data'].keys())
                    print(f"    - Data keys: {keys[:5]}...")

                break

            elif status == "error":
                print(f"\n  [ERROR] {data.get('error')}")
                break

            elif status == "processing":
                print(f"    [WAIT] Calculating...")
                if i < 10:
                    await asyncio.sleep(1.0)

        print("\n" + "="*60)
        print("Railway Test Completed")
        print("="*60)

if __name__ == "__main__":
    asyncio.run(test_railway_free_saju())
