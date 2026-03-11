#!/usr/bin/env python3

import argparse
import json
import os
import random
import string
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import boto3
from botocore.exceptions import ClientError


CONTACT_FLOW_TYPES: List[str] = [
    "CONTACT_FLOW",
    "CUSTOMER_QUEUE",
    "CUSTOMER_HOLD",
    "CUSTOMER_WHISPER",
    "AGENT_HOLD",
    "AGENT_WHISPER",
    "OUTBOUND_WHISPER",
    "AGENT_TRANSFER",
    "QUEUE_TRANSFER",
    "CAMPAIGN",
]


def _session(profile: Optional[str], region: str) -> boto3.session.Session:
    if profile:
        return boto3.session.Session(profile_name=profile, region_name=region)
    return boto3.session.Session(region_name=region)


def _connect_client(profile: Optional[str], region: str):
    return _session(profile, region).client("connect")


def _paginate(method, *, next_token_key: str = "NextToken", **kwargs) -> Iterable[Dict[str, Any]]:
    token = None
    while True:
        call_kwargs = dict(kwargs)
        if token:
            call_kwargs[next_token_key] = token
        resp = method(**call_kwargs)
        yield resp
        token = resp.get(next_token_key)
        if not token:
            break


def _random_suffix(n: int = 6) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(n))


def _now_run_id() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat().replace(":", "").replace("-", "") + "Z-" + _random_suffix(6)


def _default_runs_dir() -> Path:
    return Path.home() / "Downloads" / "acr-replication-runs"


def _resolve_replicator_script() -> Path:
    # 1) explicit full path
    p = os.environ.get("ACR_REPLICATOR_SCRIPT")
    if p:
        pp = Path(p).expanduser().resolve()
        if pp.exists():
            return pp

    # 2) explicit repo root
    repo = os.environ.get("ACR_REPO")
    if repo:
        pp = (Path(repo).expanduser().resolve() / "tools" / "connect-instance-replicator" / "connect_instance_replicate.py")
        if pp.exists():
            return pp

    # 3) default expected checkout location
    pp = (Path.home() / "amazon-connect-replicator" / "tools" / "connect-instance-replicator" / "connect_instance_replicate.py")
    if pp.exists():
        return pp

    raise FileNotFoundError(
        "Could not find connect_instance_replicate.py. Set ACR_REPO or ACR_REPLICATOR_SCRIPT, "
        "or clone https://github.com/636137/amazon-connect-replicator to ~/amazon-connect-replicator"
    )


def _run_replicator(
    *,
    replicator_script: Path,
    args: List[str],
    capture_json: bool,
    env: Optional[Dict[str, str]] = None,
) -> Any:
    cmd = [sys.executable, str(replicator_script)] + args
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise RuntimeError(
            "Replicator CLI failed:\n"
            f"  cmd: {' '.join(cmd)}\n"
            f"  exit: {proc.returncode}\n"
            f"  stdout: {proc.stdout.strip()}\n"
            f"  stderr: {proc.stderr.strip()}\n"
        )
    if capture_json:
        try:
            return json.loads(proc.stdout)
        except Exception as e:
            raise RuntimeError(
                "Replicator did not return valid JSON on stdout.\n"
                f"Parse error: {e}\n"
                f"stdout: {proc.stdout.strip()}\n"
                f"stderr: {proc.stderr.strip()}\n"
            )
    return proc.stdout


def list_instances(*, profile: Optional[str], region: str) -> List[Dict[str, Any]]:
    client = _connect_client(profile, region)
    out: List[Dict[str, Any]] = []
    for page in _paginate(client.list_instances, MaxResults=100):
        out.extend(page.get("InstanceSummaryList") or [])
    return out


def resolve_instance_id(*, profile: Optional[str], region: str, instance_id: Optional[str], alias: Optional[str]) -> str:
    if instance_id:
        return instance_id
    if not alias:
        raise ValueError("Provide --instance-id or --alias")

    candidates = list_instances(profile=profile, region=region)
    for s in candidates:
        if s.get("InstanceAlias") == alias and s.get("Id"):
            return str(s.get("Id"))

    known = ", ".join(sorted([c.get("InstanceAlias") for c in candidates if c.get("InstanceAlias")])[:25])
    raise ValueError(f"No instance found in {region} with alias '{alias}'. Known aliases (first 25): {known}")


def verify_counts(*, profile: Optional[str], region: str, instance_id: str) -> Dict[str, int]:
    client = _connect_client(profile, region)

    hours = 0
    for page in _paginate(client.list_hours_of_operations, InstanceId=instance_id, MaxResults=100):
        hours += len(page.get("HoursOfOperationSummaryList") or [])

    queues = 0
    for page in _paginate(client.list_queues, InstanceId=instance_id, MaxResults=100, QueueTypes=["STANDARD"]):
        queues += len(page.get("QueueSummaryList") or [])

    modules = 0
    for page in _paginate(client.list_contact_flow_modules, InstanceId=instance_id, MaxResults=100):
        modules += len(page.get("ContactFlowModulesSummaryList") or [])

    flows = 0
    for page in _paginate(
        client.list_contact_flows,
        InstanceId=instance_id,
        MaxResults=100,
        ContactFlowTypes=CONTACT_FLOW_TYPES,
    ):
        flows += len(page.get("ContactFlowSummaryList") or [])

    return {
        "hours": hours,
        "queues": queues,
        "modules": modules,
        "flows": flows,
    }


