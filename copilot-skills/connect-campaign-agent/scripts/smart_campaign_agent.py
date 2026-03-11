#!/usr/bin/env python3
"""
Amazon Connect Smart Campaign Agent

A comprehensive tool for building and managing intelligent outbound campaigns.
Supports: Segment building, campaign creation, personalization, deployment, monitoring, and optimization.

Usage:
    python smart_campaign_agent.py discover --region us-east-1
    python smart_campaign_agent.py list-campaigns --instance-alias my-connect
    python smart_campaign_agent.py create-segment --domain my-domain --name high-value-dormant
    python smart_campaign_agent.py create-campaign --config campaign.json
    python smart_campaign_agent.py start-campaign --campaign-id camp-xyz
    python smart_campaign_agent.py get-metrics --campaign-id camp-xyz
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import logging

try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
except ImportError:
    print("ERROR: boto3 is required. Install with: pip install boto3")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

DIALER_MODES = {
    'PREDICTIVE': 'ML-powered pacing, dials ahead of agent availability',
    'PROGRESSIVE': '1:1 agent ratio, no abandon risk',
    'PREVIEW': 'Agent sees customer context before dialing',
    'AGENTLESS': 'Automated messages without agents'
}

CHANNEL_TYPES = ['TELEPHONY', 'SMS', 'EMAIL', 'WHATSAPP']

CAMPAIGN_STATES = ['RUNNING', 'PAUSED', 'STOPPED', 'FAILED']

TCPA_DEFAULT_HOURS = {
    'start': '08:00',
    'end': '21:00'  # 9 PM
}

SUPPORTED_REGIONS = [
    'us-east-1', 'us-west-2', 'eu-west-2', 'ap-southeast-1',
    'ap-southeast-2', 'ap-northeast-1', 'eu-central-1', 'ca-central-1'
]

# =============================================================================
# CLIENT INITIALIZATION
# =============================================================================

class AWSClients:
    """Centralized AWS client management with lazy initialization."""
    
    def __init__(self, region: str = 'us-east-1', profile: Optional[str] = None):
        self.region = region
        self.profile = profile
        self._session = None
        self._clients = {}
    
    @property
    def session(self):
        if self._session is None:
            if self.profile:
                self._session = boto3.Session(profile_name=self.profile, region_name=self.region)
            else:
                self._session = boto3.Session(region_name=self.region)
        return self._session
    
    def get_client(self, service: str):
        """Get or create a boto3 client for the specified service."""
        if service not in self._clients:
            self._clients[service] = self.session.client(service)
        return self._clients[service]
    
    @property
    def connect(self):
        return self.get_client('connect')
    
    @property
    def campaigns(self):
        """Amazon Connect Outbound Campaigns V2 client."""
        return self.get_client('connectcampaignsv2')
    
    @property
    def profiles(self):
        """Amazon Connect Customer Profiles client."""
        return self.get_client('customer-profiles')
    
    @property
    def bedrock(self):
        """Amazon Bedrock Runtime client."""
        return self.get_client('bedrock-runtime')
    
    @property
    def cloudformation(self):
        return self.get_client('cloudformation')


# =============================================================================
# DISCOVERY MODULE
# =============================================================================

def discover_instances(clients: AWSClients, region: Optional[str] = None) -> List[Dict]:
    """
    Discover all Amazon Connect instances in the specified region.
    
    Args:
        clients: AWS clients wrapper
        region: Optional region override
    
    Returns:
        List of instance details
    """
    instances = []
    
    try:
        paginator = clients.connect.get_paginator('list_instances')
        for page in paginator.paginate():
            for instance in page.get('InstanceSummaryList', []):
                instances.append({
                    'id': instance.get('Id'),
                    'arn': instance.get('Arn'),
                    'alias': instance.get('InstanceAlias'),
                    'status': instance.get('InstanceStatus'),
                    'created': str(instance.get('CreatedTime', '')),
                    'identity_type': instance.get('IdentityManagementType'),
                    'inbound_calls': instance.get('InboundCallsEnabled'),
                    'outbound_calls': instance.get('OutboundCallsEnabled')
                })
    except ClientError as e:
        logger.error(f"Failed to list instances: {e}")
        raise
    
    return instances


def get_instance_by_alias(clients: AWSClients, alias: str) -> Optional[Dict]:
    """Find an instance by its alias."""
    instances = discover_instances(clients)
    for instance in instances:
        if instance['alias'] == alias:
            return instance
    return None


def list_campaigns(clients: AWSClients, instance_id: str) -> List[Dict]:
    """
    List all outbound campaigns for an instance.
    
    Args:
        clients: AWS clients wrapper
        instance_id: Connect instance ID
    
    Returns:
        List of campaign summaries
    """
    campaigns = []
    
    try:
        paginator = clients.campaigns.get_paginator('list_campaigns')
        for page in paginator.paginate(
            filters={'instanceIdFilter': {'operator': 'Eq', 'value': instance_id}}
        ):
            for campaign in page.get('campaignSummaryList', []):
                campaigns.append({
                    'id': campaign.get('id'),
                    'arn': campaign.get('arn'),
                    'name': campaign.get('name'),
                    'connect_instance_id': campaign.get('connectInstanceId'),
                    'schedule': campaign.get('schedule')
                })
    except ClientError as e:
        if 'ResourceNotFoundException' in str(e):
            logger.warning("Outbound campaigns not enabled for this instance")
            return []
        logger.error(f"Failed to list campaigns: {e}")
        raise
    
    return campaigns


def get_campaign(clients: AWSClients, campaign_id: str) -> Dict:
    """
    Get detailed information about a specific campaign.
    
    Args:
        clients: AWS clients wrapper
        campaign_id: Campaign ID
    
    Returns:
        Campaign details
    """
    try:
        response = clients.campaigns.get_campaign(id=campaign_id)
        return response.get('campaign', {})
    except ClientError as e:
        logger.error(f"Failed to get campaign {campaign_id}: {e}")
        raise


def get_campaign_state(clients: AWSClients, campaign_id: str) -> Dict:
    """
    Get the current state of a campaign.
    
    Args:
        clients: AWS clients wrapper
        campaign_id: Campaign ID
    
    Returns:
        Campaign state information
    """
    try:
        response = clients.campaigns.get_campaign_state(id=campaign_id)
        return {
            'state': response.get('state'),
            'campaign_id': campaign_id
        }
    except ClientError as e:
        logger.error(f"Failed to get campaign state: {e}")
        raise


# =============================================================================
# SEGMENT MODULE
# =============================================================================

def list_domains(clients: AWSClients) -> List[Dict]:
    """List Customer Profiles domains."""
    domains = []
    
    try:
        paginator = clients.profiles.get_paginator('list_domains')
        for page in paginator.paginate():
            for domain in page.get('Items', []):
                domains.append({
                    'name': domain.get('DomainName'),
                    'created': str(domain.get('CreatedAt', '')),
                    'last_updated': str(domain.get('LastUpdatedAt', '')),
                    'stats': domain.get('Stats', {})
                })
    except ClientError as e:
        logger.error(f"Failed to list domains: {e}")
        raise
    
    return domains


def list_segments(clients: AWSClients, domain_name: str) -> List[Dict]:
    """
    List all segment definitions in a Customer Profiles domain.
    
    Args:
        clients: AWS clients wrapper
        domain_name: Customer Profiles domain name
    
    Returns:
        List of segment definitions
    """
    segments = []
    
    try:
        # Note: This API may vary - adjust based on actual boto3 support
        response = clients.profiles.list_segment_definitions(
            DomainName=domain_name
        )
        
        for segment in response.get('Items', []):
            segments.append({
                'name': segment.get('SegmentDefinitionName'),
                'display_name': segment.get('DisplayName'),
                'description': segment.get('Description'),
                'created': str(segment.get('CreatedAt', ''))
            })
    except ClientError as e:
        if 'ValidationException' in str(e) or 'UnsupportedOperationException' in str(e):
            logger.warning("Segment definitions API not available in this region/domain")
            return []
        logger.error(f"Failed to list segments: {e}")
        raise
    
    return segments


def create_segment_from_sql(
    clients: AWSClients,
    domain_name: str,
    segment_name: str,
    display_name: str,
    description: str,
    sql_query: str
) -> Dict:
    """
    Create a customer segment using Spark SQL.
    
    Args:
        clients: AWS clients wrapper
        domain_name: Customer Profiles domain name
        segment_name: Unique segment identifier
        display_name: Human-readable name
        description: Segment description
        sql_query: Spark SQL query for segment definition
    
    Returns:
        Created segment details
    """
    try:
        response = clients.profiles.create_segment_definition(
            DomainName=domain_name,
            SegmentDefinitionName=segment_name,
            DisplayName=display_name,
            Description=description,
            SegmentGroups={
                'Groups': [],
                'Include': 'ALL'
            }
            # Note: Spark SQL segments may require different API structure
            # This is a placeholder - actual API may differ
        )
        
        return {
            'name': segment_name,
            'arn': response.get('SegmentDefinitionArn'),
            'created': str(datetime.utcnow())
        }
    except ClientError as e:
        logger.error(f"Failed to create segment: {e}")
        raise


def create_calculated_attribute(
    clients: AWSClients,
    domain_name: str,
    attribute_name: str,
    display_name: str,
    description: str,
    statistic: str,
    conditions: Dict
) -> Dict:
    """
    Create a calculated attribute for segmentation.
    
    Args:
        clients: AWS clients wrapper
        domain_name: Customer Profiles domain name
        attribute_name: Unique attribute identifier
        display_name: Human-readable name
        description: Attribute description
        statistic: Aggregation type (SUM, COUNT, AVG, MAX, MIN, etc.)
        conditions: Calculation conditions
    
    Returns:
        Created attribute details
    """
    try:
        response = clients.profiles.create_calculated_attribute_definition(
            DomainName=domain_name,
            CalculatedAttributeName=attribute_name,
            DisplayName=display_name,
            Description=description,
            Statistic=statistic,
            Conditions=conditions
        )
        
        return {
            'name': attribute_name,
            'arn': response.get('CalculatedAttributeArn'),
            'created': str(datetime.utcnow())
        }
    except ClientError as e:
        logger.error(f"Failed to create calculated attribute: {e}")
        raise


# =============================================================================
# CAMPAIGN CREATION MODULE
# =============================================================================

def create_campaign(
    clients: AWSClients,
    name: str,
    connect_instance_id: str,
    channel_config: Dict,
    source: Dict,
    schedule: Optional[Dict] = None,
    communication_limits: Optional[Dict] = None,
    communication_time: Optional[Dict] = None,
    tags: Optional[Dict] = None
) -> Dict:
    """
    Create an outbound campaign.
    
    Args:
        clients: AWS clients wrapper
        name: Campaign name
        connect_instance_id: Connect instance ID
        channel_config: Channel subtype configuration (telephony, SMS, email, etc.)
        source: Contact source (segment or contact list)
        schedule: Optional campaign schedule
        communication_limits: TCPA communication limits
        communication_time: Timezone and calling hours configuration
        tags: Resource tags
    
    Returns:
        Created campaign details
    """
    params = {
        'name': name,
        'connectInstanceId': connect_instance_id,
        'channelSubtypeConfig': channel_config
    }
    
    # Add source configuration
    if 'segmentArn' in source:
        params['source'] = {
            'customerProfilesSegmentArn': source['segmentArn']
        }
    elif 'contactListArn' in source:
        params['source'] = {
            'contactListArn': source['contactListArn']
        }
    
    # Add optional configurations
    if schedule:
        params['schedule'] = schedule
    
    if communication_limits:
        params['communicationLimitsOverride'] = communication_limits
    
    if communication_time:
        params['communicationTimeConfig'] = communication_time
    
    if tags:
        params['tags'] = tags
    
    try:
        response = clients.campaigns.create_campaign(**params)
        return {
            'id': response.get('id'),
            'arn': response.get('arn'),
            'name': name,
            'tags': response.get('tags', {})
        }
    except ClientError as e:
        logger.error(f"Failed to create campaign: {e}")
        raise


def build_telephony_config(
    contact_flow_id: str,
    source_phone_number: str,
    queue_id: Optional[str] = None,
    enable_amd: bool = True,
    amd_await_prompt: bool = True
) -> Dict:
    """
    Build telephony channel configuration.
    
    Args:
        contact_flow_id: Contact flow ARN for outbound calls
        source_phone_number: Outbound caller ID
        queue_id: Optional queue for agent-assisted campaigns
        enable_amd: Enable answering machine detection
        amd_await_prompt: Wait for voicemail beep before leaving message
    
    Returns:
        Telephony configuration dictionary
    """
    config = {
        'telephony': {
            'defaultOutboundConfig': {
                'connectContactFlowId': contact_flow_id,
                'connectSourcePhoneNumber': source_phone_number
            }
        }
    }
    
    if queue_id:
        config['telephony']['connectQueueId'] = queue_id
    
    if enable_amd:
        config['telephony']['defaultOutboundConfig']['answerMachineDetectionConfig'] = {
            'enableAnswerMachineDetection': True,
            'awaitAnswerMachinePrompt': amd_await_prompt
        }
    
    return config


def build_sms_config(
    template_arn: str,
    source_phone_number: str
) -> Dict:
    """Build SMS channel configuration."""
    return {
        'sms': {
            'defaultOutboundConfig': {
                'connectSourcePhoneNumberArn': source_phone_number,
                'wisdomTemplateArn': template_arn
            }
        }
    }


def build_email_config(
    template_arn: str,
    source_email_address: str
) -> Dict:
    """Build email channel configuration."""
    return {
        'email': {
            'defaultOutboundConfig': {
                'connectSourceEmailAddress': source_email_address,
                'wisdomTemplateArn': template_arn
            }
        }
    }


def build_communication_time_config(
    start_time: str = '08:00',
    end_time: str = '21:00',
    timezone_detection: str = 'ZIP_CODE'
) -> Dict:
    """
    Build TCPA-compliant communication time configuration.
    
    Args:
        start_time: Earliest call time (HH:MM format)
        end_time: Latest call time (HH:MM format)
        timezone_detection: How to detect customer timezone (ZIP_CODE or AREA_CODE)
    
    Returns:
        Communication time configuration
    """
    return {
        'localTimeZoneConfig': {
            'defaultTimeZone': 'America/New_York',
            'localTimeZoneDetection': [timezone_detection]
        },
        'telephony': {
            'openHours': {
                'dailyHours': {
                    'MONDAY': [{'startTime': start_time, 'endTime': end_time}],
                    'TUESDAY': [{'startTime': start_time, 'endTime': end_time}],
                    'WEDNESDAY': [{'startTime': start_time, 'endTime': end_time}],
                    'THURSDAY': [{'startTime': start_time, 'endTime': end_time}],
                    'FRIDAY': [{'startTime': start_time, 'endTime': end_time}],
                    'SATURDAY': [{'startTime': start_time, 'endTime': end_time}],
                    'SUNDAY': [{'startTime': start_time, 'endTime': end_time}]
                }
            }
        }
    }


def build_communication_limits(
    max_per_day: int = 3,
    max_per_24_hours: int = 3,
    all_channels_combined: bool = True
) -> Dict:
    """
    Build communication limits configuration for TCPA compliance.
    
    Args:
        max_per_day: Maximum contact attempts per calendar day
        max_per_24_hours: Maximum attempts in rolling 24-hour window
        all_channels_combined: Whether limit applies across all channels
    
    Returns:
        Communication limits configuration
    """
    return {
        'allChannelSubtypes': {
            'communicationLimitsList': [
                {
                    'maxCountPerRecipient': max_per_day,
                    'frequency': 1,
                    'unit': 'DAY'
                }
            ]
        }
    }


# =============================================================================
# CAMPAIGN LIFECYCLE MODULE
# =============================================================================

def start_campaign(clients: AWSClients, campaign_id: str) -> Dict:
    """Start a campaign."""
    try:
        clients.campaigns.start_campaign(id=campaign_id)
        return {'status': 'started', 'campaign_id': campaign_id}
    except ClientError as e:
        logger.error(f"Failed to start campaign: {e}")
        raise


def pause_campaign(clients: AWSClients, campaign_id: str) -> Dict:
    """Pause a running campaign."""
    try:
        clients.campaigns.pause_campaign(id=campaign_id)
        return {'status': 'paused', 'campaign_id': campaign_id}
    except ClientError as e:
        logger.error(f"Failed to pause campaign: {e}")
        raise


def resume_campaign(clients: AWSClients, campaign_id: str) -> Dict:
    """Resume a paused campaign."""
    try:
        clients.campaigns.resume_campaign(id=campaign_id)
        return {'status': 'resumed', 'campaign_id': campaign_id}
    except ClientError as e:
        logger.error(f"Failed to resume campaign: {e}")
        raise


def stop_campaign(clients: AWSClients, campaign_id: str) -> Dict:
    """Stop a campaign permanently."""
    try:
        clients.campaigns.stop_campaign(id=campaign_id)
        return {'status': 'stopped', 'campaign_id': campaign_id}
    except ClientError as e:
        logger.error(f"Failed to stop campaign: {e}")
        raise


def delete_campaign(clients: AWSClients, campaign_id: str) -> Dict:
    """Delete a campaign."""
    try:
        clients.campaigns.delete_campaign(id=campaign_id)
        return {'status': 'deleted', 'campaign_id': campaign_id}
    except ClientError as e:
        logger.error(f"Failed to delete campaign: {e}")
        raise


def put_dial_request_batch(
    clients: AWSClients,
    campaign_id: str,
    contacts: List[Dict],
    expiration_minutes: int = 30
) -> Dict:
    """
    Add a batch of contacts to dial for a running campaign.
    
    Args:
        clients: AWS clients wrapper
        campaign_id: Campaign ID
        contacts: List of contact records with phone numbers and attributes
        expiration_minutes: How long contacts remain valid for dialing
    
    Returns:
        Batch submission result
    """
    expiration_time = datetime.utcnow() + timedelta(minutes=expiration_minutes)
    
    dial_requests = []
    for contact in contacts:
        dial_request = {
            'clientToken': f"{campaign_id}-{contact.get('id', 'unknown')}-{int(time.time())}",
            'phoneNumber': contact['phone'],
            'expirationTime': expiration_time.isoformat() + 'Z'
        }
        
        if 'attributes' in contact:
            dial_request['attributes'] = contact['attributes']
        
        dial_requests.append(dial_request)
    
    try:
        response = clients.campaigns.put_dial_request_batch(
            id=campaign_id,
            dialRequests=dial_requests
        )
        
        return {
            'successful': len(response.get('successfulRequests', [])),
            'failed': len(response.get('failedRequests', [])),
            'failed_details': response.get('failedRequests', [])
        }
    except ClientError as e:
        logger.error(f"Failed to put dial request batch: {e}")
        raise


# =============================================================================
# PERSONALIZATION MODULE (BEDROCK)
# =============================================================================

def generate_script_with_bedrock(
    clients: AWSClients,
    campaign_type: str,
    customer_context: Dict,
    tone: str = 'professional',
    compliance_requirements: Optional[List[str]] = None
) -> str:
    """
    Generate personalized call scripts using Amazon Bedrock.
    
    Args:
        clients: AWS clients wrapper
        campaign_type: Type of campaign (collections, sales, retention, etc.)
        customer_context: Customer data for personalization
        tone: Script tone (professional, empathetic, urgent)
        compliance_requirements: Required disclosures (mini-miranda, etc.)
    
    Returns:
        Generated script content
    """
    compliance_text = ""
    if compliance_requirements:
        compliance_text = f"Include these compliance elements: {', '.join(compliance_requirements)}"
    
    prompt = f"""Generate a professional call script for a {campaign_type} campaign.

