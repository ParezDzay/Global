import streamlit as st
import pandas as pd
import requests, base64, os
from datetime import date, datetime, time
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

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json"
        }

        response = requests.get(url, headers=headers)
        sha = response.json().get("sha") if response.status_code == 200 else None

        payload = {
            "message": commit_message,
            "content": encoded_content,
            "branch": branch
        }
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
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()

def load_bookings() -> pd.DataFrame:
    cols = ["Date", "Doctor", "Surgery", "Hour", "Room"]
    if DATA_FILE.exists():
        df = pd.read_csv(DATA_FILE)
    else:
        df = pd.DataFrame(columns=cols)
        df.to_csv(DATA_FILE, index=False)
    df = df.reindex(columns=cols)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df

def append_booking(rec: dict):
    df = pd.DataFrame([rec])
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
with tabs[1]:
    bookings = load_bookings()
    st.subheader("📋 Booked Surgeries")
    if bookings.empty:
        st.info("No surgeries booked yet.")
    else:
        for d in sorted(bookings["Date"].dt.date.unique()):
            sub_df = bookings[bookings["Date"].dt.date == d].sort_values("Hour")
            with st.expander(d.strftime("📅 %A, %d %B %Y")):
                st.table(sub_df[["Doctor", "Surgery", "Hour", "Room"]])

# --------------------------------------
# Sidebar: Add Booking Form
# --------------------------------------
st.sidebar.header("Add Surgery Booking")

picked_date = st.sidebar.date_input("Date", value=date.today())

doctor_name = st.sidebar.text_input("Doctor Name")
surgery_choice = st.sidebar.selectbox("Surgery Type", SURGERY_TYPES)

slot_hours = [time(h, 0) for h in range(10, 23)]
slot_display = [h.strftime("%H:%M") for h in slot_hours]
sel_hour_str = st.sidebar.selectbox("Hour", slot_display)
sel_hour = datetime.strptime(sel_hour_str, "%H:%M").time()
room_choice = st.sidebar.radio("Room", ROOMS, horizontal=True)

if st.sidebar.button("💾 Save Booking"):
    if not doctor_name:
        st.sidebar.error("Doctor name required.")
    elif check_overlap(bookings, picked_date, room_choice, sel_hour):
        st.sidebar.error("Room already booked at this time.")
    else:
        record = {
            "Date": pd.Timestamp(picked_date),
            "Doctor": doctor_name.strip(),
            "Surgery": surgery_choice.strip(),
            "Hour": sel_hour.strftime("%H:%M"),
            "Surgery Type": surgery_choice,
            "Room": room_choice
        }
        append_booking(record)
        bookings = pd.concat([bookings, pd.DataFrame([record])], ignore_index=True)
        st.sidebar.success("Surgery booked successfully.")
        safe_rerun()

# --------------------------------------
# Tab 2: View Archive
# --------------------------------------
with tabs[0]:
    st.subheader("📂 Archived Operations")
    archive_df = load_bookings()
    if archive_df.empty:
        st.info("No archived records found.")
    else:
        selected_date = st.selectbox("📅 Select Date to View", sorted(archive_df["Date"].dt.date.unique(), reverse=True))
        archive_filtered = archive_df[archive_df["Date"].dt.date == selected_date].sort_values("Hour")
        st.table(archive_filtered[["Doctor", "Surgery", "Hour", "Room"]])
