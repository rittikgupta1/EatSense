from typing import Dict, Any, Optional

from orchestrator.coordinator import Coordinator, CoordinatorState


def run_interpreter(
    text_prompt: str,
    image_meta: Optional[Dict[str, Any]],
    image_data_url: Optional[str],
) -> Dict[str, Any]:
    coordinator = Coordinator(
        CoordinatorState(
            text_prompt=text_prompt,
            image_meta=image_meta,
            image_data_url=image_data_url,
        )
    )
    return coordinator.run_interpreter()


def run_clarifier(interpreter_output: Dict[str, Any], preferences: Dict[str, Any]) -> Dict[str, Any]:
    coordinator = Coordinator(CoordinatorState(preferences=preferences))
    return coordinator.run_clarifier(interpreter_output)


def run_ingredients(dish: str, servings: int, variant: str, style: str) -> Dict[str, Any]:
    coordinator = Coordinator(
        CoordinatorState(preferences={"style": style, "servings": servings, "diet": variant})
    )
    interpreter_stub = {"candidates": [{"dish": dish}]}
    return coordinator.build_outputs(interpreter_stub)["ingredients"]


def run_recipe(ingredient_output: Dict[str, Any], style: str) -> Dict[str, Any]:
    coordinator = Coordinator(CoordinatorState(preferences={"style": style}))
    interpreter_stub = {"candidates": [{"dish": ingredient_output.get("dish", "Dish")}]} 
    return coordinator.build_outputs(interpreter_stub)["recipe"]


def run_nutrition(ingredient_output: Dict[str, Any]) -> Dict[str, Any]:
    coordinator = Coordinator(CoordinatorState())
    interpreter_stub = {"candidates": [{"dish": ingredient_output.get("dish", "Dish")}]} 
    return coordinator.build_outputs(interpreter_stub)["nutrition"]


def run_commerce(dish: str) -> Dict[str, Any]:
    coordinator = Coordinator(CoordinatorState())
    interpreter_stub = {"candidates": [{"dish": dish}]}
    return coordinator.build_outputs(interpreter_stub)["commerce"]


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
