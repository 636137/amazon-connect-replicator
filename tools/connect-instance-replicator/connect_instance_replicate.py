#!/usr/bin/env python3

import argparse
import sys
import time
from typing import Dict, Iterable, List, Optional, Tuple

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def _session(profile: Optional[str], region: str) -> boto3.session.Session:
    if profile:
        return boto3.session.Session(profile_name=profile, region_name=region)
    return boto3.session.Session(region_name=region)


def _connect_client(profile: Optional[str], region: str):
    return _session(profile, region).client("connect")


def _describe_instance_status(connect_client, instance_id: str) -> Tuple[Optional[str], Optional[Dict]]:
    try:
        resp = connect_client.describe_instance(InstanceId=instance_id)
        inst = resp.get("Instance")
        if not inst:
            return None, resp
        return inst.get("InstanceStatus"), inst
    except connect_client.exceptions.ResourceNotFoundException:
        return None, None


def wait_for_instance_active(
    *,
    profile: Optional[str],
    region: str,
    instance_id: str,
    timeout_seconds: int,
    poll_seconds: int,
) -> Dict:
    deadline = time.time() + timeout_seconds
    client = _connect_client(profile, region)

    last_status = None
    while time.time() < deadline:
        status, inst = _describe_instance_status(client, instance_id)
        if status:
            last_status = status

        if status == "ACTIVE":
            return inst

        # Known terminal-ish failures for related resources. (Exact values can evolve; keep conservative.)
        if status in {"CREATION_FAILED", "FAILED"}:
            raise RuntimeError(f"Replica instance entered failure state: {status}")

        time.sleep(poll_seconds)

    raise TimeoutError(
        f"Timed out waiting for instance {instance_id} to become ACTIVE in {region}. Last status: {last_status}"
    )


def replicate_instance(
    *,
    profile: Optional[str],
    source_region: str,
    target_region: str,
    instance_id: str,
    replica_alias: str,
    client_token: Optional[str],
) -> Dict:
    client = _connect_client(profile, source_region)

    kwargs = {
        "InstanceId": instance_id,
        "ReplicaRegion": target_region,
        "ReplicaAlias": replica_alias,
    }
    if client_token:
        kwargs["ClientToken"] = client_token

    return client.replicate_instance(**kwargs)


def _get_default_tdg_id(*, profile: Optional[str], region: str, instance_id: str) -> str:
    client = _connect_client(profile, region)
    next_token = None

    while True:
        kwargs = {"InstanceId": instance_id, "MaxResults": 10}
        if next_token:
            kwargs["NextToken"] = next_token
        resp = client.list_traffic_distribution_groups(**kwargs)
        for tdg in resp.get("TrafficDistributionGroupSummaryList", []) or []:
            if tdg.get("IsDefault"):
                # Boto3 docs: if calling from replicated region, you must use ARN. Here we call from TDG's home region.
                return tdg.get("Id") or tdg.get("Arn")

        next_token = resp.get("NextToken")
        if not next_token:
            break

    raise RuntimeError("No default traffic distribution group found for instance; is replication enabled?")


def _iter_user_ids(*, profile: Optional[str], region: str, instance_id: str) -> Iterable[str]:
    client = _connect_client(profile, region)
    next_token = None

    while True:
        kwargs = {"InstanceId": instance_id, "MaxResults": 100}
        if next_token:
            kwargs["NextToken"] = next_token
        resp = client.list_users(**kwargs)
        for user in resp.get("UserSummaryList", []) or []:
            uid = user.get("Id") or user.get("Arn")
            if uid:
                yield uid

        next_token = resp.get("NextToken")
        if not next_token:
            break


def associate_users_to_default_tdg(
    *,
    profile: Optional[str],
    region: str,
    instance_id: str,
    user_ids: Optional[List[str]],
    all_users: bool,
) -> int:
    if bool(user_ids) == bool(all_users):
        raise ValueError("Specify exactly one of --user-id or --all-users")

    tdg_id = _get_default_tdg_id(profile=profile, region=region, instance_id=instance_id)
    client = _connect_client(profile, region)

    if all_users:
        to_assoc = list(_iter_user_ids(profile=profile, region=region, instance_id=instance_id))
    else:
        to_assoc = user_ids or []

    failures = 0
    for uid in to_assoc:
        try:
            client.associate_traffic_distribution_group_user(
                TrafficDistributionGroupId=tdg_id,
                InstanceId=instance_id,
                UserId=uid,
            )
        except client.exceptions.ResourceConflictException:
            # Already associated.
            continue
        except ClientError as e:
            failures += 1
            print(f"Failed to associate user {uid}: {e}", file=sys.stderr)

    return failures


