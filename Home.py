import streamlit as st
import cv2 as cv
import numpy as np

from PIL import Image
from ExtractTable import ExtractTable
from st_aggrid import AgGrid

API = ExtractTable(api_key=st.secrets["API_KEY"])


def invert(img, name):
    colored = np.array(img)
    colored = cv.cvtColor(colored, cv.COLOR_BGR2GRAY)
    
    _, t1 = cv.threshold(colored, 127, 255, cv.THRESH_BINARY_INV)
    
    made = Image.fromarray(t1)
    path = f"{name}.png"

    made.save(path)
    return path
    
    
def to_df(img, cols):
    path = invert(img, "temp")
    data = API.process_file(filepath=path, output_format="df")

    df = data[0]
    df.columns = cols
    
    return df


if __name__ == "__main__":
    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    st.write(
        f"""
        # Welcome! :wave:

        This app tracks season-by-season stats for the [@2kaveragejoes][1]
        league. The app is open source and maintained by **@The57thPick**.

        [1]: https://discord.gg/2VBR8dQ2gb
        [2]: https://github.com/jdkato/blood-tigers
        """
    )

    st.warning(
        """
    ❗Please see the [screenshot guide][1] for information on how to best provide images of game boxscores.

    [1]: https://github.com/jdkato/blood-tigers#data-collection
    """
    )
    
    et_sess = ExtractTable(api_key=st.secrets["API_KEY"])

    boxscore = st.file_uploader("Choose a boxscore", type=["png", "jpg", "jpeg"])
    if boxscore:
        image = Image.open(boxscore)
        image = image.resize([1200, 1200])

        w, h = image.size
        
        away = image.crop((400, h / 4.2, 1070, 1.7 * h / 4))
        st.image(away)
        
        df = to_df(away, [
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
        ])
        df = df.drop('GRD', axis=1)
        df['Gamertag'] = df['Gamertag'].str.lstrip("*")

        grid = AgGrid(df, editable=True)
