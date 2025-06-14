import streamlit as st
import pandas as pd
import requests, base64, os
from datetime import date, datetime, time, timedelta
from pathlib import Path

# --------------------------------------
# Simple Password Protection
# --------------------------------------
PASSWORD = "1122"
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    pwd = st.text_input("Enter password", type="password")
    if st.button("Login"):
        if pwd == PASSWORD:
            st.session_state.authenticated = True
            st.experimental_rerun()
        else:
            st.error("Incorrect password")
    st.stop()

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
# GitHub Push Function (unchanged)
# --------------------------------------

def push_to_github(file_path: Path, commit_message: str):
    try:
        token = st.secrets["github"]["token"]
        username = st.secrets["github"]["username"]
        repo = st.secrets["github"]["repo"]
        branch = st.secrets["github"]["branch"]
        content = file_path.read_text(encoding="utf-8")
        encoded = base64.b64encode(content.encode()).decode()
        url = f"https://api.github.com/repos/{username}/{repo}/contents/{file_path.name}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        res_get = requests.get(url, headers=headers)
        sha = res_get.json().get("sha") if res_get.status_code == 200 else None
        payload = {"message": commit_message, "content": encoded, "branch": branch}
        if sha:
            payload["sha"] = sha
        requests.put(url, headers=headers, json=payload)
    except Exception:
        pass  # keep UI clean

# --------------------------------------
# Helpers (all original)
# --------------------------------------

def safe_rerun():
    st.experimental_rerun()


def load_bookings() -> pd.DataFrame:
    cols = ["Date", "Doctor", "Hour", "Surgery", "Room", "Status"]
    if DATA_FILE.exists():
        df = pd.read_csv(DATA_FILE)
    else:
        df = pd.DataFrame(columns=cols)
        df.to_csv(DATA_FILE, index=False)
    df.columns = df.columns.str.title()
    if "Surgery Type" in df.columns:
        df.rename(columns={"Surgery Type": "Surgery"}, inplace=True)
    if "Status" not in df.columns:
        df["Status"] = "Booked"
    df = df.assign(**{c: df.get(c, pd.NA) for c in cols})[cols]
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df


def append_booking(rec: dict):
    df = load_bookings()
    df = pd.concat([df, pd.DataFrame([rec])], ignore_index=True)
    df.to_csv(DATA_FILE, index=False)
    push_to_github(DATA_FILE, "Add booking")


def modify_booking(row, action: str):
    df = load_bookings()
    mask = (
        (df["Date"] == row["Date"]) &
        (df["Doctor"] == row["Doctor"]) &
        (df["Hour"] == row["Hour"]) &
        (df["Room"] == row["Room"])
    )
    if action == "Delete":
        df = df.loc[~mask]
    else:
        df.loc[mask, "Status"] = action
    df.to_csv(DATA_FILE, index=False)
    push_to_github(DATA_FILE, f"{action} booking for {row['Doctor']}")


def check_overlap(df: pd.DataFrame, d: date, room: str, hr: time) -> bool:
    mask = (
        (df["Date"].dt.date == d) &
        (df["Room"] == room) &
        (pd.to_datetime(df["Hour"], format="%H:%M", errors="coerce").dt.time == hr) &
        (df["Status"] != "Cancelled")
    )
    return mask.any()


def doctor_icon(name: str) -> str:
    return f"<span style='font-size:16px;margin-right:4px;'>🩺</span>{name}"

# --------------------------------------
# Header
# --------------------------------------
if HEADER_IMAGE.exists():
    st.image(str(HEADER_IMAGE), width=250)
st.title("Global Eye Center _ Operation List")

# --------------------------------------
# Tabs
# --------------------------------------
booked_tab, archive_tab = st.tabs(["📋 Operation Booked", "📂 Operation Archive"])

# --------------------------------------
# Booked Tab
# --------------------------------------
with booked_tab:
    df = load_bookings()
    today = date.today()
    upcoming = df[(df["Date"].dt.date >= today) & (df["Status"] == "Booked")]
    st.subheader("📋 Operation Booked (Upcoming)")
    if upcoming.empty:
        st.info("No upcoming booked surgeries.")
    else:
        for d in sorted(upcoming["Date"].dt.date.unique()):
            sub = upcoming[upcoming["Date"].dt.date == d].sort_values("Hour").reset_index(drop=True)
            with st.expander(d.strftime("📅 %A, %d %B %Y")):
                st.markdown(
                    "<div style='display:flex;font-weight:bold;'>"
                    "<div style='flex:3;'>Details</div>"
                    "<div style='flex:1;text-align:center;'>✅</div>"
                    "<div style='flex:1;text-align:center;'>❌</div>"
                    "<div style='flex:1;text-align:center;'>🗑️</div>"
                    "</div>", unsafe_allow_html=True)
                for i, row in sub.iterrows():
                    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                    c1.markdown(
                        f"**Doctor:** {row['Doctor']}  \n"
                        f"**Surgery:** {row['Surgery']}  \n"
                        f"**Hour:** {row['Hour']}  \n"
                        f"**Room:** {row['Room']}"
                    )
                    if c2.button("✅", key=f"conf_{d}_{i}"):
                        modify_booking(row, "Confirmed"); safe_rerun()
                    if c3.button("❌", key=f"canc_{d}_{i}"):
                        modify_booking(row, "Cancelled"); safe_rerun()
                    if c4.button("🗑️", key=f"del_{d}_{i}"):
                        modify_booking(row, "Delete"); safe_rerun()

# --------------------------------------
# Archive Tab
# --------------------------------------
with archive_tab:
    df = load_bookings()
    yesterday = date.today() - timedelta(days=1)
    archived = df[(df["Date"].dt.date <= yesterday) & (df["Status"] == "Confirmed")]
    st.subheader("📂 Operation Archive (Confirmed)")
    if archived.empty:
        st.info("No confirmed records yet.")
    else:
        show = archived.copy()
        show["Date"] = show["Date"].dt.strftime("%Y-%m-%d")
        show["Doctor"] = show["Doctor"].apply(doctor_icon)
        show.reset_index(drop=True, inplace=True)
        show.index += 1
        st.markdown(
            show.to_html(escape=False, columns=["Date", "
