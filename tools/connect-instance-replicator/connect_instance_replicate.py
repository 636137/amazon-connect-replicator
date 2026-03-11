#!/usr/bin/env python3
"""
Amazon Connect Instance Replicator (v3.1)
Best-effort export/import of Connect configuration using primitive APIs.

Bundle v3.1 scope:
  - Hours of Operation
  - Agent Statuses
  - Security Profiles
  - User Hierarchy Groups
  - Queues (STANDARD)
  - Routing Profiles
  - Quick Connects (queue + phone; user-type skipped)
  - Contact Flow Modules
  - Contact Flows
  - Instance Attributes
  - Predefined Attributes
  - Prompts (with S3 copy)
  - Task Templates
  - Views
  - Rules
  - Evaluation Forms
  - Vocabularies
  - Lambda Functions (discovery + association + ARN replacement)
  - Lex Bots V1/V2 (discovery + association + ARN replacement)
"""

import argparse
import json
import sys
import urllib.parse
from typing import Any, Dict, Iterable, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError, ParamValidationError


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

INSTANCE_ATTRIBUTE_TYPES: List[str] = [
    "INBOUND_CALLS",
    "OUTBOUND_CALLS",
    "CONTACTFLOW_LOGS",
    "CONTACT_LENS",
    "AUTO_RESOLVE_BEST_VOICES",
    "USE_CUSTOM_TTS_VOICES",
    "EARLY_MEDIA",
    "MULTI_PARTY_CONFERENCE",
    "HIGH_VOLUME_OUTBOUND",
    "ENHANCED_CONTACT_MONITORING",
]


def _unsupported_reasons(content: str) -> List[str]:
    l = content.lower()
    reasons: List[str] = []
    if "/prompt/" in l:
        reasons.append("prompt")
    if "arn:aws:lex:" in l:
        reasons.append("lex")
    if "arn:aws:lambda:" in l:
        reasons.append("lambda")
    if "arn:aws:s3:::" in l:
        reasons.append("s3")
    if "/phone-number/" in l:
        reasons.append("phone-number")
    return reasons


def _session(profile: Optional[str], region: str) -> boto3.session.Session:
    if profile:
        return boto3.session.Session(profile_name=profile, region_name=region)
    return boto3.session.Session(region_name=region)


def _connect_client(profile: Optional[str], region: str):
    return _session(profile, region).client("connect")


def _s3_client(profile: Optional[str], region: str):
    return _session(profile, region).client("s3")


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


def _apply_replacements(content: str, replacements: List[Tuple[str, str]]) -> str:
    out = content
    for src, dst in sorted(replacements, key=lambda t: len(t[0] or ""), reverse=True):
        if not src or src == dst:
            continue
        out = out.replace(src, dst)
    return out


def _drop_none(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


# =============================================================================
# EXPORT
# =============================================================================

def _export_hours_of_operations(client, instance_id: str) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    hours_summaries: List[Dict[str, Any]] = []
    for page in _paginate(client.list_hours_of_operations, InstanceId=instance_id, MaxResults=100):
        hours_summaries.extend(page.get("HoursOfOperationSummaryList") or [])

    hours_of_operations: List[Dict[str, Any]] = []
    hours_name_by_id: Dict[str, str] = {}

    for h in hours_summaries:
        hid = h.get("Id")
        if not hid:
            continue
        try:
            d = client.describe_hours_of_operation(InstanceId=instance_id, HoursOfOperationId=hid)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"WARN: skipping hours id {hid}: ResourceNotFoundException", file=sys.stderr)
                continue
            raise
        ho = d.get("HoursOfOperation") or {}
        if ho.get("Name"):
            hours_of_operations.append({
                "id": ho.get("HoursOfOperationId"),
                "arn": ho.get("HoursOfOperationArn"),
                "name": ho.get("Name"),
                "description": ho.get("Description"),
                "timeZone": ho.get("TimeZone"),
                "config": ho.get("Config"),
                "tags": ho.get("Tags"),
            })
            hours_name_by_id[str(ho["HoursOfOperationId"])] = str(ho["Name"])

    return hours_of_operations, hours_name_by_id


def _export_agent_statuses(client, instance_id: str) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    for page in _paginate(client.list_agent_statuses, InstanceId=instance_id, MaxResults=100):
        summaries.extend(page.get("AgentStatusSummaryList") or [])

    agent_statuses: List[Dict[str, Any]] = []
    for s in summaries:
        sid = s.get("Id")
        if not sid:
            continue
        try:
            d = client.describe_agent_status(InstanceId=instance_id, AgentStatusId=sid)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"WARN: skipping agent status id {sid}: ResourceNotFoundException", file=sys.stderr)
                continue
            raise
        st = d.get("AgentStatus") or {}
        if st.get("Name"):
            agent_statuses.append({
                "id": st.get("AgentStatusId"),
                "arn": st.get("AgentStatusArn"),
                "name": st.get("Name"),
                "description": st.get("Description"),
                "type": st.get("Type"),
                "state": st.get("State"),
                "displayOrder": st.get("DisplayOrder"),
                "tags": st.get("Tags"),
            })
    return agent_statuses


def _export_security_profiles(client, instance_id: str) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    for page in _paginate(client.list_security_profiles, InstanceId=instance_id, MaxResults=100):
        summaries.extend(page.get("SecurityProfileSummaryList") or [])

    security_profiles: List[Dict[str, Any]] = []
    for s in summaries:
        sid = s.get("Id")
        if not sid:
            continue
        try:
            d = client.describe_security_profile(InstanceId=instance_id, SecurityProfileId=sid)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"WARN: skipping security profile id {sid}: ResourceNotFoundException", file=sys.stderr)
                continue
            raise
        sp = d.get("SecurityProfile") or {}
        if sp.get("SecurityProfileName"):
            perms: List[str] = []
            try:
                for ppage in _paginate(client.list_security_profile_permissions, InstanceId=instance_id, SecurityProfileId=sid, MaxResults=100):
                    perms.extend(ppage.get("Permissions") or [])
            except ClientError:
                pass
            security_profiles.append({
                "id": sp.get("Id"),
                "arn": sp.get("Arn"),
                "name": sp.get("SecurityProfileName"),
                "description": sp.get("Description"),
                "permissions": perms,
                "allowedAccessControlTags": sp.get("AllowedAccessControlTags"),
                "tagRestrictedResources": sp.get("TagRestrictedResources"),
                "tags": sp.get("Tags"),
            })
    return security_profiles


def _export_user_hierarchy_groups(client, instance_id: str) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    for page in _paginate(client.list_user_hierarchy_groups, InstanceId=instance_id, MaxResults=100):
        summaries.extend(page.get("UserHierarchyGroupSummaryList") or [])

    hierarchy_groups: List[Dict[str, Any]] = []
    for s in summaries:
        sid = s.get("Id")
        if not sid:
            continue
        try:
            d = client.describe_user_hierarchy_group(InstanceId=instance_id, HierarchyGroupId=sid)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"WARN: skipping hierarchy group id {sid}: ResourceNotFoundException", file=sys.stderr)
                continue
            raise
        hg = d.get("HierarchyGroup") or {}
        if hg.get("Name"):
            hierarchy_groups.append({
                "id": hg.get("Id"),
                "arn": hg.get("Arn"),
                "name": hg.get("Name"),
                "levelId": hg.get("LevelId"),
                "hierarchyPath": hg.get("HierarchyPath"),
                "tags": hg.get("Tags"),
            })
    return hierarchy_groups


def _export_queues(client, instance_id: str, hours_name_by_id: Dict[str, str]) -> List[Dict[str, Any]]:
    queue_summaries: List[Dict[str, Any]] = []
    for page in _paginate(client.list_queues, InstanceId=instance_id, MaxResults=100, QueueTypes=["STANDARD"]):
        queue_summaries.extend(page.get("QueueSummaryList") or [])

    queues: List[Dict[str, Any]] = []
    for q in queue_summaries:
        qid = q.get("Id")
        if not qid:
            continue
        try:
            d = client.describe_queue(InstanceId=instance_id, QueueId=qid)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"WARN: skipping queue id {qid}: ResourceNotFoundException", file=sys.stderr)
                continue
            raise
        qq = d.get("Queue") or {}
        if qq.get("Name"):
            hours_id = qq.get("HoursOfOperationId")
            queues.append({
                "id": qq.get("QueueId"),
                "arn": qq.get("QueueArn"),
                "name": qq.get("Name"),
                "description": qq.get("Description"),
                "status": qq.get("Status"),
                "maxContacts": qq.get("MaxContacts"),
                "hoursOfOperationId": hours_id,
                "hoursOfOperationName": hours_name_by_id.get(str(hours_id)) if hours_id else None,
                "outboundCallerConfig": qq.get("OutboundCallerConfig"),
                "tags": qq.get("Tags"),
            })
    return queues


