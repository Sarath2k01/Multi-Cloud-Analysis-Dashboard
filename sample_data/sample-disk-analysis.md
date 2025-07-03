# Sample Disk Analysis Scenarios

## Scenario 1: High-Cost Unattached Disks
These are expensive disks that should be prioritized for cleanup:

| Disk Name | Storage Type | Size (GB) | Monthly Cost | Days Unattached | Action |
|-----------|--------------|-----------|--------------|-----------------|---------|
| disk-db-backup-large | Premium_LRS | 1024 | $147.20 | 45 | Delete after backup verification |
| disk-analytics-temp | Premium_LRS | 512 | $73.60 | 30 | Safe to delete |
| disk-legacy-app-data | Standard_LRS | 2048 | $81.92 | 90 | Archive then delete |

## Scenario 2: Development Environment Cleanup
Development disks that can typically be safely removed:

| Disk Name | Storage Type | Size (GB) | Monthly Cost | Environment | Action |
|-----------|--------------|-----------|--------------|-------------|---------|
| disk-dev-workspace-01 | StandardSSD_LRS | 128 | $19.20 | Development | Safe to delete |
| disk-test-data-temp | Standard_LRS | 64 | $2.56 | Testing | Safe to delete |
| disk-staging-cache | Premium_LRS | 256 | $36.80 | Staging | Verify with team first |

## Scenario 3: Production Disks Requiring Caution
Production disks that need careful review:

| Disk Name | Storage Type | Size (GB) | Monthly Cost | Last VM | Action Required |
|-----------|--------------|-----------|--------------|---------|-----------------|
| disk-prod-db-backup | Premium_LRS | 512 | $73.60 | vm-database-01 | Verify backup before delete |
| disk-prod-logs-archive | Standard_LRS | 1024 | $40.96 | vm-logging-server | Check retention policy |
| disk-prod-temp-migration | Premium_LRS | 256 | $36.80 | vm-migration-tool | Confirm migration complete |

## Cost Analysis Summary

**Total Monthly Waste**: $572.84
**Immediate Savings**: $298.56 (Development + Testing)
**Requires Review**: $274.28 (Production disks)

## Recommended Actions by Priority

1. **High Priority** (Immediate deletion): Development and testing disks
2. **Medium Priority** (Verify then delete): Temporary and backup disks
3. **Low Priority** (Team review required): Production-tagged disks
