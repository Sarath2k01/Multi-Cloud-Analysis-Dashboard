import streamlit as st
import pandas as pd
import json
import math
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import warnings
import plotly.graph_objects as go
import plotly.express as px

# Suppress openpyxl warnings
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')


# Page configuration
st.set_page_config(
    page_title="Azure VM Right-Sizing Tool",
    page_icon="☁️",
    layout="wide"
)

# HARDCODED EMAIL CONFIGURATION - UPDATE THESE VALUES
EMAIL_CONFIG = {
    "sender_email": "sarath2k01@gmail.com",
    "sender_password": "wfdm pyrq oimd thkh",
    "recipients": [
        "junkiemail341@gmail.com",
        # "bharath4034.madala@gmail.com"
    ],
    "subject_prefix": "Azure VM Right-Sizing Analysis Report"
}

def clean_dataframe_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """Clean DataFrame to make it Arrow-compatible for Streamlit display"""
    df_clean = df.copy()
    
    # List of columns that should be numeric but might contain 'N/A'
    numeric_columns = [
        'Current vCPUs', 'Standard CPU Target'
    ]
    
    # Convert string 'N/A' to NaN for numeric columns
    for col in numeric_columns:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
    
    return df_clean

def load_azure_pricing_data() -> pd.DataFrame:
    """Load Azure pricing data from the JSON file"""
    try:
        with open(r"C:\Users\sarat\Desktop\FinOps\azure-data.json", 'r') as file:
            azure_data = json.load(file)
        
        df = pd.DataFrame(azure_data)
        df['memoryInGB'] = df['memoryInMB'].astype(float)
        df['numberOfCores'] = df['numberOfCores'].astype(int)
        
        def clean_price(price_str):
            if pd.isna(price_str) or price_str == '' or str(price_str).lower() in ['n/a', 'na', 'null', 'none']:
                return None
            try:
                cleaned = str(price_str).replace(',', '').replace('$', '').replace(' ', '')
                return float(cleaned)
            except:
                return None
        
        df['linuxPrice'] = df['linuxPrice'].apply(clean_price)
        df['windowsPrice'] = df['windowsPrice'].apply(clean_price)
        
        return df
    except Exception as e:
        st.error(f"Error loading Azure pricing data: {str(e)}")
        return pd.DataFrame()