def _export_routing_profiles(client, instance_id: str) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    for page in _paginate(client.list_routing_profiles, InstanceId=instance_id, MaxResults=100):
        summaries.extend(page.get("RoutingProfileSummaryList") or [])

    routing_profiles: List[Dict[str, Any]] = []
    for s in summaries:
        sid = s.get("Id")
        if not sid:
            continue
        try:
            d = client.describe_routing_profile(InstanceId=instance_id, RoutingProfileId=sid)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"WARN: skipping routing profile id {sid}: ResourceNotFoundException", file=sys.stderr)
                continue
            raise
        rp = d.get("RoutingProfile") or {}
        if rp.get("Name"):
            queue_configs: List[Dict[str, Any]] = []
            try:
                for qpage in _paginate(client.list_routing_profile_queues, InstanceId=instance_id, RoutingProfileId=sid, MaxResults=100):
                    queue_configs.extend(qpage.get("RoutingProfileQueueConfigSummaryList") or [])
            except ClientError:
                pass
            routing_profiles.append({
                "id": rp.get("RoutingProfileId"),
                "arn": rp.get("RoutingProfileArn"),
                "name": rp.get("Name"),
                "description": rp.get("Description"),
                "defaultOutboundQueueId": rp.get("DefaultOutboundQueueId"),
                "mediaConcurrencies": rp.get("MediaConcurrencies"),
                "queueConfigs": queue_configs,
                "tags": rp.get("Tags"),
            })
    return routing_profiles


def _export_quick_connects(client, instance_id: str) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    for page in _paginate(client.list_quick_connects, InstanceId=instance_id, MaxResults=100):
        summaries.extend(page.get("QuickConnectSummaryList") or [])

    quick_connects: List[Dict[str, Any]] = []
    for s in summaries:
        sid = s.get("Id")
        if not sid:
            continue
        try:
            d = client.describe_quick_connect(InstanceId=instance_id, QuickConnectId=sid)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"WARN: skipping quick connect id {sid}: ResourceNotFoundException", file=sys.stderr)
                continue
            raise
        qc = d.get("QuickConnect") or {}
        if qc.get("Name"):
            quick_connects.append({
                "id": qc.get("QuickConnectId"),
                "arn": qc.get("QuickConnectARN"),
                "name": qc.get("Name"),
                "description": qc.get("Description"),
                "quickConnectConfig": qc.get("QuickConnectConfig"),
                "tags": qc.get("Tags"),
            })
    return quick_connects


def _export_flow_modules(client, instance_id: str) -> List[Dict[str, Any]]:
    modules: List[Dict[str, Any]] = []
    for page in _paginate(client.list_contact_flow_modules, InstanceId=instance_id, MaxResults=100):
        modules.extend(page.get("ContactFlowModulesSummaryList") or [])

    flow_modules: List[Dict[str, Any]] = []
    for m in modules:
        mid = m.get("Id")
        if not mid:
            continue
        try:
            d = client.describe_contact_flow_module(InstanceId=instance_id, ContactFlowModuleId=mid)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"WARN: skipping module id {mid}: ResourceNotFoundException", file=sys.stderr)
                continue
            raise
        mod = d.get("ContactFlowModule") or {}
        if mod.get("Name"):
            flow_modules.append({
                "id": mod.get("Id"),
                "arn": mod.get("Arn"),
                "name": mod.get("Name"),
                "description": mod.get("Description"),
                "state": mod.get("State"),
                "status": mod.get("Status"),
                "content": mod.get("Content"),
                "settings": mod.get("Settings"),
                "tags": mod.get("Tags"),
            })
    return flow_modules


def _export_contact_flows(client, instance_id: str) -> List[Dict[str, Any]]:
    flows: List[Dict[str, Any]] = []
    for page in _paginate(client.list_contact_flows, InstanceId=instance_id, ContactFlowTypes=CONTACT_FLOW_TYPES, MaxResults=100):
        flows.extend(page.get("ContactFlowSummaryList") or [])

    contact_flows: List[Dict[str, Any]] = []
    for f in flows:
        fid = f.get("Id")
        if not fid:
            continue
        try:
            d = client.describe_contact_flow(InstanceId=instance_id, ContactFlowId=fid)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"WARN: skipping flow id {fid}: ResourceNotFoundException", file=sys.stderr)
                continue
            raise
        flow = d.get("ContactFlow") or {}
        if flow.get("Name") and flow.get("Type"):
            contact_flows.append({
                "id": flow.get("Id"),
                "arn": flow.get("Arn"),
                "name": flow.get("Name"),
                "type": flow.get("Type"),
                "description": flow.get("Description"),
                "state": flow.get("State"),
                "status": flow.get("Status"),
                "content": flow.get("Content"),
                "tags": flow.get("Tags"),
            })
    return contact_flows


def _export_instance_attributes(client, instance_id: str) -> List[Dict[str, Any]]:
    attrs: List[Dict[str, Any]] = []
    for attr_type in INSTANCE_ATTRIBUTE_TYPES:
        try:
            resp = client.describe_instance_attribute(InstanceId=instance_id, AttributeType=attr_type)
            a = resp.get("Attribute") or {}
            attrs.append({
                "attributeType": a.get("AttributeType"),
                "value": a.get("Value"),
            })
        except ClientError:
            pass
    return attrs


# --- V3 NEW EXPORTS ---

def _export_predefined_attributes(client, instance_id: str) -> List[Dict[str, Any]]:
    """Export predefined attributes (routing skill tags)."""
    attrs: List[Dict[str, Any]] = []
    try:
        for page in _paginate(client.list_predefined_attributes, InstanceId=instance_id, MaxResults=100):
            for pa in page.get("PredefinedAttributeSummaryList") or []:
                name = pa.get("Name")
                if not name:
                    continue
                try:
                    d = client.describe_predefined_attribute(InstanceId=instance_id, Name=name)
                    pattr = d.get("PredefinedAttribute") or {}
                    attrs.append({
                        "name": pattr.get("Name"),
                        "values": pattr.get("Values"),
                        "lastModifiedTime": str(pattr.get("LastModifiedTime")) if pattr.get("LastModifiedTime") else None,
                        "lastModifiedRegion": pattr.get("LastModifiedRegion"),
                    })
                except ClientError as e:
                    print(f"WARN: skipping predefined attribute {name}: {e}", file=sys.stderr)
    except ClientError as e:
        print(f"WARN: list_predefined_attributes not available or failed: {e}", file=sys.stderr)
    return attrs


def _export_prompts(client, instance_id: str) -> List[Dict[str, Any]]:
    """Export prompts (audio files metadata; S3 copy handled separately)."""
    prompts: List[Dict[str, Any]] = []
    try:
        for page in _paginate(client.list_prompts, InstanceId=instance_id, MaxResults=100):
            for ps in page.get("PromptSummaryList") or []:
                pid = ps.get("Id")
                if not pid:
                    continue
                try:
                    d = client.describe_prompt(InstanceId=instance_id, PromptId=pid)
                    pr = d.get("Prompt") or {}
                    prompts.append({
                        "id": pr.get("PromptId"),
                        "arn": pr.get("PromptARN"),
                        "name": pr.get("Name"),
                        "description": pr.get("Description"),
                        "s3Uri": pr.get("S3Uri"),
                        "tags": pr.get("Tags"),
                    })
                except ClientError as e:
                    print(f"WARN: skipping prompt {pid}: {e}", file=sys.stderr)
    except ClientError as e:
        print(f"WARN: list_prompts not available or failed: {e}", file=sys.stderr)
    return prompts


def _export_task_templates(client, instance_id: str) -> List[Dict[str, Any]]:
    """Export task templates."""
    templates: List[Dict[str, Any]] = []
    try:
        for page in _paginate(client.list_task_templates, InstanceId=instance_id, MaxResults=100):
            for ts in page.get("TaskTemplates") or []:
                tid = ts.get("Id")
                if not tid:
                    continue
                try:
                    d = client.get_task_template(InstanceId=instance_id, TaskTemplateId=tid)
                    templates.append({
                        "id": d.get("Id"),
                        "arn": d.get("Arn"),
                        "name": d.get("Name"),
                        "description": d.get("Description"),
                        "status": d.get("Status"),
                        "fields": d.get("Fields"),
                        "defaults": d.get("Defaults"),
                        "constraints": d.get("Constraints"),
                        "contactFlowId": d.get("ContactFlowId"),
                        "tags": d.get("Tags"),
                    })
                except ClientError as e:
                    print(f"WARN: skipping task template {tid}: {e}", file=sys.stderr)
    except ClientError as e:
        print(f"WARN: list_task_templates not available or failed: {e}", file=sys.stderr)
    return templates


def _export_views(client, instance_id: str) -> List[Dict[str, Any]]:
    """Export views (step-by-step guides)."""
    views: List[Dict[str, Any]] = []
    try:
        for page in _paginate(client.list_views, InstanceId=instance_id, MaxResults=100):
            for vs in page.get("ViewsSummaryList") or []:
                vid = vs.get("Id")
                if not vid:
                    continue
                try:
                    d = client.describe_view(InstanceId=instance_id, ViewId=vid)
                    v = d.get("View") or {}
                    views.append({
                        "id": v.get("Id"),
                        "arn": v.get("Arn"),
                        "name": v.get("Name"),
                        "description": v.get("Description"),
                        "type": v.get("Type"),
                        "status": v.get("Status"),
                        "content": v.get("Content"),
                        "tags": v.get("Tags"),
                        "version": v.get("Version"),
                        "versionDescription": v.get("VersionDescription"),
                    })
                except ClientError as e:
                    print(f"WARN: skipping view {vid}: {e}", file=sys.stderr)
    except ClientError as e:
        print(f"WARN: list_views not available or failed: {e}", file=sys.stderr)
    return views


