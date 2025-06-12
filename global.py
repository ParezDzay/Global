import streamlit as st
import pandas as pd
from datetime import date, datetime, time
from pathlib import Path

# -------------------------------------------------------------
# Streamlit configuration (must be first command)
# -------------------------------------------------------------
st.set_page_config(page_title="Surgery Booking", layout="wide")

DATA_FILE = "surgery_bookings.csv"
SURGERY_TYPES = [
    "Phaco", "PPV", "Pterygium", "Blepharoplasty",
    "Glaucoma OP", "KPL", "Trauma OP",
    "Enucleation", "Injection", "Squint OP", "Other",
]
HALLS = ["Hall 1", "Hall 2"]

# -------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------

def safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


def load_bookings() -> pd.DataFrame:
    cols = ["Date", "Hall", "Doctor", "Hour", "Surgery"]
    if Path(DATA_FILE).exists():
        df = pd.read_csv(DATA_FILE)
    else:
        df = pd.DataFrame(columns=cols)
    df = df.reindex(columns=cols)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df


def save_bookings(df: pd.DataFrame):
    df.to_csv(DATA_FILE, index=False)


def check_overlap(df: pd.DataFrame, d: date, hall: str, hr: time) -> bool:
    if df.empty:
        return False
    mask = (
        (df["Date"].dt.date == d) &
        (df["Hall"] == hall) &
        (pd.to_datetime(df["Hour"], format="%H:%M", errors="coerce").dt.time == hr)
    )
    return mask.any()

# -------------------------------------------------------------
# UI – Sidebar booking form
# -------------------------------------------------------------

st.title("🏥 Surgery Booking System – List View")

bookings = load_bookings()

st.sidebar.header("Add / Edit Booking")

picked_date = st.sidebar.date_input("Date", value=date.today())
hall_choice = st.sidebar.radio("Hall", HALLS, horizontal=True)

hour_slots = [time(h, 0) for h in range(10, 23)]  # 10:00 through 22:00 inclusive
hour_choice = st.sidebar.selectbox("Hour", [t.strftime("%H:%M") for t in hour_slots])
hour_choice_time = datetime.strptime(hour_choice, "%H:%M").time()

doctor_name = st.sidebar.text_input("Doctor Name")
surgery_choice = st.sidebar.selectbox("Surgery Type", SURGERY_TYPES)

if st.sidebar.button("💾 Save Booking"):
    if not doctor_name:
        st.sidebar.error("Doctor name required.")
    elif check_overlap(bookings, picked_date, hall_choice, hour_choice_time):
        st.sidebar.error("This timeslot is already booked for that hall.")
    else:
        new_rec = {
            "Date": pd.Timestamp(picked_date),
            "Hall": hall_choice,
            "Doctor": doctor_name.strip(),
            "Hour": hour_choice_time.strftime("%H:%M"),
            "Surgery": surgery_choice,
        }
        bookings = pd.concat([bookings, pd.DataFrame([new_rec])], ignore_index=True)
        save_bookings(bookings)
        st.sidebar.success("Saved!")
        safe_rerun()

# -------------------------------------------------------------
# UI – Main pane listing
# -------------------------------------------------------------

if bookings.empty:
    st.info("No surgeries booked yet.")
else:
    for d in sorted(bookings["Date"].dt.date.unique()):
        day_bookings = bookings[bookings["Date"].dt.date == d].sort_values("Hour")
        with st.expander(d.strftime("📅 %A, %d %B %Y"), expanded=(d == picked_date)):
            st.table(day_bookings[["Hall", "Hour", "Doctor", "Surgery"]])
