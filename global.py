import streamlit as st
import pandas as pd
from datetime import date, time
from pathlib import Path
from streamlit_calendar import calendar

"""Surgery Booking App — v2
===========================
* **Tab 1 ↠ Calendar** Book surgeries via month grid (click a day → form).
* **Tab 2 ↠ Surgeries List** See / filter every saved booking in a single table.

No more automatic hall expanders on the calendar page; daily bookings now appear in a plain table, while the full list lives in its own tab.
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
    """Return existing bookings, guaranteed with correct dtypes/columns."""
    cols = ["Date", "Hall", "Doctor", "Hour", "Surgery", "Patient"]
    if Path(path).exists():
        df = pd.read_csv(path)
    else:
        df = pd.DataFrame(columns=cols)
    df = df[cols]  # enforce order
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df


def save_bookings(df: pd.DataFrame, path: str = DATA_FILE):
    df.to_csv(path, index=False)


def check_overlap(df: pd.DataFrame, booking_date: date, hall: str, hour: time) -> bool:
    if df.empty:
        return False
    dates = pd.to_datetime(df["Date"], errors="coerce")
    cond = (
        (dates.dt.date == booking_date) &
        (df["Hall"] == hall) &
        (pd.to_datetime(df["Hour"], format="%H:%M", errors="coerce").dt.time == hour)
    )
    return cond.any()

# ------------------------------ UI ---------------------------- #
st.title("🏥 Surgery Booking System")

bookings = load_bookings()

tab_cal, tab_list = st.tabs(["🗓️ Calendar", "📋 Surgeries List"])

# ====================== TAB 1 — CALENDAR ===================== #
with tab_cal:
    cal_events = [
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

    selection = calendar(events=cal_events, options=cal_opts, key="calendar")

    clicked_date: date | None = None
    if isinstance(selection, dict) and selection.get("callback") == "dateClick":
        raw = selection.get("dateClick", {}).get("date") or selection.get("dateClick", {}).get("dateStr")
        if raw:
            try:
                clicked_date = pd.to_datetime(raw).date()
            except Exception:
                pass

    if clicked_date:
        st.subheader(clicked_date.strftime("📅 %A, %d %B %Y"))
        day_df = bookings.loc[bookings["Date"].dt.date == clicked_date]
        if day_df.empty:
            st.info("No surgeries booked for this day yet.")
        else:
            st.table(day_df.sort_values("Hour")[["Hour", "Hall", "Doctor", "Surgery", "Patient"]])

        with st.form("add_booking", clear_on_submit=True):
            st.write("### ➕ Add Surgery Booking")
            col1, col2 = st.columns(2)
            hall = st.radio("Hall", HALLS, horizontal=True)
            with col1:
                doctor = st.text_input("Doctor Name")
                patient = st.text_input("Patient Name")
            with col2:
                hour = st.time_input("Time", value=time(9, 0))
                surgery = st.selectbox("Surgery Type", SURGERY_TYPES)

            submit = st.form_submit_button("Save Booking")
            if submit:
                if not doctor or not patient:
                    st.error("Doctor and patient names are required.")
                elif check_overlap(bookings, clicked_date, hall, hour):
                    st.error(f"{hall} is already booked at {hour.strftime('%H:%M')}.")
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
                    st.success("✅ Booking saved.")
                    st.experimental_rerun()

# ==================== TAB 2 — SURGERY LIST =================== #
with tab_list:
    st.write("### All Booked Surgeries")

    if bookings.empty:
        st.warning("No surgeries have been booked yet.")
    else:
        # Add simple filters
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            filter_hall = st.selectbox("Filter by Hall", ["All"] + HALLS, index=0)
        with col_f2:
            docs = ["All"] + sorted(bookings["Doctor"].dropna().unique())
            filter_doc = st.selectbox("Filter by Doctor", docs, index=0)
        with col_f3:
            filter_type = st.selectbox("Filter by Surgery Type", ["All"] + SURGERY_TYPES, index=0)

        list_df = bookings.copy()
        if filter_hall != "All":
            list_df = list_df[list_df["Hall"] == filter_hall]
        if filter_doc != "All":
            list_df = list_df[list_df["Doctor"] == filter_doc]
        if filter_type != "All":
            list_df = list_df[list_df["Surgery"] == filter_type]

        list_df = list_df.sort_values(["Date", "Hour"]).reset_index(drop=True)
        list_df[["Date"]] = list_df[["Date"]].apply(lambda x: x.dt.strftime("%Y-%m-%d"))
        st.dataframe(list_df, use_container_width=True)

        csv = list_df.to_csv(index=False).encode()
        st.download_button("Download CSV", csv, "surgery_bookings_filtered.csv", "text/csv")
