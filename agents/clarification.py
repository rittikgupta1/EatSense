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
    "If top confidence is low or dish is unknown, ask a question to choose among top candidates. "
    "Do not ask for dish name or servings.\n\n"
    "Return JSON with this exact shape:\n"
    "{\n"
    "  \"agent\": \"ClarificationGatekeeper\",\n"
    "  \"needs_clarification\": true,\n"
    "  \"questions\": [\n"
    "    {\"id\": \"dish_choice|variant|dish_description|diet_conflict\", \"question\": \"...\"}\n"
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
    if "preference" in text or "vegetarian" in text:
        return "diet_conflict"
    if "which" in text and "dish" in text:
        return "dish_choice"
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


def decide_questions(interpreter_output: Dict[str, Any], preferences: Dict[str, Any]) -> Dict[str, Any]:
    response = call_structured(
        model_cls=ClarificationOutput,
        system_prompt=SYSTEM_PROMPT,
        user_text="Interpreter output JSON:\n" + str(interpreter_output),
        allow_invalid=True,
    )

    data = response.model_dump() if isinstance(response, ClarificationOutput) else (response or {})
    questions = _normalize_questions(data.get("questions", []))
    cues = interpreter_output.get("cues", {})
    text_present = cues.get("text_present", False)
    candidates = interpreter_output.get("candidates", [])
    diet_pref = (preferences.get("diet") or "").lower()

    # Never ask for dish name or servings (user provides these).
    questions = [q for q in questions if q.get("id") not in {"servings", "dish_name"}]

    # Diet conflict: user prefers veg but cues/candidates suggest non-veg.
    if diet_pref == "veg":
        variant_cues = cues.get("variant", [])
        nonveg_hit = any(v in {"chicken", "egg"} for v in variant_cues)
        name_hit = any(
            any(x in (c.get("dish", "").lower()) for x in ["chicken", "mutton", "fish", "egg"])
            for c in candidates
        )
        if nonveg_hit or name_hit:
            questions = [{
                "id": "diet_conflict",
                "question": "You selected Veg, but this seems non-veg. Should I keep it vegetarian or switch to non-veg?",
            }]

    if not questions:
        image_quality = cues.get("image_quality")
        if image_quality == "unclear" and not text_present:
            questions = [{
                "id": "dish_description",
                "question": "The image is unclear. Please describe the dish (name or main ingredients).",
            }]
        elif len(candidates) >= 2:
            questions = [{
                "id": "dish_choice",
                "question": "Which dish matches best from the top suggestions?",
            }]
    data["questions"] = questions
    data["needs_clarification"] = len(data["questions"]) > 0
    if "reason" not in data:
        data["reason"] = "auto_normalized"
    data["agent"] = "ClarificationGatekeeper"
    return data
