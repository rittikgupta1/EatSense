import json
import os
from pathlib import Path
from typing import Dict, Any

import streamlit as st
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

if str(ROOT_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT_DIR))

from orchestrator.pipeline import (
    run_interpreter,
    run_clarifier,
    run_ingredients,
    run_recipe,
    run_nutrition,
    run_commerce,
    compose_output,
)
from utils.io import safe_open_image


st.set_page_config(page_title="Dishwise", page_icon="🍽️", layout="centered")

st.title("Dishwise")
st.write("Identify dishes, clarify details, and generate ingredients, nutrition, and a recipe.")


if "trace" not in st.session_state:
    st.session_state.trace = {}
if "final" not in st.session_state:
    st.session_state.final = None
if "clarification" not in st.session_state:
    st.session_state.clarification = None
if "image_meta" not in st.session_state:
    st.session_state.image_meta = None
if "image_data_url" not in st.session_state:
    st.session_state.image_data_url = None


with st.form("input_form"):
    image_file = st.file_uploader("Upload a food image (optional)", type=["png", "jpg", "jpeg"])
    text_prompt = st.text_input("Or describe the dish", placeholder="e.g., veg biryani for 2 servings")
    submitted = st.form_submit_button("Analyze")

if submitted:
    image_meta = None
    image_data_url = None
    if image_file:
        image_result = safe_open_image(image_file)
        if image_result["ok"]:
            st.image(image_result["image"], caption="Uploaded image", use_column_width=True)
            image_meta = image_result["meta"]
            image_data_url = image_result.get("data_url")
        else:
            st.error("Invalid image file. Please upload a valid image.")
    try:
        interpreter_output = run_interpreter(
            text_prompt=text_prompt or "",
            image_meta=image_meta,
            image_data_url=image_data_url,
        )
        clarifier_output = run_clarifier(interpreter_output)

        st.session_state.trace = {
            "InterpreterAgent": interpreter_output,
            "ClarificationGatekeeper": clarifier_output,
        }
        st.session_state.clarification = clarifier_output
        st.session_state.final = None
        st.session_state.image_meta = image_meta
        st.session_state.image_data_url = image_data_url
    except Exception as exc:
        st.error(f"Failed to analyze input: {exc}")

clarifier_output = st.session_state.clarification

if clarifier_output and clarifier_output.get("needs_clarification"):
    st.subheader("Clarification")
    answers: Dict[str, Any] = {}
    with st.form("clarification_form"):
        for question in clarifier_output.get("questions", []):
            answers[question["id"]] = st.text_input(question["question"], key=question["id"])
        clarified = st.form_submit_button("Submit clarifications")

    if clarified:
        interpreter_output = st.session_state.trace.get("InterpreterAgent", {})
        if answers.get("dish_description"):
            try:
                interpreter_output = run_interpreter(
                    text_prompt=answers["dish_description"],
                    image_meta=st.session_state.image_meta,
                    image_data_url=st.session_state.image_data_url,
                )
                st.session_state.trace["InterpreterAgent"] = interpreter_output
            except Exception as exc:
                st.error(f"Failed to re-interpret description: {exc}")
        candidates = interpreter_output.get("candidates", [])
        if answers.get("dish_name"):
            dish_name = answers["dish_name"].strip().title()
            candidates = [
                {"dish": dish_name, "confidence": 0.95, "cues": ["user_provided"]},
                {"dish": candidates[0]["dish"] if candidates else "Mixed Dish", "confidence": 0.35, "cues": ["fallback"]},
            ]
            interpreter_output["candidates"] = candidates

        servings = interpreter_output.get("servings_guess") or 1
        if answers.get("servings"):
            try:
                servings = max(1, int(answers["servings"]))
            except ValueError:
                servings = 1

        variant = ""
        if answers.get("variant"):
            variant = answers["variant"].strip().lower()

        top_dish = interpreter_output.get("candidates", [])[0]["dish"]
        try:
            ingredient_output = run_ingredients(top_dish, servings, variant)
            recipe_output = run_recipe(ingredient_output)
            nutrition_output = run_nutrition(ingredient_output)
            commerce_output = run_commerce(top_dish)
        except Exception as exc:
            st.error(f"Failed to generate outputs: {exc}")
            ingredient_output = None
            recipe_output = None
            nutrition_output = None
            commerce_output = None

        if ingredient_output and recipe_output and nutrition_output:
            st.session_state.trace.update({
                "InterpreterAgent": interpreter_output,
                "IngredientAgent": ingredient_output,
                "RecipeAgent": recipe_output,
                "NutritionAgent": nutrition_output,
                "CommerceAgent": commerce_output,
            })

            st.session_state.final = compose_output(
                interpreter_output,
                ingredient_output,
                recipe_output,
                nutrition_output,
                commerce_output,
            )

else:
    if st.session_state.trace:
        interpreter_output = st.session_state.trace.get("InterpreterAgent", {})
        candidates = interpreter_output.get("candidates", [])
        if candidates:
            servings = interpreter_output.get("servings_guess") or 1
            top_dish = candidates[0]["dish"]
            try:
                ingredient_output = run_ingredients(top_dish, servings, "")
                recipe_output = run_recipe(ingredient_output)
                nutrition_output = run_nutrition(ingredient_output)
                commerce_output = run_commerce(top_dish)

                st.session_state.trace.update({
                    "IngredientAgent": ingredient_output,
                    "RecipeAgent": recipe_output,
                    "NutritionAgent": nutrition_output,
                    "CommerceAgent": commerce_output,
                })

                st.session_state.final = compose_output(
                    interpreter_output,
                    ingredient_output,
                    recipe_output,
                    nutrition_output,
                    commerce_output,
                )
            except Exception as exc:
                st.error(f"Failed to generate outputs: {exc}")

final_output = st.session_state.final

if final_output:
    st.subheader("Dish Candidates")
    for candidate in final_output["dish"]:
        st.write(f"- {candidate['dish']} (confidence {candidate['confidence']:.2f})")

    st.subheader("Ingredients")
    ingredients = final_output["ingredients"]["ingredients"]
    st.table(ingredients)

    st.subheader("Nutrition per Serving")
    nutrition = final_output["nutrition"]["per_serving"]
    st.write(
        f"Calories: {nutrition['calories_kcal']} kcal | "
        f"Protein: {nutrition['protein_g']} g | "
        f"Carbs: {nutrition['carbs_g']} g | "
        f"Fat: {nutrition['fat_g']} g"
    )
    st.caption("Assumptions: " + "; ".join(final_output["nutrition"].get("assumptions", [])))

    st.subheader("Recipe")
    st.write(f"Estimated time: {final_output['recipe']['time_minutes']} minutes")
    for idx, step in enumerate(final_output["recipe"]["steps"], start=1):
        st.write(f"{idx}. {step}")

    commerce = final_output.get("commerce", {})
    if commerce.get("status") in {"mock", "available"}:
        st.subheader("Commerce Lookup")
        for option in commerce.get("results", [])[:3]:
            st.write(f"- {option['name']} · {option['price']} · ETA {option['eta_minutes']} min")
        if commerce.get("quote"):
            st.caption(f"Estimated total: {commerce['quote'].get('estimated_total')}")
    elif commerce.get("status") in {"disabled", "unavailable"}:
        st.info(commerce.get("message"))

with st.expander("Agent Trace"):
    st.code(json.dumps(st.session_state.trace, indent=2), language="json")