Customer Context:
- Name: {customer_context.get('name', '[Customer Name]')}
- Account: ****{customer_context.get('account_last4', '0000')}
- Balance: ${customer_context.get('balance', '0.00')}
- Days Overdue: {customer_context.get('days_overdue', 'N/A')}
- Customer Since: {customer_context.get('tenure_years', 'N/A')} years
- Lifetime Value: ${customer_context.get('lifetime_value', '0.00')}

Requirements:
- Tone: {tone}
- {compliance_text}

Generate:
1. Opening greeting
2. Reason for call
3. Main talking points
4. Objection handling (3 common objections)
5. Closing

Format the script clearly with sections and sample language."""

    try:
        response = clients.bedrock.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 2000,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ]
            })
        )
        
        result = json.loads(response['body'].read())
        return result['content'][0]['text']
    
    except ClientError as e:
        logger.error(f"Failed to generate script with Bedrock: {e}")
        raise


def generate_customer_summary(
    clients: AWSClients,
    customer_data: Dict
) -> str:
    """
    Generate a pre-call customer summary for preview dialer.
    
    Args:
        clients: AWS clients wrapper
        customer_data: Customer profile data
    
    Returns:
        Formatted customer summary
    """
    prompt = f"""Create a concise pre-call summary for an agent about to call this customer.

