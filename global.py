import streamlit as st
import pandas as pd
from datetime import datetime, date, time
from pathlib import Path
from streamlit_calendar import calendar

# -------------------------------------------------------------
# Configuration
# -------------------------------------------------------------
st.set_page_config(page_title="Surgery Booking Calendar", layout="wide")

DATA_FILE = "surgery_bookings.csv"
SURGERY_TYPES = [
    "Phaco", "PPV", "Pterygium", "Blepharoplasty",
    "Glaucoma OP", "KPL", "Trauma OP",
    "Enucleation", "Injection", "Other",
]
HALLS = ["Hall 1", "Hall 2"]

# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------

def load_bookings(path: str = DATA_FILE) -> pd.DataFrame:
    cols = ["Date", "Hall", "Doctor", "Hour", "Surgery", "Patient"]
    if Path(path).exists():
        df = pd.read_csv(path)
    else:
        df = pd.DataFrame(columns=cols)
    df = df.reindex(columns=cols)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df


def save_bookings(df: pd.DataFrame, path: str = DATA_FILE):
    df.to_csv(path, index=False)


def check_overlap(df: pd.DataFrame, booking_date: date, hall: str, hour: time) -> bool:
    """Return True if the hall+hour slot is already taken on that date."""
    if df.empty:
        return False
    dates = pd.to_datetime(df["Date"], errors="coerce")
    hours = pd.to_datetime(df["Hour"], format="%H:%M", errors="coerce").dt.time
    mask = (
        (dates.dt.date == booking_date) &
        (df["Hall"] == hall) &
        (hours == hour)
    )
    return mask.any()

# -------------------------------------------------------------
# Main UI
# -------------------------------------------------------------

st.title("🏥 Surgery Booking System")

bookings = load_bookings()

# -------- Calendar events --------
calendar_events = [
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
    "timeZone": "local",  # guarantee local date clicks, no UTC shift
    "headerToolbar": {
        "left": "prev,next today",
        "center": "title",
        "right": "dayGridMonth,timeGridWeek,timeGridDay",
    },
}

selected = calendar(events=calendar_events, options=calendar_options, key="surgery_calendar")

# -------- Handle day click --------
clicked_date: date | None = None
if isinstance(selected, dict) and selected.get("callback") == "dateClick":
    dc = selected.get("dateClick", {})
    raw_date = dc.get("dateStr") or dc.get("date")  # dateStr is always safe
    if raw_date:
        try:
            clicked_date = datetime.fromisoformat(str(raw_date)[:10]).date()
        except Exception:
            clicked_date = None

# -------------------------------------------------------------
# Booking panel
# -------------------------------------------------------------
if clicked_date:
    st.subheader(clicked_date.strftime("📅 %A, %d %B %Y"))

    day_df = bookings.loc[bookings["Date"].dt.date == clicked_date]
    if day_df.empty:
        st.info("No surgeries booked for this day yet.")
    else:
        st.table(day_df[["Hall", "Hour", "Doctor", "Surgery", "Patient"]].sort_values("Hour"))

    st.markdown("---")
    with st.form("booking_form", clear_on_submit=True):
        st.write("### ➕ Add Surgery Booking")
        hall = st.radio("Hall", HALLS, horizontal=True)
        col1, col2 = st.columns(2)
        with col1:
            doctor = st.text_input("Doctor Name")
            patient = st.text_input("Patient Name")
        with col2:
            hour = st.time_input("Time", value=time(9, 0))
            surgery = st.selectbox("Surgery Type", SURGERY_TYPES)
        save_btn = st.form_submit_button("Save Booking")

        if save_btn:
            if not doctor or not patient:
                st.error("Doctor and patient names are required.")
            elif check_overlap(bookings, clicked_date, hall, hour):
                st.error(f"{hall} already booked at {hour.strftime('%H:%M')}.")
            else:
                new_row = {
                    "Date": pd.Timestamp(clicked_date),
                    "Hall": hall,
                    "Doctor": doctor.strip(),
                    "Hour": hour.strftime("%H:%M"),
                    "Surgery": surgery,
                    "Patient": patient.strip(),
                }
                bookings = pd.concat([bookings, pd.DataFrame([new_row])], ignore_index=True)
                save_bookings(bookings)
                st.success("✅ Booking saved!")
                st.experimental_rerun()
