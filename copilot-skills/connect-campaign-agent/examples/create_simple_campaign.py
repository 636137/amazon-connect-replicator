#!/usr/bin/env python3
"""
Example: Create a simple outbound campaign

This script demonstrates how to create a basic outbound campaign
using the Amazon Connect Outbound Campaigns V2 API.

Usage:
    python create_simple_campaign.py \
        --instance-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
        --contact-flow-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
        --queue-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
        --phone-number +12125551234 \
        --name "My Campaign"
"""

import argparse
import json
import boto3
from datetime import datetime


def create_campaign(
    instance_id: str,
    contact_flow_id: str,
    queue_id: str,
    phone_number: str,
    campaign_name: str,
    region: str = 'us-east-1'
) -> dict:
    """
    Create a simple outbound campaign with TCPA-compliant defaults.
    
    Args:
        instance_id: Amazon Connect instance ID
        contact_flow_id: Contact flow for outbound calls
        queue_id: Queue for agent routing
        phone_number: Outbound caller ID (E.164 format)
        campaign_name: Name for the campaign
        region: AWS region
    
    Returns:
        Created campaign details
    """
    
    client = boto3.client('connectcampaignsv2', region_name=region)
    
    # Build campaign configuration with best practices
    campaign_config = {
        'name': campaign_name,
        'connectInstanceId': instance_id,
        
        # Telephony channel configuration
        'channelSubtypeConfig': {
            'telephony': {
                'capacity': 0.7,  # Conservative pacing
                'connectQueueId': queue_id,
                'defaultOutboundConfig': {
                    'connectContactFlowId': contact_flow_id,
                    'connectSourcePhoneNumber': phone_number,
                    
                    # Answering Machine Detection
                    'answerMachineDetectionConfig': {
                        'enableAnswerMachineDetection': True,
                        'awaitAnswerMachinePrompt': True  # Wait for beep
                    }
                }
            }
        },
        
        # TCPA Compliance - Communication Time
        'communicationTimeConfig': {
            'localTimeZoneConfig': {
                'defaultTimeZone': 'America/New_York',
                'localTimeZoneDetection': ['ZIP_CODE', 'AREA_CODE']
            },
            'telephony': {
                'openHours': {
                    'dailyHours': {
                        day: [{'startTime': '08:00', 'endTime': '21:00'}]
                        for day in ['MONDAY', 'TUESDAY', 'WEDNESDAY', 
                                   'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']
                    }
                }
            }
        },
        
        # TCPA Compliance - Communication Limits
        'communicationLimitsOverride': {
            'allChannelSubtypes': {
                'communicationLimitsList': [
                    {
                        'maxCountPerRecipient': 3,
                        'frequency': 1,
                        'unit': 'DAY'
                    }
                ]
            }
        },
        
        # Tags for tracking
        'tags': {
            'CreatedBy': 'smart-campaign-agent',
            'CreatedAt': datetime.utcnow().isoformat(),
            'TCPACompliant': 'true'
        }
    }
    
    print(f"Creating campaign: {campaign_name}")
    print(f"Instance: {instance_id}")
    print(f"Region: {region}")
    print()
    
    # Create the campaign
    response = client.create_campaign(**campaign_config)
    
    result = {
        'id': response.get('id'),
        'arn': response.get('arn'),
        'name': campaign_name,
        'tags': response.get('tags', {})
    }
    
    print("✅ Campaign created successfully!")
    print(f"   ID: {result['id']}")
    print(f"   ARN: {result['arn']}")
    print()
    print("Next steps:")
    print(f"  1. Start: aws connectcampaignsv2 start-campaign --id {result['id']}")
    print(f"  2. Add contacts: aws connectcampaignsv2 put-dial-request-batch --id {result['id']} ...")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description='Create a simple outbound campaign',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
    python create_simple_campaign.py \\
        --instance-id abc123-def456-... \\
        --contact-flow-id xyz789-... \\
        --queue-id queue123-... \\
        --phone-number +12125551234 \\
        --name "Spring Sales Campaign"
        """
    )
    
    parser.add_argument('--instance-id', required=True,
                        help='Amazon Connect instance ID')
    parser.add_argument('--contact-flow-id', required=True,
                        help='Contact flow ID for outbound calls')
    parser.add_argument('--queue-id', required=True,
                        help='Queue ID for agent routing')
    parser.add_argument('--phone-number', required=True,
                        help='Outbound caller ID (E.164 format)')
    parser.add_argument('--name', required=True,
                        help='Campaign name')
    parser.add_argument('--region', default='us-east-1',
                        help='AWS region (default: us-east-1)')
    parser.add_argument('--output', choices=['json', 'text'], default='text',
                        help='Output format')
    
    args = parser.parse_args()
    
    try:
        result = create_campaign(
            instance_id=args.instance_id,
            contact_flow_id=args.contact_flow_id,
            queue_id=args.queue_id,
            phone_number=args.phone_number,
            campaign_name=args.name,
            region=args.region
        )
        
        if args.output == 'json':
            print(json.dumps(result, indent=2))
            
    except Exception as e:
        print(f"❌ Error creating campaign: {e}")
        raise


if __name__ == '__main__':
    main()