def _preflight_source_instance(*, profile: Optional[str], source_region: str, instance_id: str) -> None:
    client = _connect_client(profile, source_region)
    resp = client.describe_instance(InstanceId=instance_id)
    inst = resp.get("Instance") or {}

    status = inst.get("InstanceStatus")
    if status != "ACTIVE":
        raise RuntimeError(f"Source instance must be ACTIVE to replicate. Current status: {status}")

    # AWS docs note replication requires SAML enabled.
    idm = inst.get("IdentityManagementType")
    if idm != "SAML":
        raise RuntimeError(
            f"Replication requires IdentityManagementType=SAML (SAML enabled). Current: {idm}"
        )

    alias = inst.get("InstanceAlias")
    if not alias:
        raise RuntimeError("Source instance must have an InstanceAlias to replicate.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Replicate an Amazon Connect instance cross-region using ReplicateInstance (Global Resiliency)."
    )
    p.add_argument("--profile", default=None, help="AWS credential profile name (optional)")

    sub = p.add_subparsers(dest="cmd", required=True)

    rep = sub.add_parser("replicate", help="Create a replica instance in a paired region")
    rep.add_argument("--source-region", required=True, help="Region of the source instance (e.g., us-east-1)")
    rep.add_argument("--target-region", required=True, help="Region of the replica (e.g., us-west-2)")
    rep.add_argument("--instance-id", required=True, help="Source instance ID (or full instance ARN)")
    rep.add_argument(
        "--replica-alias",
        required=True,
        help="Unique alias for the replicated instance in the target region",
    )
    rep.add_argument("--client-token", default=None, help="Idempotency token (optional)")
    rep.add_argument("--wait", action="store_true", help="Wait until the replica is ACTIVE")
    rep.add_argument("--timeout-seconds", type=int, default=1800, help="Wait timeout (default 1800)")
    rep.add_argument("--poll-seconds", type=int, default=10, help="Polling interval (default 10)")

    assoc = sub.add_parser(
        "associate-users",
        help="Associate user(s) to the default traffic distribution group (post-replication step)",
    )
    assoc.add_argument(
        "--region",
        required=True,
        help="Region where the traffic distribution group exists (typically the source region)",
    )
    assoc.add_argument("--instance-id", required=True, help="Instance ID shared by source/replica")
    assoc.add_argument(
        "--user-id",
        action="append",
        default=None,
        help="User ID/ARN to associate (repeatable). Mutually exclusive with --all-users",
    )
    assoc.add_argument(
        "--all-users",
        action="store_true",
        help="Associate all users in the instance (uses ListUsers)",
    )

    return p


def main(argv: List[str]) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.cmd == "replicate":
            _preflight_source_instance(
                profile=args.profile, source_region=args.source_region, instance_id=args.instance_id
            )

            resp = replicate_instance(
                profile=args.profile,
                source_region=args.source_region,
                target_region=args.target_region,
                instance_id=args.instance_id,
                replica_alias=args.replica_alias,
                client_token=args.client_token,
            )

            # Per AWS docs: replica has same instance ID as source.
            replica_id = resp.get("Id")
            replica_arn = resp.get("Arn")
            print(f"replicate_instance started. replica_id={replica_id} replica_arn={replica_arn}")

            if args.wait:
                inst = wait_for_instance_active(
                    profile=args.profile,
                    region=args.target_region,
                    instance_id=replica_id or args.instance_id,
                    timeout_seconds=args.timeout_seconds,
                    poll_seconds=args.poll_seconds,
                )
                print(
                    "replica ACTIVE: "
                    + f"id={inst.get('Id')} arn={inst.get('Arn')} alias={inst.get('InstanceAlias')}"
                )

            return 0

        if args.cmd == "associate-users":
            failures = associate_users_to_default_tdg(
                profile=args.profile,
                region=args.region,
                instance_id=args.instance_id,
                user_ids=args.user_id,
                all_users=args.all_users,
            )
            if failures:
                print(f"Completed with {failures} failures", file=sys.stderr)
                return 2
            print("Association complete")
            return 0

        raise RuntimeError("Unknown command")

    except (ClientError, BotoCoreError) as e:
        print(f"AWS error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
