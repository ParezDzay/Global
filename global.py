import streamlit as st
import pandas as pd
from datetime import datetime, date, time
from pathlib import Path
from streamlit_calendar import calendar

"""Surgery Booking — Calendar & Day View
========================================
* **Calendar page** — default view, click a day → navigates to day view.
* **Day view** — URL query param `?date=YYYY-MM-DD`; shows bookings + add form.
* **Back to calendar** button clears the param.
"""

# --------------------------- CONFIG --------------------------- #
st.set_page_config(page_title="Surgery Booking", layout="wide")

DATA_FILE = "surgery_bookings.csv"
SURGERY_TYPES = [
    "Phaco", "PPV", "Pterygium", "Blepharoplasty",
    "Glaucoma OP", "KPL", "Trauma OP",
    "Enucleation", "Injection", "Other",
]
HALLS = ["Hall 1", "Hall 2"]

# ---------------------- STORAGE HELPERS ----------------------- #

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

# ---------------------- ROUTING LOGIC ------------------------- #
params = st.experimental_get_query_params()
selected_date_str = params.get("date", [None])[0]

try:
    selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date() if selected_date_str else None
except Exception:
    selected_date = None

bookings = load_bookings()

# ====================== DAY VIEW ============================= #
if selected_date:
    st.header(selected_date.strftime("📅 %A, %d %B %Y"))

    day_df = bookings.loc[bookings["Date"].dt.date == selected_date]
    if day_df.empty:
        st.info("No surgeries booked for this day yet.")
    else:
        st.table(day_df[["Hall", "Hour", "Doctor", "Surgery", "Patient"]].sort_values("Hour"))

    st.markdown("---")
    with st.form("add_booking", clear_on_submit=True):
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
            elif check_overlap(bookings, selected_date, hall, hour):
                st.error(f"{hall} already booked at {hour.strftime('%H:%M')}.")
            else:
                new = {
                    "Date": pd.Timestamp(selected_date),
                    "Hall": hall,
                    "Doctor": doctor.strip(),
                    "Hour": hour.strftime("%H:%M"),
                    "Surgery": surgery,
                    "Patient": patient.strip(),
                }
                bookings = pd.concat([bookings, pd.DataFrame([new])], ignore_index=True)
                save_bookings(bookings)
                st.success("✅ Booking saved!")
                st.experimental_rerun()

    # Back button clears query params
    if st.button("← Back to Calendar"):
        st.experimental_set_query_params()
        st.experimental_rerun()

# ====================== CALENDAR VIEW ======================== #
else:
    st.title("🏥 Surgery Booking Calendar")

    # Convert bookings to FullCalendar events
    events = [
        {
            "title": f"{row.Hall}: {row.Patient} ({row.Surgery})",
            "start": f"{row.Date.date()}T{row.Hour}",
            "end": f"{row.Date.date()}T{row.Hour}",
            "allDay": False,
        }
        for _, row in bookings.iterrows()
    ]

    cal_opts = {
        "initialView": "dayGridMonth",
        "height": "auto",
        "selectable": True,
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay",
        },
    }

    sel = calendar(events=events, options=cal_opts, key="surgery_calendar")

    # Handle date click → set query param then rerun
    if isinstance(sel, dict) and sel.get("callback") == "dateClick":
        raw = sel.get("dateClick", {}).get("date") or sel.get("dateClick", {}).get("dateStr")
        if raw:
            try:
                target = pd.to_datetime(raw).date()
                st.experimental_set_query_params(date=target.isoformat())
                st.experimental_rerun()
            except Exception:
                pass
