from typing import Dict, Any, Optional

from agents.interpreter import interpret
from agents.clarification import decide_questions
from agents.ingredient import build_ingredients
from agents.recipe import build_recipe
from agents.nutrition import estimate_nutrition
from agents.commerce import commerce_lookup


def run_interpreter(
    text_prompt: str,
    image_meta: Optional[Dict[str, Any]],
    image_data_url: Optional[str],
) -> Dict[str, Any]:
    return interpret(text_prompt=text_prompt, image_meta=image_meta, image_data_url=image_data_url)


def run_clarifier(interpreter_output: Dict[str, Any], preferences: Dict[str, Any]) -> Dict[str, Any]:
    return decide_questions(interpreter_output, preferences)


def run_ingredients(dish: str, servings: int, variant: str, style: str) -> Dict[str, Any]:
    return build_ingredients(dish=dish, servings=servings, variant=variant, style=style)


def run_recipe(ingredient_output: Dict[str, Any], style: str) -> Dict[str, Any]:
    return build_recipe(ingredient_output=ingredient_output, style=style)


def run_nutrition(ingredient_output: Dict[str, Any]) -> Dict[str, Any]:
    return estimate_nutrition(ingredient_output=ingredient_output)


def run_commerce(dish: str) -> Dict[str, Any]:
    return commerce_lookup(dish)


def compose_output(
    interpreter_output: Dict[str, Any],
    ingredient_output: Dict[str, Any],
    recipe_output: Dict[str, Any],
    nutrition_output: Dict[str, Any],
    commerce_output: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "dish": interpreter_output.get("candidates", []),
        "ingredients": ingredient_output,
        "recipe": recipe_output,
        "nutrition": nutrition_output,
        "commerce": commerce_output,
    }