def cmd_discover(args: argparse.Namespace) -> int:
    items = list_instances(profile=args.profile, region=args.region)
    rows = []
    for i in items:
        rows.append(
            {
                "alias": i.get("InstanceAlias"),
                "id": i.get("Id"),
                "arn": i.get("Arn"),
                "status": i.get("InstanceStatus"),
                "created": i.get("CreatedTime").isoformat() if i.get("CreatedTime") else None,
            }
        )
    print(json.dumps({"region": args.region, "instances": rows}, indent=2, default=str))
    return 0


def cmd_replicate(args: argparse.Namespace) -> int:
    replicator_script = _resolve_replicator_script()

    run_id = args.run_id or _now_run_id()
    workdir = Path(args.workdir).expanduser().resolve() if args.workdir else (_default_runs_dir() / run_id)
    workdir.mkdir(parents=True, exist_ok=True)

    bundle_path = workdir / "bundle.json"
    import_report_path = workdir / "import-report.json"
    verify_path = workdir / "verify.json"

    source_instance_id = resolve_instance_id(
        profile=args.profile,
        region=args.source_region,
        instance_id=args.source_instance_id,
        alias=args.source_alias,
    )

    # Resolve target instance (must already exist)
    target_instance_id = resolve_instance_id(
        profile=args.profile,
        region=args.target_region,
        instance_id=args.target_instance_id,
        alias=args.target_alias,
    )

    # Export
    export_args = ["--profile", args.profile] if args.profile else []
    export_args += ["export", "--region", args.source_region, "--instance-id", source_instance_id, "--out", str(bundle_path)]
    _run_replicator(replicator_script=replicator_script, args=export_args, capture_json=False)

    # Import
    if not args.dry_run and not args.yes:
        raise ValueError("Refusing to import into target without --yes (or use --dry-run)")

    import_args = ["--profile", args.profile] if args.profile else []
    import_args += ["import", "--region", args.target_region, "--instance-id", target_instance_id, "--in", str(bundle_path)]

    if args.overwrite:
        import_args.append("--overwrite")
    if args.dry_run:
        import_args.append("--dry-run")
    if args.continue_on_error:
        import_args.append("--continue-on-error")
    if args.skip_unsupported:
        import_args.append("--skip-unsupported")

    report = _run_replicator(replicator_script=replicator_script, args=import_args, capture_json=True)
    import_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    counts = verify_counts(profile=args.profile, region=args.target_region, instance_id=target_instance_id)
    verify_path.write_text(json.dumps({"region": args.target_region, "instanceId": target_instance_id, "counts": counts}, indent=2), encoding="utf-8")

    summary = {
        "runId": run_id,
        "workdir": str(workdir),
        "source": {"region": args.source_region, "instanceId": source_instance_id},
        "target": {
            "region": args.target_region,
            "instanceId": target_instance_id,
        },
        "paths": {
            "bundle": str(bundle_path),
            "importReport": str(import_report_path),
            "verify": str(verify_path),
        },
        "verifyCounts": counts,
    }

    print(json.dumps(summary, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="On-demand Amazon Connect cross-region replication wrapper (primitive APIs + amazon-connect-replicator CLI)."
    )
    p.add_argument("--profile", default=None, help="AWS credential profile name (optional)")

    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover", help="List Connect instances in a region")
    d.add_argument("--region", required=True)
    d.set_defaults(func=cmd_discover)

    r = sub.add_parser("replicate", help="Export from source, import into existing target, and verify counts")

    r.add_argument("--source-region", required=True)
    r.add_argument("--source-instance-id", default=None)
    r.add_argument("--source-alias", default=None)

    r.add_argument("--target-region", required=True)
    r.add_argument("--target-instance-id", default=None)
    r.add_argument("--target-alias", default=None, help="Alias of existing target instance to resolve")

    r.add_argument("--overwrite", action="store_true", help="Overwrite resources if they already exist in target")
    r.add_argument("--dry-run", action="store_true", help="Run importer in dry-run mode (no Create/Update)")
    r.add_argument("--continue-on-error", action="store_true")
    r.add_argument("--skip-unsupported", action="store_true")

    r.add_argument("--workdir", default=None, help="Output directory for run artifacts")
    r.add_argument("--run-id", default=None, help="Override runId used for default workdir naming")

    r.add_argument("--yes", action="store_true", help="Acknowledge live actions (import into target)")

    r.set_defaults(func=cmd_replicate)

    return p


def main(argv: List[str]) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except ClientError as e:
        print(f"AWS ERROR: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
