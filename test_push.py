import streamlit as st
import requests, base64, os
from pathlib import Path

st.set_page_config(page_title="GitHub Push Debug", layout="wide")
st.title("🔧 GitHub Push Test")

filename = "Operation Archive.csv"
path = Path(filename)

# Step 1: Create dummy CSV file
if not path.exists():
    with open(path, "w", encoding="utf-8") as f:
        f.write("Date,Hall,Doctor,Hour,Surgery\n2025-01-01,Hall 1,Dr.Test,10:00,Phaco\n")
    st.success(f"✅ File `{filename}` created")

# Step 2: Push to GitHub
try:
    token = st.secrets["github"]["token"]
    username = st.secrets["github"]["username"]
    repo = st.secrets["github"]["repo"]
    branch = st.secrets["github"]["branch"]

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    encoded = base64.b64encode(content.encode()).decode()

    url = f"https://api.github.com/repos/{username}/{repo}/contents/{filename}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    response = requests.get(url, headers=headers)
    sha = response.json().get("sha") if response.status_code == 200 else None

    payload = {
        "message": "Initial push test",
        "content": encoded,
        "branch": branch
    }
    if sha:
        payload["sha"] = sha

    result = requests.put(url, headers=headers, json=payload)
    st.write("📡 Status Code:", result.status_code)
    st.json(result.json())

    if result.status_code in [200, 201]:
        st.success("✅ Push worked!")
    else:
        st.error("❌ Push failed")
except Exception as e:
    st.error(f"Exception: {e}")
