---
name: connect-instance-replication
description: Replicate Amazon Connect instance configuration across regions using primitive APIs. Exports/imports 17 resource types into pre-existing target instances.
user-invocable: true
disable-model-invocation: false
---

# Amazon Connect Instance Replication Skill

Replicate Amazon Connect configuration from a source instance to a **pre-existing** target instance using primitive Connect APIs (not Global Resiliency).

## Design Philosophy

This skill **always replicates into a pre-existing target instance**. It does NOT create new instances on-the-fly.

**Why?** Enterprises need predictable instance IDs for:
- CloudWatch alarms and dashboards
- Cost allocation tags and billing
- IAM policies scoped to specific instance ARNs
- Integration endpoints (Lambda, Lex, Kinesis)
- Compliance/audit trails

Provision your target instance in advance, then use this skill to sync configuration.

## Bundle v3 Scope (17 resource types)

1. Hours of Operation
2. Agent Statuses
3. Security Profiles
4. User Hierarchy Groups
5. Queues (STANDARD)
6. Routing Profiles
7. Quick Connects (queue + phone types)
8. Contact Flow Modules
9. Contact Flows
10. Instance Attributes
11. Predefined Attributes
12. Prompts (with S3 copy)
13. Task Templates
14. Views
15. Rules
16. Evaluation Forms
17. Vocabularies

## Prerequisites

- AWS credentials configured (via env vars, profile, or IAM role)
- Python 3.9+ with boto3
- Both source and target Connect instances must exist and be ACTIVE
- For prompts: an S3 bucket in the target region

## Commands

### discover

List Connect instances in a region.

```bash
python3 scripts/connect_instance_replication.py discover --region us-east-1
```

### replicate

Export from source and import into target.

```bash
python3 scripts/connect_instance_replication.py replicate \
  --source-region us-east-1 \
  --source-alias my-prod-connect \
  --target-region us-west-2 \
  --target-alias my-dr-connect \
  --overwrite \
  --skip-unsupported \
  --continue-on-error \
  --yes
```

## Flags

| Flag | Description |
|------|-------------|
| `--source-region` | AWS region of source instance |
| `--source-alias` | Source instance alias (or use `--source-instance-id`) |
| `--source-instance-id` | Source instance ID (alternative to alias) |
| `--target-region` | AWS region of target instance |
| `--target-alias` | Target instance alias (or use `--target-instance-id`) |
| `--target-instance-id` | Target instance ID (alternative to alias) |
| `--overwrite` | Update existing resources in target |
| `--dry-run` | Preview without making changes |
| `--skip-unsupported` | Skip flows with external dependencies |
| `--continue-on-error` | Continue after errors |
| `--yes` | Confirm live changes (required for non-dry-run) |
| `--prompt-s3-bucket` | S3 bucket for prompt audio files |

## Safety Guardrails

- `--yes` is required for any live changes
- `--dry-run` previews without making changes
- Errors are logged but don't stop execution with `--continue-on-error`

## Output Artifacts

Each run writes to `~/Downloads/acr-replication-runs/<runId>/`:
- `bundle.json` — exported configuration
- `import-report.json` — import results
- `verify.json` — post-import resource counts

## Example Output

```json
{
  "runId": "20260311T190000Z-abc123",
  "source": { "region": "us-east-1", "instanceId": "..." },
  "target": { "region": "us-west-2", "instanceId": "..." },
  "verifyCounts": {
    "hours": 2,
    "queues": 6,
    "flows": 21,
    "predefinedAttributes": 5,
    "taskTemplates": 3,
    "views": 2
  }
}
```
