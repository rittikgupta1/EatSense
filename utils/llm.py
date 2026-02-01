import os
from typing import Any, List, Optional, Type, Union

import json

from openai import OpenAI
from pydantic import BaseModel


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY in environment.")
    base_url = os.getenv("OPENAI_BASE_URL")
    timeout = float(os.getenv("OPENAI_TIMEOUT_SECS", "30"))
    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)


def call_structured(
    model_cls: Type[BaseModel],
    system_prompt: str,
    user_text: str,
    image_data_url: Optional[str] = None,
    extra_user_text: Optional[str] = None,
    allow_invalid: bool = False,
) -> Union[BaseModel, dict]:
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    temperature = float(os.getenv("OPENAI_TEMPERATURE", "0"))
    client = _get_client()

    user_content: List[Any] | str
    if image_data_url:
        user_content = [
            {"type": "text", "text": user_text},
            {"type": "image_url", "image_url": {"url": image_data_url}},
        ]
        if extra_user_text:
            user_content.append({"type": "text", "text": extra_user_text})
    else:
        combined = user_text
        if extra_user_text:
            combined = f"{user_text}\n\n{extra_user_text}"
        user_content = combined

    if hasattr(client, "responses"):
        try:
            response = client.responses.parse(
                model=model_name,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                text_format=model_cls,
                temperature=temperature,
            )
            return response.output_parsed
        except Exception:
            if not allow_invalid:
                raise

    json_guard = "\n\nReturn JSON only. The response must be a valid JSON object."
    messages = [
        {"role": "system", "content": system_prompt + json_guard},
        {"role": "user", "content": user_content},
    ]
    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse model JSON output: {exc}") from exc
    try:
        return model_cls.model_validate(data)
    except Exception:
        if allow_invalid:
            return data
        raise
