from typing import Dict, Any, List

from pydantic import BaseModel

from utils.llm import call_structured


class NutritionPerServing(BaseModel):
    calories_kcal: int
    protein_g: float
    carbs_g: float
    fat_g: float


class NutritionOutput(BaseModel):
    agent: str = "NutritionAgent"
    servings: int
    per_serving: NutritionPerServing
    assumptions: List[str]


SYSTEM_PROMPT = (
    "You are NutritionAgent for Dishwise. Estimate calories and macros per serving "
    "deterministically from the provided ingredient list and servings. "
    "Use the midpoint of each quantity range, assume common nutrition values per 100g, "
    "and compute per-serving totals. Return assumptions explicitly. "
    "No medical advice and no long-term tracking."
    "\n\nReturn JSON with this exact shape:\n"
    "{\n"
    "  \"agent\": \"NutritionAgent\",\n"
    "  \"servings\": 2,\n"
    "  \"per_serving\": {\n"
    "    \"calories_kcal\": 420,\n"
    "    \"protein_g\": 18.0,\n"
    "    \"carbs_g\": 55.0,\n"
    "    \"fat_g\": 12.0\n"
    "  },\n"
    "  \"assumptions\": [\"...\"]\n"
    "}\n"
)


def estimate_nutrition(ingredient_output: Dict[str, Any]) -> Dict[str, Any]:
    response = call_structured(
        model_cls=NutritionOutput,
        system_prompt=SYSTEM_PROMPT,
        user_text=f"Ingredient output JSON:\n{ingredient_output}",
        allow_invalid=True,
    )
    data = response.model_dump() if isinstance(response, NutritionOutput) else (response or {})
    servings = ingredient_output.get("servings_assumption", 1)
    if "servings" not in data:
        data["servings"] = servings
    if "per_serving" not in data:
        per_serving = {}
        if "calories_per_serving" in data:
            per_serving["calories_kcal"] = data.get("calories_per_serving")
        if "protein" in data:
            per_serving["protein_g"] = data.get("protein")
        if "carbs" in data:
            per_serving["carbs_g"] = data.get("carbs")
        if "carbohydrates" in data:
            per_serving["carbs_g"] = data.get("carbohydrates")
        if "fat" in data:
            per_serving["fat_g"] = data.get("fat")
        data["per_serving"] = per_serving
    if not isinstance(data.get("per_serving"), dict):
        data["per_serving"] = {}
    per_serving = data["per_serving"]
    per_serving.setdefault("calories_kcal", 0)
    per_serving.setdefault("protein_g", 0.0)
    per_serving.setdefault("carbs_g", 0.0)
    per_serving.setdefault("fat_g", 0.0)
    if not isinstance(data.get("assumptions"), list):
        data["assumptions"] = [
            "Quantities use midpoint of provided ranges.",
            "Nutrition values are approximations per 100g.",
        ]
    data["agent"] = "NutritionAgent"
    return data
