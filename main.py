#streamlit run main.py

import streamlit as st
import os
import re
import shutil
import random
import string
import json
from datetime import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter

# --- CONFIGURATION (cloud-ready relative paths) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FORMS_DIR = os.path.join(BASE_DIR, "FORMS")
TRACKER_FILE = os.path.join(BASE_DIR, "usage_tracker.json")

# --- CREDENTIALS ---
VALID_USERNAME = "clcqmsi2026"
VALID_PASSWORD = "thankyoupo"

# --- PAPER SIZES (in points: 1 inch = 72 points) ---
PAPER_SIZES = {
    "Letter (8.5 x 11 in)": (612, 792),
    "Legal (8.5 x 14 in)":  (612, 1008),
    "A4 (8.27 x 11.69 in)": (595, 842),
}

# --- NATURAL SORT (handles "Chapter 2" before "Chapter 10") ---
def natural_sort_key(s):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', s)]

# ============================================================
# SESSION STATE INIT
# ============================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "login_error" not in st.session_state:
    st.session_state.login_error = False

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(page_title="CLC Form Manager", layout="wide", page_icon="🚢")

# ============================================================
# CSS — injected based on login state
# ============================================================
if not st.session_state.logged_in:
    st.markdown("""
    <style>
    [data-testid="InputInstructions"] { display: none !important; }
    html, body { overflow: hidden !important; height: 100% !important; }
    .stApp { overflow: hidden !important; height: 100vh !important; }
    [data-testid="stAppViewContainer"] { overflow: hidden !important; height: 100vh !important; }
    [data-testid="stMainBlockContainer"],
    [data-testid="stMain"] {
        overflow: hidden !important;
        height: 100vh !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    .block-container {
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
        max-width: 100% !important;
    }
    #MainMenu, footer, header { visibility: hidden; }
    .stDeployButton { display: none; }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
    [data-testid="InputInstructions"] { display: none !important; }
    [data-testid="stSidebar"] .manage-row > div { flex: 1; min-width: 0; }
    [data-testid="stSidebar"] .manage-row button {
        width: 100% !important;
        text-align: center !important;
        justify-content: center !important;
    }
    #MainMenu, footer, header { visibility: hidden; }
    .stDeployButton { display: none; }
    </style>
    """, unsafe_allow_html=True)


