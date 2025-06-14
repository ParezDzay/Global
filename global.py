import streamlit as st
import pandas as pd
import requests, base64, os
from datetime import date, datetime, time, timedelta
from pathlib import Path

# ---------- Simple Password Protection ----------
PASSWORD = "1122"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    pwd = st.text_input("Enter password", type="password")
    login_button = st.button("Login")
    if login_button:
        if pwd == PASSWORD:
            st.session_state.authenticated = True
        else:
            st.error("Incorrect password")
    st.stop()

# ---------- Streamlit config ----------
st.set_page_config(page_title="Global Eye Center (Operation List)", layout="wide")

# ---------- Constants and Paths ----------
BASE_DIR = Path(__file__).parent if "__file__" in globals() else Path.cwd()
DATA_FILE = BASE_DIR / "Operation Archive.csv"
HEADER_IMAGE = BASE_DIR / "Global photo.jpg"

SURGERY_TYPES = [
    "Phaco", "PPV", "Pterygium", "Blepharoplasty",
    "Glaucoma OP", "KPL", "Trauma OP", "Enucleation",
    "Injection", "Squint OP", "Other",
]
ROOMS = ["Room 1", "Room 2"]

# ---------- GitHub push function ----------
def push_to_github(file_path, commit_message):
    try:
        token = st.secrets["github"]["token"]
        username = st.secrets["github"]["username"]
        repo = st.secrets["github"]["repo"]
        branch = st.secrets["github"]["branch"]
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        encoded_content = base64.b64encode(content.encode()).decode()
        filename = os.path.basename(file_path)
        url = f"https://api.github.com/repos/{username}/{repo}/contents/{filename}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        response = requests.get(url, headers=headers)
        sha = response.json().get("sha") if response.status_code == 200 else None
        payload = {"message": commit_message, "content": encoded_content, "branch": branch}
        if sha:
            payload["sha"] = sha
        res = requests.put(url, headers=headers, json=payload)
        if res.status_code in [200, 201]:
            st.sidebar.success("✅ Operation Archive pushed to GitHub")
        else:
            st.sidebar.error(f"❌ GitHub Push Failed: {res.status_code} — {res.json().get('message')}")
    except Exception as e:
        st.sidebar.error(f"❌ GitHub Error: {e}")

# ---------- Safe rerun helper ----------
def safe_rerun():
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    elif hasattr(st, "rerun"):
        st.rerun()
    else:
        st.stop()

# ---------- Load bookings ----------
def load_bookings() -> pd.DataFrame:
    expected_cols = ["Date", "Doctor", "Hour", "Surgery Type", "Room", "Status"]
    if DATA_FILE.exists():
        df = pd.read_csv(DATA_FILE)
    else:
        df = pd.DataFrame(columns=expected_cols)
        df.to_csv(DATA_FILE, index=False)
    df.columns = df.columns.str.strip().str.title()
    if "Surgery Type" in df.columns:
        df.rename(columns={"Surgery Type": "Surgery"}, inplace=True)
    if "Status" not in df.columns:
        df["Status"] = "Booked"
    else:
        df["Status"] = df["Status"].fillna("Booked")
    df = df.assign(**{col: df.get(col, pd.NA) for col in ["Date", "Doctor", "Hour", "Surgery", "Room", "Status"]})
    df = df[["Date", "Doctor", "Hour", "Surgery", "Room", "Status"]]
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df

# ---------- Append booking ----------
def append_booking(rec: dict):
    row = {
        "Date": rec["Date"],
        "Doctor": rec["Doctor"],
        "Hour": rec["Hour"],
        "Surgery Type": rec["Surgery"],
        "Room": rec["Room"],
        "Status": "Booked",
    }
    df = pd.DataFrame([row])
    header_needed = not DATA_FILE.exists() or DATA_FILE.stat().st_size == 0
    df.to_csv(DATA_FILE, mode="a", header=header_needed, index=False)
    push_to_github(DATA_FILE, "Update Operation Archive via app")

# ---------- Check overlap ----------
def check_overlap(df: pd.DataFrame, d: date, room: str, hr: time) -> bool:
    if df.empty:
        return False
    mask = (
        (df["Date"].dt.date == d) &
        (df["Room"] == room) &
        (pd.to_datetime(df["Hour"], format="%H:%M", errors="coerce").dt.time == hr) &
        (df["Status"] != "Cancelled")
    )
    return mask.any()

# ---------- Update status ----------
def update_status(row, status):
    df = load_bookings()
    mask = (
        (df["Date"] == row["Date"]) &
        (df["Doctor"] == row["Doctor"]) &
        (df["Hour"] == row["Hour"]) &
        (df["Room"] == row["Room"])
    )
    if status == "Cancelled":
        # Remove booking completely
        df = df.loc[~mask]
    else:
        df.loc[mask, "Status"] = status
    df.to_csv(DATA_FILE, index=False)
    push_to_github(DATA_FILE, f"Operation {status} for {row['Doctor']} on {row['Date'].date()} at {row['Hour']}")

# ---------- Doctor icon ----------
def doctor_icon_html():
    return '<span style="font-size:16px; margin-right:6px;">🩺</span>'

# ---------- Header ----------
if HEADER_IMAGE.exists():
    st.image(str(HEADER_IMAGE), width=250)
