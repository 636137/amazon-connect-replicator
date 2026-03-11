#!/usr/bin/env python3
"""
Amazon Connect Instance Replication - Skill Wrapper (v2.0)

Wraps the amazon-connect-replicator CLI to provide on-demand cross-region
replication of Amazon Connect instance configuration.

Supported resource types (19 total):
  1. Hours of Operation
  2. Agent Statuses
  3. Security Profiles
  4. User Hierarchy Groups
  5. Queues (STANDARD)
  6. Routing Profiles
  7. Quick Connects
  8. Contact Flow Modules
  9. Contact Flows
  10. Instance Attributes
  11. Predefined Attributes
  12. Prompts
  13. Task Templates
  14. Views
  15. Rules
  16. Evaluation Forms
  17. Vocabularies
  18. Lambda Functions (discovery + ARN replacement)
  19. Lex Bots (discovery + ARN replacement)
"""

import argparse
import json
import os
import random
import re
import string
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

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


def _extract_json_from_output(output: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Extract JSON object from mixed output (info messages + JSON).
    Returns (parsed_json, prefix_text) or (None, full_output) if no JSON found.
    """
    # Find the last JSON object in the output (starts with { and ends with })
    # The replicator outputs info messages before the final JSON result
    lines = output.strip().split('\n')
    json_start = -1
    brace_count = 0
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('{') and json_start == -1:
            json_start = i
            brace_count = stripped.count('{') - stripped.count('}')
        elif json_start != -1:
            brace_count += stripped.count('{') - stripped.count('}')
        
        if json_start != -1 and brace_count == 0:
            # Found complete JSON block
            prefix = '\n'.join(lines[:json_start])
            json_text = '\n'.join(lines[json_start:i+1])
            try:
                return json.loads(json_text), prefix
            except json.JSONDecodeError:
                # Reset and keep looking
                json_start = -1
                brace_count = 0
    
    # Try parsing from the last { to end
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().startswith('{'):
            json_text = '\n'.join(lines[i:])
            try:
                return json.loads(json_text), '\n'.join(lines[:i])
            except json.JSONDecodeError:
                continue
    
    return None, output


def _run_replicator(
    *,
    replicator_script: Path,
    args: List[str],
    capture_json: bool,
    env: Optional[Dict[str, str]] = None,
) -> Any:
    cmd = [sys.executable, str(replicator_script)] + args
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    
    if capture_json:
        # Try to extract JSON even if there's mixed output
        parsed, prefix = _extract_json_from_output(proc.stdout)
        
        if parsed is not None:
            # Print prefix info to stderr so it's visible but doesn't break JSON
            if prefix.strip():
                print(prefix.strip(), file=sys.stderr)
            if proc.stderr.strip():
                print(proc.stderr.strip(), file=sys.stderr)
            return parsed
        
        # No JSON found - check if it's an error
        if proc.returncode != 0:
            raise RuntimeError(
                "Replicator CLI failed:\n"
                f"  cmd: {' '.join(cmd)}\n"
                f"  exit: {proc.returncode}\n"
                f"  stdout: {proc.stdout.strip()}\n"
                f"  stderr: {proc.stderr.strip()}\n"
            )
        raise RuntimeError(
            "Replicator did not return valid JSON on stdout.\n"
            f"stdout: {proc.stdout.strip()}\n"
            f"stderr: {proc.stderr.strip()}\n"
        )
    
    # Not capturing JSON - just check return code
    if proc.returncode != 0:
        raise RuntimeError(
            "Replicator CLI failed:\n"
            f"  cmd: {' '.join(cmd)}\n"
            f"  exit: {proc.returncode}\n"
            f"  stdout: {proc.stdout.strip()}\n"
            f"  stderr: {proc.stderr.strip()}\n"
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
    """
    Verify resource counts for all 19 supported resource types in the target instance.
    """
    client = _connect_client(profile, region)
    counts: Dict[str, int] = {}

    # 1. Hours of Operation
    try:
        hours = 0
        for page in _paginate(client.list_hours_of_operations, InstanceId=instance_id, MaxResults=100):
            hours += len(page.get("HoursOfOperationSummaryList") or [])
        counts["hoursOfOperations"] = hours
    except ClientError as e:
        print(f"WARN: Could not count hours of operations: {e}", file=sys.stderr)

    # 2. Agent Statuses
    try:
        agent_statuses = 0
        for page in _paginate(client.list_agent_statuses, InstanceId=instance_id, MaxResults=100):
            agent_statuses += len(page.get("AgentStatusSummaryList") or [])
        counts["agentStatuses"] = agent_statuses
    except ClientError as e:
        print(f"WARN: Could not count agent statuses: {e}", file=sys.stderr)

    # 3. Security Profiles
    try:
        security_profiles = 0
        for page in _paginate(client.list_security_profiles, InstanceId=instance_id, MaxResults=100):
            security_profiles += len(page.get("SecurityProfileSummaryList") or [])
        counts["securityProfiles"] = security_profiles
    except ClientError as e:
        print(f"WARN: Could not count security profiles: {e}", file=sys.stderr)

    # 4. User Hierarchy Groups
    try:
        hierarchy_groups = 0
        for page in _paginate(client.list_user_hierarchy_groups, InstanceId=instance_id, MaxResults=100):
            hierarchy_groups += len(page.get("UserHierarchyGroupSummaryList") or [])
        counts["userHierarchyGroups"] = hierarchy_groups
    except ClientError as e:
        print(f"WARN: Could not count user hierarchy groups: {e}", file=sys.stderr)

    # 5. Queues (STANDARD only)
    try:
        queues = 0
        for page in _paginate(client.list_queues, InstanceId=instance_id, MaxResults=100, QueueTypes=["STANDARD"]):
            queues += len(page.get("QueueSummaryList") or [])
        counts["queues"] = queues
    except ClientError as e:
        print(f"WARN: Could not count queues: {e}", file=sys.stderr)

    # 6. Routing Profiles
    try:
        routing_profiles = 0
        for page in _paginate(client.list_routing_profiles, InstanceId=instance_id, MaxResults=100):
            routing_profiles += len(page.get("RoutingProfileSummaryList") or [])
        counts["routingProfiles"] = routing_profiles
    except ClientError as e:
        print(f"WARN: Could not count routing profiles: {e}", file=sys.stderr)

    # 7. Quick Connects
    try:
        quick_connects = 0
        for page in _paginate(client.list_quick_connects, InstanceId=instance_id, MaxResults=100):
            quick_connects += len(page.get("QuickConnectSummaryList") or [])
        counts["quickConnects"] = quick_connects
    except ClientError as e:
        print(f"WARN: Could not count quick connects: {e}", file=sys.stderr)

    # 8. Contact Flow Modules
    try:
        modules = 0
        for page in _paginate(client.list_contact_flow_modules, InstanceId=instance_id, MaxResults=100):
            modules += len(page.get("ContactFlowModulesSummaryList") or [])
        counts["flowModules"] = modules
    except ClientError as e:
        print(f"WARN: Could not count flow modules: {e}", file=sys.stderr)

    # 9. Contact Flows
    try:
        flows = 0
        for page in _paginate(
            client.list_contact_flows,
            InstanceId=instance_id,
            MaxResults=100,
            ContactFlowTypes=CONTACT_FLOW_TYPES,
        ):
            flows += len(page.get("ContactFlowSummaryList") or [])
        counts["contactFlows"] = flows
    except ClientError as e:
        print(f"WARN: Could not count contact flows: {e}", file=sys.stderr)

    # 10. Instance Attributes (count enabled ones)
    try:
        instance_attrs = 0
        attr_types = [
            "INBOUND_CALLS", "OUTBOUND_CALLS", "CONTACTFLOW_LOGS", "CONTACT_LENS",
            "AUTO_RESOLVE_BEST_VOICES", "USE_CUSTOM_TTS_VOICES", "EARLY_MEDIA",
            "MULTI_PARTY_CONFERENCE", "HIGH_VOLUME_OUTBOUND", "ENHANCED_CONTACT_MONITORING",
        ]
        for attr_type in attr_types:
            try:
                resp = client.describe_instance_attribute(InstanceId=instance_id, AttributeType=attr_type)
                if resp.get("Attribute", {}).get("Value"):
                    instance_attrs += 1
            except ClientError:
                pass
        counts["instanceAttributes"] = instance_attrs
    except ClientError as e:
        print(f"WARN: Could not count instance attributes: {e}", file=sys.stderr)

    # 11. Predefined Attributes
    try:
        predefined_attrs = 0
        for page in _paginate(client.list_predefined_attributes, InstanceId=instance_id, MaxResults=100):
            predefined_attrs += len(page.get("PredefinedAttributeSummaryList") or [])
        counts["predefinedAttributes"] = predefined_attrs
    except ClientError as e:
        print(f"WARN: Could not count predefined attributes: {e}", file=sys.stderr)

    # 12. Prompts
    try:
        prompts = 0
        for page in _paginate(client.list_prompts, InstanceId=instance_id, MaxResults=100):
            prompts += len(page.get("PromptSummaryList") or [])
        counts["prompts"] = prompts
    except ClientError as e:
        print(f"WARN: Could not count prompts: {e}", file=sys.stderr)

    # 13. Task Templates
    try:
        task_templates = 0
        for page in _paginate(client.list_task_templates, InstanceId=instance_id, MaxResults=100):
            task_templates += len(page.get("TaskTemplates") or [])
        counts["taskTemplates"] = task_templates
    except ClientError as e:
        print(f"WARN: Could not count task templates: {e}", file=sys.stderr)

    # 14. Views
    try:
        views = 0
        for page in _paginate(client.list_views, InstanceId=instance_id, MaxResults=100):
            views += len(page.get("ViewsSummaryList") or [])
        counts["views"] = views
    except ClientError as e:
        print(f"WARN: Could not count views: {e}", file=sys.stderr)

    # 15. Rules
    try:
        rules = 0
        # Rules require PublishStatus filter
        for status in ["DRAFT", "PUBLISHED"]:
            try:
                for page in _paginate(client.list_rules, InstanceId=instance_id, MaxResults=100, PublishStatus=status):
                    rules += len(page.get("RuleSummaryList") or [])
            except ClientError:
                pass
        counts["rules"] = rules
    except ClientError as e:
        print(f"WARN: Could not count rules: {e}", file=sys.stderr)

    # 16. Evaluation Forms
    try:
        eval_forms = 0
        for page in _paginate(client.list_evaluation_forms, InstanceId=instance_id, MaxResults=100):
            eval_forms += len(page.get("EvaluationFormSummaryList") or [])
        counts["evaluationForms"] = eval_forms
    except ClientError as e:
        print(f"WARN: Could not count evaluation forms: {e}", file=sys.stderr)

    # 17. Vocabularies
    try:
        vocabularies = 0
        for page in _paginate(client.search_vocabularies, InstanceId=instance_id, MaxResults=100):
            vocabularies += len(page.get("VocabularySummaryList") or [])
        counts["vocabularies"] = vocabularies
    except ClientError as e:
        print(f"WARN: Could not count vocabularies: {e}", file=sys.stderr)

    # 18. Lambda Function Associations
    try:
        lambdas = 0
        for page in _paginate(client.list_lambda_functions, InstanceId=instance_id, MaxResults=25):
            lambdas += len(page.get("LambdaFunctions") or [])
        counts["lambdaFunctions"] = lambdas
    except ClientError as e:
        print(f"WARN: Could not count lambda functions: {e}", file=sys.stderr)

    # 19. Lex Bot Associations
    try:
        lex_bots = 0
        for page in _paginate(client.list_lex_bots, InstanceId=instance_id, MaxResults=25):
            lex_bots += len(page.get("LexBots") or [])
        counts["lexBots"] = lex_bots
    except ClientError as e:
        print(f"WARN: Could not count lex bots: {e}", file=sys.stderr)

    return counts


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