def map_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map data source columns to required column names"""
    column_mapping = {
        'Total Memory (GB)': 'Total Memory',
    }
    
    mapped_df = df.copy()
    mapped_df = mapped_df.rename(columns=column_mapping)
    
    return mapped_df

def calculate_actual_usage(max_cpu_percent: float, max_mem_percent: float, 
                          current_vcpus: int, current_memory_gb: float) -> Tuple[float, float]:
    """Calculate actual CPU cores and memory used based on percentages"""
    actual_cpu_cores = (max_cpu_percent / 100) * current_vcpus
    actual_memory_gb = (max_mem_percent / 100) * current_memory_gb
    return actual_cpu_cores, actual_memory_gb

def calculate_projected_requirements(actual_cpu_cores: float, actual_memory_gb: float, 
                                   buffer_percent: float = 30) -> Tuple[float, float]:
    """Calculate projected requirements with buffer"""
    projected_cpu = actual_cpu_cores * (1 + buffer_percent / 100)
    projected_memory = actual_memory_gb * (1 + buffer_percent / 100)
    
    return projected_cpu, projected_memory

def get_standard_cpu_sizes() -> List[int]:
    """Get standard CPU sizes with 4 vCPU minimum"""
    return [4, 8, 16, 32, 64, 128]

def get_standard_memory_sizes() -> List[int]:
    """Get standard memory sizes"""
    return [4, 8, 16, 32, 64, 128, 256, 512, 1024]

def round_up_to_standard_cpu(projected_cpu: float) -> int:
    """Always round UP to next standard CPU size with 4 vCPU minimum"""
    standard_sizes = get_standard_cpu_sizes()
    
    for size in standard_sizes:
        if size >= projected_cpu:
            return size
    
    return max(standard_sizes)

def round_up_to_standard_memory(projected_memory: float) -> int:
    """Always round UP to next standard memory size"""
    standard_sizes = get_standard_memory_sizes()
    
    for size in standard_sizes:
        if size >= projected_memory:
            return size
    
    return max(standard_sizes)

def determine_platform_pricing(platform: str) -> str:
    """Determine correct price column based on platform with better detection"""
    platform_lower = str(platform).lower()
    
    # Linux variants
    linux_keywords = ['linux', 'ubuntu', 'centos', 'rhel', 'redhat', 'suse', 'debian']
    if any(keyword in platform_lower for keyword in linux_keywords):
        return 'linuxPrice'
    
    # Windows variants  
    windows_keywords = ['windows', 'win']
    if any(keyword in platform_lower for keyword in windows_keywords):
        return 'windowsPrice'
    
    # Default to Linux if unclear
    return 'linuxPrice'

def get_current_instance_price_with_fallback(instance_type: str, platform: str, azure_df: pd.DataFrame) -> Optional[float]:
    """Get price with comprehensive fallback logic"""
    price_column = determine_platform_pricing(platform)
    
    # Try exact match first
    instance_data = azure_df[azure_df['name'] == instance_type]
    
    if not instance_data.empty:
        price = instance_data.iloc[0][price_column]
        if not pd.isna(price) and price is not None:
            return price  # Only return price, not source
    
    # Fallback 1: Try similar instance family
    if '_' in instance_type:
        parts = instance_type.split('_')
        if len(parts) >= 2:
            base_family = parts[1]
            similar_pattern = f"Standard_{base_family}"
            similar_instances = azure_df[azure_df['name'].str.startswith(similar_pattern, na=False)]
            
            if not similar_instances.empty:
                valid_prices = similar_instances.dropna(subset=[price_column])
                if not valid_prices.empty:
                    avg_price = valid_prices[price_column].mean()
                    return avg_price  # Only return price, not source
    
    return None  # Only return None, not tuple


def find_cost_effective_instance(cpu_req: int, memory_req: int, platform: str, 
                               current_architecture: str, current_price: Optional[float], 
                               azure_df: pd.DataFrame) -> Optional[Dict]:
    """Find cheapest instance that meets requirements with same CPU architecture"""
    
    suitable_instances = azure_df[
        (azure_df['numberOfCores'] >= cpu_req) & 
        (azure_df['memoryInGB'] >= memory_req) &
        (azure_df['cpuArchitecture'] == current_architecture)
    ].copy()
    
    if suitable_instances.empty:
        return None
    
    price_column = determine_platform_pricing(platform)
    suitable_instances = suitable_instances.dropna(subset=[price_column])
    
    if suitable_instances.empty:
        return None
    
    if current_price is not None:
        cheaper_options = suitable_instances[suitable_instances[price_column] < current_price]
        if not cheaper_options.empty:
            suitable_instances = cheaper_options
    
    cheapest = suitable_instances.loc[suitable_instances[price_column].idxmin()]
    
    return {
        'name': cheapest['name'],
        'cores': cheapest['numberOfCores'],
        'memory': cheapest['memoryInGB'],
        'price': cheapest[price_column],
        'architecture': cheapest['cpuArchitecture']
    }

def check_missing_data(row) -> bool:
    """Check if critical data is missing for analysis"""
    critical_fields = ['Max CPU (%)', 'Max Memory (%)', 'CPU Count', 'Total Memory', 'Instance Type', 'Platform']
    
    for field in critical_fields:
        value = row.get(field)
        if pd.isna(value) or value is None or value == '' or value == 0:
            return True
    return False

def should_skip_high_usage(max_cpu_percent: float, max_memory_percent: float) -> bool:
    """Skip instances with CPU ≥80% OR Memory ≥80% as they're already well-utilized"""
    return max_cpu_percent >= 80.0 or max_memory_percent >= 80.0

