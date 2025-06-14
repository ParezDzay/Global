import streamlit as st
import pandas as pd
import requests, base64, os
from datetime import date, datetime, time, timedelta
from pathlib import Path

"""
Global Eye Center – Operation Booking App
Includes:
• Confirm / Cancel / Delete buttons
• Debug mode
• Status normalization
• CSV corruption fallback handling
"""

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

st.set_page_config(page_title="Global Eye Center (Operation List)", layout="wide")
BASE_DIR = Path(__file__).parent if "__file__" in globals() else Path.cwd()
DATA_FILE = BASE_DIR / "Operation Archive.csv"
HEADER_IMG = BASE_DIR / "Global photo.jpg"

SURGERY_TYPES = ["Phaco", "PPV", "Pterygium", "Blepharoplasty", "Glaucoma OP", "KPL", "Trauma OP", "Enucleation", "Injection", "Squint OP", "Other"]
ROOMS = ["Room 1", "Room 2"]

def push_to_github(file_path: Path, commit_message: str):
    try:
        g = st.secrets["github"]
        token, username, repo = g["token"], g["username"], g["repo"]
        branch = g.get("branch", "main")
        with open(file_path, "r", encoding="utf-8") as f:
            encoded = base64.b64encode(f.read().encode()).decode()
        filename = file_path.name
        url = f"https://api.github.com/repos/{username}/{repo}/contents/{filename}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        sha = requests.get(url, headers=headers).json().get("sha")
        payload = {"message": commit_message, "content": encoded, "branch": branch}
        if sha:
            payload["sha"] = sha
        r = requests.put(url, headers=headers, json=payload)
        if r.status_code not in (200, 201):
            st.sidebar.error(f"GitHub push failed: {r.status_code} – {r.json().get('message')}")
    except Exception as e:
        st.sidebar.error(f"GitHub Error: {e}")

def safe_rerun():
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    elif hasattr(st, "rerun"):
        st.rerun()
    else:
        st.stop()

def load_bookings() -> pd.DataFrame:
    cols = ["Date", "Doctor", "Hour", "Surgery", "Room", "Status"]
    try:
        df = pd.read_csv(DATA_FILE)
    except pd.errors.ParserError:
        st.error("CSV file is corrupted. Please fix or delete it.")
        return pd.DataFrame(columns=cols)
    df.columns = df.columns.str.strip().str.title()
    if "Surgery Type" in df.columns:
        df.rename(columns={"Surgery Type": "Surgery"}, inplace=True)
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    df["Status"].fillna("Booked", inplace=True)
    df["Status"] = df["Status"].astype(str).str.strip().str.title()
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
        df = df.loc[~m]
    else:
        df.loc[m, "Status"] = new_status
    df.to_csv(DATA_FILE, index=False)
    push_to_github(DATA_FILE, f"Operation {new_status} for {row['Doctor']} on {row['Date'].date()} at {row['Hour']}")

def doctor_icon_html() -> str:
    return '<span style="font-size:16px; margin-right:6px;">🩺</span>'

if HEADER_IMG.exists():
    st.image(str(HEADER_IMG), width=250)

st.title("Global Eye Center (Operation List)")

if st.sidebar.checkbox("🔍 Debug mode"):
    dbg = load_bookings()
    st.sidebar.write("Rows in CSV:", len(dbg))
    st.sidebar.write("Unique Status values:", dbg["Status"].unique())
    st.sidebar.write(dbg.head())

booked_tab, archive_tab = st.tabs(["📋 Operation Booked", "📂 Operation Archive"])

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
                    "<div style='flex:3;'>Details</div><div style='flex:1;'>Confirm</div>"
                    "<div style='flex:1;'>Cancel</div><div style='flex:1;'>Delete</div>"
                    "</div>", unsafe_allow_html=True)
                for idx, row in by_day.iterrows():
                    cols = st.columns([3, 1, 1, 1])
                    cols[0].markdown(
                        f"**Doctor:** {row['Doctor']}  \n**Surgery:** {row['Surgery']}  \n**Hour:** {row['Hour']}  \n**Room:** {row['Room']}")
                    if cols[1].button("✅", key=f"confirm_{idx}"):
                        update_status(row, "Confirmed")
                        safe_rerun()
                    if cols[2].button("❌", key=f"cancel_{idx}"):
                        update_status(row, "Cancelled")
                        safe_rerun()
                    if cols[3].button("🗑️", key=f"delete_{idx}"):
                        tmp = load_bookings()
                        tmp = tmp.loc[~((tmp["Date"] == row["Date"]) & (tmp["Doctor"] == row["Doctor"]) & (tmp["Hour"] == row["Hour"]) & (tmp["Room"] == row["Room"]))]
                        tmp.to_csv(DATA_FILE, index=False)
                        push_to_github(DATA_FILE, f"Operation Deleted for {row['Doctor']} on {row['Date'].date()} at {row['Hour']}")
                        safe_rerun()

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
        tbl["Doctor"] = tbl["Doctor"].apply(lambda x: f"{doctor_icon_html()}{x}" if pd.notna(x) else "")
        st.markdown(tbl.to_html(escape=False, columns=["Date", "Doctor", "Surgery", "Hour", "Room"]), unsafe_allow_html=True)

st.sidebar.header("Add Surgery Booking")
picked_date  = st.sidebar.date_input("Date", value=date.today())
room_choice  = st.sidebar.radio("Room", ROOMS, horizontal=True)
time_slots   = [time(h, m) for h in range(10, 23) for m in (0, 30) if not (h == 22 and m == 30)]
sel_hour_str = st.sidebar.selectbox("Hour", [t.strftime("%H:%M") for t in time_slots])
sel_hour     = datetime.strptime(sel_hour_str, "%H:%M").time()
doctor_name  = st.sidebar.text_input("Doctor Name")
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
