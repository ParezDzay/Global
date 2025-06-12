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
    "Enucleation", "Injection", "Other"
]

# ---------------------- STORAGE HELPERS ----------------------- #
def load_bookings(path: str = DATA_FILE) -> pd.DataFrame:
    if Path(path).exists():
        df = pd.read_csv(path, parse_dates=["Date"])
        return df
    return pd.DataFrame(columns=["Date", "Hall", "Doctor", "Hour", "Surgery", "Patient"])

def save_bookings(df: pd.DataFrame, path: str = DATA_FILE):
    df.to_csv(path, index=False)

def check_overlap(df: pd.DataFrame, booking_date: date, hall: str, hour: time) -> bool:
    """Return True if another booking exists at same hall & hour."""
    same_day = df["Date"].dt.date == booking_date
    same_hall = df["Hall"] == hall
    same_hour = pd.to_datetime(df["Hour"]).dt.time == hour
    return (same_day & same_hall & same_hour).any()

# --------------------- MAIN UI COMPONENTS --------------------- #
st.title("🏥 Surgery Booking System")
bookings = load_bookings()

# Convert bookings to calendar events
events = [
    {
        "title": f"{row.Hall}: {row.Patient} ({row.Surgery})",
        "start": f"{row.Date.date()}T{row.Hour}",
        "end": f"{row.Date.date()}T{row.Hour}"
    }
    for _, row in bookings.iterrows()
]

calendar_options = {
    "initialView": "dayGridMonth",
    "height": "auto",
    "selectable": True,
    "headerToolbar": {
        "left": "prev,next today",
        "center": "title",
        "right": "dayGridMonth,timeGridWeek,timeGridDay"
    }
}

selected = calendar(events=events, options=calendar_options, key="surgery_calendar")

# calendar returns on date click under ['dateStr']
date_clicked = None
if selected and "dateStr" in selected:
    date_clicked = datetime.fromisoformat(selected["dateStr"]).date()

if date_clicked:
    st.subheader(f"Bookings for {date_clicked.strftime('%B %d, %Y')}")
    day_df = bookings[bookings["Date"].dt.date == date_clicked]
    if day_df.empty:
        st.info("No bookings for this day yet.")
    else:
        st.table(day_df[["Hall", "Hour", "Doctor", "Surgery", "Patient"]])

    st.markdown("---")
    with st.form(key="booking_form", clear_on_submit=True):
        st.write("### Add New Booking")
        hall = st.radio("Choose Hall", ["Hall 1", "Hall 2"], horizontal=True)
        col1, col2 = st.columns(2)
        with col1:
            doctor = st.text_input("Doctor Name")
            patient = st.text_input("Patient Name")
        with col2:
            hour = st.time_input("Hour of Booking", value=time(9, 0))
            surgery = st.selectbox("Type of Surgery", SURGERY_TYPES)

        submitted = st.form_submit_button("Book Surgery")

        if submitted:
            # Validation
            if not doctor or not patient:
                st.error("Doctor and patient names are required.")
            elif check_overlap(bookings, date_clicked, hall, hour):
                st.error(f"{hall} is already booked at {hour}. Choose another time or hall.")
            else:
                new_row = {
                    "Date": pd.Timestamp(date_clicked),
                    "Hall": hall,
                    "Doctor": doctor,
                    "Hour": hour.strftime("%H:%M"),
                    "Surgery": surgery,
                    "Patient": patient
                }
                bookings = pd.concat([bookings, pd.DataFrame([new_row])], ignore_index=True)
                save_bookings(bookings)
                st.success("Booking saved! Refresh calendar to see the update.")
