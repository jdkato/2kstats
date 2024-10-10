import records

import streamlit as st
import cv2 as cv
import numpy as np
import pandas as pd

from PIL import Image
from ExtractTable import ExtractTable

STATUS = """
:exclamation: [banshee2k.com](https://banshee2k.com) will update
automatically within a few minutes of uploading.
"""

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
    """
    game = {
            "home": {"boxscore": home_grid, "team": home},
            "away": {"boxscore": away_grid, "team": away},
            "score": score_grid,
            "date": game_date,
            "stream": game_stream,
        }
    """
    conn = DB.get_connection()
    tx = conn.transaction()

    try:
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

        game_id = (
            DB.query(
                """
            INSERT INTO game(date, stream, home, away, event)
            VALUES (:date, :stream, :home, :away, :event)
            RETURNING id;
        """,
                date=game["date"].strftime("%Y-%m-%d"),
                stream=game["stream"],
                home=home_id["id"],
                away=away_id["id"],
                event=event_id["id"],
            )
            .first()
            .as_dict()
        )

        tx.commit()

        # away team score
        DB.query(
            """
            INSERT INTO score(team, game, \"1st\", \"2nd\", \"3rd\", \"4th\", won)
            VALUES (:team, :game, :first, :second, :third, :fourth, :won)
            RETURNING id;
        """,
            team=away_id["id"],
            game=game_id["id"],
            first=int(game["score"]["1st"][0]),
            second=int(game["score"]["2nd"][0]),
            third=int(game["score"]["3rd"][0]),
            fourth=int(game["score"]["4th"][0]),
            won=bool(game["score"]["Final"][0] > game["score"]["Final"][1]),
        )

        # home team score
        DB.query(
            """
            INSERT INTO score(team, game, \"1st\", \"2nd\", \"3rd\", \"4th\", won)
            VALUES (:team, :game, :first, :second, :third, :fourth, :won)
            RETURNING id;
        """,
            team=home_id["id"],
            game=game_id["id"],
            first=int(game["score"]["1st"][1]),
            second=int(game["score"]["2nd"][1]),
            third=int(game["score"]["3rd"][1]),
            fourth=int(game["score"]["4th"][1]),
            won=bool(game["score"]["Final"][1] > game["score"]["Final"][0]),
        )

        # player stats
        away_stats = game["away"]["boxscore"]
        home_stats = game["home"]["boxscore"]

        gamertags = []
        for i in range(home_stats.shape[0]):
            player = home_stats.iloc[i]
            gamertags.append(player["Gamertag"])

        for i in range(away_stats.shape[0]):
            player = away_stats.iloc[i]
            gamertags.append(player["Gamertag"])

        for gamertag in gamertags:
            player_id = (
                DB.query(
                    """
                SELECT id FROM player WHERE name=:name
                """,
                    name=gamertag,
                )
                .first()
                .as_dict()
            )

            DB.query(
                """
                INSERT INTO stats(game, player, pts, reb, ast, stl, blk, fls, to, fgm, fga, 3pm, 3pa)
                VALUES (:game, :player, :pts, :reb, :ast, :stl, :blk, :fls, :tos, :fgm, :fga, :tpm, :tpa)
                RETURNING id;
            """,
                game=game_id["id"],
                player=player_id["id"],
                pts=int(player["PTS"]),
                reb=int(player["REB"]),
                ast=int(player["AST"]),
                stl=int(player["STL"]),
                blk=int(player["BLK"]),
                fls=int(player["FLS"]),
                tos=int(player["TO"]),
                fgm=int(player["FGM/FGA"].split("/")[0]),
                fga=int(player["FGM/FGA"].split("/")[1]),
                tpm=int(player["3PM/3PA"].split("/")[0]),
                tpa=int(player["3PM/3PA"].split("/")[1]),
            )

            tx.commit()
            return True
    except Exception as e:
        print(e)
        tx.rollback()
        return False
    finally:
        conn.close()


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
            pd.DataFrame(score),
            use_container_width=True,
            hide_index=True,
            on_change=None,
        )

        invalid = False
        if home == away:
            st.error("Home and away teams cannot be the same.", icon="🤔")
            invalid = True
        elif score_grid["Final"][0] == score_grid["Final"][1]:
            st.error("Final scores cannot be the same.", icon="🤔")
            invalid = True

        st.header("Step 3: Upload results")
        st.info(STATUS)

        events = DB.query("SELECT name FROM event").as_dict()
        events = [e["name"] for e in events]

        event = st.selectbox("Choose an event", reversed(events))

        col1, col2 = st.columns(2)

        game_date = col1.date_input("Date of game")
        game_stream = col2.text_input("Stream URL")

        game = {
            "home": {"boxscore": home_grid, "team": home},
            "away": {"boxscore": away_grid, "team": away},
            "score": score_grid,
            "date": game_date,
            "stream": game_stream,
        }

        if st.button(
            "Upload results",
            on_click=upload,
            args=(game, event),
            disabled=invalid,
        ):
            st.info("Results uploaded successfully!")
        else:
            st.warning("Please correct the errors above.")
