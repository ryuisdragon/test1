# AI-Powered Sales Agent Lambda Functions

This repository contains the Lambda functions for the AI-powered sales agent system that processes client information from Slack, performs automated analysis, and generates actionable reports.

## Overview

The system consists of two main Lambda functions:

1. **Lambda Router** (`lambda_router.py`) - Processes incoming Slack events and coordinates with Bedrock Agent
2. **Lambda Actions** (`lambda_actions.py`) - Handles user interactions and generates briefs

## Architecture

```
Slack → API Gateway → Lambda Router → Bedrock Agent → Lambda Actions → Slack/Database
```

## Lambda Router Function

### Purpose
- Receives Slack events via API Gateway
- Verifies Slack request signatures for security
- Transforms raw Slack messages into structured JSON
- Invokes Bedrock Agent for AI processing
- Generates Slack Block Kit responses with action buttons

### Key Components

#### SlackSignatureVerifier
- Verifies Slack request signatures using HMAC-SHA256
- Ensures request authenticity and prevents replay attacks

#### MessageTransformer
- Extracts client information from Slack messages
- Transforms unstructured text into structured JSON payload
- Identifies client IDs, attachments, and user context

#### BedrockAgentInvoker
- Manages communication with AWS Bedrock Agent
- Handles agent input/output formatting
- Extracts generated content (missing fields, competitive analysis, tags)

#### SlackMessageBuilder
- Creates rich Slack Block Kit messages
- Includes action buttons for user interaction
- Formats generated content for display

### Environment Variables Required
```bash
SLACK_SIGNING_SECRET=your_slack_signing_secret
BEDROCK_AGENT_ID=your_bedrock_agent_id
```

### Expected Input
```json
{
  "body": "Raw Slack event payload",
  "headers": {
    "x-slack-signature": "v0=...",
    "x-slack-request-timestamp": "1234567890"
  }
}
```

### Expected Output
```json
{
  "statusCode": 200,
  "body": {
    "message": "Processing completed",
    "thread_ts": "1234567890.123456"
  }
}
```

## Lambda Actions Function

### Purpose
- Handles Slack action button interactions
- Manages database operations for case status updates
- Generates briefs for planning and management teams
- Creates PDF reports with pre-signed S3 URLs

### Key Components

#### DatabaseManager
- Manages RDS database operations using Data API
- Handles case status updates and data retrieval
- Supports case data persistence and updates

#### SlackInteractionHandler
- Manages Slack modal interactions
- Handles confirmation messages and user feedback
- Builds interactive modal forms for data adjustment

#### BriefGenerator
- Generates different brief types for various audiences
- Creates planner briefs with actionable fields
- Produces manager briefs with KPIs and risk analysis

#### PDFGenerator
- Converts brief content to PDF using Jinja2 templates
- Uploads PDFs to S3 with pre-signed URLs
- Handles WeasyPrint integration for PDF generation

### Environment Variables Required
```bash
RDS_CLUSTER_ARN=arn:aws:rds:region:account:cluster:cluster-name
RDS_SECRET_ARN=arn:aws:secretsmanager:region:account:secret:secret-name
RDS_DATABASE_NAME=your_database_name
SLACK_BOT_TOKEN=xoxb-your-bot-token
S3_BUCKET_NAME=your-briefs-bucket
```

### Expected Input
```json
{
  "body": {
    "payload": {
      "type": "block_actions",
      "actions": [{"action_id": "confirm_correct"}],
      "user": {"id": "U123456"},
      "channel": {"id": "C123456"},
      "message": {"ts": "1234567890.123456"}
    }
  }
}
```

### Expected Output
```json
{
  "statusCode": 200,
  "body": "Action processed"
}
```

## Database Schema

### Cases Table
```sql
CREATE TABLE cases (
    case_id VARCHAR(255) PRIMARY KEY,
    client_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by VARCHAR(255),
    client_data JSON,
    tags JSON,
    missing_fields JSON
);
```

## Deployment

### Prerequisites
1. AWS CLI configured with appropriate permissions
2. Python 3.9+ runtime
3. Required AWS services configured (RDS, S3, Bedrock)

### Package Dependencies
```bash
pip install -r lambda_requirements.txt
```

### Deployment Steps

1. **Create deployment package**:
```bash
pip install -r lambda_requirements.txt -t package/
cp lambda_router.py package/
cp lambda_actions.py package/
cd package && zip -r ../lambda_router.zip .
cd .. && zip -r lambda_actions.zip lambda_actions.py
```

2. **Deploy Lambda Router**:
```bash
aws lambda create-function \
  --function-name sales-agent-router \
  --runtime python3.9 \
  --role arn:aws:iam::account:role/lambda-execution-role \
  --handler lambda_router.lambda_handler \
  --zip-file fileb://lambda_router.zip \
  --environment Variables='{SLACK_SIGNING_SECRET=your_secret,BEDROCK_AGENT_ID=your_agent_id}'
```

3. **Deploy Lambda Actions**:
```bash
aws lambda create-function \
  --function-name sales-agent-actions \
  --runtime python3.9 \
  --role arn:aws:iam::account:role/lambda-execution-role \
  --handler lambda_actions.lambda_handler \
  --zip-file fileb://lambda_actions.zip \
  --environment Variables='{RDS_CLUSTER_ARN=your_cluster_arn,RDS_SECRET_ARN=your_secret_arn,RDS_DATABASE_NAME=your_db,SLACK_BOT_TOKEN=your_token,S3_BUCKET_NAME=your_bucket}'
```

## Security Considerations

1. **Slack Signature Verification**: All incoming requests are verified using Slack's signing secret
2. **IAM Roles**: Lambda functions use least-privilege IAM roles
3. **Environment Variables**: Sensitive data stored in environment variables
4. **Database Security**: RDS uses Data API with IAM authentication
5. **S3 Security**: PDFs stored with pre-signed URLs and expiration

## Monitoring and Logging

- All functions log to CloudWatch with structured logging
- Critical errors stored in DynamoDB for fast querying
- Performance metrics available in CloudWatch
- Custom dashboards for monitoring system health

## Error Handling

- Comprehensive try-catch blocks throughout
- Graceful degradation for external service failures
- Detailed error logging for debugging
- Retry logic for transient failures

## Testing

### Unit Tests
```bash
python -m pytest tests/ -v
```

### Integration Tests
```bash
python -m pytest tests/integration/ -v
```

### Load Testing
```bash
python tests/load_test.py
```

### Continuous Integration
The repository includes a GitHub Actions workflow (`python-tests.yml`) that
installs dependencies and runs `pytest` on every push and pull request. This
ensures all unit tests pass before deployment.

## Contributing

1. Follow PEP 8 style guidelines
2. Add comprehensive docstrings
3. Include unit tests for new functionality
4. Update documentation for API changes

## License

This project is licensed under the MIT License - see the LICENSE file for details. 