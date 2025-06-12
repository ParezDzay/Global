import streamlit as st
import pandas as pd
from datetime import date, time
from pathlib import Path
from streamlit_calendar import calendar

"""Surgery Booking App
======================
Main features
-------------
* **Full‑month calendar** (streamlit‑calendar)
* **Day click → booking panel**
* Two halls (Hall 1 / Hall 2) with collision checks
* CSV persistence (`surgery_bookings.csv`)
* Per‑day overview split by hall
"""

# --------------------------- CONFIG --------------------------- #
st.set_page_config(page_title="Surgery Booking Calendar", layout="wide")

DATA_FILE = "surgery_bookings.csv"
SURGERY_TYPES = [
    "Phaco", "PPV", "Pterygium", "Blepharoplasty",
    "Glaucoma OP", "KPL", "Trauma OP",
    "Enucleation", "Injection", "Other",
]
HALLS = ["Hall 1", "Hall 2"]

# ---------------------- STORAGE HELPERS ----------------------- #

def load_bookings(path: str = DATA_FILE) -> pd.DataFrame:
    """Load existing bookings or create an empty table with correct dtypes."""
    if Path(path).exists():
        df = pd.read_csv(path)
    else:
        df = pd.DataFrame()

    # Ensure all columns exist
    cols = ["Date", "Hall", "Doctor", "Hour", "Surgery", "Patient"]
    for c in cols:
        if c not in df.columns:
            df[c] = []

    # Coerce Date column to datetime regardless of content
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df[cols]


def save_bookings(df: pd.DataFrame, path: str = DATA_FILE):
    df.to_csv(path, index=False)


def check_overlap(df: pd.DataFrame, booking_date: date, hall: str, hour: time) -> bool:
    """Return True if another booking exists at the same hall & hour."""
    if df.empty or hall not in HALLS:
        return False
    # Safe datetime comparison
    dates = pd.to_datetime(df["Date"], errors="coerce")
    cond_day = dates.dt.date == booking_date
    cond_hall = df["Hall"] == hall
    cond_hour = pd.to_datetime(df["Hour"], format="%H:%M", errors="coerce").dt.time == hour
    return (cond_day & cond_hall & cond_hour).any()

# --------------------- MAIN UI COMPONENTS --------------------- #
st.title("🏥 Surgery Booking System")

bookings = load_bookings()

# Convert bookings to calendar events
calendar_events = [
    {
        "title": f"{row.Hall}: {row.Patient} ({row.Surgery})",
        "start": f"{row.Date.date()}T{row.Hour}",
        "end": f"{row.Date.date()}T{row.Hour}",
        "allDay": False,
    }
    for _, row in bookings.iterrows()
]

cal_options = {
    "initialView": "dayGridMonth",
    "height": "auto",
    "selectable": True,
    "headerToolbar": {
        "left": "prev,next today",
        "center": "title",
        "right": "dayGridMonth,timeGridWeek,timeGridDay",
    },
}

selected = calendar(events=calendar_events, options=cal_options, key="surgery_calendar")

# ------------------------ CALLBACK HANDLING ------------------- #

date_clicked: date | None = None
if isinstance(selected, dict) and selected.get("callback") == "dateClick":
    dc = selected.get("dateClick", {})
    raw = dc.get("date") or dc.get("dateStr")
    if raw:
        try:
            date_clicked = pd.to_datetime(raw).date()
        except Exception:
            date_clicked = None

# ------------------- BOOKING PANEL ---------------------------- #

if date_clicked:
    st.subheader(date_clicked.strftime("📅 %A, %d %B %Y"))

    # Daily overview (split by hall)
    day_df = bookings.loc[bookings["Date"].dt.date == date_clicked]

    for hall in HALLS:
        hall_df = day_df[day_df["Hall"] == hall]
        with st.expander(f"{hall} bookings ({len(hall_df)})", expanded=True):
            if hall_df.empty:
                st.write("_No surgeries scheduled._")
            else:
                st.table(hall_df[["Hour", "Doctor", "Surgery", "Patient"]].sort_values("Hour"))

    st.markdown("---")
    with st.form("booking_form", clear_on_submit=True):
        st.write("### ➕ Add New Booking")
        hall = st.radio("Choose Hall", HALLS, horizontal=True)

        col1, col2 = st.columns(2)
        with col1:
            doctor = st.text_input("Doctor Name")
            patient = st.text_input("Patient Name")
        with col2:
            hour = st.time_input("Hour of Surgery", value=time(9, 0))
            surgery = st.selectbox("Type of Surgery", SURGERY_TYPES)

        submit = st.form_submit_button("Book Surgery")

        if submit:
            # Validation & collision check
            if not doctor or not patient:
                st.error("Doctor and patient names are required.")
            elif check_overlap(bookings, date_clicked, hall, hour):
                st.error(f"{hall} already booked at {hour.strftime('%H:%M')}.")
            else:
                new_entry = {
                    "Date": pd.Timestamp(date_clicked),
                    "Hall": hall,
                    "Doctor": doctor.strip(),
                    "Hour": hour.strftime("%H:%M"),
                    "Surgery": surgery,
                    "Patient": patient.strip(),
                }
                bookings = pd.concat([bookings, pd.DataFrame([new_entry])], ignore_index=True)
                save_bookings(bookings)
                st.success("✅ Booking saved!")
                st.experimental_rerun()  # refresh calendar & table
