import streamlit as st
import cv2 as cv
import numpy as np

from PIL import Image
from ExtractTable import ExtractTable
from st_aggrid import AgGrid


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

    boxscore = st.file_uploader("Choose a boxscore", type=["png", "jpg", "jpeg"])
    if boxscore:
        image = Image.open(boxscore)
        image = image.resize([1200, 1200])

        width, height = image.size

        left = 400
        top = height / 4.2
        right = 1070
        bottom = 1.7 * height / 4

        final = image.crop((left, top, right, bottom))

        colored = np.array(final)
        colored = cv.cvtColor(colored, cv.COLOR_BGR2GRAY)

        ret, t1 = cv.threshold(colored, 127, 255, cv.THRESH_BINARY_INV)

        img = Image.fromarray(t1)
        img.save("out.png")

        st.image(img)

        et_sess = ExtractTable(api_key=st.secrets["API_KEY"])

        table_data = et_sess.process_file(filepath="out.png", output_format="df")

        df = table_data[0]
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
        df['Gamertag'] = df['Gamertag'].str.lstrip("*")

        grid = AgGrid(df, editable=True)
