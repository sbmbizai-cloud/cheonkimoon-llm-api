"""
Claude API 호출 클라이언트
"""

import os
import time
import anthropic
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Optional

load_dotenv()


@dataclass
class LLMResponse:
    """LLM 응답 + 메타데이터"""
    text: str
    model: str
    response_time: float
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class LLMClient:
    """Claude API 클라이언트"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"
        self.max_tokens = 64000
        self.last_response_time = 0.0
        self.last_input_tokens = 0
        self.last_output_tokens = 0

    def call(self, system_prompt: str, user_message: str, conversation_history: list = None) -> str:
        """일반 API 호출"""
        messages = []
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        try:
            start_time = time.time()
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=messages
            )
            end_time = time.time()

            self.last_response_time = end_time - start_time
            self.last_input_tokens = response.usage.input_tokens
            self.last_output_tokens = response.usage.output_tokens

            return response.content[0].text
        except Exception as e:
            return f"오류 발생: {str(e)}"

    def stream(self, system_prompt: str, user_message: str, conversation_history: list = None):
        """스트리밍 API 호출 (generator)"""
        messages = []
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=messages
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            yield f"오류 발생: {str(e)}"