Customer Data:
{json.dumps(customer_data, indent=2)}

Generate a summary that includes:
1. Key customer facts (tenure, value, recent activity)
2. Account status highlights
3. Recommended approach for this call
4. Any warnings or special considerations

Keep it brief and scannable - agents have 30 seconds to review before the call."""

    try:
        response = clients.bedrock.invoke_model(
            modelId='anthropic.claude-3-haiku-20240307-v1:0',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 500,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ]
            })
        )
        
        result = json.loads(response['body'].read())
        return result['content'][0]['text']
    
    except ClientError as e:
        logger.error(f"Failed to generate customer summary: {e}")
        raise


# =============================================================================
# ANALYTICS MODULE
# =============================================================================

def get_campaign_metrics(
    clients: AWSClients,
    campaign_id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> Dict:
    """
    Get metrics for a campaign.
    
    Note: This is a placeholder - actual implementation depends on 
    Contact Lens and CloudWatch metrics integration.
    
    Args:
        clients: AWS clients wrapper
        campaign_id: Campaign ID
        start_time: Metrics start time
        end_time: Metrics end time
    
    Returns:
        Campaign metrics
    """
    # Get campaign state first
    state = get_campaign_state(clients, campaign_id)
    
    # Placeholder metrics - in production, aggregate from CloudWatch/Contact Lens
    metrics = {
        'campaign_id': campaign_id,
        'state': state.get('state'),
        'period': {
            'start': str(start_time or datetime.utcnow() - timedelta(days=1)),
            'end': str(end_time or datetime.utcnow())
        },
        'volume': {
            'total_contacts': 0,
            'dialed': 0,
            'connected': 0,
            'no_answer': 0,
            'voicemail': 0,
            'busy_failed': 0
        },
        'efficiency': {
            'connect_rate': 0.0,
            'agent_utilization': 0.0,
            'avg_handle_time': '0:00'
        },
        'outcomes': {
            'conversions': 0,
            'callbacks_scheduled': 0,
            'refused': 0
        },
        'compliance': {
            'timezone_compliant': True,
            'limit_violations': 0,
            'dnc_blocked': 0,
            'opt_outs': 0
        }
    }
    
    return metrics


def get_contact_lens_analysis(
    clients: AWSClients,
    instance_id: str,
    contact_id: str
) -> Dict:
    """
    Get Contact Lens analysis for a specific contact.
    
    Args:
        clients: AWS clients wrapper
        instance_id: Connect instance ID
        contact_id: Contact ID
    
    Returns:
        Contact Lens analysis
    """
    try:
        # Contact Lens client
        contact_lens = clients.get_client('connect-contact-lens')
        
        response = contact_lens.list_realtime_contact_analysis_segments(
            InstanceId=instance_id,
            ContactId=contact_id
        )
        
        segments = response.get('Segments', [])
        
        # Extract sentiment and categories
        analysis = {
            'contact_id': contact_id,
            'segments': segments,
            'sentiment': {
                'customer': 'NEUTRAL',
                'agent': 'NEUTRAL'
            },
            'categories': [],
            'issues': []
        }
        
        for segment in segments:
            if 'Categories' in segment:
                analysis['categories'].extend(segment['Categories'].get('MatchedCategories', []))
            if 'Transcript' in segment:
                sentiment = segment['Transcript'].get('Sentiment')
                if sentiment:
                    analysis['sentiment']['customer'] = sentiment
        
        return analysis
    
    except ClientError as e:
        logger.error(f"Failed to get Contact Lens analysis: {e}")
        raise


# =============================================================================
# CLOUDFORMATION MODULE
# =============================================================================

def generate_campaign_cloudformation(
    campaign_config: Dict
) -> str:
    """
    Generate CloudFormation template for campaign deployment.
    
    Args:
        campaign_config: Campaign configuration dictionary
    
    Returns:
        YAML CloudFormation template
    """
    template = f"""AWSTemplateFormatVersion: '2010-09-09'
