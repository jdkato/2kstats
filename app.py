import records

import streamlit as st
import cv2 as cv
import numpy as np
import pandas as pd

from PIL import Image
from ExtractTable import ExtractTable

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


@st.cache_data
def to_df(img, cols=[]):
    path = invert(img, "temp")
    data = API.process_file(filepath=path, output_format="df")

    df = data[0]
    if cols:
        df.columns = cols

    return df


def boxscore(img):
    df = to_df(img)

    if df.shape[1] == 12:
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
            "FTM/FTA",
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
            "FTM/FTA",
        ]
        df["PTS"] = df["PTS"].str.replace(r"[A-D][+-]?", "", regex=True)

    return df


def check_data(df):
    """Returns `True` if the data is in the correct format."""

    # Check for the correct number of columns
    if df.shape[1] != 11:
        st.error("Incorrect number of columns")

    # Check that the gamertag exists in the database
    gamertags = DB.query("SELECT DISTINCT name FROM player").as_dict()
    gamertags = [g["name"] for g in gamertags]

    for gamertag in df["Gamertag"]:
        if gamertag not in gamertags:
            st.warning(f"Gamertag '{gamertag}' not found in database.")

    # Check that fractional columns are in the correct format:
    for name in ["FGM/FGA", "3PM/3PA", "FTM/FTA"]:
        for value in df[name]:
            if not value.count("/"):
                st.error(f"Column '{name}' must be in the format 'X/Y'; got '{value}'.")
            x, y = value.split("/")
            if not x.isdigit() or not y.isdigit():
                st.error(f"Column '{name}' must be digits; got '{value}'.")
            if int(x) > int(y):
                st.error(f"Column '{name}' must be X > Y; got '{value}'.")


def upload(game, event):
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
    # st.set_page_config(layout="wide")

    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    st.header("Welcome! :wave:")

    st.warning(
        """
        :exclamation: Please see the [screenshot guide][1] for information on how to best
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
    if screenshot and check_password():
        image = Image.open(screenshot)
        image = image.resize([1200, 1200])

        w, h = image.size

        st.header("Step 2: Verify results")

        st.subheader("Away Stats")

        away_box = image.crop((400, h / 5.0, 1100, 1.7 * h / 4))
        away = st.selectbox("Assign team", TEAMS, key=1)
        st.image(away_box, use_column_width=True)

        away_df = boxscore(away_box)
        # Remove first row
        away_df = away_df.iloc[1:]

        away_grid = st.data_editor(
            away_df,
            use_container_width=True,
            hide_index=True,
            on_change=st.rerun,
        )

        check_data(away_grid)

        st.subheader("Home Stats")

        home_box = image.crop((400, h / 2.05, 1100, 2.9 * h / 4))
        home = st.selectbox("Assign team", TEAMS, key=2)
        st.image(home_box, use_column_width=True)

        home_df = boxscore(home_box)
        # Remove first row
        home_df = home_df.iloc[1:]

        home_grid = st.data_editor(
            home_df, use_container_width=True, hide_index=True, on_change=st.rerun
        )

        check_data(home_grid)

        st.subheader("Score Breakdown")

        score = {
            "Team": [away, home],
            "1st": [0, 0],
            "2nd": [0, 0],
            "3rd": [0, 0],
            "4th": [0, 0],
            "Final": [0, 0],
        }

        score_box = image.crop((85, h / 2.9, 330, 2.35 * h / 4))
        st.image(score_box, use_column_width=False)

        score_grid = st.data_editor(
            pd.DataFrame(score), use_container_width=True, hide_index=True
        )

        st.header("Step 3: Upload results")
        st.info(
            """
            :exclamation: [banshee2k.com](https://banshee2k.com) will update
            automatically within a few minutes of uploading.
            """
        )

        events = DB.query("SELECT name FROM event").as_dict()
        events = [e["name"] for e in events]

        event = st.selectbox("Choose an event", reversed(events))

        col1, col2 = st.columns(2)

        game_date = col1.date_input("Date of game")
        game_stream = col2.text_input("Stream URL")

        game = {
            "home": {"boxscore": home_grid, "team": home},
            "away": {"boxscore": away_grid, "away": away},
            "score": score_grid,
        }

        game = {
            "home": {"boxscore": home_grid, "team": home},
            "away": {"boxscore": away_grid, "team": away},
            "date": game_date,
            "stream": game_stream,
        }

        payload = lambda: upload(game, event)
        st.button("Upload results", on_click=payload)
