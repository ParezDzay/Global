import streamlit as st
import pandas as pd
import requests, base64
from datetime import date, datetime, time
from pathlib import Path

# -------------------------------------------------------------
# Streamlit configuration (first call!)
# -------------------------------------------------------------
st.set_page_config(page_title="Global Eye Center _ Operation List", layout="wide")

# -------------------------------------------------------------
# Paths & constants
# -------------------------------------------------------------
BASE_DIR = Path(__file__).parent if "__file__" in globals() else Path.cwd()
DATA_FILE = BASE_DIR / "Operation archive.csv"
HEADER_IMAGE = BASE_DIR / "Global photo.jpg"

SURGERY_TYPES = [
    "Phaco", "PPV", "Pterygium", "Blepharoplasty",
    "Glaucoma OP", "KPL", "Trauma OP",
    "Enucleation", "Injection", "Squint OP", "Other",
]
HALLS = ["Hall 1", "Hall 2"]

# -------------------------------------------------------------
# GitHub credentials are now pulled from st.secrets
# -------------------------------------------------------------

def get_github_secrets():
    try:
        gh = st.secrets["github"]
        return gh["token"], gh["username"], gh["repo"], gh.get("branch", "main")
    except Exception:
        return None, None, None, None

# -------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------

def safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


def load_bookings() -> pd.DataFrame:
    cols = ["Date", "Hall", "Doctor", "Hour", "Surgery"]
    if DATA_FILE.exists():
        df = pd.read_csv(DATA_FILE)
    else:
        df = pd.DataFrame(columns=cols)
        df.to_csv(DATA_FILE, index=False)
    df = df.reindex(columns=cols)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df


def append_booking(rec: dict):
    header_needed = not DATA_FILE.exists() or DATA_FILE.stat().st_size == 0
    df = pd.DataFrame([rec])
    df.to_csv(DATA_FILE, mode="a", header=header_needed, index=False)
    DATA_FILE.write_bytes(DATA_FILE.read_bytes())  # ensure write completes before pushing
    # push_to_github moved into append_booking


def push_to_github(file_path, commit_message):
    try:
        token = st.secrets["github"]["token"]
        username = st.secrets["github"]["username"]
        repo = st.secrets["github"]["repo"]
        branch = st.secrets["github"].get("branch", "main")

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
            st.sidebar.success("Pushed to GitHub ✔︎")
        else:
            st.sidebar.error(f"GitHub push failed: {res.json().get('message')}")
    except Exception as e:
        st.sidebar.error(f"❌ GitHub push failed: {e}")


def check_overlap(df: pd.DataFrame, d: date, hall: str, hr: time) -> bool:
    if df.empty:
        return False
    mask = (
        (df["Date"].dt.date == d) &
        (df["Hall"] == hall) &
        (pd.to_datetime(df["Hour"], format="%H:%M", errors="coerce").dt.time == hr)
    )
    return mask.any()

# -------------------------------------------------------------
# Header (image + title)
# -------------------------------------------------------------

if HEADER_IMAGE.exists():
    st.image(str(HEADER_IMAGE), width=250)

st.title("Global Eye Center _ Operation List")

# -------------------------------------------------------------
# Sidebar – Add Booking
# -------------------------------------------------------------

bookings = load_bookings()

st.sidebar.header("Add / Edit Booking")

picked_date = st.sidebar.date_input("Date", value=date.today())
hall_choice = st.sidebar.radio("Hall", HALLS, horizontal=True)

slot_hours = [time(h, 0) for h in range(10, 23)]
slot_display = [h.strftime("%H:%M") for h in slot_hours]
sel_hour_str = st.sidebar.selectbox("Hour", slot_display)
sel_hour = datetime.strptime(sel_hour_str, "%H:%M").time()

doctor_name = st.sidebar.text_input("Doctor Name")
surgery_choice = st.sidebar.selectbox("Surgery Type", SURGERY_TYPES)

if st.sidebar.button("💾 Save Booking"):
    if not doctor_name:
        st.sidebar.error("Doctor name required.")
    elif check_overlap(bookings, picked_date, hall_choice, sel_hour):
        st.sidebar.error("Timeslot already booked for that hall.")
    else:
        record = {
            "Date": pd.Timestamp(picked_date),
            "Hall": hall_choice,
            "Doctor": doctor_name.strip(),
            "Hour": sel_hour.strftime("%H:%M"),
            "Surgery": surgery_choice,
        }
        append_booking(record)
        bookings = pd.concat([bookings, pd.DataFrame([record])], ignore_index=True)
        push_to_github(DATA_FILE, "Update operation archive via app")
        st.sidebar.success("Saved!")
        safe_rerun()

# -------------------------------------------------------------
# Main pane – list by date
# -------------------------------------------------------------

if bookings.empty:
    st.info("No surgeries booked yet.")
else:
    for d in sorted(bookings["Date"].dt.date.unique()):
        sub_df = bookings[bookings["Date"].dt.date == d].sort_values("Hour")
        with st.expander(d.strftime("📅 %A, %d %B %Y")):
            st.table(sub_df[["Hall", "Hour", "Doctor", "Surgery"]])
