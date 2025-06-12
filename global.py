import streamlit as st
import pandas as pd
from datetime import date, datetime, time
from pathlib import Path

# -------------------------------------------------------------
# Streamlit configuration (must be first command)
# -------------------------------------------------------------
st.set_page_config(page_title="Global Eye Center _ Operation List", layout="wide")

# -------------------------------------------------------------
# Single CSV used for both active list and archive
# -------------------------------------------------------------
DATA_FILE = "Operation archive.csv"   # append‑on‑save and read on launch
FOOTER_IMAGE = "Global photo.jpg"

SURGERY_TYPES = [
    "Phaco", "PPV", "Pterygium", "Blepharoplasty",
    "Glaucoma OP", "KPL", "Trauma OP",
    "Enucleation", "Injection", "Squint OP", "Other",
]
HALLS = ["Hall 1", "Hall 2"]

# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------

def safe_rerun():
    """Trigger a refresh, regardless of Streamlit version."""
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


def save_and_append(record: dict, current_df: pd.DataFrame):
    """Append new booking to DataFrame and persist to the single CSV."""
    updated = pd.concat([current_df, pd.DataFrame([record])], ignore_index=True)
    updated.to_csv(DATA_FILE, index=False)
    return updated


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
# Sidebar – Add Booking
# -------------------------------------------------------------

st.title("Global Eye Center _ Operation List")

bookings = load_bookings()

st.sidebar.header("Add / Edit Booking")

picked_date = st.sidebar.date_input("Date", value=date.today())
hall_choice = st.sidebar.radio("Hall", HALLS, horizontal=True)

hour_options = [time(h, 0) for h in range(10, 23)]  # 10:00 … 22:00
hour_display = [h.strftime("%H:%M") for h in hour_options]
selected_hour_str = st.sidebar.selectbox("Hour", hour_display)
selected_hour = datetime.strptime(selected_hour_str, "%H:%M").time()

doctor_name = st.sidebar.text_input("Doctor Name")
surgery_choice = st.sidebar.selectbox("Surgery Type", SURGERY_TYPES)

if st.sidebar.button("💾 Save Booking"):
    if not doctor_name:
        st.sidebar.error("Doctor name required.")
    elif check_overlap(bookings, picked_date, hall_choice, selected_hour):
        st.sidebar.error("This timeslot is already booked for that hall.")
    else:
        record = {
            "Date": pd.Timestamp(picked_date),
            "Hall": hall_choice,
            "Doctor": doctor_name.strip(),
            "Hour": selected_hour.strftime("%H:%M"),
            "Surgery": surgery_choice,
        }
        bookings = save_and_append(record, bookings)
        st.sidebar.success("Saved!")
        safe_rerun()

# -------------------------------------------------------------
# Main pane – list by date
# -------------------------------------------------------------

if bookings.empty:
    st.info("No surgeries booked yet.")
else:
    for d in sorted(bookings["Date"].dt.date.unique()):
        day_df = bookings[bookings["Date"].dt.date == d].sort_values("Hour")
        with st.expander(d.strftime("📅 %A, %d %B %Y")):
            st.table(day_df[["Hall", "Hour", "Doctor", "Surgery"]])

# -------------------------------------------------------------
# Footer image
# -------------------------------------------------------------

if Path(FOOTER_IMAGE).exists():
    st.markdown("---")
    st.image(FOOTER_IMAGE, use_column_width=True)
