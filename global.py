import streamlit as st
import pandas as pd
from datetime import datetime, date, time
from pathlib import Path
from streamlit_calendar import calendar

# --------------------------- CONFIG --------------------------- #

st.set_page_config(page_title="Surgery Booking Calendar", layout="wide")

DATA_FILE = "surgery_bookings.csv"
SURGERY_TYPES = [
    "Phaco", "PPV", "Pterygium", "Blepharoplasty",
    "Glaucoma OP", "KPL", "Trauma OP",
    "Enucleation", "Injection", "Other",
]

# ---------------------- STORAGE HELPERS ----------------------- #

def load_bookings(path: str = DATA_FILE) -> pd.DataFrame:
    if Path(path).exists():
        return pd.read_csv(path, parse_dates=["Date"])
    return pd.DataFrame(columns=["Date", "Hall", "Doctor", "Hour", "Surgery", "Patient"])


def save_bookings(df: pd.DataFrame, path: str = DATA_FILE):
    df.to_csv(path, index=False)


def check_overlap(df: pd.DataFrame, booking_date: date, hall: str, hour: time) -> bool:
    """Return True if another booking exists at same hall & hour."""
    cond_day = df["Date"].dt.date == booking_date
    cond_hall = df["Hall"] == hall
    cond_hour = pd.to_datetime(df["Hour"], format="%H:%M").dt.time == hour
    return (cond_day & cond_hall & cond_hour).any()

# --------------------- MAIN UI COMPONENTS --------------------- #
st.title("🏥 Surgery Booking System")

bookings = load_bookings()

# Force Date column to datetime even for non-empty cases
if not bookings.empty:
    bookings["Date"] = pd.to_datetime(bookings["Date"], errors="coerce")

# Convert bookings to calendar events
events = [
    {
        "title": f"{row.Hall}: {row.Patient} ({row.Surgery})",
        "start": f"{row.Date.date()}T{row.Hour}",
        "end": f"{row.Date.date()}T{row.Hour}",
        "allDay": False,
    }
    for _, row in bookings.iterrows()
]

calendar_options = {
    "initialView": "dayGridMonth",
    "height": "auto",
    "selectable": True,
    # enable dateClick callback implicitly
    "headerToolbar": {
        "left": "prev,next today",
        "center": "title",
        "right": "dayGridMonth,timeGridWeek,timeGridDay",
    },
}

selected = calendar(events=events, options=calendar_options, key="surgery_calendar")

# ------------------------ CLICK LOGIC ------------------------- #

date_clicked: date | None = None

if selected and isinstance(selected, dict):
    cb_type = selected.get("callback")
    if cb_type == "dateClick":
        # Support both old (<0.5) and new (>=0.5) versions of streamlit-calendar
        dc = selected.get("dateClick", {})
        raw_date = dc.get("date") or dc.get("dateStr")  # fallback
        if raw_date:
            try:
                date_clicked = pd.to_datetime(raw_date).date()
            except Exception:
                date_clicked = None

# ------------------- BOOKING PANEL ---------------------------- #

if date_clicked:
    st.subheader(date_clicked.strftime("📅 %A, %d %B %Y"))

    # Robust filtering even on empty DataFrame or non‑datetime column
    if bookings.empty or "Date" not in bookings.columns or bookings["Date"].dtype.kind != "M":
        day_df = pd.DataFrame(columns=["Hall", "Hour", "Doctor", "Surgery", "Patient"])
    else:
        day_df = bookings.loc[bookings["Date"].dt.date == date_clicked]

    if day_df.empty:
        st.info("No bookings for this day yet.")
    else:
        st.table(day_df[["Hall", "Hour", "Doctor", "Surgery", "Patient"]])

    st.markdown("---")
    with st.form("booking_form", clear_on_submit=True):
        st.write("### Add New Booking")
        hall = st.radio("Choose Hall", ["Hall 1", "Hall 2"], horizontal=True)

        col1, col2 = st.columns(2)
        with col1:
            doctor = st.text_input("Doctor Name")
            patient = st.text_input("Patient Name")
        with col2:
            hour = st.time_input("Hour of Booking", value=time(9, 0))
            surgery = st.selectbox("Type of Surgery", SURGERY_TYPES)

        submit = st.form_submit_button("Book Surgery")

        if submit:
            if not doctor or not patient:
                st.error("Doctor and patient names are required.")
            elif check_overlap(bookings, date_clicked, hall, hour):
                st.error(f"{hall} is already booked at {hour.strftime('%H:%M')}. Choose another time or hall.")
            else:
                new_entry = {
                    "Date": pd.Timestamp(date_clicked),
                    "Hall": hall,
                    "Doctor": doctor,
                    "Hour": hour.strftime("%H:%M"),
                    "Surgery": surgery,
                    "Patient": patient,
                }
                bookings = pd.concat([bookings, pd.DataFrame([new_entry])], ignore_index=True)
                save_bookings(bookings)
                st.success("✅ Booking saved! Click any other date or refresh to see the calendar update.")
