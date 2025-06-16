import streamlit as st
import pandas as pd
import requests, base64, os
from datetime import date, datetime, time, timedelta
from pathlib import Path

# ---------- Password Protection ----------
PASSWORD = "1122"
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if not st.session_state.authenticated:
    pwd = st.text_input("Enter password", type="password")
    if st.button("Login"):
        if pwd == PASSWORD:
            st.session_state.authenticated = True
        else:
            st.error("Incorrect password")
    st.stop()

# ---------- Streamlit Page Config ----------
st.set_page_config(page_title="Global Eye Center (Operation List)", layout="wide")

# ---------- Paths and Constants ----------
BASE_DIR = Path(__file__).parent if "__file__" in globals() else Path.cwd()
DATA_FILE = BASE_DIR / "Operation Archive.csv"
HEADER_IMAGE = BASE_DIR / "Global photo.jpg"

SURGERY_TYPES = [
    "Phaco", "PPV", "Pterygium", "Blepharoplasty",
    "Glaucoma OP", "KPL", "Trauma OP", "Enucleation",
    "Injection", "Squint OP", "Other",
]
ROOMS = ["Room 1", "Room 2"]

# ---------- GitHub Push Function ----------
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
            st.sidebar.success("✅ File pushed to GitHub")
        else:
            st.sidebar.error(f"❌ GitHub Push Failed: {res.status_code} — {res.json().get('message')}")
    except Exception as e:
        st.sidebar.error(f"❌ GitHub Error: {e}")

# ---------- Safe Rerun ----------
def safe_rerun():
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    elif hasattr(st, "rerun"):
        st.rerun()
    else:
        st.stop()

# ---------- Load Bookings ----------
def load_bookings() -> pd.DataFrame:
    expected_cols = ["Date", "Doctor", "Hour", "Surgery", "Room"]
    if DATA_FILE.exists():
        df = pd.read_csv(DATA_FILE)
        df.columns = df.columns.str.strip().str.title()
        df.rename(columns={"Surgery Type": "Surgery"}, inplace=True)
        for col in expected_cols:
            if col not in df.columns:
                df[col] = pd.NA
        df = df[expected_cols]
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    else:
        df = pd.DataFrame(columns=expected_cols)
        df.to_csv(DATA_FILE, index=False)
    return df

# ---------- Append Booking ----------
def append_booking(rec: dict):
    row = {
        "Date": rec["Date"],
        "Doctor": rec["Doctor"],
        "Hour": rec["Hour"],
        "Surgery": rec["Surgery"],
        "Room": rec["Room"],
    }
    new_df = pd.DataFrame([row])
    if DATA_FILE.exists():
        try:
            existing_df = pd.read_csv(DATA_FILE)
        except Exception:
            existing_df = pd.DataFrame(columns=["Date", "Doctor", "Hour", "Surgery", "Room"])
    else:
        existing_df = pd.DataFrame(columns=["Date", "Doctor", "Hour", "Surgery", "Room"])
    full_df = pd.concat([existing_df, new_df], ignore_index=True)
    full_df.to_csv(DATA_FILE, index=False)
    if full_df.shape[0] > 0:
        push_to_github(DATA_FILE, "Update Operation Archive via app")

# ---------- Check Overlap ----------
def check_overlap(df: pd.DataFrame, d: date, room: str, hr: time) -> bool:
    if df.empty:
        return False
    mask = (
        (df["Date"].dt.date == d) &
        (df["Room"] == room) &
        (pd.to_datetime(df["Hour"], format="%H:%M", errors="coerce").dt.time == hr)
    )
    return mask.any()

# ---------- Doctor Icon HTML ----------
def doctor_icon_html():
    return '<span style="font-size:16px; margin-right:6px;">🩺</span>'

# ---------- Header Image & Title ----------
if HEADER_IMAGE.exists():
    st.image(str(HEADER_IMAGE), width=250)
st.title("Global Eye Center (Operation List)")

# ---------- Tabs ----------
tabs = st.tabs(["📋 Operation Booked", "📂 Operation Archive"])

# ---------- Tab 1: Operation Booked ----------
with tabs[0]:
    bookings = load_bookings()
    upcoming = bookings[bookings["Date"].dt.date >= date.today()]
    st.subheader("📋 Operation Booked")
    if upcoming.empty:
        st.info("No upcoming surgeries booked.")
    else:
        display = upcoming.drop_duplicates(subset=["Date", "Hour", "Room"]).sort_values(["Date", "Hour"])
        for d in display["Date"].dt.date.unique():
            day_df = display[display["Date"].dt.date == d]
            with st.expander(d.strftime("📅 %A, %d %B %Y")):
                day_df_display = day_df[["Doctor", "Surgery", "Hour", "Room"]].copy()
                day_df_display.index = range(1, len(day_df_display) + 1)
                st.dataframe(day_df_display, use_container_width=True)

# ---------- Tab 2: Archive ----------
with tabs[1]:
    bookings = load_bookings()
    archive = bookings[bookings["Date"].dt.date < date.today()]
    st.subheader("📂 Operation Archive")
    if archive.empty:
        st.info("No archived records found.")
    else:
        display = archive.drop_duplicates(subset=["Date", "Hour", "Room"]).sort_values(["Date", "Hour"], ascending=False).copy()
        display["Date"] = display["Date"].dt.strftime("%Y-%m-%d")
        display.reset_index(drop=True, inplace=True)
        display.index += 1
        display["Doctor"] = display["Doctor"].apply(lambda x: f'{doctor_icon_html()}{x}')
        st.markdown(
            display.to_html(escape=False, columns=["Date", "Doctor", "Surgery", "Hour", "Room"]),
            unsafe_allow_html=True,
        )

# ---------- Sidebar Form ----------
st.sidebar.header("Add Surgery Booking")
picked_date = st.sidebar.date_input("Date", value=date.today())
room_choice = st.sidebar.radio("Room", ROOMS, horizontal=True)

# 30-minute slots from 10:00 to 22:00
slot_hours = []
for hour in range(10, 23):
    slot_hours.append(time(hour, 0))
    if hour != 22:
        slot_hours.append(time(hour, 30))

sel_hour_str = st.sidebar.selectbox("Hour", [h.strftime("%H:%M") for h in slot_hours])
sel_hour = datetime.strptime(sel_hour_str, "%H:%M").time()

doctor_name = st.sidebar.text_input("Doctor Name")
surgery_choice = st.sidebar.selectbox("Surgery Type", SURGERY_TYPES)

if st.sidebar.button("💾 Save Booking"):
    if not doctor_name:
        st.sidebar.error("Doctor name required.")
    elif check_overlap(load_bookings(), picked_date, room_choice, sel_hour):
        st.sidebar.error("Room already booked at this time.")
    else:
        record = {
            "Date": pd.Timestamp(picked_date),
            "Doctor": doctor_name.strip(),
            "Hour": sel_hour.strftime("%H:%M"),
            "Surgery": surgery_choice,
            "Room": room_choice,
        }
        append_booking(record)
        st.sidebar.success("✅ Surgery booked successfully.")
        safe_rerun()
