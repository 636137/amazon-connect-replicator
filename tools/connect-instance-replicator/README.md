# Amazon Connect Instance Replicator CLI (v3)

A Python CLI to export and import Amazon Connect instance configuration using primitive Connect APIs.

## Bundle v3 Scope (17 resource types)

| # | Resource | Notes |
|---|----------|-------|
| 1 | Hours of Operation | |
| 2 | Agent Statuses | |
| 3 | Security Profiles | Includes permissions |
| 4 | User Hierarchy Groups | |
| 5 | Queues (STANDARD) | |
| 6 | Routing Profiles | |
| 7 | Quick Connects | Queue + phone types (user-type skipped) |
| 8 | Contact Flow Modules | |
| 9 | Contact Flows | Two-pass for cross-references |
| 10 | Instance Attributes | Feature flags |
| 11 | Predefined Attributes | Routing skill tags |
| 12 | Prompts | Requires S3 bucket for audio copy |
| 13 | Task Templates | |
| 14 | Views | Step-by-step guides |
| 15 | Rules | Contact Lens, event triggers |
| 16 | Evaluation Forms | QA forms |
| 17 | Vocabularies | Contact Lens custom vocabularies |

## Prerequisites

```bash
pip3 install -r requirements.txt
```

## Usage

### Export a bundle

```bash
python3 connect_instance_replicate.py export \
  --region us-east-1 \
  --instance-id YOUR_INSTANCE_ID \
  --out bundle.json
```

### Import a bundle into an existing target instance

```bash
python3 connect_instance_replicate.py import \
  --region us-west-2 \
  --instance-id TARGET_INSTANCE_ID \
  --in bundle.json \
  --overwrite \
  --continue-on-error \
  --skip-unsupported
```

### Import with prompts (requires S3 bucket)

```bash
python3 connect_instance_replicate.py import \
  --region us-west-2 \
  --instance-id TARGET_INSTANCE_ID \
  --in bundle.json \
  --overwrite \
  --continue-on-error \
  --skip-unsupported \
  --prompt-s3-bucket my-bucket-us-west-2
```

### Dry-run import (no Create/Update calls)

```bash
python3 connect_instance_replicate.py import \
  --region us-west-2 \
  --instance-id TARGET_INSTANCE_ID \
  --in bundle.json \
  --dry-run
```

## CLI Flags

### Export
- `--region` (required): AWS region
- `--instance-id` (required): Connect instance ID
- `--out`: Output file path (default: stdout)
- `--profile`: AWS credential profile name (optional)

### Import
- `--region` (required): AWS region
- `--instance-id` (required): Connect instance ID
- `--in` (required): Input bundle JSON path
- `--overwrite`: Update existing resources (default: skip)
- `--dry-run`: Print what would happen without making changes
- `--continue-on-error`: Continue after errors (records failures in output)
- `--skip-unsupported`: Skip flows/modules with external dependencies
- `--prompt-s3-bucket`: S3 bucket for prompt audio files (required to import prompts)
- `--profile`: AWS credential profile name (optional)

## Output (import)

```json
{
  "createdHours": 1,
  "updatedHours": 2,
  "skippedHours": 0,
  "failedHours": 0,
  "createdPredefinedAttributes": 3,
  "createdPrompts": 5,
  "createdTaskTemplates": 2,
  "createdViews": 1,
  "createdRules": 0,
  "createdEvaluationForms": 1,
  "createdVocabularies": 0,
  ...
  "errors": {},
  "dryRun": false,
  "overwrite": true,
  "continueOnError": true,
  "skipUnsupported": true
}
```

## Reliability Notes

- **Omit nils:** AWS SDKs reject `null` for optional fields; the importer omits nil keys.
- **Replace longest-first:** Replacements are applied sorted by source-string length (full ARNs before IDs).
- **Pre-map existing flows:** Flows matched by `type|name` are pre-mapped for first-pass cross-references.
- **Two-pass flow update:** Second pass catches references to flows created during the same run.
