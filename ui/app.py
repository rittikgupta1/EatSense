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


# -----------------------------
# Page + light UI styling
# -----------------------------
st.set_page_config(page_title="EatSense", page_icon="🍽️", layout="centered")

st.markdown(
    """
<style>
:root{
  --border:#e5e7eb; --muted:#6b7280; --text:#111827;
  --accent:#2f7d32; --accent-soft:#e9f4ea; --bg:#fafafa;
}
.block-container { padding-top: 1.25rem; }
.hr { height:1px; background: var(--border); margin: 0.75rem 0 1rem 0; }

.section-bar{
  border:1px solid var(--border);
  border-radius: 14px;
  padding: 12px 14px;
  background: white;
}
.section-title{
  font-weight: 650;
  color: var(--text);
  font-size: 13px;
  margin-bottom: 10px;
  display:flex; align-items:center; gap:8px;
}
.badge{
  display:inline-block;
  padding:2px 10px;
  border-radius:999px;
  font-size:12px;
  background:#f3f4f6;
  color: var(--text);
}

.stepper{
  display:flex;
  gap: 10px;
  align-items:center;
  flex-wrap: wrap;
}
.step{
  display:flex;
  align-items:center;
  gap:6px;
  padding:6px 10px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: white;
  font-size: 12px;
  color: var(--muted);
}
.dot{
  width: 8px; height: 8px; border-radius: 999px;
  background: #d1d5db;
}
.step.active { border-color: #111827; color: var(--text); }
.step.active .dot{ background:#111827; }
.step.done { border-color: #10b981; color: #065f46; background: #ecfdf5; }
.step.done .dot{ background:#10b981; }
</style>
""",
    unsafe_allow_html=True,
)


# -----------------------------
# Session state
# -----------------------------
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

# Preferences (new)
if "diet" not in st.session_state:
    st.session_state.diet = "Veg"
if "servings" not in st.session_state:
    st.session_state.servings = 1
if "style" not in st.session_state:
    st.session_state.style = "Home-style"


# -----------------------------
# Helpers
# -----------------------------
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
    # 0 Identify, 1 Clarify, 2 Ingredients, 3 Nutrition, 4 Recipe, 5 Swiggy
    steps = ["Identify", "Clarify", "Ingredients", "Nutrition", "Recipe", "Commerce"]
    html = ["<div class='stepper'>"]
    for i, s in enumerate(steps):
        cls = "step"
        if i < stage:
            cls += " done"
        elif i == stage:
            cls += " active"
        html.append(f"<div class='{cls}'><span class='dot'></span><span>{s}</span></div>")
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def build_outputs(interpreter_output: Dict[str, Any], servings: int, variant: str, style: str) -> None:
    top_dish = interpreter_output.get("candidates", [])[0]["dish"]

    ingredient_output = run_ingredients(top_dish, servings, variant, style)
    recipe_output = run_recipe(ingredient_output, style)
    nutrition_output = run_nutrition(ingredient_output)
    commerce_output = run_commerce(top_dish)

    st.session_state.trace.update(
        {
            "IngredientAgent": ingredient_output,
            "RecipeAgent": recipe_output,
            "NutritionAgent": nutrition_output,
            "CommerceAgent": commerce_output,
        }
    )

    st.session_state.final = compose_output(
        interpreter_output,
        ingredient_output,
        recipe_output,
        nutrition_output,
        commerce_output,
    )


# -----------------------------
# Header row with logo (new)
# -----------------------------
header_l, header_r = st.columns([1, 4])
with header_l:
    logo_path = ROOT_DIR / "ui" / "logo.png"
    if logo_path.exists():
        st.image(str(logo_path), width=150)
    else:
        st.write("🍽️")

with header_r:
    st.markdown("## EatSense")
    st.caption("Identify dishes, clarify details, and generate ingredients, nutrition, and a recipe.")

st.markdown("<div class='hr'></div>", unsafe_allow_html=True)


# -----------------------------
# Preferences section bar (new)
# -----------------------------
st.markdown(
    "<div class='section-bar'><div class='section-title'>⚙️ Preferences</div>",
    unsafe_allow_html=True,
)
p1, p2, p3 = st.columns([1.2, 1.0, 1.4])
with p1:
    st.radio("Dietary", ["Veg", "Egg", "Non-veg"], key="diet", horizontal=True)
with p2:
    st.number_input("Servings", min_value=1, max_value=6, step=1, key="servings")
with p3:
    st.radio("Style", ["Home-style", "Restaurant-style"], key="style", horizontal=True)
st.markdown("</div>", unsafe_allow_html=True)

st.write("")


# -----------------------------
# Input form (kept layout)
# -----------------------------
with st.form("input_form"):
    image_file = st.file_uploader("Upload a food image (optional)", type=["png", "jpg", "jpeg"])
    text_prompt = st.text_input("Or describe the dish", placeholder="e.g., veg biryani for 2 servings")

    # Optional: paste data-url without changing layout much
    with st.expander("Paste image data URL (optional)"):
        paste_data_url = st.text_area(
            "Paste image data URL",
            placeholder="data:image/png;base64,...",
            label_visibility="collapsed",
        )

    submitted = st.form_submit_button("Analyze", type="primary")


