from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field

from utils.llm import call_structured


class DishCandidate(BaseModel):
    dish: str
    confidence: float = Field(ge=0, le=1)
    cues: List[str]


class InterpreterCues(BaseModel):
    variant: List[str]
    image_present: bool
    text_present: bool
    image_quality: str = Field(description="clear|unclear|no_image")
    uncertainty_reasons: List[str]


class InterpreterOutput(BaseModel):
    agent: str = "InterpreterAgent"
    input_type: str
    candidates: List[DishCandidate]
    cues: InterpreterCues
    servings_guess: Optional[int]


SYSTEM_PROMPT = (
    "You are InterpreterAgent for Dishwise. Identify the dish from text and/or image. "
    "Return exactly two dish candidates with confidence between 0 and 1. "
    "Also extract variant cues (veg/egg/chicken/paneer) if mentioned, "
    "guess servings if explicitly stated, and assess image quality "
    "(clear, unclear, or no_image). "
    "If unsure, lower confidence and add uncertainty_reasons.\n\n"
    "Return JSON with this exact shape:\n"
    "{\n"
    "  \"agent\": \"InterpreterAgent\",\n"
    "  \"input_type\": \"text|image|image+text\",\n"
    "  \"candidates\": [\n"
    "    {\"dish\": \"...\", \"confidence\": 0.0, \"cues\": [\"...\"]},\n"
    "    {\"dish\": \"...\", \"confidence\": 0.0, \"cues\": [\"...\"]}\n"
    "  ],\n"
    "  \"cues\": {\n"
    "    \"variant\": [\"veg|egg|chicken|paneer\"],\n"
    "    \"image_present\": true,\n"
    "    \"text_present\": true,\n"
    "    \"image_quality\": \"clear|unclear|no_image\",\n"
    "    \"uncertainty_reasons\": [\"...\"]\n"
    "  },\n"
    "  \"servings_guess\": 1\n"
    "}\n"
)


def interpret(
    text_prompt: str,
    image_meta: Optional[Dict[str, Any]] = None,
    image_data_url: Optional[str] = None,
) -> Dict[str, Any]:
    text_prompt = text_prompt or ""
    image_present = bool(image_meta)
    input_type = "image+text" if image_present and text_prompt.strip() else "image" if image_present else "text"

    extra_text = None
    if image_meta:
        extra_text = f"Image metadata: filename={image_meta.get('name')}, size={image_meta.get('size')}, mode={image_meta.get('mode')}"

    response = call_structured(
        model_cls=InterpreterOutput,
        system_prompt=SYSTEM_PROMPT,
        user_text=f"Input type: {input_type}\nUser text: {text_prompt or 'N/A'}",
        image_data_url=image_data_url,
        extra_user_text=extra_text,
    )
    data = response.model_dump()
    if "candidates" not in data and "dish_candidates" in data:
        data["candidates"] = data.pop("dish_candidates")
    if "input_type" not in data:
        data["input_type"] = input_type
    if "cues" not in data:
        cues = {
            "variant": [],
            "image_present": image_present,
            "text_present": bool(text_prompt.strip()),
            "image_quality": "no_image" if not image_present else "unclear",
            "uncertainty_reasons": ["missing_cues"],
        }
        data["cues"] = cues
    if "servings_guess" not in data:
        data["servings_guess"] = None
    data["candidates"] = (data.get("candidates") or [])[:2]
    return data
