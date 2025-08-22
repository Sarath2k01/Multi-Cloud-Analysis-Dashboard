# Multi-Cloud Analysis Dashboard

[![Last Commit](https://img.shields.io/github/last-commit/Sarath2k01/Multi-Cloud-Analysis-Dashboard)]()  
[![Issues](https://img.shields.io/github/issues/Sarath2k01/Multi-Cloud-Analysis-Dashboard)]()

---

## Overview

**Multi-Cloud Analysis Dashboard** is an advanced AI-driven cloud cost optimization solution designed for AWS, Azure, and GCP environments. Created by Sarath Madala, this tool empowers organizations to achieve comprehensive cloud spend management, governance, and resource efficiency through automation, analytics, and intelligent recommendations.

The dashboard acts as a centralized control hub that seamlessly integrates multiple specialized modules to provide actionable insights and cost-saving opportunities across multi-cloud resources.

---

## Features

- Centralized, unified multi-cloud cost management and governance
- AI-powered detection of resource inefficiencies and waste elimination
- Rightsizing and reservation savings analysis with projection reports
- Automated tagging compliance checks and policy-as-code enforcement
- Interactive dashboards for real-time spend tracking and anomaly detection
- Seamless integration across multiple clouds with a consistent reporting framework
- Automated generation and distribution of executive-ready optimization reports

---

## Modules

### Main Dashboard — Control Hub
- Central command center managing all modules
- Automatically pre-configures cloud environments and system resources
- Launches four specialized cost analysis modules simultaneously
- Generates unified executive reports combining all analysis into a single comprehensive document  

<img width="1920" height="1080" alt="Screenshot 2025-07-23 010815" src="https://github.com/user-attachments/assets/1f4149fb-db01-4749-ac11-639372f8e577" />


### VM Rightsizing Module — Resource Optimization
- Analyzes VM performance across AWS and Azure
- Identifies underutilized resources while excluding already-optimized instances
- Calculates actual resource requirements with built-in safety buffers
- Suggests cost-effective instance alternatives maintaining performance standards
- Generates detailed savings projections and automated tag compliance validation  

![VM Rightsizing - Overview](./screenshots/rightsizing_dashboard.png)  
![VM Rightsizing - Savings Projection](./screenshots/rightsizing_savings_projection.png)

---

### Unattached Disks Module — Storage Waste Elimination
- Detects orphaned storage volumes that incur unnecessary costs
- Identifies detached storage volumes retained beyond acceptable periods
- Excludes critical system components from deletion
- Prioritizes cleanup actions based on cost impact and governance validation
- Provides actionable cleanup recommendations  

![Unattached Disks Module](./screenshots/unattached_disks_cleanup.png)

---

### Snapshots Module — Backup Cost Management
- Evaluates backup storage usage, retention costs, and snapshot age
- Analyzes usage frequency and associated cost implications
- Flags snapshots exceeding retention policies ensuring compliance
- Identifies cost optimization opportunities while preserving data protection

---

### Storage Tiering Module — Intelligent Data Placement
- AI-driven optimization of storage tiers across AWS, Azure, and GCP
- Analyzes data access frequency and cloud-specific cost structures
- Recommends tiering strategies:
  - Conservative (low risk)
  - Aggressive (higher savings potential)
- Provides precise savings forecasts with validated cost calculations

---

### System Integration
- Automated workflows coordinate seamless module operations
- Consistent and standardized reporting formats for all insights
- Centralized validation for governance compliance
- Outputs executive-ready documents, automated email reports, and Excel exports for stakeholder review

---

## Business Impact

By combining automation, AI, and policy-driven governance, this dashboard delivers deep cloud cost optimization that includes:

- Complete waste detection and elimination
- Intelligent, actionable cost-saving recommendations
- Streamlined, comprehensive reporting for decision-makers  
- Realized savings exceeding 27% monthly cloud expenditure reductions and over $630K in cumulative savings (as demonstrated in consultancy engagements)

---

## Getting Started

### Prerequisites
- Python 3.8+
- AWS, Azure, and GCP credentials configured with appropriate read access for billing and resource metadata
- Streamlit installed
- Terraform for running policy-as-code compliance checks
- Dependencies listed in `requirements.txt`

### Installation

1. Clone the repo:
