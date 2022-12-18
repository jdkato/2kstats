import streamlit as st
import cv2 as cv
import numpy as np

from PIL import Image
from ExtractTable import ExtractTable
from st_aggrid import AgGrid

API = ExtractTable(api_key=st.secrets["API_KEY"])
TEAMS = [
    "Purple Haze",
    "White Walkers",
    "Midnight Carnival",
    "Powered Gaming Dragons",
    "Vamanos Pest",
    "Denver Defenders",
    "Mississippi Mudkats",
    "Seattle buckets",
]


def invert(img, name):
    path = f"{name}.png"
    img.save(path)
    return path


@st.cache
def to_df(img, cols=[]):
    path = invert(img, "temp")
    data = API.process_file(filepath=path, output_format="df")

    df = data[0]
    if cols:
        df.columns = cols

    return df


def boxscore(img):
    df = to_df(img)

    if df.shape[1] == 11:
        df.columns = [
            "Gamertag",
            "GRD",
            "PTS",
            "REB",
            "AST",
            "STL",
            "BLK",
            "FLS",
            "TO",
            "FGM/FGA",
            "3PM/3PA",
        ]
        df = df.drop("GRD", axis=1)
    elif df.shape[1] == 10:
        # GRD and PTS combined: `D+ 7``
        df.columns = [
            "Gamertag",
            "PTS",
            "REB",
            "AST",
            "STL",
            "BLK",
            "FLS",
            "TO",
            "FGM/FGA",
            "3PM/3PA",
        ]
        df["PTS"] = df["PTS"].str.replace(r"[A-D][+-]?", "", regex=True)

    df["Gamertag"] = df["Gamertag"].str.lstrip("*")
    return df


if __name__ == "__main__":
    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    st.write(
        f"""
        # Welcome! :wave:

        This app is designed to expedite the process of converting NBA2K
        boxscores into queryable data structures, making it ideal for Pro-Am
        leagues or other stat-tracking websites.
        """
    )

    st.warning(
        """
    ❗Please see the [screenshot guide][1] for information on how to best provide images of game boxscores.

    [1]: https://github.com/jdkato/blood-tigers#data-collection
    """
    )

    screenshot = st.file_uploader("Choose a boxscore", type=["png", "jpg", "jpeg"])
    if screenshot:
        st.write(
            """
            After uploading your boxscore image, edit the tables below to fix
            any OCR mistakes.
            """
        )

        image = Image.open(screenshot)
        image = image.resize([1200, 1200])

        w, h = image.size

        st.header("Step 1: Home team")

        home_box = image.crop((400, h / 4.2, 1070, 1.7 * h / 4))
        home = st.selectbox("Assign team", TEAMS, key=1)
        st.image(home_box, use_column_width=True)

        home_df = boxscore(home_box)
        home_grid = AgGrid(home_df, editable=True)

        st.header("Step 2: Away team")

        away_box = image.crop((400, h / 1.9, 1070, 2.9 * h / 4))
        away = st.selectbox("Assign team", TEAMS, key=2)
        st.image(away_box, use_column_width=True)

        away_df = boxscore(away_box)
        away_grid = AgGrid(away_df, editable=True)

        st.header("Step 4: Upload results")
        st.info("Coming soon.")
