import streamlit as st
import pandas as pd
import requests, base64, os
from datetime import date, datetime, time, timedelta
from pathlib import Path

"""
Global Eye Center – Operation Booking App
Now with status normalisation so the Delete / Confirm / Cancel buttons always appear.
"""

# ---------- Simple Password Protection ----------
PASSWORD = "1122"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    pwd = st.text_input("Enter password", type="password")
    login_button = st.button("Login")
    if login_button:
        if pwd == PASSWORD:
            st.session_state.authenticated = True
        else:
            st.error("Incorrect password")
    st.stop()

# ---------- Streamlit Config ----------
st.set_page_config(page_title="Global Eye Center (Operation List)", layout="wide")

# ---------- Constants & Paths ----------
BASE_DIR = Path(__file__).parent if "__file__" in globals() else Path.cwd()
DATA_FILE = BASE_DIR / "Operation Archive.csv"
HEADER_IMAGE = BASE_DIR / "Global photo.jpg"

SURGERY_TYPES = [
    "Phaco", "PPV", "Pterygium", "Blepharoplasty",
    "Glaucoma OP", "KPL", "Trauma OP", "Enucleation",
    "Injection", "Squint OP", "Other",
]
ROOMS = ["Room 1", "Room 2"]

# ---------- GitHub Push Helper ----------

def push_to_github(file_path: Path, commit_message: str):
    try:
        token    = st.secrets["github"]["token"]
        username = st.secrets["github"]["username"]
        repo     = st.secrets["github"]["repo"]
        branch   = st.secrets["github"].get("branch", "main")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        encoded = base64.b64encode(content.encode()).decode()
        filename = os.path.basename(file_path)
        url = f"https://api.github.com/repos/{username}/{repo}/contents/{filename}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }

        resp = requests.get(url, headers=headers)
        sha  = resp.json().get("sha") if resp.status_code == 200 else None
        payload = {"message": commit_message, "content": encoded, "branch": branch}
        if sha:
            payload["sha"] = sha

        res = requests.put(url, headers=headers, json=payload)
        if res.status_code not in (200, 201):
            st.sidebar.error(f"GitHub push failed: {res.status_code} – {res.json().get('message')}")
    except Exception as e:
        st.sidebar.error(f"GitHub Error: {e}")

# ---------- Safe Rerun ----------

def safe_rerun():
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    elif hasattr(st, "rerun"):
        st.rerun()
    else:
        st.stop()

# ---------- Data Helpers ----------

def load_bookings() -> pd.DataFrame:
    """Load CSV, guarantee columns, and normalise Status."""
    cols = ["Date", "Doctor", "Hour", "Surgery", "Room", "Status"]
    if DATA_FILE.exists():
        df = pd.read_csv(DATA_FILE)
    else:
        df = pd.DataFrame(columns=cols)
        df.to_csv(DATA_FILE, index=False)

    df.columns = df.columns.str.strip().str.title()
    if "Surgery Type" in df.columns:
        df.rename(columns={"Surgery Type": "Surgery"}, inplace=True)

    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA

    df["Status"].fillna("Booked", inplace=True)
    # NEW: normalise casing and trim spaces so filter works
    df["Status"] = df["Status"].astype(str).str.strip().str.title()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df[cols]


def append_booking(record: dict):
    df = pd.DataFrame([record])
    header_needed = not DATA_FILE.exists() or DATA_FILE.stat().st_size == 0
    df.to_csv(DATA_FILE, mode="a", header=header_needed, index=False)
    push_to_github(DATA_FILE, "Update Operation Archive via app")


def check_overlap(df: pd.DataFrame, d: date, room: str, hr: time) -> bool:
    if df.empty:
        return False
    mask = (
        (df["Date"].dt.date == d) &
        (df["Room"] == room) &
        (pd.to_datetime(df["Hour"], format="%H:%M", errors="coerce").dt.time == hr) &
        (df["Status"] != "Cancelled")
    )
    return mask.any()


def update_status(row, new_status: str):
    df = load_bookings()
    mask = (
        (df["Date"] == row["Date"]) &
        (df["Doctor"] == row["Doctor"]) &
        (df["Hour"] == row["Hour"]) &
        (df["Room"] == row["Room"])
    )

    if new_status == "Cancelled":
        df = df.loc[~mask]
    else:
        df.loc[mask, "Status"] = new_status

    df.to_csv(DATA_FILE, index=False)
    push_to_github(DATA_FILE, f"Operation {new_status} for {row['Doctor']} on {row['Date'].date()} at {row['Hour']}")

# ---------- UI Helpers ----------

def doctor_icon_html() -> str:
    return '<span style="font-size:16px; margin-right:6px;">🩺</span>'

# ---------- Header ----------
if HEADER_IMAGE.exists():
    st.image(str(HEADER_IMAGE), width=250)

st.title("Global Eye Center (Operation List)")

# ---------- Tabs ----------
booked_tab, archive_tab = st.tabs(["📋 Operation Booked", "📂 Operation Archive"])

# ---------- Tab 1: Upcoming (Booked) ----------
with booked_tab:
    bookings = load_bookings()
    yesterday = date.today() - timedelta(days=1)
    upcoming = bookings[(bookings["Date"].dt.date > yesterday) & (bookings["Status"] == "Booked")]

    st.subheader("📋 Operation Booked")

    if upcoming.empty:
        st.info("No upcoming surgeries booked.")
    else:
        display = upcoming.sort_values(["Date", "Hour"]).drop_duplicates(subset=["Date", "Hour", "Room"])
        for d in display["Date"].dt.date.unique():
            day_df = display[display["Date"].dt.date == d]
            with st.expander(d.strftime("📅 %A, %d %B %Y")):
                st.markdown(
                    "<div style='display:flex; font-weight:bold; margin-bottom:10px;'>"
                    "<div style='flex:3;'>Details</div>"
                    "<div style='flex:1;'>Confirm</div>"
                    "<div style='flex:1;'>Cancel</div>"
                    "<div style='flex:1;'>Delete</div>"
                    "</div>", unsafe_allow_html=True
                )
                for idx, row in day_df.iterrows():
                    cols = st.columns([3, 1, 1, 1])

                    cols[0].markdown(
                        f"**Doctor:** {row['Doctor']}  \n"
                        f"**Surgery:** {row['Surgery']}  \n"
                        f"**Hour:** {row['Hour']}  \n"
                        f"**Room:** {row['Room']}"
                    )

                    if cols[1].button("✅", key=f"confirm_{idx}"):
                        update_status(row, "Confirmed")
                        safe_rerun()

                    if cols[2].button("❌", key=f"cancel_{idx}"):
                        update_status(row, "Cancelled")
                        safe_rerun()

                    if cols[3].button("🗑️", key=f"delete_{idx}"):
                        df = load_bookings()
                        mask = ~(
                            (df["Date"] == row["Date"]) &
                            (df["Doctor"] == row["Doctor"]) &
                            (df["Hour"] == row["Hour"]) &
                            (df["Room"] == row["Room"])
                        )
                        df = df.loc[mask]
                        df.to_csv(DATA_FILE, index=False)
                        push
