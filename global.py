import streamlit as st
import pandas as pd
import requests, base64, os
from datetime import date, datetime, time, timedelta
from pathlib import Path

# --------------------------------------
# Streamlit Config
# --------------------------------------
st.set_page_config(page_title="Global Eye Center _ Operation List", layout="wide")

# --------------------------------------
# Constants and Paths
# --------------------------------------
BASE_DIR = Path(__file__).parent if "__file__" in globals() else Path.cwd()
DATA_FILE = BASE_DIR / "Operation Archive.csv"
HEADER_IMAGE = BASE_DIR / "Global photo.jpg"

SURGERY_TYPES = [
    "Phaco", "PPV", "Pterygium", "Blepharoplasty",
    "Glaucoma OP", "KPL", "Trauma OP", "Enucleation",
    "Injection", "Squint OP", "Other",
]
ROOMS = ["Room 1", "Room 2"]

today = date.today()

# --------------------------------------
# GitHub Push Function
# --------------------------------------
def push_to_github(file_path, commit_message):
    try:
        token = st.secrets["github"]["token"]
        username = st.secrets["github"]["username"]
        repo = st.secrets["github"]["repo"]
        branch = st.secrets["github"]["branch"]
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        encoded_content = base64.b64encode(content.encode()).decode()
        filename = os.path.basename(file_path)
        url = f"https://api.github.com/repos/{username}/{repo}/contents/{filename}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        response = requests.get(url, headers=headers)
        sha = response.json().get("sha") if response.status_code == 200 else None
        payload = {"message": commit_message, "content": encoded_content, "branch": branch}
        if sha:
            payload["sha"] = sha
        res = requests.put(url, headers=headers, json=payload)
        if res.status_code in [200, 201]:
            st.sidebar.success("✅ Operation Archive pushed to GitHub")
        else:
            st.sidebar.error(f"❌ GitHub Push Failed: {res.status_code} — {res.json().get('message')}")
    except Exception as e:
        st.sidebar.error(f"❌ GitHub Error: {e}")

# --------------------------------------
# Utility Functions
# --------------------------------------
def safe_rerun():
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    elif hasattr(st, "rerun"):
        st.rerun()
    else:
        st.stop()


def load_bookings() -> pd.DataFrame:
    cols = ["Date", "Doctor", "Hour", "Surgery", "Room"]
    if DATA_FILE.exists():
        df = pd.read_csv(DATA_FILE)
    else:
        df = pd.DataFrame(columns=["Date", "Doctor", "Hour", "Surgery Type", "Room"]);
        df.to_csv(DATA_FILE, index=False)
    df.columns = df.columns.str.strip().str.title()
    if "Surgery Type" in df.columns:
        df.rename(columns={"Surgery Type": "Surgery"}, inplace=True)
    df = df.assign(**{c: df.get(c, pd.NA) for c in cols})
    df = df[cols]
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df


def append_booking(rec: dict):
    df = pd.DataFrame([
        {"Date": rec["Date"], "Doctor": rec["Doctor"], "Hour": rec["Hour"], "Surgery Type": rec["Surgery"], "Room": rec["Room"]}
    ])
    header_needed = not DATA_FILE.exists() or DATA_FILE.stat().st_size == 0
    df.to_csv(DATA_FILE, mode="a", header=header_needed, index=False)
    push_to_github(DATA_FILE, "Update Operation Archive via app")


def check_overlap(df: pd.DataFrame, d: date, room: str, hr: time) -> bool:
    if df.empty:
        return False
    mask = (
        (df["Date"].dt.date == d) &
        (df["Room"] == room) &
        (pd.to_datetime(df["Hour"], format="%H:%M", errors="coerce").dt.time == hr)
    )
    return mask.any()

# --------------------------------------
# Header
# --------------------------------------
if HEADER_IMAGE.exists():
    st.image(str(HEADER_IMAGE), width=250)
st.title("Global Eye Center _ Operation List")

# --------------------------------------
# TABS: Booked View | Archive View
# --------------------------------------
tabs = st.tabs(["📋 Operation Booked", "📂 Operation Archive"])

# --------------------------------------
# Tab 1: Booked Operations
# --------------------------------------
with tabs[0]:
    # Load all bookings and separate upcoming and past
    all_bookings = load_bookings()
    yesterday = date.today() - timedelta(days=1)
    upcoming = all_bookings[all_bookings["Date"].dt.date > yesterday]
    st.subheader("📋 Booked Surgeries")
    if upcoming.empty:
        st.info("No upcoming surgeries booked.")
    else:
        display_df = upcoming.drop_duplicates(subset=["Date", "Hour", "Room"]).sort_values(["Date", "Hour"])
        for d in display_df["Date"].dt.date.unique():
            sub_df = display_df[display_df["Date"].dt.date == d]
            with st.expander(d.strftime("📅 %A, %d %B %Y")):
                st.table(sub_df[["Doctor", "Surgery", "Hour", "Room"]])

# --------------------------------------
with tabs[1]:
    # Archived: bookings up to yesterday
    all_bookings = load_bookings()
    yesterday = date.today() - timedelta(days=1)
    archive_df = all_bookings[all_bookings["Date"].dt.date <= yesterday]
    st.subheader("📂 Archived Operations")
    if archive_df.empty:
        st.info("No archived records found.")
    else:
        display_df = archive_df.drop_duplicates(subset=["Date", "Hour", "Room"]).sort_values(["Date", "Hour"], ascending=False)
        selected_date = st.selectbox(
            "📅 Select Date to View",
            display_df["Date"].dt.date.unique(),
            format_func=lambda d: d.strftime("%A, %d %B %Y")
        )
        filtered = display_df[display_df["Date"].dt.date == selected_date]
        st.table(filtered[["Doctor", "Surgery", "Hour", "Room"]])
