import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
from branca.colormap import linear
import plotly.express as px
import io 
import plotly.express as px
from folium import Tooltip

CRIME_URL = "https://raw.githubusercontent.com/PatieCodes/Dashboards/refs/heads/main/communities.data"
NAMES_URL = "https://raw.githubusercontent.com/PatieCodes/Dashboards/refs/heads/main/communities.names"
GEOMAP_URL = "https://raw.githubusercontent.com/PatieCodes/Dashboards/refs/heads/main/gz_2010_us_040_00_500k.json"


import seaborn as sns
import matplotlib.pyplot as plt

# Load Crime Dataset
@st.cache_data
def load_crime_dataset():
    df = pd.read_csv(CRIME_URL, header=None, na_values="?")
    txt = requests.get(NAMES_URL).text.splitlines()
    cols = [line.split()[1].strip() for line in txt if line.startswith("@attribute")]
    if len(cols) == df.shape[1]:
        df.columns = cols
        df.columns = df.columns.str.strip().str.replace(" ", "")
    else:
        st.error(f"Column count mismatch: Data has {df.shape[1]} columns, but found {len(cols)} names")
        st.stop()
    return df

df = load_crime_dataset()


# Load GeoJSON for US states
@st.cache_data
def load_geojson(url):
    resp = requests.get(url)
    resp.raise_for_status()
    geojson = resp.json()
    for feature in geojson["features"]:
        name = feature["properties"]["NAME"].strip()
        feature["properties"]["NAME"] = name
        feature["properties"]["NAME_norm"] = name.lower()
    return geojson

geojson = load_geojson(GEOMAP_URL)


# Map state FIPS → State Names
state_fips_to_name = {
    1: "Alabama", 2: "Alaska", 4: "Arizona", 5: "Arkansas", 6: "California",
    8: "Colorado", 9: "Connecticut", 10: "Delaware", 11: "District of Columbia",
    12: "Florida", 13: "Georgia", 15: "Hawaii", 16: "Idaho", 17: "Illinois",
    18: "Indiana", 19: "Iowa", 20: "Kansas", 21: "Kentucky", 22: "Louisiana",
    23: "Maine", 24: "Maryland", 25: "Massachusetts", 26: "Michigan",
    27: "Minnesota", 28: "Mississippi", 29: "Missouri", 30: "Montana",
    31: "Nebraska", 32: "Nevada", 33: "New Hampshire", 34: "New Jersey",
    35: "New Mexico", 36: "New York", 37: "North Carolina", 38: "North Dakota",
    39: "Ohio", 40: "Oklahoma", 41: "Oregon", 42: "Pennsylvania",
    44: "Rhode Island", 45: "South Carolina", 46: "South Dakota",
    47: "Tennessee", 48: "Texas", 49: "Utah", 50: "Vermont", 51: "Virginia",
    53: "Washington", 54: "West Virginia", 55: "Wisconsin", 56: "Wyoming"
}

df["state_name"] = df.iloc[:, 0].astype(int).map(state_fips_to_name)
df["state_name_norm"] = df["state_name"].str.lower()


# Session state for selected state
if "selected_state" not in st.session_state:
    st.session_state.selected_state = None


# Build Folium Map
violent_col = "ViolentCrimesPerPop"
state_crime = df.groupby("state_name")[violent_col].mean().reset_index()
value_map = state_crime.set_index("state_name")[violent_col].to_dict()
vmin, vmax = state_crime[violent_col].min(), state_crime[violent_col].max()
colormap = linear.Reds_09.scale(vmin, vmax)
colormap.caption = "Avg Violent Crime Rate"

m = folium.Map(location=[39, -98], zoom_start=4, tiles="cartodbpositron")
colormap.add_to(m)

# Style function with highlight for selected state
def style_function(feature):
    name = feature["properties"]["NAME"]
    return {
        "fillOpacity": 0.7 if name == st.session_state.selected_state else 0.4,
        "weight": 1,
        "color": "white",
        "fillColor": colormap(value_map.get(name, 0)) if name != st.session_state.selected_state else "#55AAFF"
    }

# Add GeoJson layers with tooltip
from folium import Tooltip

for feature in geojson["features"]:
    state_name = feature["properties"]["NAME"]
    violent_rate = value_map.get(state_name, 0)
    
    tooltip = Tooltip(f"{state_name}<br>Avg Violent Crime Rate: {violent_rate:.3f}")
    
    folium.GeoJson(
        feature,
        style_function=style_function,
        tooltip=tooltip
    ).add_to(m)


# Capture map click
map_data = st_folium(m, width=1200, height=650, returned_objects=["last_object_clicked"])
if map_data and map_data.get("last_object_clicked"):
    last_clicked = map_data["last_object_clicked"]
    if isinstance(last_clicked, dict) and "properties" in last_clicked:
        st.session_state.selected_state = last_clicked["properties"].get("NAME")


# Sidebar dropdown uses session state
states_in_data = df['state_name'].unique()
clicked_state = st.sidebar.selectbox(
    "Select a state (or click on map)",
    options=states_in_data,
    index=states_in_data.tolist().index(st.session_state.selected_state)
          if st.session_state.selected_state in states_in_data else 0,
    key="selected_state"
)


# Show community details
if clicked_state:
    state_df = df[df['state_name'] == clicked_state]
    communities = state_df['communityname'].dropna().unique()
    
    selected_community = st.sidebar.selectbox(f"Select community in {clicked_state}", options=communities)
    
    if selected_community:
        city_row = state_df[state_df['communityname'] == selected_community].iloc[0]

        st.subheader(f"{selected_community} — {clicked_state}")

        # Race Pie Chart
        race_cols = ["racepctblack", "racePctWhite", "racePctAsian", "racePctHisp", "indianPerCap"]
        race_values = city_row[race_cols].values
        race_names = [col.replace("racePct", "") for col in race_cols]
        fig_race = px.pie(values=race_values, names=race_names, title="Race Distribution", hole=0.3)
        st.plotly_chart(fig_race, use_container_width=True)

        # Metrics
        metrics = [
            "PctPolicMinor", "OfficAssgnDrugUnits", "NumKindsDrugsSeiz", "PolicAveOTWorked",
            "LandArea", "PopDens", "PctUsePubTrans", "PolicCars", "PolicOperBudg",
            "LemasPctPolicOnPatr", "LemasGangUnitDeploy", "LemasPctOfficDrugUn",
            "PolicBudgPerPop", "ViolentCrimesPerPop"
        ]
        st.write("### Community Metrics")
        for m in metrics:
            if m in city_row:
                st.metric(m, round(city_row[m], 2))

        # Correlation Heatmap
        corr_cols = metrics
        corr_matrix = state_df[corr_cols].corr()
        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap="coolwarm", ax=ax)
        st.write("### Correlation Heatmap — Community Metrics vs Violent Crime Rate")
        st.pyplot(fig)
else:
    st.sidebar.info("Click a state on the map to view communities.")