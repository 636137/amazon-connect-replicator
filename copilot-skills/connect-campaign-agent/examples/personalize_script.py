#!/usr/bin/env python3
"""
Example: Personalize outbound campaign content with Amazon Bedrock

This script demonstrates how to use Amazon Bedrock to generate
personalized content for outbound campaigns:
- Agent call scripts
- Customer preview summaries
- Voicemail messages
- SMS templates

Usage:
    python personalize_script.py \
        --type collections \
        --tone empathetic \
        --customer-data '{"name": "John", "balance": 1500}'
"""

import argparse
import json
import boto3
from typing import Dict, Optional


def generate_call_script(
    campaign_type: str,
    customer_data: Dict,
    tone: str = 'professional',
    compliance_elements: Optional[list] = None,
    region: str = 'us-east-1'
) -> str:
    """
    Generate a personalized call script using Amazon Bedrock.
    
    Args:
        campaign_type: Type of campaign (collections, sales, retention, support)
        customer_data: Customer profile data for personalization
        tone: Script tone (professional, empathetic, urgent)
        compliance_elements: Required disclosures (e.g., mini-miranda)
        region: AWS region
    
    Returns:
        Generated call script
    """
    
    bedrock = boto3.client('bedrock-runtime', region_name=region)
    
    compliance_text = ""
    if compliance_elements:
        compliance_text = f"\n\nIMPORTANT: Include these compliance elements:\n"
        for element in compliance_elements:
            compliance_text += f"- {element}\n"
    
    prompt = f"""You are an expert at writing call scripts for contact centers.
Generate a professional {campaign_type} call script with the following requirements:

Customer Information:
{json.dumps(customer_data, indent=2)}

Tone: {tone}
{compliance_text}

Create a complete script including:
1. **Opening** - Professional greeting and identification
2. **Purpose** - Clear reason for the call
3. **Main Body** - Key talking points and value propositions
4. **Objection Handling** - 3 common objections with responses
5. **Closing** - Call to action and professional wrap-up

Format the script with clear sections and sample agent language.
Use {{variable}} syntax for personalization placeholders."""

    try:
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 3000,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ]
            })
        )
        
        result = json.loads(response['body'].read())
        return result['content'][0]['text']
        
    except Exception as e:
        return f"Error generating script: {e}"


def generate_preview_summary(
    customer_data: Dict,
    region: str = 'us-east-1'
) -> str:
    """
    Generate a customer summary for preview dialer screen.
    
    Args:
        customer_data: Customer profile data
        region: AWS region
    
    Returns:
        Formatted preview summary
    """
    
    bedrock = boto3.client('bedrock-runtime', region_name=region)
    
    prompt = f"""Create a concise customer preview summary for an agent screen.
The agent will see this for about 30 seconds before the call connects.

Customer Data:
{json.dumps(customer_data, indent=2)}

Generate a summary that includes:
1. Key customer facts at a glance
2. Account status highlights
3. Recommended approach
4. Any warnings or special notes

Format it for quick scanning with clear visual hierarchy.
Keep it brief but informative. Use ASCII box characters for structure."""

    try:
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-haiku-20240307-v1:0',  # Fast model for summaries
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
        
    except Exception as e:
        return f"Error generating summary: {e}"


def generate_voicemail_script(
    campaign_type: str,
    company_name: str,
    callback_number: str,
    region: str = 'us-east-1'
) -> str:
    """
    Generate a compliant voicemail script.
    
    Note: Voicemails should be brief and not include sensitive details.
    Any required disclosures are given on callback, not in the message.
    
    Args:
        campaign_type: Type of campaign
        company_name: Company name for identification
        callback_number: Number for customer to call back
        region: AWS region
    
    Returns:
        Voicemail script
    """
    
    bedrock = boto3.client('bedrock-runtime', region_name=region)
    
    prompt = f"""Generate a brief, professional voicemail message.

Campaign Type: {campaign_type}
Company: {company_name}
Callback Number: {callback_number}

Requirements:
- Keep under 20 seconds when spoken
- Be professional but not alarming
- Include company name and callback number
- Do NOT include specific account details or sensitive information
- Mention hours of operation if relevant

The message should encourage a callback without being pushy."""

    try:
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-haiku-20240307-v1:0',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 200,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ]
            })
        )
        
        result = json.loads(response['body'].read())
        return result['content'][0]['text']
        
    except Exception as e:
        return f"Error generating voicemail: {e}"