Description: Amazon Connect Outbound Campaign - {campaign_config.get('name', 'Campaign')}

Parameters:
  ConnectInstanceId:
    Type: String
    Description: Amazon Connect instance ID
    
  CampaignName:
    Type: String
    Default: {campaign_config.get('name', 'MyOutboundCampaign')}
    Description: Campaign name
    
  ContactFlowId:
    Type: String
    Description: Contact flow ID for outbound calls
    
  SourcePhoneNumber:
    Type: String
    Description: Outbound caller ID phone number
    
  QueueId:
    Type: String
    Description: Queue ID for agent-assisted campaigns
    Default: ''

Conditions:
  HasQueue: !Not [!Equals [!Ref QueueId, '']]

Resources:
  OutboundCampaign:
    Type: AWS::ConnectCampaignsV2::Campaign
    Properties:
      ConnectInstanceId: !Ref ConnectInstanceId
      Name: !Ref CampaignName
      ChannelSubtypeConfig:
        Telephony:
          Capacity: 1.0
          ConnectQueueId: !If [HasQueue, !Ref QueueId, !Ref 'AWS::NoValue']
          DefaultOutboundConfig:
            ConnectContactFlowId: !Ref ContactFlowId
            ConnectSourcePhoneNumber: !Ref SourcePhoneNumber
            AnswerMachineDetectionConfig:
              EnableAnswerMachineDetection: true
              AwaitAnswerMachinePrompt: true
      CommunicationTimeConfig:
        LocalTimeZoneConfig:
          DefaultTimeZone: America/New_York
          LocalTimeZoneDetection:
            - ZIP_CODE
        Telephony:
          OpenHours:
            DailyHours:
              MONDAY:
                - StartTime: '08:00'
                  EndTime: '21:00'
              TUESDAY:
                - StartTime: '08:00'
                  EndTime: '21:00'
              WEDNESDAY:
                - StartTime: '08:00'
                  EndTime: '21:00'
              THURSDAY:
                - StartTime: '08:00'
                  EndTime: '21:00'
              FRIDAY:
                - StartTime: '08:00'
                  EndTime: '21:00'
              SATURDAY:
                - StartTime: '08:00'
                  EndTime: '21:00'
              SUNDAY:
                - StartTime: '08:00'
                  EndTime: '21:00'
      CommunicationLimitsOverride:
        AllChannelSubtypes:
          CommunicationLimitsList:
            - MaxCountPerRecipient: 3
              Frequency: 1
              Unit: DAY
      Tags:
        - Key: Application
          Value: OutboundCampaigns
        - Key: ManagedBy
          Value: SmartCampaignAgent

