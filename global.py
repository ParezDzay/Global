import streamlit as st
import pandas as pd
import requests, base64, os
from datetime import date, datetime, time, timedelta
from pathlib import Path

"""
Global Eye Center – Operation Booking App
Full script with an additional Delete column (trash‑bin icon) in the 📋 Operation Booked tab.
No other functions were changed so your existing users and data remain unaffected.
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
    """Push the local CSV to GitHub so your colleagues see live updates."""
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
        # Get current SHA if file already exists
        resp = requests.get(url, headers=headers)
        sha  = resp.json().get("sha") if resp.status_code == 200 else None

        payload = {"message": commit_message, "content": encoded, "branch": branch}
        if sha:
            payload["sha"] = sha

        res = requests.put(url, headers=headers, json=payload)
        if res.status_code in (200, 201):
            st.sidebar.success("✅ Operation Archive pushed to GitHub")
        else:
            st.sidebar.error(f"❌ GitHub Push Failed: {res.status_code} — {res.json().get('message')}")
    except Exception as e:
        st.sidebar.error(f"❌ GitHub Error: {e}")

# ---------- Safe Rerun ----------

def safe_rerun():
    """Streamlit API changed over time; this keeps compatibility."""
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    elif hasattr(st, "rerun"):
        st.rerun()
    else:
        st.stop()

# ---------- Data Helpers ----------

def load_bookings() -> pd.DataFrame:
    """Load the CSV (or create it) and guarantee expected columns."""
    cols = ["Date", "Doctor", "Hour", "Surgery", "Room", "Status"]
    if DATA_FILE.exists():
        df = pd.read_csv(DATA_FILE)
    else:
        df = pd.DataFrame(columns=cols)
        df.to_csv(DATA_FILE, index=False)

    # Normalise header names
    df.columns = df.columns.str.strip().str.title()
    if "Surgery Type" in df.columns:
        df.rename(columns={"Surgery Type": "Surgery"}, inplace=True)

    # Ensure required columns
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA

    df["Status"].fillna("Booked", inplace=True)

    # Convert dates
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df[cols]


def append_booking(record: dict):
    """Append a new booking and push to GitHub."""
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
    """Update (or delete) a single booking row."""
    df = load_bookings()
    mask = (
        (df["Date"] == row["Date"]) &
        (df["Doctor"] == row["Doctor"]) &
        (df["Hour"] == row["Hour"]) &
        (df["Room"] == row["Room"])
    )

    if new_status == "Cancelled":
        df = df.loc[~mask]          # Remove row completely
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
tabs = st.tabs(["📋 Operation Booked", "📂 Operation Archive"])

# ---------- Tab 1: Upcoming Bookings ----------
with tabs[0]:
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
                # Header row
                st.markdown(
                    "<div style='display:flex; font-weight:bold; margin-bottom:10px;'>"
                    "<div style='flex:3;'>Details</div>"
                    "<div style='flex:1;'>Confirm</div>"
                    "<div style='flex:1;'>Cancel</div>"
                    "<div style='flex:1;'>Delete</div>"
                    "</div>", unsafe_allow_html=True
                )
                # Each booking row
                for idx, row in day_df.iterrows():
                    cols = st.columns([3, 1, 1, 1])

                    # Details column
                    cols[0].markdown(
                        f"**Doctor:** {row['Doctor']}  \n"
                        f"**Surgery:** {row['Surgery']}  \n"
                        f"**Hour:** {row['Hour']}  \n"
                        f"**Room:** {row['Room']}"
                    )

                    # Confirm button
                    if cols[1].button("✅", key=f"confirm_{idx}"):
                        update_status(row, "Confirmed")
                        safe_rerun()

                    # Cancel button
                    if cols[2].button("❌", key=f"cancel_{idx}"):
                        update_status(row, "Cancelled")
                        safe_rerun()

                    # **NEW: Delete button / column already present**
                    if cols[3].button("🗑️", key=f"delete_{idx}"):
                        # Remove without changing status (hard delete)
                        df = load_bookings()
                        mask = ~(
                            (df["Date"] == row["Date"]) &
                            (df["Doctor"] == row["Doctor"]) &
                            (df["Hour"] == row["Hour"]) &
                            (df["Room"] == row["Room"])
                        )
                        df = df.loc[mask]
                        df.to_csv(DATA_FILE, index=False)
                        push_to_github(DATA_FILE, f"Operation Deleted for {row['Doctor']} on {row['Date'].date()} at {row['Hour']}")
                        safe_rerun()

# ---------- Tab 2: Archive (Confirmed & Past) ----------
with tabs[1]:
    bookings = load_bookings()
    yesterday = date.today() - timedelta(days=1)
    archive = bookings[(bookings["Date"].dt.date <= yesterday) & (bookings["Status"] == "Confirmed")]

    st.subheader("📂 Operation Archive")

    if archive.empty:
        st.info("No archived records found.")
    else:
        display = archive.sort_values(["Date", "Hour"], ascending=False).drop_duplicates(subset=["Date", "Hour", "Room"]).copy()
        display["Date"] = display["Date"].dt.strftime("%Y-%m-%d")
        display.reset_index(drop=True, inplace=True)
        display.index += 1
        display["Doctor"] = display["Doctor"].apply(lambda x: f"{doctor_icon_html()}{x}")

        st.markdown(
            display.to_html(escape=False, columns=["Date", "Doctor", "Surgery", "Hour", "Room"]),
            unsafe_allow_html=True,
        )

# ---------- Sidebar – Add Booking ----------
st.sidebar.header("Add Surgery Booking")

picked_date  = st.sidebar.date_input("Date", value=date.today())
room_choice  = st.sidebar.radio("Room", ROOMS, horizontal=True)

# 30‑minute slots 10:00 – 22:00
time_slots = [time(h, m) for h in range(10, 23) for m in (0, 30) if not (h == 22 and m == 30)]
sel_hour_str = st.sidebar.selectbox("Hour", [t.strftime("%H:%M") for t in time_slots])
sel_hour = datetime.strptime(sel_hour_str, "%H:%M").time()

doctor_name = st.sidebar.text_input("Doctor Name")
surgery_choice = st.sidebar.selectbox("Surgery Type", SURGERY_TYPES)

if st.sidebar.button("💾 Save Booking"):
    if not doctor_name.strip():
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
            "Status": "Booked",
        }
        append_booking(record)
        st.sidebar.success("Surgery booked successfully.")
        safe_rerun()
