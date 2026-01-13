#!/usr/bin/env python3
"""Gemini 서버 테스트 스크립트"""

import requests
import json

def test_health():
    """헬스 체크"""
    print("=" * 60)
    print("1. 헬스 체크")
    print("=" * 60)
    response = requests.get("http://localhost:8002/")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_streaming():
    """스트리밍 API 테스트"""
    print("=" * 60)
    print("2. 전체 풀이 스트리밍 테스트")
    print("=" * 60)

    url = "http://localhost:8002/full-reading-stream"
    data = {"user_name": "테스트"}

    print(f"Request URL: {url}")
    print(f"Request Data: {data}")
    print()
    print("응답 (처음 500자):")
    print("-" * 60)

    response = requests.post(url, json=data, stream=True)

    char_count = 0
    for line in response.iter_lines():
        if line:
            decoded = line.decode('utf-8')
            print(decoded, end='', flush=True)
            char_count += len(decoded)
            if char_count > 500:
                print("\n\n[... 중략 ...]")
                break

    print("\n" + "=" * 60)
    print("✅ 스트리밍 응답 수신 성공")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_health()
        test_streaming()
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
