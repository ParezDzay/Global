import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta
from pathlib import Path
from streamlit_calendar import calendar

# First Streamlit call – MUCH stay on top
st.set_page_config(page_title="Surgery Booking Calendar", layout="wide")

"""Surgery Booking App — sidebar entry + fixed date shift
--------------------------------------------------------
* Click a calendar day → details table below + **booking form in sidebar**.
* Removes Patient Name (only Doctor, Hall, Hour, Surgery).
* Surgery list updated (includes *Squint OP*).
* Hour selector limited to **10 AM – 10 PM**.
* Date shift bug solved by slicing the first 10 chars of the ISO string, no tz math.
"""

DATA_FILE = "surgery_bookings.csv"
SURGERY_TYPES = [
    "Phaco", "PPV", "Pterygium", "Blepharoplasty",
    "Glaucoma OP", "KPL", "Trauma OP",
    "Enucleation", "Injection", "Squint OP", "Other",
]
HALLS = ["Hall 1", "Hall 2"]

# ---------- helpers ---------- #

def safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


def load_bookings(path: str = DATA_FILE) -> pd.DataFrame:
    cols = ["Date", "Hall", "Doctor", "Hour", "Surgery"]
    if Path(path).exists():
        df = pd.read_csv(path)
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
    dates = df["Date"].dt.date == d
    halls = df["Hall"] == hall
    hours = pd.to_datetime(df["Hour"], format="%H:%M", errors="coerce").dt.time == hr
    return (dates & halls & hours).any()

# ---------- UI ---------- #

st.title("🏥 Surgery Booking System")

bookings = load_bookings()

# Calendar events
cal_events = [
    {
        "title": f"{row.Hall}: {row.Doctor} ({row.Surgery})",
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
    "timeZone": "local",
    "headerToolbar": {
        "left": "prev,next today",
        "center": "title",
        "right": "dayGridMonth,timeGridWeek,timeGridDay",
    },
}

sel = calendar(events=cal_events, options=cal_opts, key="surgery_calendar")

# Parse day click – simply take first 10 chars (YYYY-MM-DD)
clicked_date: date | None = None
if isinstance(sel, dict) and sel.get("callback") == "dateClick":
    raw = sel.get("dateClick", {}).get("dateStr") or sel.get("dateClick", {}).get("date")
    if raw:
        try:
            clicked_date = datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
        except Exception:
            clicked_date = None

# ---------- Sidebar booking form ---------- #
st.sidebar.header("➕ Book Surgery")
if clicked_date:
    st.sidebar.write(f"**Selected Day:** {clicked_date.strftime('%d %B %Y')}")
    hall_sb = st.sidebar.radio("Hall", HALLS, horizontal=True)

    # Time selector limited 10:00 ‑ 22:00, 30‑min steps
    times = [
        (datetime.combine(date.today(), time(10, 0)) + timedelta(minutes=30*i)).time()
        for i in range(0, 24)  # 12 hours * 2 slots per hour
    ]
    hour_sb = st.sidebar.selectbox("Hour", [t.strftime("%H:%M") for t in times])

    doctor_sb = st.sidebar.text_input("Doctor Name")
    surgery_sb = st.sidebar.selectbox("Surgery Type", SURGERY_TYPES)
    save_sidebar = st.sidebar.button("Save Booking")

    if save_sidebar:
        hr_time = datetime.strptime(hour_sb, "%H:%M").time()
        if not doctor_sb:
            st.sidebar.error("Doctor name required.")
        elif check_overlap(bookings, clicked_date, hall_sb, hr_time):
            st.sidebar.error("Timeslot already booked for this hall.")
        else:
            new_row = {
                "Date": pd.Timestamp(clicked_date),
                "Hall": hall_sb,
                "Doctor": doctor_sb.strip(),
                "Hour": hr_time.strftime("%H:%M"),
                "Surgery": surgery_sb,
            }
            bookings = pd.concat([bookings, pd.DataFrame([new_row])], ignore_index=True)
            save_bookings(bookings)
            st.sidebar.success("Saved!")
            safe_rerun()
else:
    st.sidebar.info("Click a day on the calendar first.")

# ---------- Day details below calendar ---------- #
if clicked_date:
    st.subheader(clicked_date.strftime("📅 %A, %d %B %Y"))
    day_df = bookings[bookings["Date"].dt.date == clicked_date]
    if day_df.empty:
        st.info("No surgeries booked for this day yet.")
    else:
        st.table(day_df.sort_values("Hour")[["Hall", "Hour", "Doctor", "Surgery"]])