def generate_sms_template(
    campaign_type: str,
    company_name: str,
    callback_number: str,
    max_chars: int = 160,
    region: str = 'us-east-1'
) -> str:
    """
    Generate an SMS template for fallback communications.
    
    Args:
        campaign_type: Type of campaign
        company_name: Company name
        callback_number: Callback number
        max_chars: Maximum character limit
        region: AWS region
    
    Returns:
        SMS template with placeholders
    """
    
    bedrock = boto3.client('bedrock-runtime', region_name=region)
    
    prompt = f"""Generate a brief SMS message template.

Campaign Type: {campaign_type}
Company: {company_name}
Callback Number: {callback_number}
Max Characters: {max_chars}

Requirements:
- Must be under {max_chars} characters total
- Use {{customer_name}} for personalization
- Include callback number or short link
- Be professional and action-oriented
- Include STOP option for opt-out compliance

Count the characters and ensure compliance."""

    try:
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-haiku-20240307-v1:0',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 200,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ]
            })
        )
        
        result = json.loads(response['body'].read())
        return result['content'][0]['text']
        
    except Exception as e:
        return f"Error generating SMS: {e}"


def main():
    parser = argparse.ArgumentParser(
        description='Generate personalized campaign content with Amazon Bedrock',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate collections script
    python personalize_script.py \\
        --type collections \\
        --tone empathetic \\
        --compliance mini-miranda

    # Generate with customer data
    python personalize_script.py \\
        --type sales \\
        --tone professional \\
        --customer-data '{"name": "John Smith", "lifetime_value": 5000}'

    # Generate preview summary only
    python personalize_script.py \\
        --type collections \\
        --content preview \\
        --customer-data '{"name": "Jane", "balance": 2500, "days_overdue": 45}'

    # Generate all content types
    python personalize_script.py \\
        --type collections \\
        --content all \\
        --company "Acme Corp" \\
        --callback-number "1-800-555-0123"
        """
    )
    
    parser.add_argument('--type', required=True,
                        choices=['collections', 'sales', 'retention', 'support', 'appointment'],
                        help='Campaign type')
    parser.add_argument('--tone', default='professional',
                        choices=['professional', 'empathetic', 'urgent', 'friendly'],
                        help='Script tone')
    parser.add_argument('--content', default='script',
                        choices=['script', 'preview', 'voicemail', 'sms', 'all'],
                        help='Content type to generate')
    parser.add_argument('--customer-data', default='{}',
                        help='Customer data JSON string')
    parser.add_argument('--compliance', action='append',
                        help='Compliance elements to include (can be repeated)')
    parser.add_argument('--company', default='[Company Name]',
                        help='Company name for branding')
    parser.add_argument('--callback-number', default='1-800-XXX-XXXX',
                        help='Callback phone number')
    parser.add_argument('--region', default='us-east-1',
                        help='AWS region')
    parser.add_argument('--output', choices=['text', 'json'], default='text',
                        help='Output format')
    
    args = parser.parse_args()
    
    # Parse customer data
    try:
        customer_data = json.loads(args.customer_data)
    except json.JSONDecodeError:
        print("Error: Invalid JSON in --customer-data")
        return
    
    # Default customer data for demo
    if not customer_data:
        customer_data = {
            'name': '{{customer_name}}',
            'account_last4': '{{account_last4}}',
            'balance': '{{balance}}',
            'days_overdue': '{{days_overdue}}',
            'tenure_years': '{{tenure_years}}',
            'lifetime_value': '{{lifetime_value}}'
        }
    
    results = {}
    
    print(f"🤖 Generating {args.type} campaign content...")
    print(f"   Tone: {args.tone}")
    print(f"   Region: {args.region}")
    print("=" * 60)
    
    # Generate requested content types
    if args.content in ['script', 'all']:
        print("\n📝 CALL SCRIPT")
        print("-" * 60)
        script = generate_call_script(
            campaign_type=args.type,
            customer_data=customer_data,
            tone=args.tone,
            compliance_elements=args.compliance,
            region=args.region
        )
        print(script)
        results['call_script'] = script
    
    if args.content in ['preview', 'all']:
        print("\n👁️ PREVIEW SUMMARY")
        print("-" * 60)
        preview = generate_preview_summary(
            customer_data=customer_data,
            region=args.region
        )
        print(preview)
        results['preview_summary'] = preview
    
    if args.content in ['voicemail', 'all']:
        print("\n📞 VOICEMAIL SCRIPT")
        print("-" * 60)
        voicemail = generate_voicemail_script(
            campaign_type=args.type,
            company_name=args.company,
            callback_number=args.callback_number,
            region=args.region
        )
        print(voicemail)
        results['voicemail_script'] = voicemail
    
    if args.content in ['sms', 'all']:
        print("\n💬 SMS TEMPLATE")
        print("-" * 60)
        sms = generate_sms_template(
            campaign_type=args.type,
            company_name=args.company,
            callback_number=args.callback_number,
            region=args.region
        )
        print(sms)
        results['sms_template'] = sms
    
    print("\n" + "=" * 60)
    
    if args.output == 'json':
        print("\nJSON Output:")
        print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
