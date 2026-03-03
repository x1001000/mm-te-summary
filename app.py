import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import streamlit as st
from google import genai

FEED_URL = "https://x1001000.github.io/mm-te-summary/feed.xml"


def fetch_tiles_from_feed() -> tuple[list[dict[str, str]], str]:
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        xml_data = resp.read().decode()
    root = ET.fromstring(xml_data)
    raw = root.findtext(".//lastBuildDate", "")
    if raw:
        taipei = timezone(timedelta(hours=8))
        dt = parsedate_to_datetime(raw).astimezone(taipei)
        last_build = f"台北時間 {dt:%Y-%m-%d %H:%M:%S} 更新"
    else:
        last_build = ""
    tiles = []
    for item in root.findall(".//item"):
        title = item.findtext("title", "")
        summary = item.findtext("description", "")
        if title:
            tiles.append({"title": title, "summary": summary})
    return tiles, last_build

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
st.title("TE 圖表摘要，二創提示詞測試工具")

# --- System prompt ---
system_prompt = st.text_area(
    "調整 SYSTEM PROMPT",
    value='''Please rewrite the following paragraph into a professional institutional-level financial research report style in Traditional Chinese (maximum 100 words).
Requirements:
Fully reconstruct and substantially rephrase the content to ensure clear differentiation from the original wording and sentence structure.
Do NOT replicate phrases, sentence patterns, or sequencing from the source text.
Preserve all key data points, figures, and analytical logic.
Structure the output strictly in 1 paragraph with below items:
1.Headline Data
2.Subindex / Components
3.Reasons / Insights
Emphasize quantitative data and component breakdowns.
Highlight the primary drivers behind the changes.
Do NOT include any third-party forecasts or external projections.
Maintain a formal, sell-side macro research tone (institutional, analytical, and precise).
Improve logical clarity where necessary without adding new speculation.
Avoid informal language.
Output only the rewritten version.''',
    height=400,
)

# --- Fetch tiles on first load ---
if "tiles" not in st.session_state:
    with st.spinner("讀取 TE 首頁最近一小時內更新的六個方塊文字..."):
        try:
            st.session_state.tiles, st.session_state.last_build = fetch_tiles_from_feed()
        except Exception as e:
            st.error(f"Failed to fetch tiles: {e}")
            st.stop()

tiles = st.session_state.tiles
if not tiles:
    st.warning("No tiles found.")
    st.stop()

# --- Tile selector ---
tile_titles = [t["title"] for t in tiles]
choice = st.radio(f"選取 USER PROMPT（[TE 首頁 ](https://tradingeconomics.com)的六個方塊為例，{st.session_state.last_build}）", tile_titles)
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
