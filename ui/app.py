import base64
import io
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

import streamlit as st
from dotenv import load_dotenv
from PIL import Image

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


st.set_page_config(page_title="Dishwise", page_icon="🍽️", layout="wide")

st.markdown(
    """
<style>
:root { --border: #e5e7eb; --muted: #6b7280; --bg: #fafafa; }
.block-container { padding-top: 1.5rem; }
.card { border: 1px solid var(--border); border-radius: 16px; padding: 16px; background: white; }
.card-title { font-weight: 600; margin-bottom: 8px; }
.metric-card { border: 1px solid var(--border); border-radius: 14px; padding: 12px; background: #fff; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; background: #f3f4f6; }
.step { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.step-dot { width: 10px; height: 10px; border-radius: 999px; background: #d1d5db; }
.step-dot.active { background: #111827; }
.step-dot.done { background: #10b981; }
.step-label { font-size: 12px; color: var(--muted); }
.copy-btn { border: 1px solid var(--border); padding: 6px 10px; border-radius: 8px; background: #fff; cursor: pointer; font-size: 12px; }
""",
    unsafe_allow_html=True,
)


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
if "input_text" not in st.session_state:
    st.session_state.input_text = ""
if "diet" not in st.session_state:
    st.session_state.diet = "Veg"
if "servings" not in st.session_state:
    st.session_state.servings = 1
if "style" not in st.session_state:
    st.session_state.style = "Home-style"


def reset_state() -> None:
    st.session_state.trace = {}
    st.session_state.final = None
    st.session_state.clarification = None
    st.session_state.image_meta = None
    st.session_state.image_data_url = None
    st.session_state.input_text = ""
    st.session_state.diet = "Veg"
    st.session_state.servings = 1
    st.session_state.style = "Home-style"


def load_example() -> None:
    st.session_state.input_text = "paneer butter masala, 2 servings"
    st.session_state.image_meta = None
    st.session_state.image_data_url = None


def copy_button(label: str, text: str) -> None:
    safe_text = text.replace("\\", "\\\\").replace("`", "\\`")
    st.components.v1.html(
        f"""
        <button class="copy-btn" onclick="navigator.clipboard.writeText(`{safe_text}`)">{label}</button>
        """,
        height=32,
    )


def data_url_to_image(data_url: str) -> Optional[Image.Image]:
    if not data_url.startswith("data:image"):
        return None
    try:
        header, b64 = data_url.split(",", 1)
        data = base64.b64decode(b64)
        return Image.open(io.BytesIO(data))
    except Exception:
        return None


def render_stepper(stage: int) -> None:
    steps = ["Identify", "Clarify", "Ingredients", "Nutrition", "Recipe"]
    cols = st.columns(len(steps))
    for idx, label in enumerate(steps):
        status = "done" if idx < stage else "active" if idx == stage else ""
        dot_class = "step-dot"
        if status == "done":
            dot_class += " done"
        elif status == "active":
            dot_class += " active"
        with cols[idx]:
            st.markdown(
                f"<div class='step'><div class='{dot_class}'></div><div class='step-label'>{label}</div></div>",
                unsafe_allow_html=True,
            )


def build_outputs(interpreter_output: Dict[str, Any], servings: int, variant: str) -> None:
    top_dish = interpreter_output.get("candidates", [])[0]["dish"]
    ingredient_output = run_ingredients(top_dish, servings, variant)
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


# Top bar
left_top, right_top = st.columns([3, 1])
with left_top:
    st.markdown("## Dishwise")
with right_top:
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Load Example"):
            load_example()
    with col_b:
        if st.button("Reset"):
            reset_state()

# Main layout
left, right = st.columns([1, 1.3], gap="large")

