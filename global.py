import streamlit as st
import pandas as pd
import os
import base64
import requests
from datetime import datetime

# GitHub push function
def push_to_github(file_path, commit_message):
    try:
        token = "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"
        username = "ParezDzay"
        repo = "Global"
        branch = "main"

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        encoded_content = base64.b64encode(content.encode()).decode()
        filename = os.path.basename(file_path)
        url = f"https://api.github.com/repos/{username}/{repo}/contents/{filename}"

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json"
        }

        response = requests.get(url, headers=headers)
        sha = response.json().get("sha") if response.status_code == 200 else None

        payload = {
            "message": commit_message,
            "content": encoded_content,
            "branch": branch
        }
        if sha:
            payload["sha"] = sha

        res = requests.put(url, headers=headers, json=payload)
        return res.status_code in [200, 201]
    except Exception as e:
        st.error(f"❌ GitHub push failed: {e}")
        return False

# Page config
st.set_page_config(page_title="Operation Archive Manager", layout="wide")
file_path = "Operation Archive.csv"

# Initialize CSV
if not os.path.exists(file_path):
    pd.DataFrame(columns=["Date", "Patient_ID", "Operation_Type", "Doctor", "Status", "Notes"]).to_csv(file_path, index=False)

df = pd.read_csv(file_path)

# Sidebar
menu = st.sidebar.radio("📁 Menu", ["➕ New Operation", "📊 View Operations"], index=0)

if menu == "➕ New Operation":
    st.title("➕ Register New Operation")

    try:
        last_id = df["Patient_ID"].dropna().astype(str).str.extract('(\\d+)')[0].astype(int).max()
        next_id = f"{last_id + 1:04d}"
    except:
        next_id = "0001"
    st.markdown(f"**Generated Patient ID:** `{next_id}`")

    with st.form("operation_form", clear_on_submit=True):
        date = st.date_input("Operation Date")
        op_type = st.text_input("Operation Type")
        doctor = st.text_input("Doctor Name")
        status = st.selectbox("Operation Status", ["Scheduled", "Completed", "Cancelled"])
        notes = st.text_area("Notes")

        if st.form_submit_button("Submit Operation"):
            new_entry = pd.DataFrame([{
                "Date": date,
                "Patient_ID": next_id,
                "Operation_Type": op_type,
                "Doctor": doctor,
                "Status": status,
                "Notes": notes
            }])
            df = pd.concat([df, new_entry], ignore_index=True)
            try:
                df.to_csv(file_path, index=False)
                st.success("✅ Operation recorded locally.")
                if push_to_github(file_path, f"New operation added for Patient {next_id}"):
                    st.success("✅ Pushed to GitHub.")
                else:
                    st.warning("⚠️ GitHub push failed.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Save failed: {e}")

elif menu == "📊 View Operations":
    st.title("📊 Operation Archive")
    tab1, tab2 = st.tabs(["📋 All Records", "🗕 Download CSV"])
    with tab1:
        st.dataframe(df, use_container_width=True)
    with tab2:
        st.download_button(
            label="⬇️ Download Archive",
            data=df.to_csv(index=False),
            file_name="Operation_Archive.csv",
            mime="text/csv"
        )