def create_analysis_table(df: pd.DataFrame, azure_df: pd.DataFrame) -> pd.DataFrame:
    """Create analysis table with updated logic and proper data types"""
    analysis_results = []
    
    for _, row in df.iterrows():
        try:
            if check_missing_data(row):
                analysis_results.append({
                    'Instance Name': row.get('Instance Name or ID', 'N/A'),
                    'Current vCPUs': 'N/A',
                    'Current Memory (GB)': 'N/A',
                    'Current CPU Usage (%)': 'N/A',
                    'Current Memory Usage (%)': 'N/A',
                    'Actual CPU Cores Used': 'N/A',
                    'Actual Memory Used (GB)': 'N/A',
                    'Projected CPU Cores (30% buffer)': 'N/A',
                    'Projected Memory (30% buffer)': 'N/A',
                    'Standard CPU Target': 'N/A',
                    'Standard Memory Target': 'N/A',
                    'CPU Architecture': 'N/A',
                    'Status': 'Insufficient Data'
                })
                continue
            
            cpu_usage_pct = row['Max CPU (%)']
            memory_usage_pct = row['Max Memory (%)']
            
            if should_skip_high_usage(cpu_usage_pct, memory_usage_pct):
                analysis_results.append({
                    'Instance Name': row.get('Instance Name or ID', 'N/A'),
                    'Current vCPUs': str(int(row['CPU Count'])),
                    'Current Memory (GB)': f"{row['Total Memory']:.1f}",
                    'Current CPU Usage (%)': f"{cpu_usage_pct:.1f}%",
                    'Current Memory Usage (%)': f"{memory_usage_pct:.1f}%",
                    'Actual CPU Cores Used': 'N/A',
                    'Actual Memory Used (GB)': 'N/A',
                    'Projected CPU Cores (30% buffer)': 'N/A',
                    'Projected Memory (30% buffer)': 'N/A',
                    'Standard CPU Target': 'N/A',
                    'Standard Memory Target': 'N/A',
                    'CPU Architecture': 'N/A',
                    'Status': 'High Usage (CPU≥80% OR Memory≥80%) - Skip'
                })
                continue
            
            current_vcpus = row['CPU Count']
            current_memory = row['Total Memory']
            
            actual_cpu, actual_memory = calculate_actual_usage(
                cpu_usage_pct, memory_usage_pct, current_vcpus, current_memory
            )
            
            projected_cpu, projected_memory = calculate_projected_requirements(
                actual_cpu, actual_memory, 30
            )
            
            standard_cpu = round_up_to_standard_cpu(projected_cpu)
            standard_memory = round_up_to_standard_memory(projected_memory)
            
            current_instance_data = azure_df[azure_df['name'] == row['Instance Type']]
            current_architecture = 'N/A'
            if not current_instance_data.empty:
                current_architecture = current_instance_data.iloc[0].get('cpuArchitecture', 'N/A')
            
            analysis_results.append({
                'Instance Name': row.get('Instance Name or ID', 'N/A'),
                'Current vCPUs': str(int(current_vcpus)),
                'Current Memory (GB)': f"{current_memory:.1f}",
                'Current CPU Usage (%)': f"{cpu_usage_pct:.1f}%",
                'Current Memory Usage (%)': f"{memory_usage_pct:.1f}%",
                'Actual CPU Cores Used': f"{actual_cpu:.2f}",
                'Actual Memory Used (GB)': f"{actual_memory:.1f}",
                'Projected CPU Cores (30% buffer)': f"{projected_cpu:.2f}",
                'Projected Memory (30% buffer)': f"{projected_memory:.1f}",
                'Standard CPU Target': str(int(standard_cpu)),
                'Standard Memory Target': f"{standard_memory} GB",
                'CPU Architecture': current_architecture,
                'Status': 'Ready for Analysis'
            })
            
        except Exception as e:
            analysis_results.append({
                'Instance Name': row.get('Instance Name or ID', 'N/A'),
                'Current vCPUs': 'Error',
                'Current Memory (GB)': 'Error',
                'Current CPU Usage (%)': 'Error',
                'Current Memory Usage (%)': 'Error',
                'Actual CPU Cores Used': 'Error',
                'Actual Memory Used (GB)': 'Error',
                'Projected CPU Cores (30% buffer)': 'Error',
                'Projected Memory (30% buffer)': 'Error',
                'Standard CPU Target': 'Error',
                'Standard Memory Target': 'Error',
                'CPU Architecture': 'Error',
                'Status': f'Processing Error: {str(e)}'
            })
    
    return pd.DataFrame(analysis_results)

def process_vm_data(df: pd.DataFrame, azure_df: pd.DataFrame) -> pd.DataFrame:
    """Process VM data with updated logic"""
    results = []
    
    for _, row in df.iterrows():
        try:
            if check_missing_data(row):
                results.append({
                    'CCID': row.get('o9 CCID', 'N/A'),
                    'Instance Name or ID': row.get('Instance Name or ID', 'N/A'),
                    'Instance Type(current)': row.get('Instance Type', 'N/A'),
                    'Recommended Instance Type': 'Insufficient Data',
                    'Current Instance Price': 'N/A',
                    'Recommended Instance Price': 'N/A',
                    'Savings': 'N/A',
                    'CPU Architecture': 'N/A',
                })
                continue
            
            if should_skip_high_usage(row['Max CPU (%)'], row['Max Memory (%)']):
                results.append({
                    'CCID': row.get('o9 CCID', 'N/A'),
                    'Instance Name or ID': row.get('Instance Name or ID', 'N/A'),
                    'Current CPU Usage (%)': f"{row['Max CPU (%)']:.1f}%",
                    'Current Memory Usage (%)': f"{row['Max Memory (%)']:.1f}%",
                    'Instance Type(current)': row['Instance Type'],
                    'Recommended Instance Type': 'High Usage - No Right-sizing',
                    'Current Instance Price': 'N/A',
                    'Recommended Instance Price': 'N/A',
                    'Savings': 'N/A',
                    'CPU Architecture': 'N/A',
                })

                continue
            
            actual_cpu, actual_memory = calculate_actual_usage(
                row['Max CPU (%)'], row['Max Memory (%)'], 
                row['CPU Count'], row['Total Memory']
            )
            
            projected_cpu, projected_memory = calculate_projected_requirements(
                actual_cpu, actual_memory, 30
            )
            
            standard_cpu = round_up_to_standard_cpu(projected_cpu)
            standard_memory = round_up_to_standard_memory(projected_memory)
            
            current_instance_data = azure_df[azure_df['name'] == row['Instance Type']]
            current_architecture = 'x64'
            if not current_instance_data.empty:
                current_architecture = current_instance_data.iloc[0].get('cpuArchitecture', 'x64')
            
            current_price = get_current_instance_price_with_fallback(
                row['Instance Type'], row['Platform'], azure_df
            )
            
            recommended = find_cost_effective_instance(
                standard_cpu, standard_memory, row['Platform'], 
                current_architecture, current_price, azure_df
            )
            
            savings = None
            savings_text = 'N/A'
            if current_price is not None and recommended is not None:
                savings = current_price - recommended['price']
                savings_text = f"${savings:.2f}"
            elif recommended is not None and current_price is None:
                savings_text = "Cannot Calculate (Current Price Unknown)"
            
            results.append({
                'CCID': row.get('o9 CCID', 'N/A'),
                'Instance Name or ID': row.get('Instance Name or ID', 'N/A'),
                'Current CPU Usage (%)': f"{row['Max CPU (%)']:.1f}%",
                'Current Memory Usage (%)': f"{row['Max Memory (%)']:.1f}%",
                'Instance Type(current)': row['Instance Type'],
                'Recommended Instance Type': recommended['name'] if recommended else 'No Suitable Instance',
                'Current Instance Price': f"${current_price:.2f}" if current_price is not None else 'N/A',
                'Recommended Instance Price': f"${recommended['price']:.2f}" if recommended else 'N/A',
                'Savings': savings_text,
                'CPU Architecture': recommended['architecture'] if recommended else current_architecture,
            })
            
        except Exception as e:
            results.append({
                    'CCID': row.get('o9 CCID', 'N/A'),
                    'Instance Name or ID': row.get('Instance Name or ID', 'N/A'),
                    'Current CPU Usage (%)': 'N/A',
                    'Current Memory Usage (%)': 'N/A',
                    'Instance Type(current)': row.get('Instance Type', 'N/A'),
                    'Recommended Instance Type': 'Insufficient Data',
                    'Current Instance Price': 'N/A',
                    'Recommended Instance Price': 'N/A',
                    'Savings': 'N/A',
                    'CPU Architecture': 'N/A',
            })

    
    return pd.DataFrame(results)


