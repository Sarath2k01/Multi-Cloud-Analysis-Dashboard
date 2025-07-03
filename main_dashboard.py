import streamlit as st
import subprocess
import webbrowser
import os

def clear_old_results():
    """Clear any existing result files on dashboard startup"""
    result_files = ["vm_summary.html", "snap_summary.html", "disks_summary.html"]
    for file in result_files:
        if os.path.exists(file):
            os.remove(file)

# Add this right after your imports and before the main UI
if 'dashboard_initialized' not in st.session_state:
    clear_old_results()
    st.session_state.dashboard_initialized = True

st.set_page_config(page_title="Cloud Infra Dashboard", layout="wide")
st.title("☁️ Cloud Infra Analysis Dashboard")

def load_results():
    results = {}
    try:
        if os.path.exists("vm_summary.html"):
            with open("vm_summary.html", "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():  # Check if content is not empty
                    results["VM Rightsizing"] = content
                else:
                    print("VM summary file is empty")
        
        if os.path.exists("snap_summary.html"):
            with open("snap_summary.html", "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():
                    results["Snapshots"] = content
        
        if os.path.exists("disks_summary.html"):
            with open("disks_summary.html", "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():
                    results["Unattached Disks"] = content
    except Exception as e:
        print(f"Error loading results: {e}")
    
    return results


def get_app_status():
    """Check which apps have results available"""
    return {
        "VM Rightsizing": os.path.exists("vm_summary.html"),
        "Snapshots": os.path.exists("snap_summary.html"),
        "Unattached Disks": os.path.exists("disks_summary.html")
    }

st.header("Launch Analysis Tools")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Open VM Rightsizing App"):
        vm_path = os.path.abspath("vm.py")
        if not os.path.exists(vm_path):
            st.error(f"File not found: {vm_path}")
        else:
            subprocess.Popen(f'streamlit run "{vm_path}" --server.port 8502', shell=True)
            webbrowser.open_new_tab("http://localhost:8502")

with col2:
    if st.button("Open Snapshots App"):
        snap_path = os.path.abspath("snapshots.py")
        if not os.path.exists(snap_path):
            st.error(f"File not found: {snap_path}")
        else:
            subprocess.Popen(f'streamlit run "{snap_path}" --server.port 8503', shell=True)
            webbrowser.open_new_tab("http://localhost:8503")

with col3:
    if st.button("Open Unattached Disks App"):
        disks_path = os.path.abspath("disks.py")
        if not os.path.exists(disks_path):
            st.error(f"File not found: {disks_path}")
        else:
            subprocess.Popen(f'streamlit run "{disks_path}" --server.port 8504', shell=True)
            webbrowser.open_new_tab("http://localhost:8504")

st.divider()

# --- Refresh Button ---
if st.button("🔄 Refresh Results"):
    st.rerun()

# --- New App Status List UI ---
st.header("📊 Available Results")

app_status = get_app_status()
results = load_results()

# Create app list with status indicators
st.markdown("### Analysis Apps Status")

# Initialize session state for selected apps if not exists
if 'selected_apps' not in st.session_state:
    st.session_state.selected_apps = []

# Display apps with status and selection
for app_name, has_results in app_status.items():
    col1, col2, col3 = st.columns([6, 1, 2])
    
    with col1:
        # App name with checkbox for selection
        if has_results:
            is_selected = st.checkbox(
                f"**{app_name}**", 
                key=f"select_{app_name}",
                value=app_name in st.session_state.selected_apps
            )
            if is_selected and app_name not in st.session_state.selected_apps:
                st.session_state.selected_apps.append(app_name)
            elif not is_selected and app_name in st.session_state.selected_apps:
                st.session_state.selected_apps.remove(app_name)
        else:
            st.markdown(f"**{app_name}**")
    
    with col2:
        # Status indicator
        if has_results:
            st.markdown("✅")  # Green checkmark
        else:
            st.markdown("❌")  # Red X
    
    with col3:
        # Status text
        if has_results:
            st.markdown("**Ready**")
        else:
            st.markdown("*No Results*")

st.divider()

# Display selected results
if st.session_state.selected_apps:
    st.header("📋 Selected Results")
    
    for app_name in st.session_state.selected_apps:
        if app_name in results:
            st.markdown(f"### **{app_name} Summary:**")
            st.html(results[app_name])
            st.divider()
    
    # Email functionality
    if st.button("📧 Send Selected Results via Email") and st.session_state.selected_apps:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        
        EMAIL_CONFIG = {
            "sender_email": "sarath2k01@gmail.com",
            "sender_password": "wfdm pyrq oimd thkh",
            "recipients": [
                "junkiemail341@gmail.com",
            ],
            "subject_prefix": "Cloud Infra Combined Report"
        }
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = EMAIL_CONFIG["subject_prefix"]
        msg['From'] = EMAIL_CONFIG["sender_email"]
        msg['To'] = ", ".join(EMAIL_CONFIG["recipients"])
        
        html_content = ""
        for app_name in st.session_state.selected_apps:
            if app_name in results:
                html_content += f"<h2>{app_name} Summary</h2>{results[app_name]}"
        
        msg.attach(MIMEText(html_content, 'html'))
        
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(EMAIL_CONFIG["sender_email"], EMAIL_CONFIG["sender_password"])
                server.sendmail(
                    EMAIL_CONFIG["sender_email"],
                    EMAIL_CONFIG["recipients"],
                    msg.as_string()
                )
            st.success("📧 Email sent successfully!")
            st.balloons()
        except Exception as e:
            st.error(f"❌ Failed to send email: {e}")
else:
    st.info("👆 Select apps above to view their results")

# --- Status Summary Card ---
st.sidebar.header("📈 Status Summary")
total_apps = len(app_status)
completed_apps = sum(app_status.values())
completion_rate = (completed_apps / total_apps) * 100 if total_apps > 0 else 0

st.sidebar.metric(
    label="Apps with Results",
    value=f"{completed_apps}/{total_apps}",
    delta=f"{completion_rate:.0f}% Complete"
)

# Progress bar in sidebar
st.sidebar.progress(completion_rate / 100)

# Individual app status in sidebar
st.sidebar.markdown("#### App Status:")
for app_name, has_results in app_status.items():
    status_icon = "✅" if has_results else "⏳"
    st.sidebar.markdown(f"{status_icon} {app_name}")
