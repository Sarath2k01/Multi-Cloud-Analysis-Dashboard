import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import json
import os
from collections import defaultdict
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- EMAIL CONFIGURATION (for dashboard use only) ---
EMAIL_CONFIG = {
    "sender_email": "sarath2k01@gmail.com",
    "sender_password": "wfdm pyrq oimd thkh",  # Gmail App Password
    "recipients": [
        "junkiemail341@gmail.com",
        # "bharath4034.madala@gmail.com"
    ],
    "subject_prefix": "Unattached Disks Summary Report"
}

st.set_page_config(page_title="Unattached Disks Analysis Report", layout="wide")

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
            ccid = entry.get("CCID (Unique Per Customer)", "").strip()
            if not ccid or ccid == "":
                continue
            
            # Extract all non-empty CENVIDs for this CCID
            cenvids = []
            for key in ["CENVID (PRE PROD)", "CENVID (PROD)", "CENVID (DEV)", "CENVID (STG)", "CENVID(PSR)"]:
                cenvid = entry.get(key, "").strip()
                if cenvid and cenvid != "":
                    cenvids.append(cenvid)
            
            # Add all valid CENVIDs for this CCID
            ccid_cenvid_mapping[ccid].update(cenvids)
        
        # Convert sets to lists for easier handling
        return {ccid: list(cenvids) for ccid, cenvids in ccid_cenvid_mapping.items()}
    
    except Exception as e:
        return {}

def check_tag_compliance(df, ccid, compliance_mapping):
    """Check tag compliance for unattached disks"""
    if not compliance_mapping:
        return {
            'total_instances': len(df),
            'compliant_instances': 0,
            'non_compliant_instances': len(df),
            'compliance_percentage': 0,
            'status': 'No compliance data available'
        }
    
    if ccid not in compliance_mapping:
        return {
            'total_instances': len(df),
            'compliant_instances': 0,
            'non_compliant_instances': len(df),
            'compliance_percentage': 0,
            'status': f'CCID {ccid} not found in compliance mapping'
        }
    
    valid_cenvids = compliance_mapping[ccid]
    total_instances = len(df)
    compliant_count = 0
    
    for idx, row in df.iterrows():
        instance_cenvid = row.get('o9 CENVID', '')
        if instance_cenvid in valid_cenvids:
            compliant_count += 1
    
    compliance_percentage = (compliant_count / total_instances * 100) if total_instances > 0 else 0
    
    return {
        'total_instances': total_instances,
        'compliant_instances': compliant_count,
        'non_compliant_instances': total_instances - compliant_count,
        'compliance_percentage': round(compliance_percentage, 2),
        'status': 'Compliance check completed'
    }

def analyze_tag_coverage(df):
    """Analyze tag coverage across all instances"""
    total_instances = len(df)
    
    if total_instances == 0:
        return {
            'total_instances': 0,
            'tagged_instances': 0,
            'untagged_instances': 0,
            'coverage_percentage': 0,
            'missing_tags': {}
        }
    
    # Define required tags
    required_tags = ['o9 CCID', 'o9 CENVID']
    
    tagged_count = 0
    missing_tags = {tag: 0 for tag in required_tags}
    
    for idx, row in df.iterrows():
        instance_has_all_tags = True
        
        for tag in required_tags:
            tag_value = str(row.get(tag, '')).strip()
            if not tag_value or tag_value == '' or tag_value.lower() == 'nan':
                missing_tags[tag] += 1
                instance_has_all_tags = False
        
        if instance_has_all_tags:
            tagged_count += 1
    
    coverage_percentage = (tagged_count / total_instances * 100) if total_instances > 0 else 0
    
    return {
        'total_instances': total_instances,
        'tagged_instances': tagged_count,
        'untagged_instances': total_instances - tagged_count,
        'coverage_percentage': round(coverage_percentage, 2),
        'missing_tags': missing_tags
    }

