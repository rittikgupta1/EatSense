from typing import Dict, Any, List

from pydantic import BaseModel

from utils.llm import call_structured


class RecipeOutput(BaseModel):
    agent: str = "RecipeAgent"
    dish: str
    ingredients_used: int
    time_minutes: int
    style: str
    steps: List[str]


SYSTEM_PROMPT = (
    "You are RecipeAgent for Dishwise. Use only the provided ingredient list "
    "to generate a simple recipe. Use the requested style (home-style or restaurant-style). "
    "Provide 4-7 steps and an estimated time in minutes."
    "\n\nReturn JSON with this exact shape:\n"
    "{\n"
    "  \"agent\": \"RecipeAgent\",\n"
    "  \"dish\": \"...\",\n"
    "  \"ingredients_used\": 6,\n"
    "  \"time_minutes\": 25,\n"
    "  \"style\": \"home-style|restaurant-style\",\n"
    "  \"steps\": [\"...\"]\n"
    "}\n"
)


def build_recipe(ingredient_output: Dict[str, Any], style: str) -> Dict[str, Any]:
    dish = ingredient_output.get("dish", "Dish")
    ingredients = ingredient_output.get("ingredients", [])
    response = call_structured(
        model_cls=RecipeOutput,
        system_prompt=SYSTEM_PROMPT,
        user_text=f"Dish: {dish}\nStyle: {style}\nIngredients: {ingredients}",
        allow_invalid=True,
    )
    data = response.model_dump() if isinstance(response, RecipeOutput) else (response or {})
    if "recipe" in data and isinstance(data["recipe"], dict):
        inner = data.pop("recipe")
        data.setdefault("dish", inner.get("name") or dish)
        data.setdefault("steps", inner.get("steps"))
        if "time_minutes" not in data:
            data["time_minutes"] = inner.get("time_minutes") or inner.get("time") or 25
    if "dish" not in data:
        data["dish"] = dish
    if "steps" not in data:
        data["steps"] = []
    if "time_minutes" not in data:
        data["time_minutes"] = 25
    data["ingredients_used"] = len(ingredients)
    data["style"] = style or "home-style"
    data["agent"] = "RecipeAgent"
    return data