Outputs:
  CampaignId:
    Description: Campaign ID
    Value: !Ref OutboundCampaign
    
  CampaignArn:
    Description: Campaign ARN
    Value: !GetAtt OutboundCampaign.Arn
"""
    
    return template


def deploy_cloudformation_stack(
    clients: AWSClients,
    stack_name: str,
    template_body: str,
    parameters: Dict
) -> Dict:
    """
    Deploy a CloudFormation stack.
    
    Args:
        clients: AWS clients wrapper
        stack_name: CloudFormation stack name
        template_body: Template YAML content
        parameters: Stack parameters
    
    Returns:
        Stack creation result
    """
    try:
        cfn_params = [
            {'ParameterKey': k, 'ParameterValue': v}
            for k, v in parameters.items()
        ]
        
        response = clients.cloudformation.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=cfn_params,
            Capabilities=['CAPABILITY_IAM'],
            Tags=[
                {'Key': 'Application', 'Value': 'SmartCampaignAgent'},
                {'Key': 'CreatedBy', 'Value': 'connect-campaign-agent'}
            ]
        )
        
        return {
            'stack_id': response['StackId'],
            'stack_name': stack_name,
            'status': 'CREATE_IN_PROGRESS'
        }
    
    except ClientError as e:
        logger.error(f"Failed to deploy CloudFormation stack: {e}")
        raise


# =============================================================================
# OPTIMIZATION MODULE
# =============================================================================

def generate_optimization_recommendations(
    clients: AWSClients,
    campaign_id: str,
    metrics: Dict
) -> List[Dict]:
    """
    Generate AI-powered optimization recommendations.
    
    Args:
        clients: AWS clients wrapper
        campaign_id: Campaign ID
        metrics: Current campaign metrics
    
    Returns:
        List of optimization recommendations
    """
    recommendations = []
    
    # Analyze connect rate
    connect_rate = metrics.get('efficiency', {}).get('connect_rate', 0)
    if connect_rate < 0.30:
        recommendations.append({
            'category': 'TIMING',
            'priority': 'HIGH',
            'title': 'Low Connect Rate Detected',
            'finding': f'Current connect rate is {connect_rate*100:.1f}%',
            'recommendation': 'Analyze hourly connect rates and shift capacity to peak hours',
            'projected_impact': '+5-10% connect rate improvement'
        })
    
    # Analyze agent utilization
    utilization = metrics.get('efficiency', {}).get('agent_utilization', 0)
    if utilization < 0.60:
        recommendations.append({
            'category': 'CAPACITY',
            'priority': 'MEDIUM',
            'title': 'Low Agent Utilization',
            'finding': f'Agent utilization is {utilization*100:.1f}%',
            'recommendation': 'Consider reducing agent count or increasing dial rate',
            'projected_impact': '+20% efficiency improvement'
        })
    
    # Check compliance
    violations = metrics.get('compliance', {}).get('limit_violations', 0)
    if violations > 0:
        recommendations.append({
            'category': 'COMPLIANCE',
            'priority': 'CRITICAL',
            'title': 'Compliance Violations Detected',
            'finding': f'{violations} communication limit violations',
            'recommendation': 'Review and tighten communication limits immediately',
            'projected_impact': 'Risk mitigation - prevent potential $50K+ exposure'
        })
    
    return recommendations


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main entry point for the Smart Campaign Agent."""
    parser = argparse.ArgumentParser(
        description='Amazon Connect Smart Campaign Agent',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--region', default='us-east-1',
                        help='AWS region (default: us-east-1)')
    parser.add_argument('--profile', help='AWS profile name')
    parser.add_argument('--output', choices=['json', 'text'], default='json',
                        help='Output format')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Discover command
    discover_parser = subparsers.add_parser('discover', help='Discover Connect instances')
    
    # List campaigns command
    list_campaigns_parser = subparsers.add_parser('list-campaigns', help='List outbound campaigns')
    list_campaigns_parser.add_argument('--instance-id', help='Connect instance ID')
    list_campaigns_parser.add_argument('--instance-alias', help='Connect instance alias')
    
    # Get campaign command
    get_campaign_parser = subparsers.add_parser('get-campaign', help='Get campaign details')
    get_campaign_parser.add_argument('--campaign-id', required=True, help='Campaign ID')
    
    # Create campaign command
    create_campaign_parser = subparsers.add_parser('create-campaign', help='Create outbound campaign')
    create_campaign_parser.add_argument('--config', required=True, help='Campaign config JSON file')
    
    # Start campaign command
    start_parser = subparsers.add_parser('start-campaign', help='Start a campaign')
    start_parser.add_argument('--campaign-id', required=True, help='Campaign ID')
    
    # Pause campaign command
    pause_parser = subparsers.add_parser('pause-campaign', help='Pause a campaign')
    pause_parser.add_argument('--campaign-id', required=True, help='Campaign ID')
    
    # Resume campaign command
    resume_parser = subparsers.add_parser('resume-campaign', help='Resume a campaign')
    resume_parser.add_argument('--campaign-id', required=True, help='Campaign ID')
    
    # Stop campaign command
    stop_parser = subparsers.add_parser('stop-campaign', help='Stop a campaign')
    stop_parser.add_argument('--campaign-id', required=True, help='Campaign ID')
    
    # Get metrics command
    metrics_parser = subparsers.add_parser('get-metrics', help='Get campaign metrics')
    metrics_parser.add_argument('--campaign-id', required=True, help='Campaign ID')
    
    # List segments command
    segments_parser = subparsers.add_parser('list-segments', help='List customer segments')
    segments_parser.add_argument('--domain', required=True, help='Customer Profiles domain')
    
    # Generate script command
    script_parser = subparsers.add_parser('generate-script', help='Generate call script with Bedrock')
    script_parser.add_argument('--type', required=True, 
                               choices=['collections', 'sales', 'retention', 'support'],
                               help='Campaign type')
    script_parser.add_argument('--tone', default='professional',
                               choices=['professional', 'empathetic', 'urgent'],
                               help='Script tone')
    
    # Generate CloudFormation command
    cfn_parser = subparsers.add_parser('generate-cfn', help='Generate CloudFormation template')
    cfn_parser.add_argument('--config', required=True, help='Campaign config JSON file')
    cfn_parser.add_argument('--output-file', help='Output file path')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Initialize clients
    clients = AWSClients(region=args.region, profile=args.profile)
    
    result = None
    
    try:
        if args.command == 'discover':
            result = discover_instances(clients)
            
        elif args.command == 'list-campaigns':
            if args.instance_alias:
                instance = get_instance_by_alias(clients, args.instance_alias)
                if not instance:
                    logger.error(f"Instance not found: {args.instance_alias}")
                    sys.exit(1)
                instance_id = instance['id']
            else:
                instance_id = args.instance_id
            
            if not instance_id:
                logger.error("Either --instance-id or --instance-alias is required")
                sys.exit(1)
            
            result = list_campaigns(clients, instance_id)
            
        elif args.command == 'get-campaign':
            result = get_campaign(clients, args.campaign_id)
            
        elif args.command == 'create-campaign':
            with open(args.config) as f:
                config = json.load(f)
            
            result = create_campaign(
                clients,
                name=config['name'],
                connect_instance_id=config['connect_instance_id'],
                channel_config=config['channel_config'],
                source=config['source'],
                schedule=config.get('schedule'),
                communication_limits=config.get('communication_limits'),
                communication_time=config.get('communication_time'),
                tags=config.get('tags')
            )
            
        elif args.command == 'start-campaign':
            result = start_campaign(clients, args.campaign_id)
            
        elif args.command == 'pause-campaign':
            result = pause_campaign(clients, args.campaign_id)
            
        elif args.command == 'resume-campaign':
            result = resume_campaign(clients, args.campaign_id)
            
        elif args.command == 'stop-campaign':
            result = stop_campaign(clients, args.campaign_id)
            
        elif args.command == 'get-metrics':
            result = get_campaign_metrics(clients, args.campaign_id)
            
        elif args.command == 'list-segments':
            result = list_segments(clients, args.domain)
            
        elif args.command == 'generate-script':
            result = generate_script_with_bedrock(
                clients,
                campaign_type=args.type,
                customer_context={
                    'name': '{{customer_name}}',
                    'account_last4': '{{account_last4}}',
                    'balance': '{{balance}}',
                    'days_overdue': '{{days_overdue}}',
                    'tenure_years': '{{tenure_years}}',
                    'lifetime_value': '{{lifetime_value}}'
                },
                tone=args.tone,
                compliance_requirements=['Mini-Miranda disclosure'] if args.type == 'collections' else None
            )
            
        elif args.command == 'generate-cfn':
            with open(args.config) as f:
                config = json.load(f)
            
            template = generate_campaign_cloudformation(config)
            
            if args.output_file:
                with open(args.output_file, 'w') as f:
                    f.write(template)
                result = {'status': 'success', 'file': args.output_file}
            else:
                result = template
        
        # Output result
        if args.output == 'json' and isinstance(result, (dict, list)):
            print(json.dumps(result, indent=2, default=str))
        else:
            print(result)
            
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
