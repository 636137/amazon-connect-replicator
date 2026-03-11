# Amazon Connect Instance Replicator CLI (v2)

A Python CLI to export and import Amazon Connect instance configuration using primitive Connect APIs.

## Bundle v2 Scope

This CLI exports/imports the following resource types:

1. Hours of Operation
2. Agent Statuses
3. Security Profiles
4. User Hierarchy Groups
5. Queues (STANDARD)
6. Routing Profiles
7. Quick Connects (queue + phone types; user-type skipped)
8. Contact Flow Modules
9. Contact Flows
10. Instance Attributes (feature flags)

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
- `--skip-unsupported`: Skip flows/modules with external dependencies (prompts, Lex, Lambda, S3, phone numbers)
- `--profile`: AWS credential profile name (optional)

## Output (import)

The import command outputs a JSON report:

```json
{
  "createdHours": 1,
  "updatedHours": 2,
  "skippedHours": 0,
  "failedHours": 0,
  "createdAgentStatuses": 0,
  "updatedAgentStatuses": 3,
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
- **Replace longest-first:** Replacements are applied sorted by source-string length (full ARNs before IDs) to avoid corrupting ARNs.
- **Pre-map existing flows:** Flows that already exist in the target are pre-mapped by `type|name` so cross-flow references can be rewritten on the first pass.
- **Two-pass flow update:** A second pass catches references to flows created during the same import run.
