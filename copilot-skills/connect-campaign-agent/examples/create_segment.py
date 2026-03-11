#!/usr/bin/env python3
"""
Example: Create a customer segment using natural language

This script demonstrates how to use the Segment AI Assistant concept
to create customer segments from natural language descriptions.

Note: The actual Segment AI Assistant is available in the AWS Console.
This script simulates the process using Amazon Bedrock to generate
Spark SQL from natural language, which can then be used with the
CreateSegmentDefinition API.

Usage:
    python create_segment.py \
        --domain my-domain \
        --prompt "High-value customers who haven't ordered in 60 days"
"""

import argparse
import json
import boto3
from datetime import datetime


def generate_spark_sql_from_natural_language(
    prompt: str,
    region: str = 'us-east-1'
) -> str:
    """
    Use Amazon Bedrock to generate Spark SQL from natural language.
    
    This simulates what the Segment AI Assistant does in the AWS Console.
    
    Args:
        prompt: Natural language description of desired segment
        region: AWS region
    
    Returns:
        Generated Spark SQL query
    """
    
    bedrock = boto3.client('bedrock-runtime', region_name=region)
    
    system_prompt = """You are a Customer Profiles segmentation expert. 
Generate Spark SQL queries for Amazon Connect Customer Profiles.

Available standard fields:
- profile_id (string) - Unique customer identifier
- first_name, last_name (string) - Customer name
- email_address (string) - Email
- phone_number (string) - Phone in E.164 format
- address, city, state, postal_code, country (string) - Address fields
- birth_date (date) - Customer birthday
- account_number (string) - Account identifier

Available calculated attributes (pre-computed):
- lifetime_value (decimal) - Total customer spend
- days_since_last_order (integer) - Days since most recent order
- total_orders (integer) - Number of orders
- average_order_value (decimal) - Average order amount
- support_contact_count (integer) - Number of support contacts
- churn_probability (decimal 0-1) - ML-predicted churn risk
- engagement_score (decimal 0-100) - Customer engagement level
- preferred_channel (string) - Most used contact channel

Always include:
- SELECT * (full profile for campaign)
- WHERE opt_in_status = 'OPTED_IN' (compliance)
- Comment explaining the segment

Return ONLY the SQL query, no explanation."""

    user_prompt = f"""Generate a Spark SQL query for this segment:

"{prompt}"

The query should select customers from CustomerProfiles table."""

    try:
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 1000,
                'system': system_prompt,
                'messages': [
                    {'role': 'user', 'content': user_prompt}
                ]
            })
        )
        
        result = json.loads(response['body'].read())
        sql = result['content'][0]['text'].strip()
        
        # Clean up the SQL if it has markdown code blocks
        if sql.startswith('```'):
            sql = sql.split('```')[1]
            if sql.startswith('sql'):
                sql = sql[3:]
        sql = sql.strip()
        
        return sql
        
    except Exception as e:
        print(f"Warning: Bedrock not available, using template SQL")
        # Fallback template
        return f"""-- Segment: {prompt}
SELECT *
FROM CustomerProfiles
WHERE lifetime_value > 1000
  AND days_since_last_order > 30
  AND opt_in_status = 'OPTED_IN'"""


