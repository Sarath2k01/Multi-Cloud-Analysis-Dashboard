import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import json
import os
from collections import defaultdict

# --- EMAIL CONFIGURATION (for dashboard use only) ---
EMAIL_CONFIG = {
    "sender_email": "sarath2k01@gmail.com",
    "sender_password": "wfdm pyrq oimd thkh",  # Gmail App Password
    "recipients": [
        "junkiemail341@gmail.com",
        # "bharath4034.madala@gmail.com"
    ],
    "subject_prefix": "Snapshot Summary Report"
}

st.set_page_config(page_title="Snapshot Analysis Report", layout="wide")

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1f77b4, #ff7f0e);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #1f77b4;
    }
    .compliance-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #28a745;
    }
</style>
""", unsafe_allow_html=True)

def normalize_ccid(ccid):
    return str(ccid).upper().strip()

def format_creation_time_custom(creation_date, current_date):
    delta = relativedelta(current_date, creation_date)
    parts = []
    if delta.years > 0:
        parts.append(f"{delta.years} year{'s' if delta.years > 1 else ''}")
    if delta.months > 0:
        parts.append(f"{delta.months} month{'s' if delta.months > 1 else ''}")
    if delta.days > 0 and delta.years == 0:
        parts.append(f"{delta.days} day{'s' if delta.days > 1 else ''}")
    if not parts:
        return "0 days ago"
    return ' '.join(parts) + ' ago'

def to_naive(dt):
    if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
        return dt.tz_convert(None).to_pydatetime() if hasattr(dt, 'tz_convert') else dt.replace(tzinfo=None)
    return dt

def load_compliance_data(json_file_path):
    """Load tag compliance data from JSON file"""
    try:
        with open(json_file_path, 'r') as file:
            compliance_data = json.load(file)
        
        ccid_cenvid_mapping = defaultdict(set)
        
        for entry in compliance_data:
            ccid = entry.get("CCID (Unique Per Customer)", "").strip().upper()  # Normalize to uppercase
            if not ccid or ccid == "":
                continue
                
            # Extract all non-empty CENVIDs for this CCID
            cenvids = []
            for key in ["CENVID (PRE PROD)", "CENVID (PROD)", "CENVID (DEV)", "CENVID (STG)", "CENVID(PSR)"]:
                cenvid = entry.get(key, "").strip().upper()  # Normalize to uppercase
                if cenvid and cenvid != "":
                    cenvids.append(cenvid)
            
            # Add all valid CENVIDs for this CCID
            ccid_cenvid_mapping[ccid].update(cenvids)
        
        # Convert sets to lists for easier handling
        return {ccid: list(cenvids) for ccid, cenvids in ccid_cenvid_mapping.items()}
    
    except Exception as e:
        return {}

def check_tag_compliance(df, ccid, compliance_mapping):
    """Check tag compliance for snapshots"""
    if not compliance_mapping:
        return {
            'total_instances': len(df),
            'compliant_instances': 0,
            'non_compliant_instances': len(df),
            'compliance_percentage': 0,
            'status': 'No compliance data file found',
            'non_compliant_details': []
        }
    
    # Normalize ccid to uppercase
    ccid = ccid.upper().strip()
    
    if ccid not in compliance_mapping:
        return {
            'total_instances': len(df),
            'compliant_instances': 0,
            'non_compliant_instances': len(df),
            'compliance_percentage': 0,
            'status': f'CCID {ccid} not found in compliance mapping',
            'non_compliant_details': []
        }
    
    valid_cenvids = compliance_mapping[ccid]
    total_instances = len(df)
    compliant_count = 0
    non_compliant_details = []
    
    # Check for CENVID column variations
    cenvid_column = None
    possible_cenvid_columns = ['o9 CENVID tag', '09 CENVID tag', 'CENVID', 'cenvid']
    for col in possible_cenvid_columns:
        if col in df.columns:
            cenvid_column = col
            break
    
    if not cenvid_column:
        return {
            'total_instances': total_instances,
            'compliant_instances': 0,
            'non_compliant_instances': total_instances,
            'compliance_percentage': 0,
            'status': 'CENVID column not found',
            'non_compliant_details': []
        }
    
    for idx, row in df.iterrows():
        instance_cenvid = str(row.get(cenvid_column, '')).upper().strip()
        snapshot_id = row.get('Snapshot ID', f'snapshot_{idx}')
        
        if instance_cenvid in valid_cenvids:
            compliant_count += 1
        else:
            non_compliant_details.append({
                'snapshot_id': snapshot_id,
                'ccid': ccid,
                'current_cenvid': instance_cenvid if instance_cenvid else 'None',
                'valid_cenvids': valid_cenvids,
                'issue': 'Invalid CENVID' if instance_cenvid else 'Missing CENVID',
                'creation_time': row.get('Creation Time', 'N/A'),
                'cost_since_created': row.get('Cost Since Created', 'N/A')
            })
    
    compliance_percentage = (compliant_count / total_instances * 100) if total_instances > 0 else 0
    
    return {
        'total_instances': total_instances,
        'compliant_instances': compliant_count,
        'non_compliant_instances': total_instances - compliant_count,
        'compliance_percentage': round(compliance_percentage, 2),
        'status': 'Compliance check completed',
        'non_compliant_details': non_compliant_details
    }

def display_non_compliant_instances(non_compliant_details):
    """Display non-compliant instances in a simple tabular format"""
    if not non_compliant_details:
        st.success("🎉 All snapshots are compliant!")
        return
    
    st.markdown("### 🚩 Non-Compliant Snapshots")
    st.markdown(f"Found **{len(non_compliant_details)}** non-compliant snapshots that need attention:")
    
    # Convert to DataFrame and sort by cost (highest first)
    non_compliant_df = pd.DataFrame(non_compliant_details)
    
    # Convert cost to numeric for proper sorting
    non_compliant_df['cost_numeric'] = pd.to_numeric(
        non_compliant_df['cost_since_created'].astype(str).str.replace('$', '').str.replace(',', ''), 
        errors='coerce'
    ).fillna(0)
    
    # Sort by cost descending
    non_compliant_df_sorted = non_compliant_df.sort_values(by='cost_numeric', ascending=False)
    
    # Prepare display DataFrame - simple format
    display_df = pd.DataFrame({
        'Rank': range(1, len(non_compliant_df_sorted) + 1),
        'Snapshot ID': non_compliant_df_sorted['snapshot_id'].values,
        'CCID': non_compliant_df_sorted['ccid'].values,
        'Current CENVID': non_compliant_df_sorted['current_cenvid'].values,
        'Valid CENVIDs': [', '.join(cenvids) for cenvids in non_compliant_df_sorted['valid_cenvids'].values],
        'Issue Type': non_compliant_df_sorted['issue'].values,
        'Creation Time': non_compliant_df_sorted['creation_time'].values,
        'Cost Since Created': non_compliant_df_sorted['cost_since_created'].values
    })
    
    # Display the table WITHOUT styling - simple white background
    st.dataframe(
        display_df,
        use_container_width=True,
        height=400,
        hide_index=True
    )
    
    # Summary statistics - STYLED TO MATCH TAG COMPLIANCE COVERAGE
    missing_cenvid = len([item for item in non_compliant_details if item['issue'] == 'Missing CENVID'])
    invalid_cenvid = len([item for item in non_compliant_details if item['issue'] == 'Invalid CENVID'])
    total_cost = non_compliant_df['cost_numeric'].sum()
    
    # Create HTML table with a cool blue-purple gradient styling
    summary_html = f"""
    <div style="background:linear-gradient(135deg, #e0f2f1, #b2dfdb);border:2px solid #00695c;border-radius:15px;padding:0 0 20px 0;margin-bottom:20px;box-shadow:0 8px 16px rgba(0,0,0,0.1);">
        <div style="background:linear-gradient(135deg, #00695c, #004d40);color:#fff;border-radius:15px 15px 0 0;padding:15px 0 15px 25px;font-size:1.3em;font-weight:bold;letter-spacing:0.8px;text-shadow:1px 1px 2px rgba(0,0,0,0.3);">
            📊 Non-Compliance Summary
        </div>
        <div style="padding:20px;">
            <table style="width:100%;font-size:1.2em;color:#3f51b5;text-align:center;border-collapse:collapse;">
                <tr style="background:rgba(63,81,181,0.1);">
                    <td style="padding:15px;border:1px solid #3f51b540;"><b>❌ Missing CENVID</b></td>
                    <td style="padding:15px;border:1px solid #3f51b540;"><b>⚠️ Invalid CENVID</b></td>
                    <td style="padding:15px;border:1px solid #3f51b540;"><b>📊 Total Non-Compliant</b></td>
                    <td style="padding:15px;border:1px solid #3f51b540;"><b>💰 Total Cost Impact</b></td>
                </tr>
                <tr>
                    <td style="font-size:2em;color:#3f51b5;padding:20px;font-weight:bold;text-shadow:1px 1px 2px rgba(0,0,0,0.1);">{missing_cenvid}</td>
                    <td style="font-size:2em;color:#3f51b5;padding:20px;font-weight:bold;text-shadow:1px 1px 2px rgba(0,0,0,0.1);">{invalid_cenvid}</td>
                    <td style="font-size:2em;color:#3f51b5;padding:20px;font-weight:bold;text-shadow:1px 1px 2px rgba(0,0,0,0.1);">{len(non_compliant_details)}</td>
                    <td style="font-size:2em;color:#3f51b5;padding:20px;font-weight:bold;text-shadow:1px 1px 2px rgba(0,0,0,0.1);">${total_cost:.2f}</td>
                </tr>
            </table>
        </div>
    </div>
    """

    
    # Display the styled summary
    st.markdown(summary_html, unsafe_allow_html=True)
    
    # Action items
    st.markdown("""
    #### 📋 Action Required:
    - **Missing CENVID (❌)**: Add appropriate CENVID tag from the valid list
    - **Invalid CENVID (⚠️)**: Update current CENVID to match valid options
    - **Priority**: Address highest cost items first to maximize impact
    """)


def generate_non_compliant_html_table(non_compliant_details):
    """Generate HTML table for non-compliant instances for email reports"""
    if not non_compliant_details:
        return ""
    
    # Convert to DataFrame and sort by cost (highest first)
    non_compliant_df = pd.DataFrame(non_compliant_details)
    
    # Convert cost to numeric for proper sorting
    non_compliant_df['cost_numeric'] = pd.to_numeric(
        non_compliant_df['cost_since_created'].astype(str).str.replace('$', '').str.replace(',', ''), 
        errors='coerce'
    ).fillna(0)
    
    # Sort by cost descending
    non_compliant_df_sorted = non_compliant_df.sort_values(by='cost_numeric', ascending=False)
    
    # Generate HTML table with inline CSS for email compatibility
    html_table = f"""
    <div style="margin: 20px 0; padding: 15px; border: 2px solid #f44336; border-radius: 8px; background-color: #ffebee;">
        <h3 style="color: #d32f2f; margin-top: 0; font-family: Arial, sans-serif;">
            🚩 Non-Compliant Snapshots ({len(non_compliant_details)} instances)
        </h3>
        <p style="color: #666; font-family: Arial, sans-serif; margin-bottom: 15px;">
            The following snapshots require immediate attention for tag compliance. Sorted by highest cost impact.
        </p>
        
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; font-size: 12px;">
            <thead>
                <tr style="background-color: #f44336; color: white;">
                    <th style="padding: 12px 8px; text-align: left; font-weight: bold;">Rank</th>
                    <th style="padding: 12px 8px; text-align: left; font-weight: bold;">Snapshot ID</th>
                    <th style="padding: 12px 8px; text-align: left; font-weight: bold;">CCID</th>
                    <th style="padding: 12px 8px; text-align: left; font-weight: bold;">Current CENVID</th>
                    <th style="padding: 12px 8px; text-align: left; font-weight: bold;">Valid CENVIDs</th>
                    <th style="padding: 12px 8px; text-align: left; font-weight: bold;">Issue Type</th>
                    <th style="padding: 12px 8px; text-align: left; font-weight: bold;">Creation Time</th>
                    <th style="padding: 12px 8px; text-align: left; font-weight: bold;">Cost Since Created</th>
                </tr>
            </thead>
            <tbody>
    """
    
    # Add table rows
    for rank, (_, row) in enumerate(non_compliant_df_sorted.iterrows(), 1):
        # Determine row color based on issue type
        row_color = "#ffcdd2" if row['issue'] == 'Missing CENVID' else "#ffe0b2"
        issue_icon = "❌" if row['issue'] == 'Missing CENVID' else "⚠️"
        
        # Format valid CENVIDs
        valid_cenvids_str = ', '.join(row['valid_cenvids'])
        if len(valid_cenvids_str) > 50:  # Truncate if too long
            valid_cenvids_str = valid_cenvids_str[:47] + "..."
        
        # Format current CENVID
        current_cenvid = row['current_cenvid'] if row['current_cenvid'] and row['current_cenvid'] != 'None' else '<span style="color: #999; font-style: italic;">None</span>'
        
        html_table += f"""
                <tr style="background-color: {row_color};">
                    <td style="padding: 8px; text-align: center; font-weight: bold; color: #d32f2f;">#{rank}</td>
                    <td style="padding: 8px; font-family: monospace; font-weight: bold;">{row['snapshot_id']}</td>
                    <td style="padding: 8px; font-weight: bold;">{row['ccid']}</td>
                    <td style="padding: 8px;">{current_cenvid}</td>
                    <td style="padding: 8px; font-size: 11px;">{valid_cenvids_str}</td>
                    <td style="padding: 8px; font-weight: bold;">{issue_icon} {row['issue']}</td>
                    <td style="padding: 8px;">{row['creation_time']}</td>
                    <td style="padding: 8px; font-weight: bold; color: #d32f2f;">{row['cost_since_created']}</td>
                </tr>
        """
    
    html_table += """
            </tbody>
        </table>
        
        <div style="margin-top: 15px; padding: 10px; background-color: #fff3e0; border-left: 4px solid #ff9800; font-family: Arial, sans-serif;">
            <h4 style="margin: 0 0 8px 0; color: #ef6c00;">📋 Action Required:</h4>
            <ul style="margin: 0; padding-left: 20px; color: #666;">
                <li><strong>Missing CENVID (❌):</strong> Add appropriate CENVID tag from the valid list</li>
                <li><strong>Invalid CENVID (⚠️):</strong> Update current CENVID to match valid options</li>
                <li><strong>Priority:</strong> Address highest cost items first to maximize impact</li>
            </ul>
        </div>
    </div>
    """
    
    return html_table

def generate_compliance_summary_table(non_compliant_details):
    """Generate compliance summary table for dashboard"""
    if not non_compliant_details:
        return """
        <div style="margin: 20px 0; padding: 15px; border: 2px solid #4caf50; border-radius: 8px; background-color: #e8f5e8;">
            <h3 style="color: #2e7d32; margin-top: 0; font-family: Arial, sans-serif;">
                ✅ Perfect Compliance!
            </h3>
            <p style="color: #666; font-family: Arial, sans-serif;">All snapshots are properly tagged and compliant.</p>
        </div>
        """
    
    # Group by issue type
    missing_cenvid = [item for item in non_compliant_details if item['issue'] == 'Missing CENVID']
    invalid_cenvid = [item for item in non_compliant_details if item['issue'] == 'Invalid CENVID']
    
    # Calculate total cost impact
    total_cost = 0
    for item in non_compliant_details:
        try:
            cost_str = str(item['cost_since_created']).replace('$', '').replace(',', '')
            total_cost += float(cost_str)
        except:
            pass
    
    return f"""
    <div style="margin: 20px 0; padding: 15px; border: 2px solid #ff9800; border-radius: 8px; background-color: #fff8e1;">
        <h3 style="color: #ef6c00; margin-top: 0; font-family: Arial, sans-serif;">
            📊 Non-Compliance Summary
        </h3>
        
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; margin-bottom: 15px;">
            <thead>
                <tr style="background-color: #ff9800; color: white;">
                    <th style="padding: 10px; text-align: left;">Issue Type</th>
                    <th style="padding: 10px; text-align: center;">Count</th>
                    <th style="padding: 10px; text-align: center;">Percentage</th>
                </tr>
            </thead>
            <tbody>
                <tr style="background-color: #ffcdd2;">
                    <td style="padding: 8px;">❌ Missing CENVID</td>
                    <td style="padding: 8px; text-align: center; font-weight: bold;">{len(missing_cenvid)}</td>
                    <td style="padding: 8px; text-align: center; font-weight: bold;">{(len(missing_cenvid)/len(non_compliant_details)*100):.1f}%</td>
                </tr>
                <tr style="background-color: #ffe0b2;">
                    <td style="padding: 8px;">⚠️ Invalid CENVID</td>
                    <td style="padding: 8px; text-align: center; font-weight: bold;">{len(invalid_cenvid)}</td>
                    <td style="padding: 8px; text-align: center; font-weight: bold;">{(len(invalid_cenvid)/len(non_compliant_details)*100):.1f}%</td>
                </tr>
                <tr style="background-color: #ffecb3; font-weight: bold;">
                    <td style="padding: 8px;">📊 Total Non-Compliant</td>
                    <td style="padding: 8px; text-align: center; font-weight: bold;">{len(non_compliant_details)}</td>
                    <td style="padding: 8px; text-align: center; font-weight: bold;">100%</td>
                </tr>
            </tbody>
        </table>
        
        <div style="background-color: #fff3e0; padding: 10px; border-radius: 5px;">
            <p style="margin: 0; color: #ef6c00; font-weight: bold;">
                💰 Total Cost Impact: ${total_cost:.2f}
            </p>
        </div>
    </div>
    """

def generate_html_report():
    if not st.session_state.get('analysis_complete', False):
        return "No analysis data available."
    df_html = st.session_state.filtered_df.to_html(index=False)
    summary = st.session_state.summary_stats
    
    # Generate tag compliance section
    compliance_html = ""
    if 'tag_compliance' in summary:
        compliance = summary['tag_compliance']
        if compliance['status'] == 'Compliance check completed':
            compliance_color = "#4caf50" if compliance['compliance_percentage'] >= 80 else "#ff9800" if compliance['compliance_percentage'] >= 60 else "#f44336"
            
            compliance_html = f"""
    <div style="background:linear-gradient(135deg, #e8f5e8, #f1f8e9);border:2px solid {compliance_color};border-radius:15px;padding:0 0 20px 0;margin-bottom:20px;box-shadow:0 8px 16px rgba(0,0,0,0.1);">
        <div style="background:linear-gradient(135deg, {compliance_color}, {compliance_color}dd);color:#fff;border-radius:15px 15px 0 0;padding:15px 0 15px 25px;font-size:1.3em;font-weight:bold;letter-spacing:0.8px;text-shadow:1px 1px 2px rgba(0,0,0,0.3);">
            🏷️ Tag Compliance Coverage
        </div>
        <div style="padding:20px;">
            <table style="width:100%;font-size:1.2em;color:{compliance_color};text-align:center;border-collapse:collapse;">
                <tr style="background:rgba(76,175,80,0.1);">
                    <td style="padding:15px;border:1px solid {compliance_color}40;"><b>📊 Total Instances</b></td>
                    <td style="padding:15px;border:1px solid {compliance_color}40;"><b>✅ Compliant</b></td>
                    <td style="padding:15px;border:1px solid {compliance_color}40;"><b>❌ Non-Compliant</b></td>
                    <td style="padding:15px;border:1px solid {compliance_color}40;"><b>📈 Compliance Rate</b></td>
                </tr>
                <tr>
                    <td style="font-size:2em;color:{compliance_color};padding:20px;font-weight:bold;text-shadow:1px 1px 2px rgba(0,0,0,0.1);">{compliance['total_instances']}</td>
                    <td style="font-size:2em;color:{compliance_color};padding:20px;font-weight:bold;text-shadow:1px 1px 2px rgba(0,0,0,0.1);">{compliance['compliant_instances']}</td>
                    <td style="font-size:2em;color:{compliance_color};padding:20px;font-weight:bold;text-shadow:1px 1px 2px rgba(0,0,0,0.1);">{compliance['non_compliant_instances']}</td>
                    <td style="font-size:2em;color:{compliance_color};padding:20px;font-weight:bold;text-shadow:1px 1px 2px rgba(0,0,0,0.1);">{compliance['compliance_percentage']}%</td>
                </tr>
            </table>
        </div>
    </div>
    
            """
    
    summary_html = f"""
    <div style="background:#e3f2fd;color:#1976d2;padding:18px 24px 10px 24px;border-radius:8px;font-size:1.2em;font-weight:bold;letter-spacing:0.5px;">
        Snapshot Analysis Report
    </div>
    <br>
    <div style="background:#f5faff;color:#222;padding:10px 20px 10px 20px;border-radius:8px;margin-bottom:16px;font-size:1em;border-left:4px solid #1976d2;">
        <b>CCID:</b> {summary['ccid']}<br>
        <b>Server Type:</b> Snapshot<br>
        <b>Generated:</b> {summary['generated']}<br>
        <b>Analysis Type:</b> Cost & Age Overview
    </div>
    <div style="background:#fff;border:2px solid #1976d2;border-radius:10px;padding:0 0 16px 0;margin-bottom:16px;">
        <div style="background:#1976d2;color:#fff;border-radius:10px 10px 0 0;padding:12px 0 12px 20px;font-size:1.2em;font-weight:bold;letter-spacing:0.5px;">
            Executive Summary
        </div>
        <table style="width:100%;font-size:1.1em;color:#1976d2;"text-align:center;">
            <tr>
                <td><b>Total Snapshots</b></td>
                <td><b>Wastage till date</b></td>
                <td><b>Potential 30-day cost</b></td>
                <td><b>Oldest snapshot</b></td>
                <td><b>Highest billed snapshot</b></td>
            </tr>
            <tr>
                <td style="font-size:1.7em;color:#1976d2;">{summary['snapshot_count']}</td>
                <td style="font-size:1.7em;color:#1976d2;">${summary['wastage']:.2f}</td>
                <td style="font-size:1.7em;color:#1976d2;">${summary['potential_savings']:.2f}</td>
                <td style="font-size:1.7em;color:#1976d2;">{summary['oldest_snapshot']}</td>
                <td style="font-size:1.7em;color:#1976d2;">{summary['max_cost_snapshot']}</td>
            </tr>
        </table>
    </div>
    {compliance_html}
    <div style="background:#fff8e1;color:#333;border-left:5px solid #ffb300;padding:12px 18px 12px 18px;margin-bottom:18px;border-radius:8px;font-size:1em;">
        <b>Notes:</b>
        <ul>
            <li>Snapshots with IDs starting with 'pvc' have been excluded from this analysis.</li>
            <li>Highlighted rows in the table indicate the highest billed snapshots.</li>
            <li>Contact your IT team for further optimization suggestions.</li>
        </ul>
    </div>
    """
    return summary_html

# Styled title
st.markdown('<div class="main-header"><h1>📊 CCID Snapshot Summary Dashboard</h1></div>', unsafe_allow_html=True)

# Load compliance data at startup
compliance_mapping = {}
compliance_file_path = r"C:\Users\sarat\Desktop\FinOps\Tags.json"
if os.path.exists(compliance_file_path):
    compliance_mapping = load_compliance_data(compliance_file_path)

uploaded_file = st.file_uploader(
    "Choose an Excel file", type=["xlsx"], key="snapshot_file_uploader"
)

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)

    # Normalize CCID and CENVID columns
    if 'o9 CCID tag' in df.columns:
        df['o9 CCID tag'] = df['o9 CCID tag'].astype(str).str.upper().str.strip()

    if 'o9 CENVID tag' in df.columns:
        df['o9 CENVID tag'] = df['o9 CENVID tag'].astype(str).str.upper().str.strip()

    df['o9 CCID tag'] = df['o9 CCID tag'].apply(normalize_ccid)
    ccid_options = df['o9 CCID tag'].unique()
    selected_ccid = st.selectbox(
        'Select CCID to filter', ccid_options, key="snapshot_ccid_select"
    )

    if selected_ccid:
        filtered = df[df['o9 CCID tag'] == selected_ccid]
        filtered = filtered[~filtered['Snapshot ID'].str.startswith('pvc', na=False)]
        filtered['Creation Time'] = pd.to_datetime(filtered['Creation Time'])
        filtered['Creation Time'] = filtered['Creation Time'].apply(to_naive)

        # Sort by Creation Time (newest first)
        filtered = filtered.sort_values(by='Creation Time', ascending=False)
        # Sort by Cost Since Created (largest billed first)
        filtered = filtered.sort_values(by='Cost Since Created', ascending=False)

        now = datetime.now()
        filtered['Creation Time Raw'] = filtered['Creation Time']
        filtered['Creation Time'] = filtered['Creation Time Raw'].apply(
            lambda x: format_creation_time_custom(x, now)
        )

        # Executive Summary values FOR SELECTED CCID ONLY
        snapshot_count = len(filtered)
        wastage = filtered['Cost Since Created'].sum()
        potential_savings = (
            filtered['Cost 30-Day'].sum() if 'Cost 30-Day' in filtered.columns else 0
        )
        oldest_snapshot_str = (
            filtered['Creation Time Raw'].min().strftime('%Y-%m-%d')
            if not filtered.empty else "N/A"
        )
        max_cost_snapshot = (
            filtered.loc[filtered['Cost Since Created'].idxmax(), 'Snapshot ID']
            if not filtered.empty else "N/A"
        )

        # Check tag compliance
        tag_compliance = check_tag_compliance(filtered, selected_ccid, compliance_mapping)

        # Store for dashboard/email
        st.session_state.filtered_df = filtered.drop(columns=['Creation Time Raw']).copy()
        st.session_state.summary_stats = {
            'ccid': selected_ccid,
            'wastage': wastage,
            'potential_savings': potential_savings,
            'snapshot_count': snapshot_count,
            'oldest_snapshot': oldest_snapshot_str,
            'max_cost_snapshot': max_cost_snapshot,
            'generated': now.strftime('%Y-%m-%d %H:%M:%S'),
            'tag_compliance': tag_compliance
        }
        st.session_state.analysis_complete = True

        # Show the summary (HTML) and the scrollable table
        st.markdown(generate_html_report(), unsafe_allow_html=True)
        st.dataframe(
            filtered.drop(columns=['Creation Time Raw']),
            use_container_width=True,
            height=400
        )

        # Display non-compliant instances if any
        if st.session_state.summary_stats['tag_compliance'].get('non_compliant_details'):
            display_non_compliant_instances(st.session_state.summary_stats['tag_compliance']['non_compliant_details'])

        # Button to save results to dashboard/server
        if st.button("Save Results to Dashboard", key="save_summary_button"):
            summary_html = generate_html_report()
            with open("snap_summary.html", "w", encoding="utf-8") as f:
                f.write(summary_html)
            st.success("Snapshot summary saved to dashboard! You can now send all results from the main dashboard.")
            st.balloons()

else:
    st.info('Please upload an Excel file to get started.')
