import streamlit as st
from google import genai

from main import fetch_tiles

DEFAULT_MODEL = "gemini-3-flash-preview"

PRICING = {
    "gemini-3-flash-preview": {"input": 0.5, "output": 3, "thinking": 3, "caching": 0.05},
}


def calculate_cost(usage_metadata, model=DEFAULT_MODEL):
    """Calculate API call cost from usage metadata."""
    return (
        usage_metadata.prompt_token_count * PRICING[model]["input"]
        + usage_metadata.candidates_token_count * PRICING[model]["output"]
        + (usage_metadata.cached_content_token_count or 0) * PRICING[model]["caching"]
        + (usage_metadata.thoughts_token_count or 0) * PRICING[model]["thinking"]
    ) / 1e6

st.set_page_config(page_title="TE Tile Analyzer", layout="wide")
st.title("TE 圖表摘要二創")

# --- System prompt ---
system_prompt = st.text_area(
    "調整 SYSTEM PROMPT",
    value='''Please rewrite the following paragraph into a professional institutional-level financial research report style in English (maximum 100 words).

Requirements:

Fully reconstruct and substantially rephrase the content to ensure clear differentiation from the original wording and sentence structure.

Do NOT replicate phrases, sentence patterns, or sequencing from the source text.

Preserve all key data points, figures, and analytical logic.

Structure the output strictly in three parts:

Headline Data

Subindex / Components

Reasons / Insights

Emphasize quantitative data and component breakdowns.

Highlight the primary drivers behind the changes.

Do NOT include any third-party forecasts or external projections.

Maintain a formal, sell-side macro research tone (institutional, analytical, and precise).

Improve logical clarity where necessary without adding new speculation.

Avoid informal language.

Output only the rewritten version.'''.replace("\n\n", "\n"),
    height=400,
)

# --- Fetch tiles on first load ---
if "tiles" not in st.session_state:
    with st.spinner("讀取 TE 首頁目前六個方塊文字..."):
        try:
            st.session_state.tiles = fetch_tiles()
        except Exception as e:
            st.error(f"Failed to fetch tiles: {e}")
            st.stop()

tiles = st.session_state.tiles
if not tiles:
    st.warning("No tiles found.")
    st.stop()

# --- Tile selector ---
tile_titles = [t["title"] for t in tiles]
choice = st.radio("選取 USER PROMPT", tile_titles)
selected = tiles[tile_titles.index(choice)]

# st.subheader("Preview")
# st.markdown(f"**{selected['title']}**")
st.write(selected["summary"])

# --- Gemini ---
if st.button("打 Gemini API", type="primary"):
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

    with st.spinner("等待 API 回應..."):
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
            ),
            contents=selected["summary"],
        )

    st.divider()
    st.markdown(response.text)

    cost = calculate_cost(response.usage_metadata)
    um = response.usage_metadata
    st.caption(
        f"Tokens: {um.prompt_token_count:,} in, {um.candidates_token_count:,} out, "
        f"{um.thoughts_token_count:,} think, {(um.cached_content_token_count or 0):,} cache  \n"
        f"Cost: \\${cost:.4f}"
    )