def create_segment(
    domain_name: str,
    segment_name: str,
    display_name: str,
    description: str,
    spark_sql: str,
    region: str = 'us-east-1',
    dry_run: bool = False
) -> dict:
    """
    Create a segment in Customer Profiles.
    
    Note: This uses the conceptual API structure. Actual API may differ.
    
    Args:
        domain_name: Customer Profiles domain
        segment_name: Unique segment identifier (kebab-case)
        display_name: Human-readable name
        description: Segment description
        spark_sql: Spark SQL query for segment definition
        region: AWS region
        dry_run: If True, only show what would be created
    
    Returns:
        Created segment details
    """
    
    if dry_run:
        print("DRY RUN - Would create segment:")
        print(f"  Domain: {domain_name}")
        print(f"  Name: {segment_name}")
        print(f"  Display Name: {display_name}")
        print(f"  Description: {description}")
        print()
        print("Spark SQL Query:")
        print("-" * 60)
        print(spark_sql)
        print("-" * 60)
        return {'dry_run': True}
    
    profiles = boto3.client('customer-profiles', region_name=region)
    
    # Note: Actual API structure may differ
    # This represents the conceptual segment definition
    try:
        response = profiles.create_segment_definition(
            DomainName=domain_name,
            SegmentDefinitionName=segment_name,
            DisplayName=display_name,
            Description=description,
            # SegmentGroups or SparkSQL configuration here
        )
        
        return {
            'name': segment_name,
            'arn': response.get('SegmentDefinitionArn'),
            'domain': domain_name,
            'created': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        print(f"Note: Segment API may not be available. Error: {e}")
        print()
        print("To create this segment manually:")
        print("1. Go to Amazon Connect Console > Customer Profiles")
        print("2. Select your domain")
        print("3. Go to Segments > Create segment")
        print("4. Use the SQL query generated above")
        
        return {
            'manual_creation_required': True,
            'spark_sql': spark_sql
        }


def estimate_segment_size(
    domain_name: str,
    spark_sql: str,
    region: str = 'us-east-1'
) -> dict:
    """
    Estimate the size of a segment (placeholder - actual implementation
    would require Customer Profiles query API).
    
    Args:
        domain_name: Customer Profiles domain
        spark_sql: Spark SQL query
        region: AWS region
    
    Returns:
        Estimated segment statistics
    """
    
    # This is a placeholder - actual implementation would query Customer Profiles
    return {
        'estimated_size': 'Unknown (requires Customer Profiles query API)',
        'note': 'Use AWS Console to preview segment size before creation'
    }


def main():
    parser = argparse.ArgumentParser(
        description='Create a customer segment using natural language',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate SQL from natural language
    python create_segment.py \\
        --domain my-domain \\
        --prompt "High-value customers who haven't ordered in 60 days"
    
    # Create with custom name
    python create_segment.py \\
        --domain my-domain \\
        --prompt "Customers likely to churn based on support frequency" \\
        --name churn-risk-high \\
        --display-name "High Churn Risk Customers"
    
    # Dry run (preview without creating)
    python create_segment.py \\
        --domain my-domain \\
        --prompt "VIP customers in California" \\
        --dry-run
        """
    )
    
    parser.add_argument('--domain', required=True,
                        help='Customer Profiles domain name')
    parser.add_argument('--prompt', required=True,
                        help='Natural language description of desired segment')
    parser.add_argument('--name', 
                        help='Segment identifier (auto-generated if not provided)')
    parser.add_argument('--display-name',
                        help='Display name (uses prompt if not provided)')
    parser.add_argument('--region', default='us-east-1',
                        help='AWS region (default: us-east-1)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview without creating')
    parser.add_argument('--output', choices=['json', 'text'], default='text',
                        help='Output format')
    
    args = parser.parse_args()
    
    # Auto-generate segment name if not provided
    segment_name = args.name or args.prompt.lower().replace(' ', '-')[:64]
    segment_name = ''.join(c for c in segment_name if c.isalnum() or c == '-')
    
    display_name = args.display_name or args.prompt[:128]
    
    print(f"🎯 Generating segment from natural language...")
    print(f"   Prompt: \"{args.prompt}\"")
    print()
    
    # Generate Spark SQL from natural language
    spark_sql = generate_spark_sql_from_natural_language(
        prompt=args.prompt,
        region=args.region
    )
    
    print("📊 Generated Spark SQL:")
    print("=" * 60)
    print(spark_sql)
    print("=" * 60)
    print()
    
    # Estimate segment size
    estimate = estimate_segment_size(
        domain_name=args.domain,
        spark_sql=spark_sql,
        region=args.region
    )
    print(f"📈 Estimated size: {estimate['estimated_size']}")
    print()
    
    # Create segment
    result = create_segment(
        domain_name=args.domain,
        segment_name=segment_name,
        display_name=display_name,
        description=f"AI-generated segment: {args.prompt}",
        spark_sql=spark_sql,
        region=args.region,
        dry_run=args.dry_run
    )
    
    if args.output == 'json':
        result['spark_sql'] = spark_sql
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
