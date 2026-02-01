from typing import Dict, Any, List

from pydantic import BaseModel

from utils.llm import call_structured


class IngredientItem(BaseModel):
    item: str
    quantity_range: str
    unit: str


class IngredientOutput(BaseModel):
    agent: str = "IngredientAgent"
    dish: str
    servings_assumption: int
    variant: str
    ingredients: List[IngredientItem]


SYSTEM_PROMPT = (
    "You are IngredientAgent for Dishwise. Produce a structured ingredient list "
    "for the dish using total quantities for the given servings. "
    "Provide rough quantity ranges like '120-160' with a unit (g/ml/tbsp). "
    "Include the servings assumption and variant. Keep to 6-12 ingredients."
    "\n\nReturn JSON with this exact shape:\n"
    "{\n"
    "  \"agent\": \"IngredientAgent\",\n"
    "  \"dish\": \"...\",\n"
    "  \"servings_assumption\": 2,\n"
    "  \"variant\": \"standard|veg|egg|chicken|paneer|...\",\n"
    "  \"ingredients\": [\n"
    "    {\"item\": \"...\", \"quantity_range\": \"120-160\", \"unit\": \"g\"}\n"
    "  ]\n"
    "}\n"
)


def build_ingredients(
    dish: str,
    servings: int,
    variant: str,
) -> Dict[str, Any]:
    response = call_structured(
        model_cls=IngredientOutput,
        system_prompt=SYSTEM_PROMPT,
        user_text=f"Dish: {dish}\nServings: {servings}\nVariant: {variant or 'standard'}",
        allow_invalid=True,
    )
    data = response.model_dump() if isinstance(response, IngredientOutput) else (response or {})
    if "servings_assumption" not in data:
        data["servings_assumption"] = servings
    if "variant" not in data:
        data["variant"] = variant or "standard"
    if "dish" not in data:
        data["dish"] = dish
    if "ingredients" not in data and "ingredients_list" in data:
        data["ingredients"] = data.pop("ingredients_list")
    if isinstance(data.get("ingredients"), dict):
        normalized = []
        for key, value in data["ingredients"].items():
            if isinstance(value, dict):
                normalized.append({
                    "item": key,
                    "quantity_range": value.get("quantity") or value.get("quantity_range") or "0-0",
                    "unit": value.get("unit") or "g",
                })
        data["ingredients"] = normalized
    data["agent"] = "IngredientAgent"
    return data
