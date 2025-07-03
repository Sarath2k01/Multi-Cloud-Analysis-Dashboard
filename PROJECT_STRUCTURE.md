# Project Structure

multi-cloud-analysis-dashboard/
├── 📄 main_dashboard.py # Main dashboard interface
├── 🖥️ vm-mail.py # VM right-sizing analysis
├── 📸 snapshots.py # Snapshot cost analysis
├── 💾 disks.py # Unattached disk analysis
├── 📊 azure-data.json # Azure pricing data
├── 🏷️ Tags.json # Tag compliance rules
├── 📋 requirements.txt # Python dependencies
├── 📖 README.md # Project documentation
├── 📜 LICENSE # MIT License
├── 🔧 .gitignore # Git ignore rules
├── 📝 CONTRIBUTING.md # Contribution guidelines
├── 📅 CHANGELOG.md # Version history
├── 🏗️ PROJECT_STRUCTURE.md # This file
├── 🖼️ images/ # Screenshots and assets
│ ├── dashboard-overview.png
│ ├── vm-analysis.png
│ ├── email-report.png
│ └── snapshot-analysis.png

## File Descriptions

### Core Application Files
- **main_dashboard.py**: Central hub for all analysis tools
- **vm-mail.py**: VM performance analysis and right-sizing recommendations
- **snapshots.py**: Snapshot cost analysis and tag compliance
- **disks.py**: Unattached disk identification and cost analysis

### Configuration Files
- **azure-data.json**: Azure VM pricing and specifications
- **Tags.json**: CCID to CENVID mapping for compliance validation
- **requirements.txt**: Python package dependencies
- **.streamlit/config.toml**: Streamlit application configuration

### Documentation
- **README.md**: Main project documentation
- **CHANGELOG.md**: Version history and changes
- **PROJECT_STRUCTURE.md**: This file explaining project organization

### Development Files
- **.gitignore**: Files and folders to exclude from version control
- **images/**: Screenshots and visual assets for documentation