def generate_dashboard_report(summary_stats, selected_ccid):
    """Generate full-width dashboard-style report"""
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Get oldest disk date for display
    oldest_disk_date = "N/A"
    if summary_stats['oldest_disk'] != 'N/A':
        oldest_disk_date = summary_stats['oldest_disk'].split(' (')[0] if ' (' in summary_stats['oldest_disk'] else summary_stats['oldest_disk']
    
    dashboard_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Unattached Disks Analysis Report</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
                background-color: #2c3e50;
                color: white;
                width: 100vw;
                overflow-x: hidden;
            }}
            .container {{
                width: 100%;
                max-width: 100vw;
                margin: 0;
                padding: 20px;
                box-sizing: border-box;
            }}
            .report-section {{
                background: #34495e;
                margin: 20px 0;
                border-radius: 8px;
                overflow: hidden;
                width: 100%;
            }}
            .section-header {{
                padding: 20px 30px;
                font-weight: bold;
                font-size: 20px;
            }}
            .section-content {{
                padding: 30px;
                background: #ecf0f1;
                color: #2c3e50;
            }}
            .info-header {{
                background: #6c9bd1;
            }}
            .summary-header {{
                background: #4a90e2;
            }}
            .compliance-header {{
                background: #5cb85c;
            }}
            .notes-header {{
                background: #f39c12;
            }}
            .metric-grid {{
                display: grid;
                grid-template-columns: repeat(5, 1fr);
                gap: 25px;
                margin: 20px 0;
                width: 100%;
            }}
            .compliance-grid {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 25px;
                margin: 20px 0;
                width: 100%;
            }}
            .metric-item {{
                text-align: center;
                padding: 25px 15px;
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .metric-label {{
                font-weight: bold;
                color: #6c9bd1;
                margin-bottom: 15px;
                font-size: 14px;
                line-height: 1.3;
            }}
            .metric-value {{
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                line-height: 1.2;
                word-break: break-word;
            }}
            .info-grid {{
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 30px;
                width: 100%;
            }}
            .info-item {{
                display: flex;
                justify-content: space-between;
                margin: 8px 0;
                padding: 12px;
                background: white;
                border-radius: 5px;
                align-items: center;
            }}
            .info-label {{
                font-weight: bold;
                color: #6c9bd1;
            }}
            ul {{
                margin: 15px 0;
                padding-left: 25px;
            }}
            li {{
                margin: 10px 0;
                line-height: 1.6;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="report-section">
                <div class="section-header info-header">
                    Unattached Disks Analysis Report
                </div>
                <div class="section-content">
                    <div class="info-grid">
                        <div>
                            <div class="info-item">
                                <span class="info-label">CCID:</span>
                                <span>{selected_ccid}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Analysis Type:</span>
                                <span>Cost & Age Overview</span>
                            </div>
                        </div>
                        <div>
                            <div class="info-item">
                                <span class="info-label">Generated:</span>
                                <span>{current_time}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Resource Type:</span>
                                <span>Unattached Disk</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="report-section">
                <div class="section-header summary-header">
                    Executive Summary
                </div>
                <div class="section-content">
                    <div class="metric-grid">
                        <div class="metric-item">
                            <div class="metric-label">Total Disks</div>
                            <div class="metric-value">{summary_stats['disk_count']}</div>
                        </div>
                        <div class="metric-item">
                            <div class="metric-label">Wastage till date</div>
                            <div class="metric-value">${summary_stats['wastage']:.2f}</div>
                        </div>
                        <div class="metric-item">
                            <div class="metric-label">Potential 30-day cost</div>
                            <div class="metric-value">${summary_stats['potential_savings']:.2f}</div>
                        </div>
                        <div class="metric-item">
                            <div class="metric-label">Oldest disk</div>
                            <div class="metric-value" style="font-size: 16px;">{oldest_disk_date}</div>
                        </div>
                        <div class="metric-item">
                            <div class="metric-label">Highest billed disk</div>
                            <div class="metric-value" style="font-size: 14px;">{summary_stats['max_cost_disk'].split(' (')[0] if ' (' in summary_stats['max_cost_disk'] else summary_stats['max_cost_disk']}</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="report-section">
                <div class="section-header compliance-header">
                    Tag Compliance Coverage
                </div>
                <div class="section-content">
                    <div class="compliance-grid">
                        <div class="metric-item">
                            <div class="metric-label">Total Disks</div>
                            <div class="metric-value">{summary_stats['tag_compliance']['total_instances']}</div>
                        </div>
                        <div class="metric-item">
                            <div class="metric-label">Compliant</div>
                            <div class="metric-value">{summary_stats['tag_compliance']['compliant_instances']}</div>
                        </div>
                        <div class="metric-item">
                            <div class="metric-label">Non-Compliant</div>
                            <div class="metric-value">{summary_stats['tag_compliance']['non_compliant_instances']}</div>
                        </div>
                        <div class="metric-item">
                            <div class="metric-label">Compliance Rate</div>
                            <div class="metric-value">{summary_stats['tag_compliance']['compliance_percentage']}%</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="report-section">
                <div class="section-header notes-header">
                    Notes:
                </div>
                <div class="section-content">
                    <ul>
                        <li>Disks with IDs starting with 'pvc' have been excluded from this analysis.</li>
                        <li>Highlighted rows in the table indicate the highest billed disks.</li>
                        <li>Contact your IT team for further optimization suggestions.</li>
                    </ul>
                </div>
            </div>
            
        </div>
    </body>
    </html>
    """
    
    return dashboard_html

def analyze_unattached_disks(df, ccid, compliance_mapping):
    """Analyze unattached disks data"""
    current_date = datetime.now()
    
    # Filter out disks with IDs starting with 'pvc' (as mentioned in notes)
    df = df[~df['Disk Name'].str.startswith('pvc', na=False)]
    
    # Basic statistics
    total_disks = len(df)
    
    if total_disks == 0:
        return {
            'disk_count': 0,
            'total_size_gb': 0,
            'wastage': 0,
            'potential_savings': 0,
            'oldest_disk': 'N/A',
            'max_cost_disk': 'N/A',
            'tag_compliance': {
                'total_instances': 0,
                'compliant_instances': 0,
                'non_compliant_instances': 0,
                'compliance_percentage': 0,
                'status': 'No data available'
            },
            'tag_coverage': {
                'total_instances': 0,
                'tagged_instances': 0,
                'untagged_instances': 0,
                'coverage_percentage': 0,
                'missing_tags': {}
            }
        }
    
    # Calculate total size
    total_size_gb = df['Size'].sum()
    
    # Calculate costs using existing cost columns
    total_wastage = df['Cost Since Created'].sum()
    potential_monthly_savings = df['Cost 30-Day'].sum()
    
    # Find highest cost disk
    if len(df) > 0:
        max_cost_idx = df['Cost Since Created'].idxmax()
        max_cost_disk = f"{df.loc[max_cost_idx, 'Disk Name']} (${df.loc[max_cost_idx, 'Cost Since Created']:.2f})"
    else:
        max_cost_disk = "N/A"
    
    # Find oldest disk by last detachment time
    df['Last Detachment Time'] = pd.to_datetime(df['Last Detachment Time'])
    # Convert to naive datetime to avoid timezone comparison issues
    df['Last Detachment Time'] = df['Last Detachment Time'].dt.tz_localize(None)
    
    oldest_disk_row = df.loc[df['Last Detachment Time'].idxmin()]
    oldest_disk_age = format_creation_time_custom(oldest_disk_row['Last Detachment Time'], current_date)
    oldest_disk = f"{oldest_disk_row.get('Disk Name', 'Unknown')} ({oldest_disk_age})"
    
    # Check tag compliance
    tag_compliance = check_tag_compliance(df, ccid, compliance_mapping)
    
    # Analyze tag coverage
    tag_coverage = analyze_tag_coverage(df)
    
    return {
        'disk_count': total_disks,
        'total_size_gb': total_size_gb,
        'wastage': total_wastage,
        'potential_savings': potential_monthly_savings,
        'oldest_disk': oldest_disk,
        'max_cost_disk': max_cost_disk,
        'tag_compliance': tag_compliance,
        'tag_coverage': tag_coverage
    }

def main():
    """Main application function"""
    st.markdown('<div class="main-header"><h1>🔍 Unattached EBS Volumes Analysis</h1></div>', unsafe_allow_html=True)
    
    # Hardcoded JSON file path for compliance data
    json_file_path = "tag_compliance.json"
    
    # Load compliance data from hardcoded path
    compliance_mapping = load_compliance_data(json_file_path)
    
    # File upload for unattached disks data (drag and drop Excel support)
    uploaded_file = st.file_uploader(
        "Drag and drop or click to upload Unattached Disks Excel file",
        type=['xlsx', 'xls'],
        help="Upload Excel file containing unattached EBS volumes data"
    )
    
    if uploaded_file is not None:
        try:
            # Load the Excel data
            df = pd.read_excel(uploaded_file)
            
            # Display basic info
            st.info(f"📊 Loaded {len(df)} unattached disk records from {uploaded_file.name}")
            
            # CCID filter (exactly like snapshots.py)
            if 'o9 CCID' in df.columns:
                ccids = ['All'] + sorted(df['o9 CCID'].dropna().unique().tolist())
                selected_ccid = st.selectbox("Select CCID", ccids)
                
                if selected_ccid != 'All':
                    df = df[df['o9 CCID'] == selected_ccid]
                    ccid_for_compliance = selected_ccid
                else:
                    ccid_for_compliance = 'All'
            else:
                selected_ccid = 'All'
                ccid_for_compliance = 'All'
            
            # Sort by Last Detachment Time (oldest first)
            if 'Last Detachment Time' in df.columns:
                df['Last Detachment Time'] = pd.to_datetime(df['Last Detachment Time'])
                df = df.sort_values('Last Detachment Time', ascending=True)
            
            # Store filtered data
            st.session_state.filtered_df = df
            
            # Analyze the data
            if len(df) > 0:
                summary_stats = analyze_unattached_disks(df, ccid_for_compliance, compliance_mapping)
                st.session_state.summary_stats = summary_stats
                st.session_state.analysis_complete = True
                
                # Generate and display dashboard report
                dashboard_html = generate_dashboard_report(summary_stats, selected_ccid)
                st.components.v1.html(dashboard_html, height=900, scrolling=True)
                
                # Data table with full width - Filter out PVC disks for display
                st.header("📋 Detailed Disk Information")
                
                # Filter out PVC disks from the display table
                display_df = df[~df['Disk Name'].str.startswith('pvc', na=False)].copy()
                
                # Replace Create Time column with age format
                if 'Create Time' in display_df.columns:
                    current_date = datetime.now()
                    display_df['Create Time'] = display_df['Create Time'].apply(lambda x: format_creation_time_custom(pd.to_datetime(x).replace(tzinfo=None), current_date))
                
                # Replace Last Detachment Time column with age format
                if 'Last Detachment Time' in display_df.columns:
                    current_date = datetime.now()
                    display_df['Last Detachment Time'] = display_df['Last Detachment Time'].apply(
                        lambda x: format_creation_time_custom(pd.to_datetime(x).replace(tzinfo=None), current_date) if pd.notna(x) and x != '' else 'N/A'
                    )
                
                st.dataframe(display_df, use_container_width=True)
                
                # Button to save results to dashboard/server
                if st.button("Save Results to Dashboard", key="save_summary_button"):
                    with open("disks_summary.html", "w", encoding="utf-8") as f:
                        f.write(dashboard_html)
                    st.success("Disk dashboard report saved! You can now access the styled report from the saved HTML file.")
                    st.balloons()
            
            else:
                st.warning("No data matches the selected filters.")
        
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
            st.info("Please ensure the uploaded Excel file contains the expected columns.")
    
    else:
        st.info("👆 Please upload an Excel file containing unattached disks data to begin analysis.")

if __name__ == "__main__":
    main()