def _export_rules(client, instance_id: str) -> List[Dict[str, Any]]:
    """Export rules (Contact Lens, event triggers)."""
    rules: List[Dict[str, Any]] = []
    try:
        for page in _paginate(client.list_rules, InstanceId=instance_id, MaxResults=100, PublishStatus="PUBLISHED"):
            for rs in page.get("RuleSummaryList") or []:
                rid = rs.get("RuleId")
                if not rid:
                    continue
                try:
                    d = client.describe_rule(InstanceId=instance_id, RuleId=rid)
                    r = d.get("Rule") or {}
                    rules.append({
                        "id": r.get("RuleId"),
                        "arn": r.get("RuleArn"),
                        "name": r.get("Name"),
                        "publishStatus": r.get("PublishStatus"),
                        "eventSourceName": r.get("EventSourceName"),
                        "function": r.get("Function"),
                        "actions": r.get("Actions"),
                        "triggerEventSource": r.get("TriggerEventSource"),
                        "tags": r.get("Tags"),
                    })
                except ClientError as e:
                    print(f"WARN: skipping rule {rid}: {e}", file=sys.stderr)
    except ClientError as e:
        print(f"WARN: list_rules not available or failed: {e}", file=sys.stderr)
    return rules


def _export_evaluation_forms(client, instance_id: str) -> List[Dict[str, Any]]:
    """Export evaluation forms (QA forms)."""
    forms: List[Dict[str, Any]] = []
    try:
        for page in _paginate(client.list_evaluation_forms, InstanceId=instance_id, MaxResults=100):
            for fs in page.get("EvaluationFormSummaryList") or []:
                fid = fs.get("EvaluationFormId")
                if not fid:
                    continue
                try:
                    # Get the latest active version
                    version = fs.get("LatestVersion") or fs.get("ActiveVersion") or 1
                    d = client.describe_evaluation_form(InstanceId=instance_id, EvaluationFormId=fid, EvaluationFormVersion=version)
                    ef = d.get("EvaluationForm") or {}
                    forms.append({
                        "id": ef.get("EvaluationFormId"),
                        "arn": ef.get("EvaluationFormArn"),
                        "title": ef.get("Title"),
                        "description": ef.get("Description"),
                        "status": ef.get("Status"),
                        "items": ef.get("Items"),
                        "scoringStrategy": ef.get("ScoringStrategy"),
                        "tags": ef.get("Tags"),
                    })
                except ClientError as e:
                    print(f"WARN: skipping evaluation form {fid}: {e}", file=sys.stderr)
    except ClientError as e:
        print(f"WARN: list_evaluation_forms not available or failed: {e}", file=sys.stderr)
    return forms


def _export_vocabularies(client, instance_id: str) -> List[Dict[str, Any]]:
    """Export custom vocabularies (Contact Lens)."""
    vocabs: List[Dict[str, Any]] = []
    try:
        for page in _paginate(client.list_default_vocabularies, InstanceId=instance_id, MaxResults=100):
            for vs in page.get("DefaultVocabularyList") or []:
                vid = vs.get("VocabularyId")
                if vid:
                    try:
                        d = client.describe_vocabulary(InstanceId=instance_id, VocabularyId=vid)
                        v = d.get("Vocabulary") or {}
                        vocabs.append({
                            "id": v.get("Id"),
                            "arn": v.get("Arn"),
                            "name": v.get("Name"),
                            "languageCode": v.get("LanguageCode"),
                            "state": v.get("State"),
                            "content": v.get("Content"),
                            "tags": v.get("Tags"),
                        })
                    except ClientError as e:
                        print(f"WARN: skipping vocabulary {vid}: {e}", file=sys.stderr)
        # Also try search_vocabularies for non-default
        for page in _paginate(client.search_vocabularies, InstanceId=instance_id, MaxResults=100):
            for vs in page.get("VocabularySummaryList") or []:
                vid = vs.get("Id")
                if vid and not any(v.get("id") == vid for v in vocabs):
                    try:
                        d = client.describe_vocabulary(InstanceId=instance_id, VocabularyId=vid)
                        v = d.get("Vocabulary") or {}
                        vocabs.append({
                            "id": v.get("Id"),
                            "arn": v.get("Arn"),
                            "name": v.get("Name"),
                            "languageCode": v.get("LanguageCode"),
                            "state": v.get("State"),
                            "content": v.get("Content"),
                            "tags": v.get("Tags"),
                        })
                    except ClientError as e:
                        print(f"WARN: skipping vocabulary {vid}: {e}", file=sys.stderr)
    except ClientError as e:
        print(f"WARN: vocabulary APIs not available or failed: {e}", file=sys.stderr)
    return vocabs


def _export_lambda_functions(client, instance_id: str) -> List[Dict[str, Any]]:
    """Export Lambda function associations from Connect instance."""
    lambdas: List[Dict[str, Any]] = []
    try:
        for page in _paginate(client.list_lambda_functions, InstanceId=instance_id, MaxResults=100):
            for arn in page.get("LambdaFunctions") or []:
                if arn:
                    # Parse ARN to extract function name and region
                    # Format: arn:aws:lambda:us-east-1:123456789012:function:MyFunction
                    parts = arn.split(":")
                    lambdas.append({
                        "arn": arn,
                        "region": parts[3] if len(parts) > 3 else None,
                        "accountId": parts[4] if len(parts) > 4 else None,
                        "functionName": parts[6] if len(parts) > 6 else None,
                    })
    except ClientError as e:
        print(f"WARN: list_lambda_functions not available or failed: {e}", file=sys.stderr)
    return lambdas


def _export_lex_bots(client, instance_id: str) -> List[Dict[str, Any]]:
    """Export Lex bot associations from Connect instance (V1 and V2)."""
    bots: List[Dict[str, Any]] = []
    
    # Try Lex V2 bots first
    try:
        for page in _paginate(client.list_bots, InstanceId=instance_id, LexVersion="V2", MaxResults=100):
            for bot in page.get("LexBots") or []:
                alias_arn = bot.get("LexBotAliasArn")
                if alias_arn:
                    # Parse ARN: arn:aws:lex:us-east-1:123456789012:bot-alias/BOTID/ALIASID
                    parts = alias_arn.split(":")
                    bots.append({
                        "aliasArn": alias_arn,
                        "lexVersion": "V2",
                        "region": parts[3] if len(parts) > 3 else None,
                        "accountId": parts[4] if len(parts) > 4 else None,
                        "botAliasId": bot.get("BotAliasId"),
                        "botName": bot.get("BotName"),
                    })
    except ClientError as e:
        print(f"WARN: list_bots V2 not available or failed: {e}", file=sys.stderr)
    
    # Try Lex V1 bots
    try:
        for page in _paginate(client.list_bots, InstanceId=instance_id, LexVersion="V1", MaxResults=100):
            for bot in page.get("LexBots") or []:
                bots.append({
                    "name": bot.get("Name"),
                    "lexVersion": "V1",
                    "lexRegion": bot.get("LexRegion"),
                })
    except ClientError as e:
        print(f"WARN: list_bots V1 not available or failed: {e}", file=sys.stderr)
    
    return bots


def export_bundle(*, profile: Optional[str], region: str, instance_id: str) -> Dict[str, Any]:
    client = _connect_client(profile, region)

    hours_of_operations, hours_name_by_id = _export_hours_of_operations(client, instance_id)
    agent_statuses = _export_agent_statuses(client, instance_id)
    security_profiles = _export_security_profiles(client, instance_id)
    user_hierarchy_groups = _export_user_hierarchy_groups(client, instance_id)
    queues = _export_queues(client, instance_id, hours_name_by_id)
    routing_profiles = _export_routing_profiles(client, instance_id)
    quick_connects = _export_quick_connects(client, instance_id)
    flow_modules = _export_flow_modules(client, instance_id)
    contact_flows = _export_contact_flows(client, instance_id)
    instance_attributes = _export_instance_attributes(client, instance_id)
    # V3 new
    predefined_attributes = _export_predefined_attributes(client, instance_id)
    prompts = _export_prompts(client, instance_id)
    task_templates = _export_task_templates(client, instance_id)
    views = _export_views(client, instance_id)
    rules = _export_rules(client, instance_id)
    evaluation_forms = _export_evaluation_forms(client, instance_id)
    vocabularies = _export_vocabularies(client, instance_id)
    # V3.1 - External integrations discovery
    lambda_functions = _export_lambda_functions(client, instance_id)
    lex_bots = _export_lex_bots(client, instance_id)

    return {
        "version": 3,
        "exportedAt": __import__("datetime").datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "source": {"region": region, "instanceId": instance_id},
        "hoursOfOperations": hours_of_operations,
        "agentStatuses": agent_statuses,
        "securityProfiles": security_profiles,
        "userHierarchyGroups": user_hierarchy_groups,
        "queues": queues,
        "routingProfiles": routing_profiles,
        "quickConnects": quick_connects,
        "flowModules": flow_modules,
        "contactFlows": contact_flows,
        "instanceAttributes": instance_attributes,
        # V3 new
        "predefinedAttributes": predefined_attributes,
        "prompts": prompts,
        "taskTemplates": task_templates,
        "views": views,
        "rules": rules,
        "evaluationForms": evaluation_forms,
        "vocabularies": vocabularies,
        # V3.1 - External integrations
        "lambdaFunctions": lambda_functions,
        "lexBots": lex_bots,
    }


# =============================================================================
# IMPORT
# =============================================================================

