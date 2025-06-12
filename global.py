import streamlit as st
import pandas as pd
from datetime import date, datetime, time
from pathlib import Path

# -------------------------------------------------------------
# Streamlit configuration (first command!)
# -------------------------------------------------------------
st.set_page_config(page_title="Global Eye Center _ Operation List", layout="wide")

# -------------------------------------------------------------
# Paths & constants
# -------------------------------------------------------------
# Guarantee the CSV lives beside this script, regardless of the CWD
BASE_DIR = Path(__file__).parent if "__file__" in globals() else Path.cwd()
DATA_FILE = BASE_DIR / "Operation archive.csv"
HEADER_IMAGE = BASE_DIR / "Global photo.jpg"

SURGERY_TYPES = [
    "Phaco", "PPV", "Pterygium", "Blepharoplasty",
    "Glaucoma OP", "KPL", "Trauma OP",
    "Enucleation", "Injection", "Squint OP", "Other",
]
HALLS = ["Hall 1", "Hall 2"]

# -------------------------------------------------------------
# Load / Save helpers
# -------------------------------------------------------------

def load_bookings() -> pd.DataFrame:
    cols = ["Date", "Hall", "Doctor", "Hour", "Surgery"]
    if DATA_FILE.exists():
        df = pd.read_csv(DATA_FILE)
    else:
        df = pd.DataFrame(columns=cols)
        df.to_csv(DATA_FILE, index=False)
    df = df.reindex(columns=cols)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df


def append_booking(record: dict):
    """Append a new record directly to disk (no risk of race)."""
    header_needed = not DATA_FILE.exists() or DATA_FILE.stat().st_size == 0
    pd.DataFrame([record]).to_csv(DATA_FILE, mode="a", header=header_needed, index=False)


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
# Header (image + title)
# -------------------------------------------------------------

if HEADER_IMAGE.exists():
    st.image(str(HEADER_IMAGE), width=250)

st.title("Global Eye Center _ Operation List")

# -------------------------------------------------------------
# Sidebar – Add Booking
# -------------------------------------------------------------

bookings = load_bookings()

st.sidebar.header("Add / Edit Booking")

picked_date = st.sidebar.date_input("Date", value=date.today())
hall_choice = st.sidebar.radio("Hall", HALLS, horizontal=True)

hour_opts = [time(h, 0) for h in range(10, 23)]
selected_hour = st.sidebar.selectbox("Hour", [t.strftime("%H:%M") for t in hour_opts])
selected_hour_time = datetime.strptime(selected_hour, "%H:%M").time()

doctor_name = st.sidebar.text_input("Doctor Name")
surgery_choice = st.sidebar.selectbox("Surgery Type", SURGERY_TYPES)

if st.sidebar.button("💾 Save Booking"):
    if not doctor_name:
        st.sidebar.error("Doctor name required.")
    elif check_overlap(bookings, picked_date, hall_choice, selected_hour_time):
        st.sidebar.error("This timeslot is already booked for that hall.")
    else:
        rec = {
            "Date": pd.Timestamp(picked_date),
            "Hall": hall_choice,
            "Doctor": doctor_name.strip(),
            "Hour": selected_hour_time.strftime("%H:%M"),
            "Surgery": surgery_choice,
        }
        append_booking(rec)
        bookings = pd.concat([bookings, pd.DataFrame([rec])], ignore_index=True)
        st.sidebar.success("Saved!")("Saved!")

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
