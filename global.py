import streamlit as st
import pandas as pd
from datetime import date, datetime, time, timedelta
from pathlib import Path

# --------------- MUST be first Streamlit call ----------------
st.set_page_config(page_title="Surgery Booking", layout="wide")

"""Surgery Booking App – list view only
======================================
• Removes the calendar: the main pane now just lists surgeries.
• Sidebar hosts the **Add Booking** form.
• Hour selector: every 1 h, 10 AM → 10 PM.
• No patient name field. (Columns: Date, Hall, Hour, Doctor, Surgery)
"""

DATA_FILE = "surgery_bookings.csv"
SURGERY_TYPES = [
    "Phaco", "PPV", "Pterygium", "Blepharoplasty",
    "Glaucoma OP", "KPL", "Trauma OP",
    "Enucleation", "Injection", "Squint OP", "Other",
]
HALLS = ["Hall 1", "Hall 2"]

# ----------------------- Helpers -----------------------------

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

# ----------------------- UI -----------------------------

st.title("🏥 Surgery Booking System (List View)")

bookings = load_bookings()

# Sidebar — Add Booking
st.sidebar.header("➕ Add / Edit Booking")

# Date picker defaults to today; allow choosing any date
chosen_date = st.sidebar.date_input("Date", value=date.today())
hall_sel = st.sidebar.radio("Hall", HALLS, horizontal=True)

# Hour dropdown 10:00‑22:00 step 1 h
hour_slots = [time(h, 0) for h in range(10, 22 + 1)]
hour_display = [t.strftime("%H:%M") for t in hour_slots]
hour_sel_str = st.sidebar.selectbox("Hour", hour_display)
hour_sel = datetime.strptime(hour_sel_str, "%H:%M").time()

doctor_sel = st.sidebar.text_input("Doctor Name")
surg_sel = st.sidebar.selectbox("Surgery Type", SURGERY_TYPES)

if st.sidebar.button("Save Booking"):
    if not doctor_sel:
        st.sidebar.error("Doctor name required.")
    elif check_overlap(bookings, chosen_date, hall_sel, hour_sel):
        st.sidebar.error("This timeslot is already booked for that hall.")
    else:
        new = {
            "Date": pd.Timestamp(chosen_date),
            "Hall": hall_sel,
            "Doctor": doctor_sel.strip(),
            "Hour": hour_sel.strftime("%H:%M"),
            "Surgery": surg_sel,
        }
        bookings = pd.concat([bookings, pd.DataFrame([new])], ignore_index=True)
        save_bookings(bookings)
        st.sidebar.success("Saved!")
        safe_rerun()

# ----------------------- Main Pane -----------------------------

if bookings.empty:
    st.info("No surgeries booked yet.")
else:
    # Grouped display: list dates; click to expand
    for d in sorted(bookings["Date"].dt.date.unique()):
        day_df = bookings[bookings["Date"].dt.date == d].sort_values("Hour")
        with st.expander(d.strftime("📅 %A, %d %B %Y"), expanded=(d == chosen_date)):
            st.table(day_df[["Hall", "Hour", "Doctor", "Surgery"]])
