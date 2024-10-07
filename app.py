import records

import streamlit as st
import cv2 as cv
import numpy as np
import pandas as pd

from PIL import Image
from ExtractTable import ExtractTable
from st_aggrid import AgGrid

API = ExtractTable(api_key=st.secrets["API_KEY"])
DB = records.Database(st.secrets["DATABASE_URL"])
TEAMS = [
    "Bad Boys",
    "Brick Bros",
    "Hector's Code",
    "Overpowered",
    "Secret Service",
    "Silver Swishers",
    "Splash Dynasty",
    "The Diddlers",
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
    colored = np.array(img)
    colored = cv.cvtColor(colored, cv.COLOR_BGR2GRAY)

    _, t1 = cv.threshold(colored, 127, 255, cv.THRESH_BINARY_INV)

    made = Image.fromarray(t1)
    path = f"{name}.png"

    made.save(path)
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


def upload(event, game):
    # df = home_grid['data']

    event_id = (
        DB.query(
            """
        SELECT id FROM event WHERE name=:name
        """,
            name=event,
        )
        .first()
        .as_dict()
    )

    home_id = (
        DB.query(
            """
        SELECT id FROM team WHERE name=:name
        """,
            name=game["home"]["team"],
        )
        .first()
        .as_dict()
    )

    away_id = (
        DB.query(
            """
        SELECT id FROM team WHERE name=:name
        """,
            name=game["away"]["team"],
        )
        .first()
        .as_dict()
    )

    tx = DB.transaction()

    DB.query(
        """
        INSERT INTO game(date, stream, home, away, event)
        VALUES (:date, :stream, :home, :away, :event)
        RETURNING id;
    """,
        date=game["date"],
        stream=game["stream"],
        home=home_id,
        away=away_id,
        event=event_id,
    )

    # core, and stats

    tx.commit()


if __name__ == "__main__":
    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    st.header("Welcome! :wave:")

    st.warning(
        """
        ❗Please see the [screenshot guide][1] for information on how to best
        provide images of game boxscores.

        [1]: https://github.com/jdkato/blood-tigers#data-collection
        """
    )

    st.write(
        """
        This app is designed to expedite the process of converting NBA 2K
        boxscores into queryable data structures for use in the [Banshee 2K
        league website][1].

        [1]: https://banshee2k.com
        """
    )
    st.code(API.check_usage())

    st.header("Step 1: Upload a screenshot")

    screenshot = st.file_uploader("Choose a boxscore", type=["png", "jpg", "jpeg"])
    if screenshot:
        st.write(
            """
            After uploading your boxscore image, please edit the tables below
            to fix any OCR mistakes.
            """
        )

        image = Image.open(screenshot)
        image = image.resize([1200, 1200])

        w, h = image.size

        st.header("Step 2: Verify results")

        st.subheader("Game Information")

        game_date = st.date_input("Date")
        game_stream = st.text_input("Stream URL")

        st.subheader("Away Stats")

        away_box = image.crop((400, h / 4.2, 1070, 1.7 * h / 4))
        away = st.selectbox("Assign team", TEAMS, key=1)
        st.image(away_box, use_column_width=True)

        away_df = boxscore(away_box)
        away_grid = AgGrid(away_df, editable=True)

        st.subheader("Home Stats")

        home_box = image.crop((400, h / 1.9, 1070, 2.9 * h / 4))
        home = st.selectbox("Assign team", TEAMS, key=2)
        st.image(home_box, use_column_width=True)

        home_df = boxscore(home_box)
        home_grid = AgGrid(home_df, editable=True)

        st.subheader("Score Breakdown")

        score = {
            "Team": [away, home],
            "1st": [0, 0],
            "2nd": [0, 0],
            "3rd": [0, 0],
            "4th": [0, 0],
            "Final": [0, 0],
        }
        score_grid = AgGrid(pd.DataFrame(score), editable=True)

        st.header("Step 3: Upload results")
        st.info(
            "Results will appear automatically on [banshee2k.com](https://banshee2k.com)."
        )

        events = db.query("SELECT name FROM event").as_dict()

        event = st.selectbox("Choose an event", [e["name"] for e in events])
        game = {
            "home": {"boxscore": home_grid, "team": home},
            "away": {"boxscore": away_grid, "away": away},
            "score": score_grid,
        }

        col1, col2 = st.columns(2)

        date = col1.date_input("Date of game")
        url = col2.text_input("Stream URL")

        game = {
            "home": {"boxscore": home_grid, "team": home},
            "away": {"boxscore": away_grid, "team": away},
            "date": date,
            "stream": url,
        }

        payload = lambda: upload(event, game)
        st.button("Upload results", on_click=payload)
