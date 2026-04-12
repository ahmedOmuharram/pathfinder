# Terraform Dashboard Apply

This directory provisions the generated PathFinder dashboards into SigNoz.

## Prerequisites

- Terraform 1.5+
- SigNoz provider `Signoz/signoz`
- A SigNoz API token with dashboard-management permissions

## Usage

```bash
export TF_VAR_signoz_endpoint="https://signoz.example.org"
export TF_VAR_signoz_access_token="replace-me"

terraform init
terraform plan
terraform apply
```

## Scope

- Dashboards are applied from `../dashboards/*.json`
- Alerts stay source-controlled in `../alerts/pathfinder-alert-catalog.json`
- Alert routing remains environment-specific on purpose, because channel names and policy contracts differ across local, staging, production, and Cedar-hosted environments