def generate_html_report(analysis_df: pd.DataFrame, recommendations_df: pd.DataFrame, 
                        summary_stats: Dict, ccid: str, server_type: str) -> str:
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Convert DataFrames to HTML
    recommendations_html = recommendations_df.to_html(
        index=False, 
        escape=False, 
        classes="recommendations-table",
        table_id="recommendations-table"
    )
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Azure VM Right-Sizing Analysis Report</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
                box-sizing: border-box;
            }}
            
            * {{
                box-sizing: border-box;
            }}
            
            .container {{
                max-width: 100%;
                margin: 0 auto;
                background: white;
                padding: 40px;
                border-radius: 15px;
                box-shadow: 0 0 25px rgba(0,0,0,0.1);
            }}
            
            .header {{
                text-align: center;
                margin-bottom: 40px;
                padding: 30px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border-radius: 15px;
            }}
            
            /* Improved Summary Section with Even Spacing */
            .summary-section {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 40px;
                border-radius: 20px;
                color: white;
                margin: 40px 0;
                box-shadow: 0 15px 35px rgba(0,0,0,0.2);
            }}
            
            .summary-title {{
                font-size: 2.2em;
                font-weight: bold;
                text-align: center;
                margin-bottom: 40px;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
            }}
            
            .summary-grid {{
                display: flex;
                justify-content: space-evenly;
                align-items: stretch;
                gap: 25px;
                margin-top: 30px;
                flex-wrap: wrap;
            }}
            
            .summary-card {{
                background: linear-gradient(135deg, #fff, #f8f9fa);
                border-radius: 18px;
                padding: 30px 20px;
                text-align: center;
                box-shadow: 0 10px 25px rgba(0,0,0,0.15);
                flex: 1 1 200px;
                min-width: 200px;
                max-width: 250px;
                border: 3px solid rgba(255,255,255,0.3);
                transition: transform 0.3s ease, box-shadow 0.3s ease;
                display: flex;
                flex-direction: column;
                justify-content: center;
            }}
            
            .summary-card:hover {{
                transform: translateY(-10px);
                box-shadow: 0 15px 30px rgba(0,0,0,0.25);
            }}
            
            .summary-value {{
                font-size: 2.5em;
                font-weight: bold;
                margin-bottom: 15px;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
                line-height: 1;
            }}
            
            .summary-label {{
                font-weight: 600;
                color: #555;
                font-size: 1em;
                line-height: 1.3;
                margin-top: auto;
            }}
            
            /* Improved Savings Section with Even Spacing */
            .savings-section {{
                background: linear-gradient(135deg, #4caf50 0%, #2e7d32 100%);
                padding: 40px;
                border-radius: 20px;
                color: white;
                margin: 40px 0;
                box-shadow: 0 15px 35px rgba(0,0,0,0.2);
            }}
            
            .savings-grid {{
                display: flex;
                justify-content: space-evenly;
                align-items: stretch;
                gap: 30px;
                margin-top: 30px;
                flex-wrap: wrap;
            }}
            
            .savings-card {{
                background: linear-gradient(135deg, #fff, #f8f9fa);
                border-radius: 18px;
                padding: 35px 25px;
                text-align: center;
                box-shadow: 0 10px 25px rgba(0,0,0,0.15);
                flex: 1 1 250px;
                min-width: 250px;
                max-width: 300px;
                border: 3px solid rgba(255,255,255,0.3);
                transition: transform 0.3s ease, box-shadow 0.3s ease;
                display: flex;
                flex-direction: column;
                justify-content: center;
            }}
            
            .savings-card:hover {{
                transform: translateY(-10px);
                box-shadow: 0 15px 30px rgba(0,0,0,0.25);
            }}
            
            /* Table Section - NO EXPANDABLE */
            .table-section {{
                margin: 50px 0;
                border-radius: 15px;
                overflow: hidden;
                box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            }}
            
            .table-header {{
                background: linear-gradient(135deg, #2196f3, #1976d2);
                color: white;
                padding: 30px;
                text-align: center;
            }}
            
            .table-header h2 {{
                margin: 0;
                font-size: 1.8em;
                font-weight: bold;
            }}
            
            /* Table Always Visible */
            .table-content {{
                background: white;
                padding: 30px;
                border-top: 3px solid #2196f3;
                display: block;
            }}
            
            /* Table Styling */
            .recommendations-table {{
                width: 100% !important;
                border-collapse: collapse;
                margin: 0;
                font-size: 13px;
                table-layout: fixed;
                background-color: white !important;
            }}
            
            .recommendations-table th {{
                background: linear-gradient(135deg, #2196f3, #1976d2) !important;
                color: white !important;
                padding: 18px 15px;
                text-align: left;
                font-weight: bold;
                border: none;
                word-wrap: break-word;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
            }}
            
            .recommendations-table td {{
                padding: 15px;
                border: 1px solid #e0e0e0;
                word-wrap: break-word;
                overflow-wrap: break-word;
                background-color: white !important;
                color: #333 !important;
            }}
            
            .recommendations-table tr:nth-child(even) td {{
                background-color: #f8f9fa !important;
                color: #333 !important;
            }}
            
            .recommendations-table tr:hover td {{
                background-color: #e3f2fd !important;
                color: #333 !important;
            }}
            
            /* Responsive Design */
            @media (max-width: 768px) {{
                .summary-grid, .savings-grid {{
                    flex-direction: column;
                    align-items: center;
                }}
                
                .summary-card, .savings-card {{
                    min-width: 100%;
                    max-width: 100%;
                }}
                
                .container {{
                    padding: 20px;
                }}
                
                .summary-section, .savings-section {{
                    padding: 25px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>☁️ Azure VM Right-Sizing Analysis Report</h1>
                <p><strong>CCID:</strong> {ccid} | <strong>Server Type:</strong> {server_type}</p>
                <p><strong>Generated:</strong> {current_time}</p>
            </div>
            
            <div class="summary-section">
                <div class="summary-title">📊 Summary Metrics</div>
                <div class="summary-grid">
                    <div class="summary-card">
                        <div class="summary-value" style="color:#1976d2;">{summary_stats['total']}</div>
                        <div class="summary-label">Total VMs</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-value" style="color:#4caf50;">{summary_stats['successful']}</div>
                        <div class="summary-label">Successful Recommendations</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-value" style="color:#ff9800;">{summary_stats['high_usage']}</div>
                        <div class="summary-label">High Usage (Skipped)</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-value" style="color:#f44336;">{summary_stats['no_suitable']}</div>
                        <div class="summary-label">No Suitable Option</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-value" style="color:#9c27b0;">{summary_stats['insufficient_data']}</div>
                        <div class="summary-label">Insufficient Data</div>
                    </div>
                </div>
            </div>
            
            <div class="savings-section">
                <div class="summary-title">💰 Calculated Savings</div>
                <div class="savings-grid">
                    <div class="savings-card">
                        <div class="summary-value" style="color:#4caf50;">${summary_stats['total_savings']:.2f}</div>
                        <div class="summary-label">Total Monthly Savings</div>
                    </div>
                    <div class="savings-card">
                        <div class="summary-value" style="color:#2196f3;">${summary_stats['avg_savings']:.2f}</div>
                        <div class="summary-label">Average Savings per VM</div>
                    </div>
                    <div class="savings-card">
                        <div class="summary-value" style="color:#ff5722;">{summary_stats['savings_count']}</div>
                        <div class="summary-label">VMs with Calculated Savings</div>
                    </div>
                </div>
            </div>
            
            <div class="table-section">
                <div class="table-header">
                    <h2>💡 Architecture-Aware Recommendations</h2>
                </div>
                <div class="table-content">
                    {recommendations_html}
                </div>
            </div>
 
        </div>
    </body>
    </html>
    """
    
    return html_content



def send_email_smtp(html_content: str, ccid: str, server_type: str) -> Tuple[bool, str]:
    """Send email using hardcoded Gmail SMTP configuration"""
    try:
        # Check if email configuration is still using placeholder values
        if "your.email@gmail.com" in EMAIL_CONFIG["sender_email"] or "your-app-password" in EMAIL_CONFIG["sender_password"]:
            return False, "❌ Email configuration not updated. Please update EMAIL_CONFIG with your actual Gmail credentials."
        
        # Use hardcoded configuration
        sender_email = EMAIL_CONFIG["sender_email"]
        sender_password = EMAIL_CONFIG["sender_password"]
        recipients = EMAIL_CONFIG["recipients"]
        subject = f"{EMAIL_CONFIG['subject_prefix']} - {ccid} - {server_type}"
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = ', '.join(recipients)
        
        # Add HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Connect to Gmail SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Enable encryption
        server.login(sender_email, sender_password)
        
        # Send email
        text = msg.as_string()
        server.sendmail(sender_email, recipients, text)
        server.quit()
        
        return True, f"✅ Email sent successfully to {len(recipients)} recipient(s)!"
        
    except smtplib.SMTPAuthenticationError:
        return False, "❌ Authentication failed. Please check your email and app password."
    except smtplib.SMTPRecipientsRefused:
        return False, "❌ Invalid recipient email address(es)."
    except smtplib.SMTPServerDisconnected:
        return False, "❌ Connection to email server failed."
    except Exception as e:
        return False, f"❌ Error sending email: {str(e)}"

# Main Streamlit App
def main():
    st.title("☁️ Azure VM Right-Sizing Tool (Auto-Email Reports)")
    st.markdown("Upload your VM data and get recommendations with automatic email reporting.")
    
    # Initialize session state
    if 'analysis_complete' not in st.session_state:
        st.session_state.analysis_complete = False
    if 'analysis_df' not in st.session_state:
        st.session_state.analysis_df = None
    if 'recommendations_df' not in st.session_state:
        st.session_state.recommendations_df = None
    if 'summary_stats' not in st.session_state:
        st.session_state.summary_stats = None
    if 'selected_ccid' not in st.session_state:
        st.session_state.selected_ccid = None
    if 'selected_server_type' not in st.session_state:
        st.session_state.selected_server_type = None
    if 'filtered_df' not in st.session_state:
        st.session_state.filtered_df = None
    
    # Email configuration warning
    if "your.email@gmail.com" in EMAIL_CONFIG["sender_email"]:
        st.error("""
        ⚠️ **EMAIL CONFIGURATION REQUIRED**
        
        Please update the EMAIL_CONFIG section at the top of the script with:
        - Your actual Gmail address
        - Your Gmail App Password (16 characters)
        - Actual recipient email addresses
        """)
    else:
        st.success("✅ Email configuration detected")
    
    st.info("""
    **Enhanced Features:**
    - ✅ **4 vCPU Minimum** - All recommendations start from 4 vCPUs minimum
    - ✅ **High Usage Filter** - Skips instances with CPU≥80% OR Memory≥80%
    - ✅ **CPU Architecture Matching** - Ensures recommended instances have same architecture
    - ✅ **Auto Email Reports** - Automatically sends reports to configured recipients
    - ✅ **Cost-effective only** - Only recommends cheaper instances
    """)
    
    azure_df = load_azure_pricing_data()
    
    if azure_df.empty:
        st.error("Failed to load Azure pricing data. Please check the data file.")
        return
    
    with st.expander("🔍 Configuration Details"):
        st.write(f"**Minimum vCPUs:** {min(get_standard_cpu_sizes())}")
        st.write(f"**Standard CPU sizes:** {get_standard_cpu_sizes()}")
        st.write(f"**Standard Memory sizes (GB):** {get_standard_memory_sizes()}")
        st.write(f"**Total instances in Azure data:** {len(azure_df)}")
        
        # Show email configuration (without sensitive data)
        st.write("**📧 Email Configuration:**")
        st.write(f"**Sender:** {EMAIL_CONFIG['sender_email']}")
        st.write(f"**Recipients:** {len(EMAIL_CONFIG['recipients'])} configured")
        st.write(f"**Recipients:** {', '.join(EMAIL_CONFIG['recipients'])}")
        
        if 'cpuArchitecture' in azure_df.columns:
            architectures = azure_df['cpuArchitecture'].value_counts()
            st.write(f"**Available CPU Architectures:** {architectures.to_dict()}")
    
    uploaded_file = st.file_uploader("Choose an Excel file", type=["xlsx"])
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        df.columns = df.columns.str.strip()
        df = map_columns(df)
        
        df = df.drop_duplicates(subset=["Instance Name or ID", "Private IP Address", "o9 CENVID"])
        
        ccid_options = df["o9 CCID"].dropna().unique().tolist()
        selected_ccid = st.selectbox("Filter by CCID", ccid_options)
        df = df[df["o9 CCID"] == selected_ccid]
        
        server_type_options = df["Server Type"].dropna().unique().tolist()
        selected_server_type = st.selectbox("Filter by Server Type", server_type_options)
        df = df[df["Server Type"] == selected_server_type]
        
        def safe_numeric(val):
            try:
                return float(str(val).strip('% ').replace(',', '').replace('None', 'nan'))
            except:
                return None
        
        df["Max CPU (%)"] = df["Max CPU (%)"].apply(safe_numeric)
        df["Max Memory (%)"] = df["Max Memory (%)"].apply(safe_numeric)
        
        st.success(f"🎯 {df.shape[0]} unique VM(s) shown after applying all filters.")
        
        if not df.empty:
            high_usage_count = len(df[(df["Max CPU (%)"] >= 80) | (df["Max Memory (%)"] >= 80)])
            low_usage_count = len(df[(df["Max CPU (%)"] < 80) & (df["Max Memory (%)"] < 80)])
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("High Usage (CPU≥80% OR Memory≥80%)", high_usage_count)
            with col2:
                st.metric("Eligible for Right-sizing", low_usage_count)
        
        display_columns = [
            'Cloud', 'Platform', 'Server Type', 'Instance Name or ID', 
            'Instance Type', 'Max CPU (%)', 'Max Memory (%)', 'CPU Count', 'Total Memory'
        ]
        
        available_display_columns = [col for col in display_columns if col in df.columns]
        
        st.write("### Data Preview")
        if available_display_columns:
            st.dataframe(df[available_display_columns])
        else:
            st.dataframe(df)
        
        # Analysis button - stores results in session state
        if st.button("Run Enhanced Architecture-Aware Analysis"):
            with st.spinner("Running enhanced analysis with architecture matching..."):
                try:
                    # Store filter values and data in session state
                    st.session_state.selected_ccid = selected_ccid
                    st.session_state.selected_server_type = selected_server_type
                    st.session_state.filtered_df = df.copy()
                    
                    # Run analysis and store results in session state
                    st.session_state.analysis_df = create_analysis_table(df, azure_df)
                    st.session_state.recommendations_df = process_vm_data(df, azure_df)
                    
                    # Calculate summary stats
                    insufficient_data_count = len(st.session_state.recommendations_df[st.session_state.recommendations_df['Recommended Instance Type'] == 'Insufficient Data'])
                    high_usage_count = len(st.session_state.recommendations_df[st.session_state.recommendations_df['Recommended Instance Type'] == 'High Usage - No Right-sizing'])
                    no_suitable_count = len(st.session_state.recommendations_df[st.session_state.recommendations_df['Recommended Instance Type'] == 'No Suitable Instance'])
                    processing_error_count = len(st.session_state.recommendations_df[st.session_state.recommendations_df['Recommended Instance Type'] == 'Processing Error'])
                    successful_analysis_count = len(st.session_state.recommendations_df) - insufficient_data_count - high_usage_count - no_suitable_count - processing_error_count
                    
                    # Calculate savings
                    savings_values = []
                    for savings_str in st.session_state.recommendations_df['Savings']:
                        if savings_str != 'N/A' and 'Cannot Calculate' not in str(savings_str):
                            try:
                                savings_value = float(str(savings_str).replace('$', ''))
                                if savings_value > 0:
                                    savings_values.append(savings_value)
                            except:
                                continue
                    
                    total_savings = sum(savings_values) if savings_values else 0
                    avg_savings = (sum(savings_values) / len(savings_values)) if savings_values else 0
                    
                    # Store summary stats in session state
                    st.session_state.summary_stats = {
                        'total': len(st.session_state.recommendations_df),
                        'successful': successful_analysis_count,
                        'high_usage': high_usage_count,
                        'insufficient_data': insufficient_data_count,
                        'no_suitable': no_suitable_count,
                        'processing_error': processing_error_count,
                        'total_savings': total_savings,
                        'avg_savings': avg_savings,
                        'savings_count': len(savings_values)
                    }
                    
                    st.session_state.analysis_complete = True
                    st.rerun()  # Refresh to show results
                    
                except Exception as e:
                    st.error(f"Error calculating recommendations: {str(e)}")
                    
    
    # Display results if analysis is complete
    if st.session_state.analysis_complete and st.session_state.analysis_df is not None:
        st.header("📊 Hardware Analysis")
        analysis_df_clean = clean_dataframe_for_display(st.session_state.analysis_df)
        st.dataframe(analysis_df_clean, use_container_width=True)
        
        st.header("💡 Architecture-Aware Recommendations")
        recommendations_df_clean = clean_dataframe_for_display(st.session_state.recommendations_df)
        st.dataframe(recommendations_df_clean, use_container_width=True)
        
        # Beautiful Summary Section with CSS styling
        summary_html = f"""
        <div style="background:linear-gradient(135deg, #667eea 0%, #764ba2 100%);padding:20px;border-radius:20px;color:white;font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;box-shadow:0 10px 30px rgba(0,0,0,0.3);margin:20px 0;">
            <div style="font-size:1.5em;font-weight:bold;text-align:center;margin-bottom:20px;">📊 Summary Metrics</div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:15px;">
                <div style="background:linear-gradient(135deg, #fff, #f8f9fa);border-radius:15px;padding:20px;text-align:center;box-shadow:0 8px 16px rgba(0,0,0,0.1);border:2px solid transparent;">
                    <div style="font-size:2.5em;font-weight:bold;color:#1976d2;margin-bottom:5px;">{st.session_state.summary_stats['total']}</div>
                    <div style="font-weight:bold;color:#666;">Total VMs</div>
                </div>
                <div style="background:linear-gradient(135deg, #fff, #f8f9fa);border-radius:15px;padding:20px;text-align:center;box-shadow:0 8px 16px rgba(0,0,0,0.1);border:2px solid transparent;">
                    <div style="font-size:2.5em;font-weight:bold;color:#4caf50;margin-bottom:5px;">{st.session_state.summary_stats['successful']}</div>
                    <div style="font-weight:bold;color:#666;">Successful Recommendations</div>
                </div>
                <div style="background:linear-gradient(135deg, #fff, #f8f9fa);border-radius:15px;padding:20px;text-align:center;box-shadow:0 8px 16px rgba(0,0,0,0.1);border:2px solid transparent;">
                    <div style="font-size:2.5em;font-weight:bold;color:#ff9800;margin-bottom:5px;">{st.session_state.summary_stats['high_usage']}</div>
                    <div style="font-weight:bold;color:#666;">High Usage (Skipped)</div>
                </div>
                <div style="background:linear-gradient(135deg, #fff, #f8f9fa);border-radius:15px;padding:20px;text-align:center;box-shadow:0 8px 16px rgba(0,0,0,0.1);border:2px solid transparent;">
                    <div style="font-size:2.5em;font-weight:bold;color:#f44336;margin-bottom:5px;">{st.session_state.summary_stats['no_suitable']}</div>
                    <div style="font-weight:bold;color:#666;">No Suitable Option</div>
                </div>
                <div style="background:linear-gradient(135deg, #fff, #f8f9fa);border-radius:15px;padding:20px;text-align:center;box-shadow:0 8px 16px rgba(0,0,0,0.1);border:2px solid transparent;">
                    <div style="font-size:2.5em;font-weight:bold;color:#9c27b0;margin-bottom:5px;">{st.session_state.summary_stats['insufficient_data']}</div>
                    <div style="font-weight:bold;color:#666;">Insufficient Data</div>
                </div>
            </div>
        </div>
        """

        st.html(summary_html)

        if st.session_state.summary_stats['savings_count'] > 0:
            savings_html = f"""
            <div style="background:linear-gradient(135deg, #4caf50 0%, #2e7d32 100%);padding:20px;border-radius:20px;color:white;font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;box-shadow:0 10px 30px rgba(0,0,0,0.3);margin:20px 0;">
                <div style="font-size:1.5em;font-weight:bold;text-align:center;margin-bottom:20px;">💰 Calculated Savings</div>
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(250px, 1fr));gap:15px;">
                    <div style="background:linear-gradient(135deg, #fff, #f8f9fa);border-radius:15px;padding:20px;text-align:center;box-shadow:0 8px 16px rgba(0,0,0,0.1);border:2px solid transparent;">
                        <div style="font-size:2.5em;font-weight:bold;color:#4caf50;margin-bottom:5px;">${st.session_state.summary_stats['total_savings']:.2f}</div>
                        <div style="font-weight:bold;color:#666;">Total Monthly Savings</div>
                    </div>
                    <div style="background:linear-gradient(135deg, #fff, #f8f9fa);border-radius:15px;padding:20px;text-align:center;box-shadow:0 8px 16px rgba(0,0,0,0.1);border:2px solid transparent;">
                        <div style="font-size:2.5em;font-weight:bold;color:#2196f3;margin-bottom:5px;">${st.session_state.summary_stats['avg_savings']:.2f}</div>
                        <div style="font-weight:bold;color:#666;">Average Savings per VM</div>
                    </div>
                    <div style="background:linear-gradient(135deg, #fff, #f8f9fa);border-radius:15px;padding:20px;text-align:center;box-shadow:0 8px 16px rgba(0,0,0,0.1);border:2px solid transparent;">
                        <div style="font-size:2.5em;font-weight:bold;color:#ff5722;margin-bottom:5px;">{st.session_state.summary_stats['savings_count']}</div>
                        <div style="font-weight:bold;color:#666;">VMs with Calculated Savings</div>
                    </div>
                </div>
            </div>
            """
            
            st.html(savings_html)         
    
        # Save Results to Dashboard functionality
        if st.session_state.get('analysis_complete', False):
            if st.button("💾 Save Results to Dashboard", type="primary"):
                try:
                    # Ensure we have the required data
                    if (st.session_state.analysis_df is not None and 
                        st.session_state.recommendations_df is not None and 
                        st.session_state.summary_stats is not None):
                        
                        # Generate HTML report with recommendations and summary
                        html_report = generate_html_report(
                            st.session_state.analysis_df,
                            st.session_state.recommendations_df,
                            st.session_state.summary_stats,
                            st.session_state.selected_ccid,
                            st.session_state.selected_server_type
                        )
                        
                        # Save to dashboard file
                        with open("vm_summary.html", "w", encoding="utf-8") as f:
                            f.write(html_report)
                        
                        st.success("✅ VM analysis results saved to dashboard! You can now send all results from the main dashboard.")
                        st.balloons()
                    else:
                        st.error("❌ No analysis data available. Please run the analysis first.")
                        
                except Exception as e:
                    st.error(f"❌ Error saving to dashboard: {str(e)}")
                    st.write("Debug info:")
                    st.write(f"Analysis DF exists: {st.session_state.analysis_df is not None}")
                    st.write(f"Recommendations DF exists: {st.session_state.recommendations_df is not None}")
                    st.write(f"Summary stats exists: {st.session_state.summary_stats is not None}")





if __name__ == "__main__":
    main()