with left:
    st.markdown("### Input & Controls")
    with st.container():
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<div class='card-title'>Image Upload</div>", unsafe_allow_html=True)
        image_file = st.file_uploader("Drag & drop or click to upload", type=["png", "jpg", "jpeg"], label_visibility="visible")
        paste_data_url = st.text_area("Paste image data URL (optional)", placeholder="data:image/png;base64,...")

        image_meta = None
        image_data_url = None
        if image_file:
            image_result = safe_open_image(image_file)
            if image_result["ok"]:
                st.image(image_result["image"], caption="Preview", use_column_width=True)
                image_meta = image_result["meta"]
                image_data_url = image_result.get("data_url")
            else:
                st.error("Invalid image file. Please upload a valid image.")
        elif paste_data_url:
            pasted = data_url_to_image(paste_data_url.strip())
            if pasted:
                st.image(pasted, caption="Pasted image", use_column_width=True)
                image_meta = {"name": "pasted_image", "size": pasted.size, "mode": pasted.mode}
                image_data_url = paste_data_url.strip()
            else:
                st.warning("Paste a valid data URL starting with data:image...")

        st.markdown("</div>", unsafe_allow_html=True)

    st.write("")

    text_prompt = st.text_input(
        "Text Input (Optional)",
        value=st.session_state.input_text,
        placeholder="Or describe the dish (e.g., ‘paneer butter masala, 1 serving’)"
    )
    st.session_state.input_text = text_prompt

    with st.expander("Preferences"):
        st.radio("Dietary", ["Veg", "Egg", "Non-veg"], key="diet", horizontal=True)
        st.number_input("Servings", min_value=1, max_value=4, step=1, key="servings")
        st.radio("Style", ["Home-style", "Restaurant-style"], key="style", horizontal=True)

    can_analyze = bool(image_file or paste_data_url or text_prompt.strip())
    if st.button("Analyze Dish", disabled=not can_analyze, type="primary"):
        st.session_state.image_meta = image_meta
        st.session_state.image_data_url = image_data_url
        st.session_state.final = None
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
        except Exception as exc:
            st.error(f"Failed to analyze input: {exc}")

