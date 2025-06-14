import streamlit as st
import pandas as pd
import requests, base64, os
from datetime import date, datetime, time, timedelta
from pathlib import Path

# ---------- Simple Password Protection ----------
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

# ---------- Streamlit config ----------
st.set_page_config(page_title="Global Eye Center (Operation List)", layout="wide")

# ---------- Constants and Paths ----------
BASE_DIR = Path(__file__).parent if "__file__" in globals() else Path.cwd()
DATA_FILE   = BASE_DIR / "Operation Archive.csv"
HEADER_IMAGE = BASE_DIR / "Global photo.jpg"

SURGERY_TYPES = [
    "Phaco", "PPV", "Pterygium", "Blepharoplasty",
    "Glaucoma OP", "KPL", "Trauma OP", "Enucleation",
    "Injection", "Squint OP", "Other",
]
ROOMS = ["Room 1", "Room 2"]

# ---------- GitHub push function ----------
def push_to_github(file_path, commit_message):
    try:
        token     = st.secrets["github"]["token"]
        username  = st.secrets["github"]["username"]
        repo      = st.secrets["github"]["repo"]
        branch    = st.secrets["github"]["branch"]
        content   = file_path.read_text("utf-8")
        encoded   = base64.b64encode(content.encode()).decode()
        url       = f"https://api.github.com/repos/{username}/{repo}/contents/{file_path.name}"
        headers   = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        sha       = requests.get(url, headers=headers).json().get("sha")
        payload   = {"message": commit_message, "content": encoded, "branch": branch}
        if sha:
            payload["sha"] = sha
        requests.put(url, headers=headers, json=payload)
    except Exception:
        pass   # silently ignore GitHub issues for user experience

# ---------- Safe rerun helper ----------
def safe_rerun():
    st.experimental_rerun()

# ---------- Load bookings ----------
def load_bookings() -> pd.DataFrame:
    """Return dataframe; skip any malformed CSV rows so the app never crashes."""
    cols = ["Date", "Doctor", "Hour", "Surgery", "Room", "Status"]
    try:
        df = pd.read_csv(DATA_FILE)
    except pd.errors.ParserError:
        # Fallback – ignore bad lines
        df = pd.read_csv(DATA_FILE, engine="python", on_bad_lines="skip")
    df.columns = df.columns.str.title()
    if "Surgery Type" in df.columns:
        df.rename(columns={"Surgery Type": "Surgery"}, inplace=True)
    if "Status" not in df.columns:
        df["Status"] = "Booked"
    df = df.assign(**{c: df.get(c, pd.NA) for c in cols})[cols]
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df

# ---------- Append booking ----------
def append_booking(rec: dict):
    df = load_bookings()
    df = pd.concat([df, pd.DataFrame([rec])], ignore_index=True)
    df.to_csv(DATA_FILE, index=False)
    push_to_github(DATA_FILE, "Add booking")

# ---------- Modify (Confirm/Cancel/Delete) ----------
def modify_booking(row: pd.Series, action: str):
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

# ---------- Check overlap ----------
def check_overlap(df: pd.DataFrame, d: date, room: str, hr: time) -> bool:
    mask = (
        (df["Date"].dt.date == d) &
        (df["Room"] == room) &
        (pd.to_datetime(df["Hour"], format="%H:%M", errors="coerce").dt.time == hr) &
        (df["Status"] != "Cancelled")
    )
    return mask.any()

# ---------- Icon helper ----------
def doctor_icon(name: str) -> str:
    return f"<span style='font-size:16px;margin-right:4px;'>🩺</span>{name}"

# ---------- Header ----------
if HEADER_IMAGE.exists():
    st.image(str(HEADER_IMAGE), width=250)
st.title("Global Eye Center (Operation List)")

# ---------- Tabs ----------
tab_booked, tab_archive = st.tabs(["📋 Operation Booked", "📂 Operation Archive"])

# ===== Tab 1 – Operation Booked =====
with tab_booked:
    df = load_bookings()
    upcoming = df[(df["Date"].dt.date >= date.today()) & (df["Status"] == "Booked")]
    st.subheader("📋 Operation Booked")
    if upcoming.empty:
        st.info("No upcoming surgeries booked.")
    else:
        for d in sorted(upcoming["Date"].dt.date.unique()):
            subset = upcoming[upcoming["Date"].dt.date == d].sort_values("Hour").reset_index(drop=True)
            with st.expander(d.strftime("📅 %A, %d %B %Y")):
                # header row
                st.markdown(
                    "<div style='display:flex;font-weight:bold;'>"
                    "<div style='flex:3;'>Details</div>"
                    "<div style='flex:1;text-align:center;'>Confirm</div>"
                    "<div style='flex:1;text-align:center;'>Cancel</div>"
                    "<div style='flex:1;text-align:center;'>Delete</div>"
                    "</div>", unsafe_allow_html=True)
                # rows
                for i, row in subset.iterrows():
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
                    if c4.button("Delete", key=f"del_{d}_{i}"):
                        modify_booking(row, "Delete"); safe_rerun()

# ===== Tab 2 – Archive (Confirmed) =====
with tab_archive:
    df = load_bookings()
    archived = df[(df["Date"].dt.date < date.today()) & (df["Status"] == "Confirmed")]
    st.subheader("📂 Operation Archive")
    if archived.empty:
        st.info("No archived records found.")
    else:
        table = archived.copy()
        table["Date"] = table["Date"].dt.strftime("%Y-%m-%d")
        table["Doctor"] = table["Doctor"].apply(doctor_icon)
        table.reset_index(drop=True, inplace=True)
        table.index += 1
        st.markdown(
            table.to_html(escape=False, columns=["Date", "Doctor", "Surgery", "Hour", "Room"], index_names=False),
            unsafe_allow_html=True)

# ---------- Sidebar: Add Booking ----------
st.sidebar.header("Add Surgery Booking")
picked_date = st.sidebar.date_input("Date", value=date.today())
room_choice  = st.sidebar.radio("Room", ROOMS, horizontal=True)

# 30-minute slots 10:00–22:00 (no 22:30)
slots = [time(h, m) for h in range(10, 23) for m in (0, 30) if not (h == 22 and m == 30)]
sel_hour_str = st.sidebar.selectbox("Hour", [t.strftime("%H:%M") for t in slots])
sel_hour     = datetime.strptime(sel_hour_str, "%H:%M").time()

doctor_name   = st.sidebar.text_input("Doctor Name")
surgery_choice = st.sidebar.selectbox("Surgery Type", SURGERY_TYPES)

if st.sidebar.button("💾 Save Booking"):
    if not doctor_name:
        st.sidebar.error("Doctor name required.")
    elif check_overlap(load_bookings(), picked_date, room_choice, sel_hour):
        st.sidebar.error("Room already booked at this time.")
    else:
        record = {
            "Date":    pd.Timestamp(picked_date),
            "Doctor":  doctor_name.strip(),
            "Hour":    sel_hour.strftime("%H:%M"),
            "Surgery": surgery_choice,
            "Room":    room_choice,
            "Status":  "Booked",
        }
        append_booking(record)
        st.sidebar.success("Surgery booked successfully.")
        safe_rerun()
