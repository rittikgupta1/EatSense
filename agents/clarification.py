from typing import Dict, Any, List

from pydantic import BaseModel, Field

from utils.llm import call_structured


class ClarificationQuestion(BaseModel):
    id: str
    question: str


class ClarificationOutput(BaseModel):
    agent: str = "ClarificationGatekeeper"
    needs_clarification: bool
    questions: List[ClarificationQuestion]
    reason: str


SYSTEM_PROMPT = (
    "You are ClarificationGatekeeper for Dishwise. Decide if clarification is needed. "
    "Ask at most 2 short questions. "
    "If image quality is unclear and no useful text is provided, ask for a short dish description. "
    "If servings are missing, ask for servings. "
    "If top confidence is low or dish is unknown, ask for dish name. "
    "Do not ask unnecessary questions.\n\n"
    "Return JSON with this exact shape:\n"
    "{\n"
    "  \"agent\": \"ClarificationGatekeeper\",\n"
    "  \"needs_clarification\": true,\n"
    "  \"questions\": [\n"
    "    {\"id\": \"dish_name|servings|variant|dish_description\", \"question\": \"...\"}\n"
    "  ],\n"
    "  \"reason\": \"...\"\n"
    "}\n"
)


def _infer_id(question_text: str) -> str:
    text = question_text.lower()
    if "serving" in text or "portion" in text or "people" in text:
        return "servings"
    if "variant" in text or "veg" in text or "egg" in text or "chicken" in text or "paneer" in text:
        return "variant"
    if "describe" in text or "description" in text or "ingredients" in text:
        return "dish_description"
    return "dish_name"


def _normalize_questions(raw_questions: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for idx, item in enumerate(raw_questions):
        question = item.get("question") if isinstance(item, dict) else None
        if not question:
            continue
        qid = item.get("id") if isinstance(item, dict) else None
        if not qid:
            qid = _infer_id(question)
        normalized.append({"id": qid, "question": question})
        if len(normalized) >= 2:
            break
    return normalized


def decide_questions(interpreter_output: Dict[str, Any]) -> Dict[str, Any]:
    response = call_structured(
        model_cls=ClarificationOutput,
        system_prompt=SYSTEM_PROMPT,
        user_text="Interpreter output JSON:\n" + str(interpreter_output),
        allow_invalid=True,
    )

    data = response.model_dump() if isinstance(response, ClarificationOutput) else (response or {})
    questions = _normalize_questions(data.get("questions", []))
    cues = interpreter_output.get("cues", {})
    if not questions:
        image_quality = cues.get("image_quality")
        text_present = cues.get("text_present", False)
        if image_quality == "unclear" and not text_present:
            questions = [{
                "id": "dish_description",
                "question": "The image is unclear. Please describe the dish (name or main ingredients).",
            }]
    data["questions"] = questions
    data["needs_clarification"] = len(data["questions"]) > 0
    if "reason" not in data:
        data["reason"] = "auto_normalized"
    data["agent"] = "ClarificationGatekeeper"
    return data