st.title("Global Eye Center (Operation List)")

# ---------- Tabs ----------
tabs = st.tabs(["📋 Operation Booked", "📂 Operation Archive"])

# ---------- Tab 1: Upcoming Bookings with Confirm/Cancel/Delete ----------
with tabs[0]:
    bookings = load_bookings()
    yesterday = date.today() - timedelta(days=1)
    booked = bookings[(bookings["Date"].dt.date > yesterday) & (bookings["Status"] == "Booked")]
    st.subheader("📋 Operation Booked")
    if booked.empty:
        st.info("No upcoming surgeries booked.")
    else:
        display = booked.drop_duplicates(subset=["Date", "Hour", "Room"]).sort_values(["Date", "Hour"])
        for d in display["Date"].dt.date.unique():
            day_df = display[display["Date"].dt.date == d]
            with st.expander(d.strftime("📅 %A, %d %B %Y")):
                day_df_display = day_df[["Doctor", "Surgery", "Hour", "Room"]].copy()
                day_df_display.index = range(1, len(day_df_display) + 1)

                st.write("")  # spacer
                cols_header = st.columns([3, 1, 1, 1])
                cols_header[0].markdown("**Details**")
                cols_header[1].markdown("**Confirm**")
                cols_header[2].markdown("**Cancel**")
                cols_header[3].markdown("**Delete**")

                for idx, row in day_df_display.iterrows():
                    cols = st.columns([3, 1, 1, 1])
                    cols[0].write(
                        f"Doctor: {row['Doctor']}  \n"
                        f"Surgery: {row['Surgery']}  \n"
                        f"Hour: {row['Hour']}  \n"
                        f"Room: {row['Room']}"
                    )
                    if cols[1].button(f"✅ Confirm #{idx}", key=f"confirm_{row['Doctor']}_{row['Hour']}_{idx}"):
                        update_status(row, "Confirmed")
                        safe_rerun()
                    if cols[2].button(f"❌ Cancel #{idx}", key=f"cancel_{row['Doctor']}_{row['Hour']}_{idx}"):
                        update_status(row, "Cancelled")
                        safe_rerun()
                    if cols[3].button(f"🗑️ Delete #{idx}", key=f"delete_{row['Doctor']}_{row['Hour']}_{idx}"):
                        df = load_bookings()
                        mask = ~(
                            (df["Date"] == row["Date"]) &
                            (df["Doctor"] == row["Doctor"]) &
                            (df["Hour"] == row["Hour"]) &
                            (df["Room"] == row["Room"])
                        )
                        df = df.loc[mask]
                        df.to_csv(DATA_FILE, index=False)
                        push_to_github(DATA_FILE, f"Operation Deleted for {row['Doctor']} on {row['Date'].date()} at {row['Hour']}")
                        safe_rerun()


# ---------- Tab 2: Archive Bookings (Confirmed only) ----------
with tabs[1]:
    bookings = load_bookings()
    yesterday = date.today() - timedelta(days=1)
    archive = bookings[(bookings["Date"].dt.date <= yesterday) & (bookings["Status"] == "Confirmed")]
    st.subheader("📂 Operation Archive")
    if archive.empty:
        st.info("No archived records found.")
    else:
        display = archive.drop_duplicates(subset=["Date", "Hour", "Room"]).sort_values(["Date", "Hour"], ascending=False).copy()
        display["Date"] = display["Date"].dt.strftime("%Y-%m-%d")
        display.reset_index(drop=True, inplace=True)
        display.index += 1
        display["Doctor"] = display["Doctor"].apply(lambda x: f'{doctor_icon_html()}{x}')
        st.markdown(
            display.to_html(escape=False, columns=["Date", "Doctor", "Surgery", "Hour", "Room"]),
            unsafe_allow_html=True,
        )

# ---------- Sidebar: Add Booking Form ----------
st.sidebar.header("Add Surgery Booking")
picked_date = st.sidebar.date_input("Date", value=date.today())
room_choice = st.sidebar.radio("Room", ROOMS, horizontal=True)

# 30-minute intervals from 10:00 to 22:00
slot_hours = []
for hour in range(10, 23):
    slot_hours.append(time(hour, 0))
    if hour != 22:
        slot_hours.append(time(hour, 30))

sel_hour_str = st.sidebar.selectbox("Hour", [h.strftime("%H:%M") for h in slot_hours])
sel_hour = datetime.strptime(sel_hour_str, "%H:%M").time()

doctor_name = st.sidebar.text_input("Doctor Name")
surgery_choice = st.sidebar.selectbox("Surgery Type", SURGERY_TYPES)

if st.sidebar.button("💾 Save Booking"):
    if not doctor_name:
        st.sidebar.error("Doctor name required.")
    elif check_overlap(bookings, picked_date, room_choice, sel_hour):
        st.sidebar.error("Room already booked at this time.")
    else:
        record = {
            "Date": pd.Timestamp(picked_date),
            "Doctor": doctor_name.strip(),
            "Hour": sel_hour.strftime("%H:%M"),
            "Surgery": surgery_choice,
            "Room": room_choice,
            "Status": "Booked",
        }
        append_booking(record)
        st.sidebar.success("Surgery booked successfully.")
        safe_rerun()