def _copy_s3_prompt(s3_client, source_uri: str, target_bucket: str, target_key: str) -> str:
    """Copy a prompt's audio file from source S3 to target S3."""
    # Parse s3://bucket/key from source_uri
    parsed = urllib.parse.urlparse(source_uri)
    src_bucket = parsed.netloc
    src_key = parsed.path.lstrip("/")
    
    copy_source = {"Bucket": src_bucket, "Key": src_key}
    s3_client.copy_object(CopySource=copy_source, Bucket=target_bucket, Key=target_key)
    return f"s3://{target_bucket}/{target_key}"


def import_bundle(
    *,
    profile: Optional[str],
    region: str,
    instance_id: str,
    bundle: Dict[str, Any],
    overwrite: bool,
    dry_run: bool,
    continue_on_error: bool = False,
    skip_unsupported: bool = False,
    prompt_s3_bucket: Optional[str] = None,
) -> Dict[str, Any]:
    version = bundle.get("version")
    if version not in (1, 2, 3):
        raise ValueError(f"Unsupported bundle version: {version}")

    client = _connect_client(profile, region)
    s3_client = _s3_client(profile, region) if prompt_s3_bucket else None

    # Replacement mappings (source -> target)
    replacements: List[Tuple[str, str]] = []

    # Stats
    stats: Dict[str, int] = {}
    errors: Dict[str, List[Dict[str, Any]]] = {}

    def inc(key: str):
        stats[key] = stats.get(key, 0) + 1

    def add_error(category: str, err: Dict[str, Any]):
        if category not in errors:
            errors[category] = []
        if len(errors[category]) < 50:
            errors[category].append(err)

    def add_repl(src_id: Optional[str], dst_id: Optional[str], src_arn: Optional[str] = None, dst_arn: Optional[str] = None):
        if src_id and dst_id:
            replacements.append((src_id, dst_id))
        if src_arn and dst_arn:
            replacements.append((src_arn, dst_arn))

    # -------------------------------------------------------------------------
    # 0. Build Lambda/Lex ARN replacements (source region → target region)
    # -------------------------------------------------------------------------
    source_region = bundle.get("source", {}).get("region")
    target_region = region
    
    lambda_arn_replacements: List[Tuple[str, str]] = []
    lex_arn_replacements: List[Tuple[str, str]] = []
    
    # Lambda ARNs: replace source region with target region
    # arn:aws:lambda:us-east-1:123456789012:function:MyFunc → arn:aws:lambda:us-west-2:...
    for lf in bundle.get("lambdaFunctions") or []:
        src_arn = lf.get("arn")
        if src_arn and source_region and target_region != source_region:
            target_arn = src_arn.replace(f":{source_region}:", f":{target_region}:")
            lambda_arn_replacements.append((src_arn, target_arn))
            print(f"  Lambda ARN mapping: {src_arn} → {target_arn}")
    
    # Lex V2 ARNs: replace source region with target region
    # arn:aws:lex:us-east-1:123456789012:bot-alias/XXX/YYY → arn:aws:lex:us-west-2:...
    for lb in bundle.get("lexBots") or []:
        src_arn = lb.get("aliasArn")
        if src_arn and source_region and target_region != source_region:
            target_arn = src_arn.replace(f":{source_region}:", f":{target_region}:")
            lex_arn_replacements.append((src_arn, target_arn))
            print(f"  Lex V2 ARN mapping: {src_arn} → {target_arn}")
        # Also handle Lex V1 region references in flow content
        lex_region = lb.get("lexRegion")
        if lex_region and lex_region != target_region:
            # V1 bots reference region in flow content as "LexRegion": "us-east-1"
            lex_arn_replacements.append((f'"LexRegion":"{lex_region}"', f'"LexRegion":"{target_region}"'))
            lex_arn_replacements.append((f'"LexRegion": "{lex_region}"', f'"LexRegion": "{target_region}"'))
    
    # Add to main replacements list (these will be applied to all flow content)
    replacements.extend(lambda_arn_replacements)
    replacements.extend(lex_arn_replacements)
    
    print(f"Built {len(lambda_arn_replacements)} Lambda and {len(lex_arn_replacements)} Lex ARN replacements")

    # -------------------------------------------------------------------------
    # 1. Hours of Operation
    # -------------------------------------------------------------------------
    existing_hours: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_hours_of_operations, InstanceId=instance_id, MaxResults=100):
        for h in page.get("HoursOfOperationSummaryList") or []:
            if h.get("Name"):
                existing_hours[h["Name"]] = h

    for h in bundle.get("hoursOfOperations") or []:
        name = h.get("name")
        if not name:
            continue
        existing = existing_hours.get(name)

        if existing and existing.get("Id"):
            add_repl(h.get("id"), existing["Id"], h.get("arn"), existing.get("Arn"))
            if not overwrite:
                inc("skippedHours")
                continue
            if dry_run:
                inc("updatedHours")
                continue
            try:
                client.update_hours_of_operation(**_drop_none({
                    "InstanceId": instance_id,
                    "HoursOfOperationId": existing["Id"],
                    "Name": name,
                    "Description": h.get("description"),
                    "TimeZone": h.get("timeZone"),
                    "Config": h.get("config"),
                }))
                inc("updatedHours")
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedHours")
                add_error("hours", {"name": name, "action": "update", "error": str(e)})
        else:
            if dry_run:
                inc("createdHours")
                continue
            try:
                resp = client.create_hours_of_operation(**_drop_none({
                    "InstanceId": instance_id,
                    "Name": name,
                    "Description": h.get("description"),
                    "TimeZone": h.get("timeZone"),
                    "Config": h.get("config"),
                    "Tags": h.get("tags"),
                }))
                inc("createdHours")
                existing_hours[name] = {"Id": resp.get("HoursOfOperationId"), "Arn": resp.get("HoursOfOperationArn"), "Name": name}
                add_repl(h.get("id"), resp.get("HoursOfOperationId"), h.get("arn"), resp.get("HoursOfOperationArn"))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedHours")
                add_error("hours", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 2. Agent Statuses
    # -------------------------------------------------------------------------
    existing_agent_statuses: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_agent_statuses, InstanceId=instance_id, MaxResults=100):
        for s in page.get("AgentStatusSummaryList") or []:
            if s.get("Name"):
                existing_agent_statuses[s["Name"]] = s

    for s in bundle.get("agentStatuses") or []:
        name = s.get("name")
        if not name:
            continue
        existing = existing_agent_statuses.get(name)

        if existing and existing.get("Id"):
            add_repl(s.get("id"), existing["Id"], s.get("arn"), existing.get("Arn"))
            if not overwrite:
                inc("skippedAgentStatuses")
                continue
            if dry_run:
                inc("updatedAgentStatuses")
                continue
            try:
                client.update_agent_status(**_drop_none({
                    "InstanceId": instance_id,
                    "AgentStatusId": existing["Id"],
                    "Name": name,
                    "Description": s.get("description"),
                    "State": s.get("state"),
                    "DisplayOrder": s.get("displayOrder"),
                    "ResetOrderNumber": False,
                }))
                inc("updatedAgentStatuses")
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedAgentStatuses")
                add_error("agentStatuses", {"name": name, "action": "update", "error": str(e)})
        else:
            if dry_run:
                inc("createdAgentStatuses")
                continue
            try:
                resp = client.create_agent_status(**_drop_none({
                    "InstanceId": instance_id,
                    "Name": name,
                    "Description": s.get("description"),
                    "State": s.get("state"),
                    "DisplayOrder": s.get("displayOrder"),
                    "Tags": s.get("tags"),
                }))
                inc("createdAgentStatuses")
                existing_agent_statuses[name] = {"Id": resp.get("AgentStatusId"), "Arn": resp.get("AgentStatusARN"), "Name": name}
                add_repl(s.get("id"), resp.get("AgentStatusId"), s.get("arn"), resp.get("AgentStatusARN"))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedAgentStatuses")
                add_error("agentStatuses", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 3. Security Profiles
    # -------------------------------------------------------------------------
    existing_security_profiles: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_security_profiles, InstanceId=instance_id, MaxResults=100):
        for sp in page.get("SecurityProfileSummaryList") or []:
            if sp.get("Name"):
                existing_security_profiles[sp["Name"]] = sp

    for sp in bundle.get("securityProfiles") or []:
        name = sp.get("name")
        if not name:
            continue
        existing = existing_security_profiles.get(name)

        if existing and existing.get("Id"):
            add_repl(sp.get("id"), existing["Id"], sp.get("arn"), existing.get("Arn"))
            if not overwrite:
                inc("skippedSecurityProfiles")
                continue
            if dry_run:
                inc("updatedSecurityProfiles")
                continue
            try:
                update_args = _drop_none({
                    "InstanceId": instance_id,
                    "SecurityProfileId": existing["Id"],
                    "Description": sp.get("description"),
                    "Permissions": sp.get("permissions") or [],
                    "AllowedAccessControlTags": sp.get("allowedAccessControlTags"),
                    "TagRestrictedResources": sp.get("tagRestrictedResources"),
                })
                client.update_security_profile(**update_args)
                inc("updatedSecurityProfiles")
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedSecurityProfiles")
                add_error("securityProfiles", {"name": name, "action": "update", "error": str(e)})
        else:
            if dry_run:
                inc("createdSecurityProfiles")
                continue
            try:
                resp = client.create_security_profile(**_drop_none({
                    "InstanceId": instance_id,
                    "SecurityProfileName": name,
                    "Description": sp.get("description"),
                    "Permissions": sp.get("permissions") or [],
                    "AllowedAccessControlTags": sp.get("allowedAccessControlTags"),
                    "TagRestrictedResources": sp.get("tagRestrictedResources"),
                    "Tags": sp.get("tags"),
                }))
                inc("createdSecurityProfiles")
                existing_security_profiles[name] = {"Id": resp.get("SecurityProfileId"), "Arn": resp.get("SecurityProfileArn"), "Name": name}
                add_repl(sp.get("id"), resp.get("SecurityProfileId"), sp.get("arn"), resp.get("SecurityProfileArn"))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedSecurityProfiles")
                add_error("securityProfiles", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 4. User Hierarchy Groups
    # -------------------------------------------------------------------------
    existing_hierarchy_groups: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_user_hierarchy_groups, InstanceId=instance_id, MaxResults=100):
        for hg in page.get("UserHierarchyGroupSummaryList") or []:
            if hg.get("Name"):
                existing_hierarchy_groups[hg["Name"]] = hg

    for hg in bundle.get("userHierarchyGroups") or []:
        name = hg.get("name")
        if not name:
            continue
        existing = existing_hierarchy_groups.get(name)

        if existing and existing.get("Id"):
            add_repl(hg.get("id"), existing["Id"], hg.get("arn"), existing.get("Arn"))
            if not overwrite:
                inc("skippedHierarchyGroups")
                continue
            if dry_run:
                inc("updatedHierarchyGroups")
                continue
            try:
                client.update_user_hierarchy_group_name(InstanceId=instance_id, HierarchyGroupId=existing["Id"], Name=name)
                inc("updatedHierarchyGroups")
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedHierarchyGroups")
                add_error("hierarchyGroups", {"name": name, "action": "update", "error": str(e)})
        else:
            if dry_run:
                inc("createdHierarchyGroups")
                continue
            try:
                resp = client.create_user_hierarchy_group(**_drop_none({
                    "InstanceId": instance_id,
                    "Name": name,
                    "Tags": hg.get("tags"),
                }))
                inc("createdHierarchyGroups")
                existing_hierarchy_groups[name] = {"Id": resp.get("HierarchyGroupId"), "Arn": resp.get("HierarchyGroupArn"), "Name": name}
                add_repl(hg.get("id"), resp.get("HierarchyGroupId"), hg.get("arn"), resp.get("HierarchyGroupArn"))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedHierarchyGroups")
                add_error("hierarchyGroups", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 5. Queues
    # -------------------------------------------------------------------------
    existing_queues: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_queues, InstanceId=instance_id, MaxResults=100, QueueTypes=["STANDARD"]):
        for q in page.get("QueueSummaryList") or []:
            if q.get("Name"):
                existing_queues[q["Name"]] = q

    for q in bundle.get("queues") or []:
        name = q.get("name")
        if not name:
            continue
        existing = existing_queues.get(name)

        # Resolve hours by name
        hours_name = q.get("hoursOfOperationName")
        target_hours_id = None
        if hours_name and hours_name in existing_hours:
            target_hours_id = existing_hours[hours_name].get("Id")
        if not target_hours_id:
            src_hours_id = q.get("hoursOfOperationId")
            if src_hours_id:
                for r in replacements:
                    if r[0] == src_hours_id:
                        target_hours_id = r[1]
                        break
            if not target_hours_id:
                target_hours_id = src_hours_id

        if existing and existing.get("Id"):
            add_repl(q.get("id"), existing["Id"], q.get("arn"), existing.get("Arn"))
            if not overwrite:
                inc("skippedQueues")
                continue
            if dry_run:
                inc("updatedQueues")
                continue
            try:
                if q.get("description") is not None:
                    client.update_queue_name(InstanceId=instance_id, QueueId=existing["Id"], Name=name, Description=q.get("description"))
                if target_hours_id:
                    client.update_queue_hours_of_operation(InstanceId=instance_id, QueueId=existing["Id"], HoursOfOperationId=target_hours_id)
                if q.get("maxContacts") is not None:
                    client.update_queue_max_contacts(InstanceId=instance_id, QueueId=existing["Id"], MaxContacts=q.get("maxContacts"))
                if q.get("status") is not None:
                    client.update_queue_status(InstanceId=instance_id, QueueId=existing["Id"], Status=q.get("status"))
                occ = q.get("outboundCallerConfig")
                if occ:
                    occ_clean = _drop_none({
                        "OutboundCallerIdName": occ.get("OutboundCallerIdName"),
                        "OutboundCallerIdNumberId": occ.get("OutboundCallerIdNumberId"),
                        "OutboundFlowId": occ.get("OutboundFlowId"),
                    })
                    if occ_clean:
                        client.update_queue_outbound_caller_config(InstanceId=instance_id, QueueId=existing["Id"], OutboundCallerConfig=occ_clean)
                inc("updatedQueues")
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedQueues")
                add_error("queues", {"name": name, "action": "update", "error": str(e)})
        else:
            if dry_run:
                inc("createdQueues")
                continue
            try:
                resp = client.create_queue(**_drop_none({
                    "InstanceId": instance_id,
                    "Name": name,
                    "Description": q.get("description"),
                    "HoursOfOperationId": target_hours_id,
                    "MaxContacts": q.get("maxContacts"),
                    "OutboundCallerConfig": _drop_none(q.get("outboundCallerConfig") or {}),
                    "Tags": q.get("tags"),
                }))
                inc("createdQueues")
                existing_queues[name] = {"Id": resp.get("QueueId"), "Arn": resp.get("QueueArn"), "Name": name}
                add_repl(q.get("id"), resp.get("QueueId"), q.get("arn"), resp.get("QueueArn"))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedQueues")
                add_error("queues", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 6. Routing Profiles
    # -------------------------------------------------------------------------
    existing_routing_profiles: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_routing_profiles, InstanceId=instance_id, MaxResults=100):
        for rp in page.get("RoutingProfileSummaryList") or []:
            if rp.get("Name"):
                existing_routing_profiles[rp["Name"]] = rp

    for rp in bundle.get("routingProfiles") or []:
        name = rp.get("name")
        if not name:
            continue
        existing = existing_routing_profiles.get(name)

        # Resolve default outbound queue
        def_out_q = rp.get("defaultOutboundQueueId")
        target_def_q = None
        if def_out_q:
            for repl in replacements:
                if repl[0] == def_out_q:
                    target_def_q = repl[1]
                    break
            if not target_def_q:
                for qn, qinfo in existing_queues.items():
                    if qinfo.get("Id") == def_out_q:
                        target_def_q = def_out_q
                        break
        if not target_def_q and existing_queues:
            target_def_q = list(existing_queues.values())[0].get("Id")

        if existing and existing.get("Id"):
            add_repl(rp.get("id"), existing["Id"], rp.get("arn"), existing.get("Arn"))
            if not overwrite:
                inc("skippedRoutingProfiles")
                continue
            if dry_run:
                inc("updatedRoutingProfiles")
                continue
            try:
                if rp.get("description") is not None or name:
                    client.update_routing_profile_name(InstanceId=instance_id, RoutingProfileId=existing["Id"], Name=name, Description=rp.get("description"))
                if target_def_q:
                    client.update_routing_profile_default_outbound_queue(InstanceId=instance_id, RoutingProfileId=existing["Id"], DefaultOutboundQueueId=target_def_q)
                mcs = rp.get("mediaConcurrencies")
                if mcs:
                    client.update_routing_profile_concurrency(InstanceId=instance_id, RoutingProfileId=existing["Id"], MediaConcurrencies=mcs)
                inc("updatedRoutingProfiles")
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedRoutingProfiles")
                add_error("routingProfiles", {"name": name, "action": "update", "error": str(e)})
        else:
            if dry_run:
                inc("createdRoutingProfiles")
                continue
            try:
                if not target_def_q:
                    print(f"WARN: skipping routing profile {name}: no default outbound queue", file=sys.stderr)
                    inc("skippedRoutingProfiles")
                    continue
                resp = client.create_routing_profile(**_drop_none({
                    "InstanceId": instance_id,
                    "Name": name,
                    "Description": rp.get("description"),
                    "DefaultOutboundQueueId": target_def_q,
                    "MediaConcurrencies": rp.get("mediaConcurrencies") or [{"Channel": "VOICE", "Concurrency": 1}],
                    "Tags": rp.get("tags"),
                }))
                inc("createdRoutingProfiles")
                existing_routing_profiles[name] = {"Id": resp.get("RoutingProfileId"), "Arn": resp.get("RoutingProfileArn"), "Name": name}
                add_repl(rp.get("id"), resp.get("RoutingProfileId"), rp.get("arn"), resp.get("RoutingProfileArn"))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedRoutingProfiles")
                add_error("routingProfiles", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 7. Quick Connects
    # -------------------------------------------------------------------------
    existing_quick_connects: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_quick_connects, InstanceId=instance_id, MaxResults=100):
        for qc in page.get("QuickConnectSummaryList") or []:
            if qc.get("Name"):
                existing_quick_connects[qc["Name"]] = qc

    for qc in bundle.get("quickConnects") or []:
        name = qc.get("name")
        if not name:
            continue
        qc_config = qc.get("quickConnectConfig") or {}
        qc_type = qc_config.get("QuickConnectType")
        if qc_type == "USER":
            inc("skippedQuickConnects")
            continue
        existing = existing_quick_connects.get(name)

        # Rewrite IDs in config
        config_str = json.dumps(qc_config)
        config_str = _apply_replacements(config_str, replacements)
        qc_config = json.loads(config_str)

        if existing and existing.get("Id"):
            add_repl(qc.get("id"), existing["Id"], qc.get("arn"), existing.get("Arn"))
            if not overwrite:
                inc("skippedQuickConnects")
                continue
            if dry_run:
                inc("updatedQuickConnects")
                continue
            try:
                client.update_quick_connect_config(InstanceId=instance_id, QuickConnectId=existing["Id"], QuickConnectConfig=qc_config)
                if qc.get("description") is not None or name:
                    client.update_quick_connect_name(InstanceId=instance_id, QuickConnectId=existing["Id"], Name=name, Description=qc.get("description"))
                inc("updatedQuickConnects")
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedQuickConnects")
                add_error("quickConnects", {"name": name, "action": "update", "error": str(e)})
        else:
            if dry_run:
                inc("createdQuickConnects")
                continue
            try:
                resp = client.create_quick_connect(**_drop_none({
                    "InstanceId": instance_id,
                    "Name": name,
                    "Description": qc.get("description"),
                    "QuickConnectConfig": qc_config,
                    "Tags": qc.get("tags"),
                }))
                inc("createdQuickConnects")
                existing_quick_connects[name] = {"Id": resp.get("QuickConnectId"), "Arn": resp.get("QuickConnectARN"), "Name": name}
                add_repl(qc.get("id"), resp.get("QuickConnectId"), qc.get("arn"), resp.get("QuickConnectARN"))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedQuickConnects")
                add_error("quickConnects", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 8. Flow Modules
    # -------------------------------------------------------------------------
    existing_modules: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_contact_flow_modules, InstanceId=instance_id, MaxResults=100):
        for m in page.get("ContactFlowModulesSummaryList") or []:
            if m.get("Name"):
                existing_modules[m["Name"]] = m

    for m in bundle.get("flowModules") or []:
        name = m.get("name")
        if not name:
            continue
        content = m.get("content") or ""
        if skip_unsupported:
            reasons = _unsupported_reasons(content)
            if reasons:
                print(f"WARN: skipping module {name}: unsupported deps {reasons}", file=sys.stderr)
                inc("skippedModules")
                continue
        content = _apply_replacements(content, replacements)
        existing = existing_modules.get(name)

        if existing and existing.get("Id"):
            add_repl(m.get("id"), existing["Id"], m.get("arn"), existing.get("Arn"))
            if not overwrite:
                inc("skippedModules")
                continue
            if dry_run:
                inc("updatedModules")
                continue
            try:
                client.update_contact_flow_module_content(InstanceId=instance_id, ContactFlowModuleId=existing["Id"], Content=content)
                inc("updatedModules")
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedModules")
                add_error("modules", {"name": name, "action": "update", "error": str(e)})
        else:
            if dry_run:
                inc("createdModules")
                continue
            try:
                resp = client.create_contact_flow_module(**_drop_none({
                    "InstanceId": instance_id,
                    "Name": name,
                    "Description": m.get("description"),
                    "Content": content,
                    "Tags": m.get("tags"),
                }))
                inc("createdModules")
                existing_modules[name] = {"Id": resp.get("Id"), "Arn": resp.get("Arn"), "Name": name}
                add_repl(m.get("id"), resp.get("Id"), m.get("arn"), resp.get("Arn"))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedModules")
                add_error("modules", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 9. Contact Flows (two-pass)
    # -------------------------------------------------------------------------
    existing_flows: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_contact_flows, InstanceId=instance_id, ContactFlowTypes=CONTACT_FLOW_TYPES, MaxResults=100):
        for f in page.get("ContactFlowSummaryList") or []:
            if f.get("Name") and f.get("ContactFlowType"):
                key = f"{f['ContactFlowType']}|{f['Name']}"
                existing_flows[key] = f

    # Pre-map existing flows for cross-flow reference rewriting
    for f in bundle.get("contactFlows") or []:
        name = f.get("name")
        flow_type = f.get("type")
        if not name or not flow_type:
            continue
        key = f"{flow_type}|{name}"
        existing = existing_flows.get(key)
        if existing:
            add_repl(f.get("id"), existing.get("Id"), f.get("arn"), existing.get("Arn"))

    second_pass_flows: List[Tuple[Dict[str, Any], str]] = []

    for f in bundle.get("contactFlows") or []:
        name = f.get("name")
        flow_type = f.get("type")
        if not name or not flow_type:
            continue
        content = f.get("content") or ""
        if skip_unsupported:
            reasons = _unsupported_reasons(content)
            if reasons:
                print(f"WARN: skipping flow {name} ({flow_type}): unsupported deps {reasons}", file=sys.stderr)
                inc("skippedFlows")
                continue
        content = _apply_replacements(content, replacements)
        key = f"{flow_type}|{name}"
        existing = existing_flows.get(key)

        if existing and existing.get("Id"):
            if not overwrite:
                inc("skippedFlows")
                continue
            if dry_run:
                inc("updatedFlows")
                continue
            try:
                client.update_contact_flow_content(InstanceId=instance_id, ContactFlowId=existing["Id"], Content=content)
                inc("updatedFlows")
                second_pass_flows.append((f, existing["Id"]))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedFlows")
                add_error("flows", {"name": name, "type": flow_type, "action": "update", "error": str(e)})
        else:
            if dry_run:
                inc("createdFlows")
                continue
            try:
                resp = client.create_contact_flow(**_drop_none({
                    "InstanceId": instance_id,
                    "Name": name,
                    "Type": flow_type,
                    "Description": f.get("description"),
                    "Content": content,
                    "Tags": f.get("tags"),
                }))
                inc("createdFlows")
                new_id = resp.get("ContactFlowId")
                new_arn = resp.get("ContactFlowArn")
                existing_flows[key] = {"Id": new_id, "Arn": new_arn, "Name": name, "ContactFlowType": flow_type}
                add_repl(f.get("id"), new_id, f.get("arn"), new_arn)
                second_pass_flows.append((f, new_id))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedFlows")
                add_error("flows", {"name": name, "type": flow_type, "action": "create", "error": str(e)})

    # Second pass for cross-flow references
    if not dry_run:
        for src_flow, target_id in second_pass_flows:
            content = src_flow.get("content") or ""
            content2 = _apply_replacements(content, replacements)
            try:
                client.update_contact_flow_content(InstanceId=instance_id, ContactFlowId=target_id, Content=content2)
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedFlows")
                add_error("flows", {"name": src_flow.get("name"), "type": src_flow.get("type"), "action": "secondPassUpdate", "error": str(e)})

    # -------------------------------------------------------------------------
    # 10. Instance Attributes
    # -------------------------------------------------------------------------
    for attr in bundle.get("instanceAttributes") or []:
        attr_type = attr.get("attributeType")
        value = attr.get("value")
        if not attr_type or value is None:
            continue
        if dry_run:
            inc("updatedInstanceAttributes")
            continue
        try:
            client.update_instance_attribute(InstanceId=instance_id, AttributeType=attr_type, Value=value)
            inc("updatedInstanceAttributes")
        except (ClientError, ParamValidationError) as e:
            if not continue_on_error:
                raise
            inc("failedInstanceAttributes")
            add_error("instanceAttributes", {"attributeType": attr_type, "error": str(e)})

    # -------------------------------------------------------------------------
    # 11. Predefined Attributes (V3)
    # -------------------------------------------------------------------------
    if version >= 3:
        existing_predefined: Dict[str, Dict[str, Any]] = {}
        try:
            for page in _paginate(client.list_predefined_attributes, InstanceId=instance_id, MaxResults=100):
                for pa in page.get("PredefinedAttributeSummaryList") or []:
                    if pa.get("Name"):
                        existing_predefined[pa["Name"]] = pa
        except ClientError:
            pass

        for pa in bundle.get("predefinedAttributes") or []:
            name = pa.get("name")
            if not name:
                continue
            existing = existing_predefined.get(name)
            values = pa.get("values")

            if existing:
                if not overwrite:
                    inc("skippedPredefinedAttributes")
                    continue
                if dry_run:
                    inc("updatedPredefinedAttributes")
                    continue
                try:
                    client.update_predefined_attribute(InstanceId=instance_id, Name=name, Values=values)
                    inc("updatedPredefinedAttributes")
                except (ClientError, ParamValidationError) as e:
                    if not continue_on_error:
                        raise
                    inc("failedPredefinedAttributes")
                    add_error("predefinedAttributes", {"name": name, "action": "update", "error": str(e)})
            else:
                if dry_run:
                    inc("createdPredefinedAttributes")
                    continue
                try:
                    client.create_predefined_attribute(**_drop_none({
                        "InstanceId": instance_id,
                        "Name": name,
                        "Values": values,
                    }))
                    inc("createdPredefinedAttributes")
                except (ClientError, ParamValidationError) as e:
                    if not continue_on_error:
                        raise
                    inc("failedPredefinedAttributes")
                    add_error("predefinedAttributes", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 12. Prompts (V3) - requires S3 bucket for audio copy
    # -------------------------------------------------------------------------
    if version >= 3 and prompt_s3_bucket:
        existing_prompts: Dict[str, Dict[str, Any]] = {}
        try:
            for page in _paginate(client.list_prompts, InstanceId=instance_id, MaxResults=100):
                for ps in page.get("PromptSummaryList") or []:
                    if ps.get("Name"):
                        existing_prompts[ps["Name"]] = ps
        except ClientError:
            pass

        for pr in bundle.get("prompts") or []:
            name = pr.get("name")
            s3_uri = pr.get("s3Uri")
            if not name or not s3_uri:
                continue
            existing = existing_prompts.get(name)

            if existing and existing.get("Id"):
                add_repl(pr.get("id"), existing["Id"], pr.get("arn"), existing.get("Arn"))
                inc("skippedPrompts")  # Can't update prompt audio
                continue

            if dry_run:
                inc("createdPrompts")
                continue
            try:
                # Copy S3 file
                target_key = f"connect-prompts/{instance_id}/{name}.wav"
                new_s3_uri = _copy_s3_prompt(s3_client, s3_uri, prompt_s3_bucket, target_key)
                resp = client.create_prompt(**_drop_none({
                    "InstanceId": instance_id,
                    "Name": name,
                    "Description": pr.get("description"),
                    "S3Uri": new_s3_uri,
                    "Tags": pr.get("tags"),
                }))
                inc("createdPrompts")
                add_repl(pr.get("id"), resp.get("PromptId"), pr.get("arn"), resp.get("PromptARN"))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedPrompts")
                add_error("prompts", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 13. Task Templates (V3)
    # -------------------------------------------------------------------------
    if version >= 3:
        existing_task_templates: Dict[str, Dict[str, Any]] = {}
        try:
            for page in _paginate(client.list_task_templates, InstanceId=instance_id, MaxResults=100):
                for tt in page.get("TaskTemplates") or []:
                    if tt.get("Name"):
                        existing_task_templates[tt["Name"]] = tt
        except ClientError:
            pass

        for tt in bundle.get("taskTemplates") or []:
            name = tt.get("name")
            if not name:
                continue
            existing = existing_task_templates.get(name)

            # Rewrite flow IDs in contactFlowId
            cf_id = tt.get("contactFlowId")
            if cf_id:
                cf_id = _apply_replacements(cf_id, replacements)

            fields = tt.get("fields")
            if fields:
                fields_str = json.dumps(fields)
                fields_str = _apply_replacements(fields_str, replacements)
                fields = json.loads(fields_str)

            if existing and existing.get("Id"):
                add_repl(tt.get("id"), existing["Id"], tt.get("arn"), existing.get("Arn"))
                if not overwrite:
                    inc("skippedTaskTemplates")
                    continue
                if dry_run:
                    inc("updatedTaskTemplates")
                    continue
                try:
                    client.update_task_template(**_drop_none({
                        "InstanceId": instance_id,
                        "TaskTemplateId": existing["Id"],
                        "Name": name,
                        "Description": tt.get("description"),
                        "Fields": fields,
                        "Defaults": tt.get("defaults"),
                        "Constraints": tt.get("constraints"),
                        "ContactFlowId": cf_id,
                        "Status": tt.get("status"),
                    }))
                    inc("updatedTaskTemplates")
                except (ClientError, ParamValidationError) as e:
                    if not continue_on_error:
                        raise
                    inc("failedTaskTemplates")
                    add_error("taskTemplates", {"name": name, "action": "update", "error": str(e)})
            else:
                if dry_run:
                    inc("createdTaskTemplates")
                    continue
                try:
                    resp = client.create_task_template(**_drop_none({
                        "InstanceId": instance_id,
                        "Name": name,
                        "Description": tt.get("description"),
                        "Fields": fields,
                        "Defaults": tt.get("defaults"),
                        "Constraints": tt.get("constraints"),
                        "ContactFlowId": cf_id,
                        "Status": tt.get("status") or "ACTIVE",
                    }))
                    inc("createdTaskTemplates")
                    add_repl(tt.get("id"), resp.get("Id"), tt.get("arn"), resp.get("Arn"))
                except (ClientError, ParamValidationError) as e:
                    if not continue_on_error:
                        raise
                    inc("failedTaskTemplates")
                    add_error("taskTemplates", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 14. Views (V3)
    # -------------------------------------------------------------------------
    if version >= 3:
        existing_views: Dict[str, Dict[str, Any]] = {}
        try:
            for page in _paginate(client.list_views, InstanceId=instance_id, MaxResults=100):
                for vs in page.get("ViewsSummaryList") or []:
                    if vs.get("Name"):
                        existing_views[vs["Name"]] = vs
        except ClientError:
            pass

        for v in bundle.get("views") or []:
            name = v.get("name")
            if not name:
                continue
            existing = existing_views.get(name)
            content = v.get("content")
            if content:
                content_str = json.dumps(content) if isinstance(content, dict) else str(content)
                content_str = _apply_replacements(content_str, replacements)
                content = json.loads(content_str) if content_str.startswith("{") else content_str

            if existing and existing.get("Id"):
                add_repl(v.get("id"), existing["Id"], v.get("arn"), existing.get("Arn"))
                if not overwrite:
                    inc("skippedViews")
                    continue
                if dry_run:
                    inc("updatedViews")
                    continue
                try:
                    client.update_view_content(**_drop_none({
                        "InstanceId": instance_id,
                        "ViewId": existing["Id"],
                        "Content": content,
                        "Status": v.get("status") or "PUBLISHED",
                    }))
                    inc("updatedViews")
                except (ClientError, ParamValidationError) as e:
                    if not continue_on_error:
                        raise
                    inc("failedViews")
                    add_error("views", {"name": name, "action": "update", "error": str(e)})
            else:
                if dry_run:
                    inc("createdViews")
                    continue
                try:
                    resp = client.create_view(**_drop_none({
                        "InstanceId": instance_id,
                        "Name": name,
                        "Description": v.get("description"),
                        "Content": content,
                        "Status": v.get("status") or "PUBLISHED",
                        "Tags": v.get("tags"),
                    }))
                    inc("createdViews")
                    view_resp = resp.get("View") or {}
                    add_repl(v.get("id"), view_resp.get("Id"), v.get("arn"), view_resp.get("Arn"))
                except (ClientError, ParamValidationError) as e:
                    if not continue_on_error:
                        raise
                    inc("failedViews")
                    add_error("views", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 15. Rules (V3)
    # -------------------------------------------------------------------------
    if version >= 3:
        existing_rules: Dict[str, Dict[str, Any]] = {}
        try:
            for page in _paginate(client.list_rules, InstanceId=instance_id, MaxResults=100, PublishStatus="PUBLISHED"):
                for rs in page.get("RuleSummaryList") or []:
                    if rs.get("Name"):
                        existing_rules[rs["Name"]] = rs
        except ClientError:
            pass

        for r in bundle.get("rules") or []:
            name = r.get("name")
            if not name:
                continue
            existing = existing_rules.get(name)

            # Rewrite IDs in actions
            actions = r.get("actions")
            if actions:
                actions_str = json.dumps(actions)
                actions_str = _apply_replacements(actions_str, replacements)
                actions = json.loads(actions_str)

            trigger = r.get("triggerEventSource")
            if trigger:
                trigger_str = json.dumps(trigger)
                trigger_str = _apply_replacements(trigger_str, replacements)
                trigger = json.loads(trigger_str)

            func = r.get("function")
            if func:
                func = _apply_replacements(func, replacements)

            if existing and existing.get("RuleId"):
                add_repl(r.get("id"), existing["RuleId"], r.get("arn"), existing.get("RuleArn"))
                if not overwrite:
                    inc("skippedRules")
                    continue
                if dry_run:
                    inc("updatedRules")
                    continue
                try:
                    client.update_rule(**_drop_none({
                        "InstanceId": instance_id,
                        "RuleId": existing["RuleId"],
                        "Name": name,
                        "Function": func,
                        "Actions": actions,
                        "PublishStatus": r.get("publishStatus") or "PUBLISHED",
                    }))
                    inc("updatedRules")
                except (ClientError, ParamValidationError) as e:
                    if not continue_on_error:
                        raise
                    inc("failedRules")
                    add_error("rules", {"name": name, "action": "update", "error": str(e)})
            else:
                if dry_run:
                    inc("createdRules")
                    continue
                try:
                    resp = client.create_rule(**_drop_none({
                        "InstanceId": instance_id,
                        "Name": name,
                        "Function": func,
                        "Actions": actions or [],
                        "TriggerEventSource": trigger,
                        "PublishStatus": r.get("publishStatus") or "PUBLISHED",
                    }))
                    inc("createdRules")
                    add_repl(r.get("id"), resp.get("RuleId"), r.get("arn"), resp.get("RuleArn"))
                except (ClientError, ParamValidationError) as e:
                    if not continue_on_error:
                        raise
                    inc("failedRules")
                    add_error("rules", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 16. Evaluation Forms (V3)
    # -------------------------------------------------------------------------
    if version >= 3:
        existing_eval_forms: Dict[str, Dict[str, Any]] = {}
        try:
            for page in _paginate(client.list_evaluation_forms, InstanceId=instance_id, MaxResults=100):
                for ef in page.get("EvaluationFormSummaryList") or []:
                    if ef.get("Title"):
                        existing_eval_forms[ef["Title"]] = ef
        except ClientError:
            pass

        for ef in bundle.get("evaluationForms") or []:
            title = ef.get("title")
            if not title:
                continue
            existing = existing_eval_forms.get(title)
            items = ef.get("items")

            if existing and existing.get("EvaluationFormId"):
                add_repl(ef.get("id"), existing["EvaluationFormId"], ef.get("arn"), existing.get("EvaluationFormArn"))
                inc("skippedEvaluationForms")  # Eval forms require versioning for updates
                continue

            if dry_run:
                inc("createdEvaluationForms")
                continue
            try:
                resp = client.create_evaluation_form(**_drop_none({
                    "InstanceId": instance_id,
                    "Title": title,
                    "Description": ef.get("description"),
                    "Items": items or [],
                    "ScoringStrategy": ef.get("scoringStrategy"),
                }))
                inc("createdEvaluationForms")
                add_repl(ef.get("id"), resp.get("EvaluationFormId"), ef.get("arn"), resp.get("EvaluationFormArn"))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedEvaluationForms")
                add_error("evaluationForms", {"title": title, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 17. Vocabularies (V3)
    # -------------------------------------------------------------------------
    if version >= 3:
        existing_vocabs: Dict[str, Dict[str, Any]] = {}
        try:
            for page in _paginate(client.search_vocabularies, InstanceId=instance_id, MaxResults=100):
                for vs in page.get("VocabularySummaryList") or []:
                    if vs.get("Name"):
                        existing_vocabs[vs["Name"]] = vs
        except ClientError:
            pass

        for voc in bundle.get("vocabularies") or []:
            name = voc.get("name")
            lang = voc.get("languageCode")
            content = voc.get("content")
            if not name or not lang:
                continue
            existing = existing_vocabs.get(name)

            if existing and existing.get("Id"):
                add_repl(voc.get("id"), existing["Id"], voc.get("arn"), existing.get("Arn"))
                inc("skippedVocabularies")  # Can't update vocabulary content
                continue

            if dry_run:
                inc("createdVocabularies")
                continue
            try:
                resp = client.create_vocabulary(**_drop_none({
                    "InstanceId": instance_id,
                    "VocabularyName": name,
                    "LanguageCode": lang,
                    "Content": content,
                    "Tags": voc.get("tags"),
                }))
                inc("createdVocabularies")
                add_repl(voc.get("id"), resp.get("VocabularyId"), voc.get("arn"), resp.get("VocabularyArn"))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedVocabularies")
                add_error("vocabularies", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 18. Associate Lambda Functions with Target Instance
    # -------------------------------------------------------------------------
    existing_lambdas: set = set()
    try:
        for page in _paginate(client.list_lambda_functions, InstanceId=instance_id, MaxResults=100):
            for arn in page.get("LambdaFunctions") or []:
                if arn:
                    existing_lambdas.add(arn)
    except ClientError:
        pass

    for lf in bundle.get("lambdaFunctions") or []:
        src_arn = lf.get("arn")
        if not src_arn:
            continue
        # Build target ARN by replacing region
        target_arn = src_arn.replace(f":{source_region}:", f":{target_region}:") if source_region else src_arn
        
        if target_arn in existing_lambdas:
            inc("skippedLambdas")
            continue
        
        if dry_run:
            inc("associatedLambdas")
            continue
        
        try:
            client.associate_lambda_function(InstanceId=instance_id, FunctionArn=target_arn)
            inc("associatedLambdas")
            print(f"  Associated Lambda: {target_arn}")
        except ClientError as e:
            # Lambda might not exist in target region
            err_code = e.response.get("Error", {}).get("Code", "")
            if err_code in ("ResourceNotFoundException", "InvalidParameterException"):
                inc("failedLambdas")
                add_error("lambdas", {"arn": target_arn, "action": "associate", "error": str(e)})
                print(f"  WARN: Lambda not found in target region: {target_arn}", file=sys.stderr)
            elif not continue_on_error:
                raise
            else:
                inc("failedLambdas")
                add_error("lambdas", {"arn": target_arn, "action": "associate", "error": str(e)})

    # -------------------------------------------------------------------------
    # 19. Associate Lex Bots with Target Instance
    # -------------------------------------------------------------------------
    existing_lex_v2: set = set()
    existing_lex_v1: set = set()
    try:
        for page in _paginate(client.list_bots, InstanceId=instance_id, LexVersion="V2", MaxResults=100):
            for bot in page.get("LexBots") or []:
                if bot.get("LexBotAliasArn"):
                    existing_lex_v2.add(bot["LexBotAliasArn"])
    except ClientError:
        pass
    try:
        for page in _paginate(client.list_bots, InstanceId=instance_id, LexVersion="V1", MaxResults=100):
            for bot in page.get("LexBots") or []:
                if bot.get("Name"):
                    existing_lex_v1.add(bot["Name"])
    except ClientError:
        pass

    for lb in bundle.get("lexBots") or []:
        lex_version = lb.get("lexVersion")
        
        if lex_version == "V2":
            src_arn = lb.get("aliasArn")
            if not src_arn:
                continue
            target_arn = src_arn.replace(f":{source_region}:", f":{target_region}:") if source_region else src_arn
            
            if target_arn in existing_lex_v2:
                inc("skippedLexBots")
                continue
            
            if dry_run:
                inc("associatedLexBots")
                continue
            
            try:
                client.associate_bot(InstanceId=instance_id, LexV2Bot={"AliasArn": target_arn})
                inc("associatedLexBots")
                print(f"  Associated Lex V2 bot: {target_arn}")
            except ClientError as e:
                err_code = e.response.get("Error", {}).get("Code", "")
                if err_code in ("ResourceNotFoundException", "InvalidParameterException"):
                    inc("failedLexBots")
                    add_error("lexBots", {"arn": target_arn, "action": "associate", "error": str(e)})
                    print(f"  WARN: Lex V2 bot not found in target region: {target_arn}", file=sys.stderr)
                elif not continue_on_error:
                    raise
                else:
                    inc("failedLexBots")
                    add_error("lexBots", {"arn": target_arn, "action": "associate", "error": str(e)})
        
        elif lex_version == "V1":
            bot_name = lb.get("name")
            src_region = lb.get("lexRegion")
            if not bot_name:
                continue
            
            if bot_name in existing_lex_v1:
                inc("skippedLexBots")
                continue
            
            if dry_run:
                inc("associatedLexBots")
                continue
            
            try:
                client.associate_lex_bot(InstanceId=instance_id, LexBot={"Name": bot_name, "LexRegion": target_region})
                inc("associatedLexBots")
                print(f"  Associated Lex V1 bot: {bot_name} in {target_region}")
            except ClientError as e:
                err_code = e.response.get("Error", {}).get("Code", "")
                if err_code in ("ResourceNotFoundException", "InvalidParameterException"):
                    inc("failedLexBots")
                    add_error("lexBots", {"name": bot_name, "action": "associate", "error": str(e)})
                    print(f"  WARN: Lex V1 bot not found in target region: {bot_name}", file=sys.stderr)
                elif not continue_on_error:
                    raise
                else:
                    inc("failedLexBots")
                    add_error("lexBots", {"name": bot_name, "action": "associate", "error": str(e)})

    return {
        **stats,
        "errors": errors,
        "dryRun": dry_run,
        "overwrite": overwrite,
        "continueOnError": continue_on_error,
        "skipUnsupported": skip_unsupported,
    }


# =============================================================================
# CLI
# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Best-effort Amazon Connect exporter/importer using primitive Connect APIs (v3: hours, agent statuses, security profiles, hierarchy groups, queues, routing profiles, quick connects, modules, flows, predefined attrs, prompts, task templates, views, rules, eval forms, vocabularies)."
    )
    p.add_argument("--profile", default=None, help="AWS credential profile name (optional)")

    sub = p.add_subparsers(dest="cmd", required=True)

    exp = sub.add_parser("export", help="Export a bundle (v3)")
    exp.add_argument("--region", required=True)
    exp.add_argument("--instance-id", required=True)
    exp.add_argument("--out", required=False, default="-", help="Output file path, or '-' for stdout")

    imp = sub.add_parser("import", help="Import a bundle into an existing instance")
    imp.add_argument("--region", required=True)
    imp.add_argument("--instance-id", required=True)
    imp.add_argument("--in", dest="in_path", required=True, help="Input bundle JSON path")
    imp.add_argument("--overwrite", action="store_true", help="Overwrite (update content) if resource exists")
    imp.add_argument("--dry-run", action="store_true", help="Print what would happen, but do not call Create/Update")
    imp.add_argument("--continue-on-error", action="store_true", help="Continue importing after errors")
    imp.add_argument("--skip-unsupported", action="store_true", help="Skip flows/modules with external deps")
    imp.add_argument("--prompt-s3-bucket", default=None, help="S3 bucket in target region for prompt audio files")

    return p


def main(argv: List[str]) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.cmd == "export":
            b = export_bundle(profile=args.profile, region=args.region, instance_id=args.instance_id)
            data = json.dumps(b, indent=2)
            if args.out == "-":
                print(data)
            else:
                with open(args.out, "w", encoding="utf-8") as f:
                    f.write(data)
                print(f"Wrote bundle: {args.out}", file=sys.stderr)
            return 0

        if args.cmd == "import":
            with open(args.in_path, "r", encoding="utf-8") as f:
                bundle = json.load(f)
            out = import_bundle(
                profile=args.profile,
                region=args.region,
                instance_id=args.instance_id,
                bundle=bundle,
                overwrite=args.overwrite,
                dry_run=args.dry_run,
                continue_on_error=args.continue_on_error,
                skip_unsupported=args.skip_unsupported,
                prompt_s3_bucket=getattr(args, "prompt_s3_bucket", None),
            )
            print(json.dumps(out, indent=2))
            return 0

        raise RuntimeError("Unknown command")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