# ============================================================
# LOGIN GATE
# ============================================================
def login_page():
    col1, col2, col3 = st.columns([1.5, 2, 1.5])
    with col2:
        st.markdown(
            """
            <div style='text-align: center; padding: 20px 0 10px 0;'>
                <div style='font-size: 52px;'>🚢</div>
                <h2 style='margin: 8px 0 2px 0;'>CLC QEA Marine Services Inc.</h2>
                <p style='color: gray; margin: 0;'>Form Management System</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 🔐 Sign In")

        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", placeholder="Enter your password", type="password")

        if st.session_state.login_error:
            st.error("❌ Incorrect username or password. Please try again.")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Login", use_container_width=True, type="primary"):
            if username == VALID_USERNAME and password == VALID_PASSWORD:
                st.session_state.logged_in = True
                st.session_state.login_error = False
                st.rerun()
            else:
                st.session_state.login_error = True
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            "<p style='text-align:center; color: gray; font-size: 12px;'>© 2026 CLC QEA Marine Services Inc. All rights reserved.</p>",
            unsafe_allow_html=True
        )


# ============================================================
# MAIN APP (only shown after login)
# ============================================================
def main_app():

    def generate_clc_id():
        now = datetime.now()
        date_part = now.strftime("%m%d%Y")
        time_part = now.strftime("%H%M")
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"{date_part}CLC{time_part}H-{suffix}", suffix

    def process_pdf(full_path):
        unique_id, suffix = generate_clc_id()
        template_pdf = PdfReader(open(full_path, "rb"))
        first_page = template_pdf.pages[0]
        width = float(first_page.mediabox.width)
        height = float(first_page.mediabox.height)

        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=(width, height))
        can.setFont("Helvetica-Bold", 10)
        can.drawRightString(width - 30, height - 25, f"ID: {unique_id}")
        can.save()
        packet.seek(0)

        id_layer = PdfReader(packet)
        writer = PdfWriter()
        for i in range(len(template_pdf.pages)):
            page = template_pdf.pages[i]
            if i == 0:
                page.merge_page(id_layer.pages[0])
            writer.add_page(page)

        output_buffer = BytesIO()
        writer.write(output_buffer)
        output_buffer.seek(0)
        return output_buffer, suffix, unique_id

    def get_all_folders():
        if not os.path.exists(FORMS_DIR):
            return []
        folders = [d for d in os.listdir(FORMS_DIR) if os.path.isdir(os.path.join(FORMS_DIR, d))]
        return sorted(folders, key=natural_sort_key)

    def get_pdfs_in_folder(folder_path):
        if not os.path.exists(folder_path):
            return []
        pdfs = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
        return sorted(pdfs, key=natural_sort_key)

    def load_tracker():
        if os.path.exists(TRACKER_FILE):
            with open(TRACKER_FILE, "r") as f:
                return json.load(f)
        return {}

    def save_tracker(data):
        os.makedirs(os.path.dirname(TRACKER_FILE), exist_ok=True)
        with open(TRACKER_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def log_download(folder_name, form_name, unique_id):
        tracker = load_tracker()
        if form_name not in tracker:
            tracker[form_name] = []
        tracker[form_name].append({
            "folder": folder_name,
            "id": unique_id,
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        save_tracker(tracker)

    def load_metadata():
        meta_file = os.path.join(BASE_DIR, "metadata.json")
        if os.path.exists(meta_file):
            with open(meta_file, "r") as f:
                return json.load(f)
        return {}

    def save_metadata(data):
        meta_file = os.path.join(BASE_DIR, "metadata.json")
        with open(meta_file, "w") as f:
            json.dump(data, f, indent=2)

    def set_paper_size(folder_name, pdf_name, size_label):
        meta = load_metadata()
        key = f"{folder_name}/{pdf_name}"
        meta[key] = size_label
        save_metadata(meta)

    def get_paper_size(folder_name, pdf_name):
        meta = load_metadata()
        key = f"{folder_name}/{pdf_name}"
        return meta.get(key, "Letter (8.5 x 11 in)")

    os.makedirs(FORMS_DIR, exist_ok=True)

    # ── SIDEBAR ───────────────────────────────────────────────
    with st.sidebar:
        st.title("🚢 CLC QEA Marine")

        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.login_error = False
            st.rerun()

        st.divider()

        folders = get_all_folders()
        st.markdown("### 📁 Folders")

        if folders:
            folder_options = ["🗂️ All Forms"] + [f"📁  {f}" for f in folders]
            selected_raw = st.radio("", folder_options, label_visibility="collapsed")
            active_folder = None if selected_raw == "🗂️ All Forms" else selected_raw.replace("📁  ", "")
        else:
            st.info("No folders yet. Create one below.")
            active_folder = None

        st.divider()

        # ── CREATE FOLDER ─────────────────────────────────────
        st.markdown("### ➕ New Folder")
        st.markdown("**Folder Name:**")
        new_folder_name = st.text_input(
            "folder_name_hidden",
            key="new_folder_input",
            label_visibility="collapsed"
        )
        if st.button("Create Folder", use_container_width=True, key="create_folder_btn"):
            if new_folder_name.strip():
                safe = new_folder_name.strip().replace("/", "-").replace("\\", "-")
                target = os.path.join(FORMS_DIR, safe)
                if os.path.exists(target):
                    st.warning("Folder already exists.")
                else:
                    os.makedirs(target)
                    st.success(f"✅ '{safe}' created!")
                    st.rerun()
            else:
                st.error("Enter a folder name.")

        st.divider()

        # ── UPLOAD PDFs ───────────────────────────────────────
        st.markdown("### 📤 Upload PDFs")
        if folders:
            upload_dest = st.selectbox("Upload to folder", folders)

            selected_size = st.selectbox(
                "📐 Paper Size",
                list(PAPER_SIZES.keys())
            )

            uploaded = st.file_uploader(
                "Choose PDF files", type=["pdf"],
                accept_multiple_files=True, label_visibility="collapsed"
            )

            if uploaded and st.button("⬆️ Upload Files", use_container_width=True):
                dest_path = os.path.join(FORMS_DIR, upload_dest)
                os.makedirs(dest_path, exist_ok=True)
                count = 0
                for uf in uploaded:
                    save_path = os.path.join(dest_path, uf.name)
                    if os.path.exists(save_path):
                        base, ext = os.path.splitext(uf.name)
                        save_path = os.path.join(dest_path, f"{base}_{datetime.now().strftime('%H%M%S')}{ext}")
                    with open(save_path, "wb") as out:
                        out.write(uf.getbuffer())
                    set_paper_size(upload_dest, uf.name, selected_size)
                    count += 1
                st.success(f"✅ {count} file(s) uploaded to **{upload_dest}** as **{selected_size}**!")
                st.rerun()
        else:
            st.caption("Create a folder first to enable uploads.")

        st.divider()

        # ── MANAGE FOLDER ─────────────────────────────────────
        if folders:
            st.markdown("### ⚙️ Manage Folder")
            manage_target = st.selectbox("Select folder to manage", folders, key="manage_sel")
            manage_path = os.path.join(FORMS_DIR, manage_target)

            st.markdown('<div class="manage-row">', unsafe_allow_html=True)
            col_r, col_d = st.columns(2)
            with col_r:
                with st.popover("Rename", use_container_width=True):
                    rn = st.text_input("New name", key="rn_input")
                    if st.button("Confirm Rename", key="rn_confirm", use_container_width=True):
                        if rn.strip():
                            new_p = os.path.join(FORMS_DIR, rn.strip())
                            if os.path.exists(new_p):
                                st.error("Name already taken.")
                            else:
                                os.rename(manage_path, new_p)
                                st.success("Renamed!")
                                st.rerun()
            with col_d:
                with st.popover("Delete", use_container_width=True):
                    st.warning(f"Delete **{manage_target}** and ALL its files?")
                    if st.button("Yes, Delete", key="del_folder_confirm", use_container_width=True):
                        shutil.rmtree(manage_path)
                        st.success("Folder deleted.")
                        st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # ── MAIN AREA ─────────────────────────────────────────────
    st.title("🚢 CLC QEA Marine Services Inc.")
    st.caption("Trial Version - For demonstration purposes only")

    tab_browse, tab_tracker = st.tabs(["📂  Browse & Download", "📊  Record of Use"])

    # ── TAB 1: BROWSE & DOWNLOAD ──────────────────────────────
    with tab_browse:
        if active_folder is None:
            heading = "🗂️ All Forms"
            all_files = []
            for folder in get_all_folders():
                for pdf in get_pdfs_in_folder(os.path.join(FORMS_DIR, folder)):
                    all_files.append((folder, pdf))
        else:
            heading = f"📁 {active_folder}"
            all_files = [(active_folder, pdf) for pdf in get_pdfs_in_folder(os.path.join(FORMS_DIR, active_folder))]

        st.markdown(f"## {heading}")
        search = st.text_input("🔍 Search", placeholder="Filter by file name...", key="browse_search")
        if search:
            all_files = [(fol, pdf) for fol, pdf in all_files if search.lower() in pdf.lower()]

        st.caption(f"{len(all_files)} form(s) found")
        st.markdown("---")

        if not all_files:
            st.info("No PDFs found. Upload files using the sidebar.")
        else:
            hc1, hc2, hc3, hc4, hc5 = st.columns([3, 2, 1.5, 1, 1.8])
            hc1.markdown("**📄 Form Name**")
            hc2.markdown("**📁 Folder**")
            hc3.markdown("**📐 Paper Size**")
            hc4.markdown("**Size**")
            hc5.markdown("**Action**")
            st.markdown("---")

            for folder_name, pdf_name in all_files:
                full_path = os.path.join(FORMS_DIR, folder_name, pdf_name)
                c1, c2, c3, c4, c5 = st.columns([3, 2, 1.5, 1, 1.8])

                paper_size_label = get_paper_size(folder_name, pdf_name)

                with c1:
                    st.write(f"📄 {pdf_name}")
                with c2:
                    st.write(f"{folder_name}")
                with c3:
                    st.write(f"📐 {paper_size_label.split(' ')[0]}")
                with c4:
                    try:
                        kb = os.path.getsize(full_path) / 1024
                        st.write(f"{kb:.1f} KB")
                    except:
                        st.write("—")
                with c5:
                    if st.button("✨ Download", key=f"dl_{folder_name}_{pdf_name}", use_container_width=True):
                        with st.spinner("Stamping..."):
                            try:
                                pdf_out, code, full_id = process_pdf(full_path)
                                log_download(folder_name, pdf_name, full_id)
                                new_name = f"{os.path.splitext(pdf_name)[0]} - {code}.pdf"
                                st.success(f"ID stamped: `{full_id}`")
                                st.download_button(
                                    label="📥 Save File",
                                    data=pdf_out,
                                    file_name=new_name,
                                    mime="application/pdf",
                                    key=f"save_{folder_name}_{pdf_name}_{code}"
                                )
                            except Exception as e:
                                st.error(f"Error: {e}")
                st.markdown("---")

    # ── TAB 2: USAGE TRACKER ──────────────────────────────────
    with tab_tracker:
        import pandas as pd

        st.markdown("## 📊 Records")
        st.divider()

        tracker = load_tracker()

        if not tracker:
            st.info("No downloads recorded yet. Download a form to start tracking.")
        else:
            search_t = st.text_input("🔍 Filter by form name", placeholder="Type to filter...", key="tracker_search")
            forms_to_show = {k: v for k, v in tracker.items() if search_t.lower() in k.lower()} if search_t else tracker

            if not forms_to_show:
                st.warning("No matching forms found.")
            else:
                st.markdown("### 📋 Per-Form Breakdown")
                st.caption("Each form has its own table — showing which folders downloaded it and when.")
                st.markdown("---")

                for form_name, records in forms_to_show.items():
                    st.markdown(f"#### 📄 {form_name}")
                    st.caption(f"Total downloads: **{len(records)}**")

                    rows = [
                        {"Folder": r["folder"], "Downloaded At": r["datetime"], "Unique ID": r["id"]}
                        for r in sorted(records, key=lambda x: x["datetime"], reverse=True)
                    ]
                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True, hide_index=True)

                    csv = df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        label=f"📥 Export {form_name} log",
                        data=csv,
                        file_name=f"usage_{form_name.replace(' ', '_')}.csv",
                        mime="text/csv",
                        key=f"csv_{form_name}"
                    )
                    st.markdown("---")

            st.markdown("### 🗂️ Full Summary Log")
            all_rows = [
                {"Form": fn, "Folder": r["folder"], "Downloaded At": r["datetime"], "Unique ID": r["id"]}
                for fn, records in tracker.items() for r in records
            ]
            if all_rows:
                summary_df = pd.DataFrame(all_rows).sort_values("Downloaded At", ascending=False)
                st.dataframe(summary_df, use_container_width=True, hide_index=True)
                full_csv = summary_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Export Full Log as CSV",
                    data=full_csv,
                    file_name="full_usage_log.csv",
                    mime="text/csv",
                    key="full_csv_export"
                )

            st.divider()
            with st.popover("🗑️ Clear All Logs"):
                st.warning("This will permanently delete all download history!")
                if st.button("Yes, Clear Everything", key="clear_tracker"):
                    save_tracker({})
                    st.success("All logs cleared.")
                    st.rerun()


# ============================================================
# ROUTER — Login gate
# ============================================================
if not st.session_state.logged_in:
    login_page()
else:
    main_app()