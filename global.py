import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
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
        else:
            st.error("Incorrect password")
    st.stop()

# ---------- Streamlit config & Header ----------
st.set_page_config(page_title="Global Eye Center (Operation List)", layout="wide")
BASE_DIR     = Path(__file__).parent if "__file__" in globals() else Path.cwd()
HEADER_IMAGE = BASE_DIR / "Global photo.jpg"
if HEADER_IMAGE.exists():
    st.image(str(HEADER_IMAGE), width=250)
st.title("Global Eye Center (Operation List)")

# ---------- Google Sheets Setup ----------
# Your sheet ID
SHEET_ID = "1e1RZvdlYDBCdlxtumkx5rrk6sYdKOrmxEutSdz5xUgc"

# Cache the sheet connection to avoid repeated metadata calls
def _get_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1

@st.cache_resource
def get_sheet():
    return _get_sheet()

sheet = get_sheet()

# ---------- Data Functions ----------
def load_bookings() -> pd.DataFrame:
    """
    Fetch rows from Google Sheet and return a DataFrame with typed Date and Hour.
    """
    records = sheet.get_all_records()  # reads first row as header
    df = pd.DataFrame(records)
    # Ensure expected columns
    expected = ["Date", "Doctor", "Hour", "Surgery", "Room"]
    df = df.reindex(columns=expected)
    # Convert types
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Hour"] = pd.to_datetime(df["Hour"], format="%H:%M", errors="coerce").dt.strftime("%H:%M")
    return df


def append_booking(rec: dict):
    """
    Append one new booking to the sheet.
    rec: keys = Date, Doctor, Hour, Surgery, Room
    """
    sheet.append_row([
        rec["Date"],
        rec["Doctor"],
        rec["Hour"],
        rec["Surgery"],
        rec["Room"],
    ], value_input_option="USER_ENTERED")

# ---------- Check overlap ----------
def check_overlap(df: pd.DataFrame, d: date, room: str, hr: time) -> bool:
    if df.empty:
        return False
    target_date = pd.Timestamp(d)
    mask = (
        (df["Date"] == target_date) &
        (df["Room"] == room) &
        (df["Hour"] == hr)
    )
    return mask.any()

# ---------- Doctor icon ----------
def doctor_icon_html():
    return '<span style="font-size:16px; margin-right:6px;">🩺</span>'

# ---------- Safe rerun helper ----------
def safe_rerun():
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    elif hasattr(st, "rerun"):
        st.rerun()
    else:
        st.stop()

# ---------- UI Constants ----------
SURGERY_TYPES = [
    "Phaco", "PPV", "Pterygium", "Blepharoplasty",
    "Glaucoma OP", "KPL", "Trauma OP", "Enucleation",
    "Injection", "Squint OP", "DCR", "SOR", 
    "Other",
]
ROOMS = ["Room 1", "Room 2"]

# ---------- Main Tabs ----------
tabs = st.tabs(["📋 Operation Booked", "📂 Operation Archive"])

# Tab: Upcoming Bookings
with tabs[0]:
    bookings  = load_bookings()
    yesterday = pd.Timestamp(date.today() - timedelta(days=1))
    upcoming  = bookings[bookings["Date"] > yesterday]

    st.subheader("📋 Operation Booked")
    if upcoming.empty:
        st.info("No upcoming surgeries booked.")
    else:
        disp = (
            upcoming
            .drop_duplicates(subset=["Date", "Hour", "Room"])  
            .sort_values(["Date", "Hour"])
        )
        for d in disp["Date"].dt.date.unique():
            day_df = disp[disp["Date"].dt.date == d]
            with st.expander(d.strftime("📅 %A, %d %B %Y")):
                dd = day_df[["Doctor","Surgery","Hour","Room"]].reset_index(drop=True)
                dd.index = range(1, len(dd)+1)
                st.dataframe(dd, use_container_width=True)

# Tab: Archived Bookings
with tabs[1]:
    bookings  = load_bookings()
    yesterday = pd.Timestamp(date.today() - timedelta(days=1))
    archive   = bookings[bookings["Date"] <= yesterday]

    st.subheader("📂 Operation Archive")
    if archive.empty:
        st.info("No archived records found.")
    else:
        disp = (
            archive
            .drop_duplicates(subset=["Date","Hour","Room"] )
            .sort_values(["Date","Hour"], ascending=False)
            .copy()
        )
        disp["Date"] = disp["Date"].dt.strftime("%Y-%m-%d")
        disp.reset_index(drop=True, inplace=True)
        disp.index += 1
        disp["Doctor"] = disp["Doctor"].apply(lambda x: f'{doctor_icon_html()}{x}')
        st.markdown(
            disp.to_html(escape=False, columns=["Date","Doctor","Surgery","Hour","Room"]),
            unsafe_allow_html=True
        )

# ---------- Sidebar: Add Booking Form ----------
st.sidebar.header("Add Surgery Booking")
picked_date    = st.sidebar.date_input("Date", value=date.today())
room_choice    = st.sidebar.radio("Room", ROOMS, horizontal=True)

# 30-minute intervals from 10:00 to 22:00
slot_hours = []
for hr in range(10, 23):
    slot_hours.append(time(hr, 0))
    if hr != 22:
        slot_hours.append(time(hr, 30))

sel_hour_str   = st.sidebar.selectbox("Hour", [h.strftime("%H:%M") for h in slot_hours])
sel_hour       = datetime.strptime(sel_hour_str, "%H:%M").time()
doctor_name    = st.sidebar.text_input("Doctor Name")
surgery_choice = st.sidebar.selectbox("Surgery Type", SURGERY_TYPES)

if st.sidebar.button("💾 Save Booking"):
    if not doctor_name:
        st.sidebar.error("Doctor name required.")
    elif check_overlap(bookings, picked_date, room_choice, sel_hour):
        st.sidebar.error("Room already booked at this time.")
    else:
        record = {
            "Date":    picked_date.isoformat(),
            "Doctor":  doctor_name.strip(),
            "Hour":    sel_hour_str,
            "Surgery": surgery_choice,
            "Room":    room_choice,
        }
        append_booking(record)
        st.sidebar.success("Surgery booked successfully.")
        safe_rerun()
