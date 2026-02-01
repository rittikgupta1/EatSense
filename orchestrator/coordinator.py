from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from agents.interpreter import interpret
from agents.clarification import decide_questions
from agents.ingredient import build_ingredients
from agents.recipe import build_recipe
from agents.nutrition import estimate_nutrition
from agents.commerce import commerce_lookup


@dataclass
class CoordinatorState:
    text_prompt: str = ""
    image_meta: Optional[Dict[str, Any]] = None
    image_data_url: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    clarifications: Dict[str, Any] = field(default_factory=dict)
    trace: Dict[str, Any] = field(default_factory=dict)


class Coordinator:
    """Coordinator that routes tasks to agent modules and reconciles outputs."""

    def __init__(self, state: CoordinatorState) -> None:
        self.state = state

    def run_interpreter(self) -> Dict[str, Any]:
        output = interpret(
            text_prompt=self.state.text_prompt,
            image_meta=self.state.image_meta,
            image_data_url=self.state.image_data_url,
        )
        self.state.trace["InterpreterAgent"] = output
        return output

    def run_clarifier(self, interpreter_output: Dict[str, Any]) -> Dict[str, Any]:
        output = decide_questions(interpreter_output, self.state.preferences)
        self.state.trace["ClarificationGatekeeper"] = output
        return output

    def apply_clarifications(self, interpreter_output: Dict[str, Any]) -> Dict[str, Any]:
        answers = self.state.clarifications

        if answers.get("dish_description"):
            interpreter_output = interpret(
                text_prompt=answers["dish_description"],
                image_meta=self.state.image_meta,
                image_data_url=self.state.image_data_url,
            )

        candidates = interpreter_output.get("candidates", [])
        if answers.get("dish_name"):
            dish_name = answers["dish_name"].strip().title()
            candidates = [
                {"dish": dish_name, "confidence": 0.95, "cues": ["user_provided"]},
                {"dish": candidates[0]["dish"] if candidates else "Mixed Dish", "confidence": 0.35, "cues": ["fallback"]},
            ]
            interpreter_output["candidates"] = candidates

        if answers.get("dish_choice"):
            dish_name = answers["dish_choice"].strip().title()
            candidates = [
                {"dish": dish_name, "confidence": 0.95, "cues": ["user_selected"]},
                {"dish": candidates[0]["dish"] if candidates else "Mixed Dish", "confidence": 0.35, "cues": ["fallback"]},
            ]
            interpreter_output["candidates"] = candidates

        self.state.trace["InterpreterAgent"] = interpreter_output
        return interpreter_output

    def build_outputs(self, interpreter_output: Dict[str, Any]) -> Dict[str, Any]:
        servings = self._resolve_servings(interpreter_output)
        variant = self._resolve_variant()
        style = (self.state.preferences.get("style") or "home-style").lower()

        top_dish = interpreter_output.get("candidates", [])[0]["dish"]
        ingredient_output = build_ingredients(top_dish, servings, variant, style)
        recipe_output = build_recipe(ingredient_output, style)
        nutrition_output = estimate_nutrition(ingredient_output)
        commerce_output = commerce_lookup(top_dish)

        self.state.trace.update({
            "IngredientAgent": ingredient_output,
            "RecipeAgent": recipe_output,
            "NutritionAgent": nutrition_output,
            "CommerceAgent": commerce_output,
        })

        return self._compose_output(
            interpreter_output,
            ingredient_output,
            recipe_output,
            nutrition_output,
            commerce_output,
        )

    def _resolve_servings(self, interpreter_output: Dict[str, Any]) -> int:
        answers = self.state.clarifications
        if answers.get("servings"):
            try:
                return max(1, int(answers["servings"]))
            except ValueError:
                pass
        pref = self.state.preferences.get("servings")
        if pref:
            return int(pref)
        return int(interpreter_output.get("servings_guess") or 1)

    def _resolve_variant(self) -> str:
        answers = self.state.clarifications
        if answers.get("diet_conflict"):
            choice = answers["diet_conflict"]
            if choice == "switch to egg":
                return "egg"
            if choice == "switch to chicken":
                return "chicken"
            return "veg"
        if answers.get("variant"):
            return answers["variant"]
        return (self.state.preferences.get("diet") or "veg").lower()

    def _compose_output(
        self,
        interpreter_output: Dict[str, Any],
        ingredient_output: Dict[str, Any],
        recipe_output: Dict[str, Any],
        nutrition_output: Dict[str, Any],
        commerce_output: Dict[str, Any],
    ) -> Dict[str, Any]:
        # Reconcile dish name if recipe mismatches
        top_dish = interpreter_output.get("candidates", [{}])[0].get("dish")
        if top_dish and recipe_output.get("dish") and recipe_output.get("dish") != top_dish:
            recipe_output["dish"] = top_dish

        return {
            "dish": interpreter_output.get("candidates", []),
            "ingredients": ingredient_output,
            "recipe": recipe_output,
            "nutrition": nutrition_output,
            "commerce": commerce_output,
        }