with right:
    st.markdown("### Results")

    clarification = st.session_state.clarification
    has_questions = clarification and clarification.get("needs_clarification")

    stage = 0
    if st.session_state.trace.get("InterpreterAgent"):
        stage = 0 if has_questions else 2
    if st.session_state.final:
        stage = 4
    render_stepper(stage)
    st.write("")

    if has_questions:
        @st.dialog("Quick questions before I finalize")
        def clarification_dialog() -> None:
            answers: Dict[str, Any] = {}
            for question in clarification.get("questions", [])[:2]:
                qid = question.get("id")
                qtext = question.get("question")
                options = None
                if qid == "variant":
                    options = ["veg", "egg", "chicken", "paneer"]
                if qid == "servings":
                    options = ["1", "2", "3", "4"]
                if options:
                    answers[qid] = st.selectbox(qtext, options)
                else:
                    answers[qid] = st.text_input(qtext)

            if st.button("Continue", type="primary"):
                interpreter_output = st.session_state.trace.get("InterpreterAgent", {})
                if answers.get("dish_description"):
                    try:
                        interpreter_output = run_interpreter(
                            text_prompt=answers["dish_description"],
                            image_meta=st.session_state.image_meta,
                            image_data_url=st.session_state.image_data_url,
                        )
                    except Exception as exc:
                        st.error(f"Failed to re-interpret description: {exc}")
                        return

                candidates = interpreter_output.get("candidates", [])
                if answers.get("dish_name"):
                    dish_name = answers["dish_name"].strip().title()
                    candidates = [
                        {"dish": dish_name, "confidence": 0.95, "cues": ["user_provided"]},
                        {"dish": candidates[0]["dish"] if candidates else "Mixed Dish", "confidence": 0.35, "cues": ["fallback"]},
                    ]
                    interpreter_output["candidates"] = candidates

                servings = int(answers.get("servings") or st.session_state.servings)
                variant = answers.get("variant") or st.session_state.diet.lower()

                try:
                    st.session_state.trace["InterpreterAgent"] = interpreter_output
                    build_outputs(interpreter_output, servings, variant)
                    st.session_state.clarification = None
                except Exception as exc:
                    st.error(f"Failed to generate outputs: {exc}")

        clarification_dialog()
        st.info("Answer the quick questions to unlock results.")
    else:
        if st.session_state.trace and not st.session_state.final:
            interpreter_output = st.session_state.trace.get("InterpreterAgent", {})
            candidates = interpreter_output.get("candidates", [])
            if candidates:
                servings = st.session_state.servings
                variant = st.session_state.diet.lower()
                try:
                    build_outputs(interpreter_output, servings, variant)
                except Exception as exc:
                    st.error(f"Failed to generate outputs: {exc}")

    final_output = st.session_state.final

    if final_output and not has_questions:
        tabs = st.tabs(["Summary", "Ingredients", "Nutrition", "Recipe"] + (["Find on Swiggy"] if final_output.get("commerce") else []))

        with tabs[0]:
            candidates = final_output["dish"]
            primary = candidates[0]
            secondary = candidates[1] if len(candidates) > 1 else None
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
                st.markdown("<div class='card-title'>Dish</div>", unsafe_allow_html=True)
                st.write(primary["dish"])
                st.markdown(f"<span class='badge'>Confidence {primary['confidence']:.2f}</span>", unsafe_allow_html=True)
                if secondary:
                    st.caption(f"Alt: {secondary['dish']} ({secondary['confidence']:.2f})")
                st.markdown("</div>", unsafe_allow_html=True)
            with col2:
                nutrition = final_output["nutrition"]["per_serving"]
                st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
                st.markdown("<div class='card-title'>Calories</div>", unsafe_allow_html=True)
                st.write(f"{nutrition['calories_kcal']} kcal per serving")
                st.caption(f"Protein {nutrition['protein_g']}g · Carbs {nutrition['carbs_g']}g · Fat {nutrition['fat_g']}g")
                st.markdown("</div>", unsafe_allow_html=True)

            col3, col4 = st.columns(2)
            with col3:
                st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
                st.markdown("<div class='card-title'>Cook Time</div>", unsafe_allow_html=True)
                st.write(f"{final_output['recipe']['time_minutes']} mins")
                st.markdown("</div>", unsafe_allow_html=True)
            with col4:
                st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
                st.markdown("<div class='card-title'>Assumptions</div>", unsafe_allow_html=True)
                st.write(f"Servings: {final_output['ingredients']['servings_assumption']}")
                st.caption(f"Style: {st.session_state.style}")
                st.markdown("</div>", unsafe_allow_html=True)

        with tabs[1]:
            ingredients = final_output["ingredients"]["ingredients"]
            copy_button("Copy ingredients", json.dumps(ingredients, indent=2))
            st.write("")
            for item in ingredients:
                st.markdown(f"- **{item['item']}**: {item['quantity_range']} {item['unit']}")

        with tabs[2]:
            nutrition = final_output["nutrition"]["per_serving"]
            st.markdown("**Macros per serving**")
            st.progress(min(nutrition["protein_g"] / 60, 1.0), text=f"Protein {nutrition['protein_g']}g")
            st.progress(min(nutrition["carbs_g"] / 150, 1.0), text=f"Carbs {nutrition['carbs_g']}g")
            st.progress(min(nutrition["fat_g"] / 70, 1.0), text=f"Fat {nutrition['fat_g']}g")
            copy_button("Copy nutrition", json.dumps(nutrition, indent=2))

        with tabs[3]:
            recipe = final_output["recipe"]
            copy_button("Copy recipe", json.dumps(recipe, indent=2))
            st.write("")
            st.markdown(f"Prep + cook: {recipe['time_minutes']} mins")
            st.markdown("**Difficulty:** Easy")
            for idx, step in enumerate(recipe["steps"], start=1):
                st.markdown(f"{idx}. {step}")

        if len(tabs) > 4:
            with tabs[4]:
                commerce = final_output.get("commerce", {})
                if commerce.get("status") in {"mock", "available"}:
                    for option in commerce.get("results", [])[:3]:
                        st.markdown(f"- **{option['name']}** · {option['price']} · ETA {option['eta_minutes']} min")
                else:
                    st.info("Swiggy lookup unavailable for this dish.")

    with st.expander("Agent Trace (Debug / Judges)"):
        st.code(json.dumps(st.session_state.trace, indent=2), language="json")
