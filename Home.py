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


def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["PASS"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct.
        return True


def invert(img, name):
    path = f"{name}.png"
    img.save(path)
    return path


@st.cache(allow_output_mutation=True)
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


def upload(game_type, home, away):
    pass


if __name__ == "__main__":
    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    st.warning(
        """
    ❗Please see the [screenshot guide][1] for information on how to best provide images of game boxscores.

    [1]: https://github.com/jdkato/blood-tigers#data-collection
    """
    )

    st.header("Welcome! :wave:")
    st.write(
        """
        This app is designed to expedite the process of converting NBA2K
        boxscores into queryable data structures, making it ideal for Pro-Am
        leagues or other stat-tracking websites.
        """
    )
    st.code(API.check_usage())

    st.header("Step 1: Upload a screenshot")

    col1, col2 = st.columns(2)

    game_type = col1.radio(
        "Game type", ["Pre Season", "Regular Season", "Post Season"], index=1
    )
    season = col2.number_input("Season", 1, 10)

    screenshot = st.file_uploader("Choose a boxscore", type=["png", "jpg", "jpeg"])
    if screenshot and check_password():
        st.write(
            """
            After uploading your boxscore image, edit the tables below to fix
            any OCR mistakes.
            """
        )

        image = Image.open(screenshot)
        image = image.resize([1200, 1200])

        w, h = image.size

        st.header("Step 2: Verify results")

        tab1, tab2 = st.tabs(["Home", "Away"])

        home_box = image.crop((400, h / 4.2, 1070, 1.7 * h / 4))
        home = tab1.selectbox("Assign team", TEAMS, key=1)
        tab1.image(home_box, use_column_width=True)

        home_df = boxscore(home_box)
        with tab1:
            home_grid = AgGrid(home_df, editable=True)

        away_box = image.crop((400, h / 1.9, 1070, 2.9 * h / 4))
        away = tab2.selectbox("Assign team", TEAMS, key=2)
        tab2.image(away_box, use_column_width=True)

        away_df = boxscore(away_box)
        with tab2:
            away_grid = AgGrid(away_df, editable=True)

        st.header("Step 3: Upload results")
        st.info(
            "Results will appear automatically on [banshee2k.gg](https://banshee2k.gg)."
        )

        payload = lambda: upload(game_type, home_grid, away_grid)
        st.button("Upload results", on_click=payload)