# -----------------------------
# Analyze flow
# -----------------------------
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
    elif paste_data_url and paste_data_url.strip():
        pasted = data_url_to_image(paste_data_url.strip())
        if pasted:
            st.image(pasted, caption="Pasted image", use_column_width=True)
            image_meta = {"name": "pasted_image", "size": pasted.size, "mode": pasted.mode}
            image_data_url = paste_data_url.strip()
        else:
            st.warning("Paste a valid data URL starting with data:image...")

    try:
        interpreter_output = run_interpreter(
            text_prompt=text_prompt or "",
            image_meta=image_meta,
            image_data_url=image_data_url,
        )
        clarifier_output = run_clarifier(
            interpreter_output,
            {"diet": st.session_state.diet, "style": st.session_state.style, "servings": st.session_state.servings},
        )

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


# -----------------------------
# Status bar / stepper (new)
# -----------------------------
clarifier_output = st.session_state.clarification
has_questions = bool(clarifier_output and clarifier_output.get("needs_clarification"))

# stage logic:
# If interpreted but needs clarification -> stage 1
# If final exists -> stage 5 (or 4 if no commerce)
# Else if interpreted -> stage 2 (generating)
stage = 0
if st.session_state.trace.get("InterpreterAgent"):
    stage = 1 if has_questions else 2
if st.session_state.final:
    stage = 5 if (st.session_state.final.get("commerce")) else 4

render_stepper(stage)
st.write("")


# -----------------------------
# Clarification dialog (new)
# -----------------------------
if has_questions:
    def _render_clarification() -> None:
        answers: Dict[str, Any] = {}

        for q in clarifier_output.get("questions", [])[:2]:
            qid = q.get("id")
            qtext = q.get("question", "Clarify:")

            if qid == "variant":
                answers[qid] = st.selectbox(qtext, ["veg", "egg", "chicken", "paneer"])
            elif qid == "servings":
                answers[qid] = st.selectbox(qtext, ["1", "2", "3", "4", "5", "6"])
            elif qid == "dish_choice":
                choices = [c.get("dish") for c in st.session_state.trace.get("InterpreterAgent", {}).get("candidates", []) if c.get("dish")]
                if choices:
                    answers[qid] = st.selectbox(qtext, choices)
                else:
                    answers[qid] = st.text_input(qtext)
            elif qid == "diet_conflict":
                answers[qid] = st.selectbox(qtext, ["keep veg", "switch to egg", "switch to chicken"])
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
                    {
                        "dish": candidates[0]["dish"] if candidates else "Mixed Dish",
                        "confidence": 0.35,
                        "cues": ["fallback"],
                    },
                ]
                interpreter_output["candidates"] = candidates
            if answers.get("dish_choice"):
                dish_name = answers["dish_choice"].strip().title()
                candidates = [
                    {"dish": dish_name, "confidence": 0.95, "cues": ["user_selected"]},
                    {"dish": candidates[0]["dish"] if candidates else "Mixed Dish", "confidence": 0.35, "cues": ["fallback"]},
                ]
                interpreter_output["candidates"] = candidates

            servings = st.session_state.servings
            if answers.get("servings"):
                try:
                    servings = max(1, int(answers["servings"]))
                except ValueError:
                    servings = st.session_state.servings
            else:
                servings = interpreter_output.get("servings_guess") or servings or 1

            variant = (answers.get("variant") or st.session_state.diet).strip().lower()
            if answers.get("diet_conflict"):
                choice = answers["diet_conflict"]
                if choice == "switch to egg":
                    variant = "egg"
                elif choice == "switch to chicken":
                    variant = "chicken"
                else:
                    variant = "veg"

            try:
                st.session_state.trace["InterpreterAgent"] = interpreter_output
                build_outputs(interpreter_output, servings, variant, st.session_state.style)
                st.session_state.clarification = None
            except Exception as exc:
                st.error(f"Failed to generate outputs: {exc}")

    if hasattr(st, "dialog"):
        @st.dialog("Quick questions before I finalize")
        def clarification_dialog() -> None:
            _render_clarification()

        clarification_dialog()
        st.info("Answer the quick questions to unlock results.")
    else:
        st.info("Answer the quick questions to unlock results.")
        _render_clarification()


# -----------------------------
# If no questions, auto-generate outputs (kept behavior)
# -----------------------------
if (not has_questions) and st.session_state.trace and (not st.session_state.final):
    interpreter_output = st.session_state.trace.get("InterpreterAgent", {})
    candidates = interpreter_output.get("candidates", [])
    if candidates:
        # Servings priority: preferences bar -> interpreter guess -> 1
        servings = st.session_state.servings or (interpreter_output.get("servings_guess") or 1)
        top_dish = candidates[0]["dish"]
        try:
            # Variant from preference bar
            variant = st.session_state.diet.lower()
            ingredient_output = run_ingredients(top_dish, servings, variant, st.session_state.style)
            recipe_output = run_recipe(ingredient_output, st.session_state.style)
            nutrition_output = run_nutrition(ingredient_output)
            commerce_output = run_commerce(top_dish)

            st.session_state.trace.update(
                {
                    "IngredientAgent": ingredient_output,
                    "RecipeAgent": recipe_output,
                    "NutritionAgent": nutrition_output,
                    "CommerceAgent": commerce_output,
                }
            )

            st.session_state.final = compose_output(
                interpreter_output,
                ingredient_output,
                recipe_output,
                nutrition_output,
                commerce_output,
            )
        except Exception as exc:
            st.error(f"Failed to generate outputs: {exc}")


# -----------------------------
# Results (kept layout)
# -----------------------------
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
    elif commerce.get("status") in {"disabled", "unavailable", "unauthorized"}:
        st.info(commerce.get("message"))


with st.expander("Agent Trace"):
    st.code(json.dumps(st.session_state.trace, indent=2), language="json")
