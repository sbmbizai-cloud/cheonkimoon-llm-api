"""
Gemini API 호출 클라이언트
"""

import os
import time
import google.generativeai as genai
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
    """Gemini API 클라이언트"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=self.api_key)
        self.model_name = "gemini-3-flash-preview"
        self.max_output_tokens = 8192  # Gemini 권장값
        self.last_response_time = 0.0
        self.last_input_tokens = 0
        self.last_output_tokens = 0

    def call(self, system_prompt: str, user_message: str, conversation_history: list = None) -> str:
        """일반 API 호출"""
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt
            )

            generation_config = genai.types.GenerationConfig(
                max_output_tokens=self.max_output_tokens,
                temperature=1.0
            )

            start_time = time.time()
            response = model.generate_content(
                user_message,
                generation_config=generation_config
            )
            end_time = time.time()

            self.last_response_time = end_time - start_time
            if hasattr(response, 'usage_metadata'):
                self.last_input_tokens = response.usage_metadata.prompt_token_count
                self.last_output_tokens = response.usage_metadata.candidates_token_count

            return response.text

        except Exception as e:
            return f"오류 발생: {str(e)}"

    def stream(self, system_prompt: str, user_message: str, conversation_history: list = None):
        """스트리밍 API 호출 (generator)"""
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt
            )

            generation_config = genai.types.GenerationConfig(
                max_output_tokens=self.max_output_tokens,
                temperature=1.0
            )

            response = model.generate_content(
                user_message,
                generation_config=generation_config,
                stream=True
            )

            for chunk in response:
                if hasattr(chunk, 'text') and chunk.text:
                    yield chunk.text

        except Exception as e:
            yield f"오류 발생: {str(e)}"
