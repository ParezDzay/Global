import streamlit as st
import pandas as pd
import requests, base64, os
from datetime import date, datetime, time, timedelta
from pathlib import Path

"""
Global Eye Center – Operation Booking App
Full, self‑contained script **including**:
• Delete / Confirm / Cancel icons in 📋 Operation Booked
• Status normalisation (so filters never miss rows)
• One‑click 🔍 *Debug mode* in the sidebar to inspect live data
Save this file over your existing `.py`, stop the old Streamlit process, and run:  
`streamlit run operation_booking_app.py`
"""

# ---------- Simple Password Protection ----------
PASSWORD = "1122"
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if not st.session_state.authenticated:
    pwd = st.text_input("Enter password", type="password")
    if st.button("Login"):
        st.session_state.authenticated = (pwd == PASSWORD)
        if not st.session_state.authenticated:
            st.error("Incorrect password")
    st.stop()

# ---------- Streamlit Config ----------
st.set_page_config(page_title="Global Eye Center (Operation List)", layout="wide")

# ---------- Constants & Paths ----------
BASE_DIR   = Path(__file__).parent if "__file__" in globals() else Path.cwd()
DATA_FILE  = BASE_DIR / "Operation Archive.csv"
HEADER_IMG = BASE_DIR / "Global photo.jpg"

SURGERY_TYPES = [
    "Phaco", "PPV", "Pterygium", "Blepharoplasty",
    "Glaucoma OP", "KPL", "Trauma OP", "Enucleation",
    "Injection", "Squint OP", "Other",
]
ROOMS = ["Room 1", "Room 2"]

# ---------- GitHub Push Helper ----------

def push_to_github(file_path: Path, commit_message: str):
    """Push CSV to the repo defined in .streamlit/secrets.toml."""
    try:
        g = st.secrets["github"]
        token, username, repo = g["token"], g["username"], g["repo"]
        branch = g.get("branch", "main")

        with open(file_path, "r", encoding="utf-8") as f:
            encoded = base64.b64encode(f.read().encode()).decode()
        filename = file_path.name
        url = f"https://api.github.com/repos/{username}/{repo}/contents/{filename}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

        sha = requests.get(url, headers=headers).json().get("sha")  # existing file SHA (if any)
        payload = {"message": commit_message, "content": encoded, "branch": branch}
        if sha:
            payload["sha"] = sha
        r = requests.put(url, headers=headers, json=payload)
        if r.status_code not in (200, 201):
            st.sidebar.error(f"GitHub push failed: {r.status_code} – {r.json().get('message')}")
    except Exception as e:
        st.sidebar.error(f"GitHub Error: {e}")

# ---------- Safe Rerun ----------

def safe_rerun():
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    else:
        st.rerun() if hasattr(st, "rerun") else st.stop()

# ---------- Data Helpers ----------

def load_bookings() -> pd.DataFrame:
    """Read/initialise CSV; return DF with guaranteed columns & cleaned Status."""
    cols = ["Date", "Doctor", "Hour", "Surgery", "Room", "Status"]
    df = pd.read_csv(DATA_FILE) if DATA_FILE.exists() else pd.DataFrame(columns=cols)

    # Normalise headers + fill
    df.columns = df.columns.str.strip().str.title()
    if "Surgery Type" in df.columns:
        df.rename(columns={"Surgery Type": "Surgery"}, inplace=True)
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA

    # Clean status
    df["Status"].fillna("Booked", inplace=True)
    df["Status"] = df["Status"].astype(str).str.strip().str.title()  # Booked, Confirmed, Cancelled

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df[cols]


def append_booking(record: dict):
    df = pd.DataFrame([record])
    df.to_csv(DATA_FILE, mode="a", header=not DATA_FILE.exists(), index=False)
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
    m = (
        (df["Date"] == row["Date"]) & (df["Doctor"] == row["Doctor"]) &
        (df["Hour"] == row["Hour"]) & (df["Room"] == row["Room"])
    )
    if new_status == "Cancelled":
        df = df.loc[~m]  # remove row
    else:
        df.loc[m, "Status"] = new_status
    df.to_csv(DATA_FILE, index=False)
    push_to_github(DATA_FILE, f"Operation {new_status} for {row['Doctor']} on {row['Date'].date()} at {row['Hour']}")

# ---------- UI Helpers ----------

def doctor_icon_html() -> str:
    return '<span style="font-size:16px; margin-right:6px;">🩺</span>'

# ---------- Header ----------
if HEADER_IMG.exists():
    st.image(str(HEADER_IMG), width=250)

st.title("Global Eye Center (Operation List)")

# ---------- Quick Debug Panel ----------
if st.sidebar.checkbox("🔍 Debug mode"):
    dbg = load_bookings()
    st.sidebar.write("Rows in CSV:", len(dbg))
    st.sidebar.write("Unique Status values:", dbg["Status"].unique())
    st.sidebar.write(dbg.head())

# ---------- Tabs ----------
booked_tab, archive_tab = st.tabs(["📋 Operation Booked", "📂 Operation Archive"])

# ---------- Tab 1: Upcoming (Booked) ----------
with booked_tab:
    df_all = load_bookings()
    yesterday = date.today() - timedelta(days=1)
    upcoming = df_all[(df_all["Date"].dt.date > yesterday) & (df_all["Status"] == "Booked")]

    st.subheader("📋 Operation Booked")

    if upcoming.empty:
        st.info("No upcoming surgeries booked.")
    else:
        display = upcoming.sort_values(["Date", "Hour"]).drop_duplicates(subset=["Date", "Hour", "Room"])
        for d in display["Date"].dt.date.unique():
            by_day = display[display["Date"].dt.date == d]
            with st.expander(d.strftime("📅 %A, %d %B %Y")):
                st.markdown(
                    "<div style='display:flex; font-weight:bold; margin-bottom:10px;'>"
                    "<div style='flex:3;'>Details</div>"
                    "<div style='flex:1;'>Confirm</div>"
                    "<div style='flex:1;'>Cancel</div>"
                    "<div style='flex:1;'>Delete</div>"
                    "</div>", unsafe_allow_html=True
                )
                for idx, row in by_day.iterrows():
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
                        tmp = load_bookings()
                        tmp = tmp.loc[~(
                            (tmp["Date"] == row["Date"]) &
                            (tmp["Doctor"] == row["Doctor"]) &
                            (tmp["Hour"] == row["Hour"]) &
                            (tmp["Room"] == row["Room"])
                        )]
                        tmp.to_csv(DATA_FILE, index=False)
                        push_to_github(DATA_FILE, f"Operation Deleted for {row['Doctor']} on {row['Date'].date()} at {row['Hour']}")
                        safe_rerun()

# ---------- Tab 2: Archive (Confirmed & in the past) ----------
with archive_tab:
    df_all = load_bookings()
    yesterday = date.today() - timedelta(days=1)
    archive = df_all[(df_all["Date"].dt.date <= yesterday) & (df_all["Status"] == "Confirmed")]

    st.subheader("📂 Operation Archive")

    if archive.empty:
        st.info("No archived records found.")
    else:
        tbl = archive.sort_values(["Date", "Hour"], ascending=False).drop_duplicates(subset=["Date", "Hour", "Room"]).copy()
        tbl["Date"] = tbl["Date"].dt.strftime("%Y-%m-%d")
        tbl.reset_index(drop=True, inplace=True)
        tbl.index += 1
        tbl["Doctor"] = tbl["Doctor"].apply(lambda x
