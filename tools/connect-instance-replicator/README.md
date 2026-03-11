# Amazon Connect bundle export/import (primitive APIs)

This folder contains a Python CLI (boto3) to export/import a JSON “bundle” using Amazon Connect’s primitive APIs.

## Scope (bundle v1)
- Hours of operation
- Queues (STANDARD)
- Contact flow modules
- Contact flows

## Install
```bash
cd tools/connect-instance-replicator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Export a bundle
```bash
python connect_instance_replicate.py export \
  --region us-east-1 \
  --instance-id <SOURCE_INSTANCE_ID> \
  --out bundle.json
```

## Import a bundle (dry-run)
Shows what would be created/updated/skipped without calling `Create*`/`Update*`.

```bash
python connect_instance_replicate.py import \
  --region us-west-2 \
  --instance-id <TARGET_INSTANCE_ID> \
  --in bundle.json \
  --overwrite \
  --dry-run
```

## Import a bundle (live)
```bash
python connect_instance_replicate.py import \
  --region us-west-2 \
  --instance-id <TARGET_INSTANCE_ID> \
  --in bundle.json \
  --overwrite \
  --continue-on-error \
  --skip-unsupported
```

### Flags
- `--overwrite`: update resources if they already exist (matched by name)
- `--dry-run`: do not call Create/Update, only report planned actions
- `--continue-on-error`: keep going and record failures instead of aborting the whole import
- `--skip-unsupported`: skip flows/modules that reference prompts/Lex/Lambda/S3/phone numbers (external deps)

## Notes / limitations
- This CLI does **not** create a new Connect instance; it copies supported resources into an existing instance.
- Flow JSON often contains embedded IDs/ARNs. The importer rewrites known IDs/ARNs (hours/queues/modules/flows) best-effort and uses a two-pass flow update.

References:
- Admin guide (flow import/export): https://docs.aws.amazon.com/connect/latest/adminguide/contact-flow-import-export.html
- API `DescribeContactFlow`: https://docs.aws.amazon.com/connect/latest/APIReference/API_DescribeContactFlow.html
- API `CreateContactFlow`: https://docs.aws.amazon.com/connect/latest/APIReference/API_CreateContactFlow.html
