# Amazon Connect Replicator (Global Resiliency)

This repo contains **only** what we built in this session:
- A small **Python CLI** for Amazon Connect Global Resiliency replication (Connect `ReplicateInstance`).
- A minimal **API + React UI** to list regions/instances, download a JSON “snapshot”, and trigger replication.

## What this does (fast path)
Amazon Connect Global Resiliency provides **native cross-region instance replication** via `ReplicateInstance` (for supported region pairs). This is the fastest way to stand up a replica in minutes.

Key constraints from AWS docs:
- Only specific region pairs are supported (includes **us-east-1 ↔ us-west-2**).
- The feature can be **access-gated** (you may see errors like “AWS account not allowlisted”).
- Source instance must be **ACTIVE** and have **SAML** identity management.
- External integrations (Lambda/Lex/3rd-party) are not automatically made redundant.

## Prereqs
- AWS credentials available to the API server and/or Python CLI (env vars, SSO, or profiles).
- Node.js 20+ (for UI/API) and Python 3.9+ (for CLI).

## Run the UI + API
```bash
npm install
npm run dev
```
- UI: http://localhost:3000
- API: http://localhost:3001

## Python CLI
See: `tools/connect-instance-replicator/README.md`

## AWS CLI equivalent
```bash
aws connect replicate-instance \
  --region us-east-1 \
  --instance-id <SOURCE_INSTANCE_ID> \
  --replica-region us-west-2 \
  --replica-alias <UNIQUE_REPLICA_ALIAS> \
  --no-cli-pager
```

References:
- API `ReplicateInstance`: https://docs.aws.amazon.com/connect/latest/APIReference/API_ReplicateInstance.html
- CLI `replicate-instance`: https://docs.aws.amazon.com/cli/latest/reference/connect/replicate-instance.html
