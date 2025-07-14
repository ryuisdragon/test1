import json
import logging
import hmac
import hashlib
import os
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError

# Configure logging with unified format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s [request_id=%(request_id)s]",
)
logger = logging.getLogger(__name__)

def get_logger(request_id: str = "-") -> logging.LoggerAdapter:
    return logging.LoggerAdapter(logger, {"request_id": request_id})


class SlackSignatureVerifier:
    """Handles Slack signature verification for security"""
    
    def __init__(self, signing_secret: str):
        self.signing_secret = signing_secret
    
    def verify_signature(self, body: str, headers: Dict[str, str]) -> bool:
        """
        Verify Slack request signature
        
        Args:
            body: Raw request body
            headers: Request headers containing signature
            
        Returns:
            bool: True if signature is valid, False otherwise
        """
        try:
            timestamp = headers.get('x-slack-request-timestamp', '')
            signature = headers.get('x-slack-signature', '')
            
            if not timestamp or not signature:
                logger.error("Missing Slack signature headers")
                return False
            
            # Create signature base string
            sig_basestring = f"v0:{timestamp}:{body}"
            
            # Create expected signature
            expected_signature = 'v0=' + hmac.new(
                self.signing_secret.encode('utf-8'),
                sig_basestring.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(f"Signature verification failed: {str(e)}")
            return False

class MessageTransformer:
    """Transforms Slack messages into structured JSON payload"""
    
    def transform_slack_message(self, slack_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform raw Slack event into structured payload for Bedrock Agent
        
        Args:
            slack_event: Raw Slack event payload
            
        Returns:
            Dict containing structured client data
        """
        try:
            # Extract message data
            event = slack_event.get('event', {})
            user_id = event.get('user', '')
            text = event.get('text', '')
            
            # Extract attachments (files, links, etc.)
            attachments = []
            if 'files' in event:
                for file in event['files']:
                    if 'url_private' in file:
                        attachments.append(file['url_private'])
            
            # Extract thread information
            thread_ts = event.get('thread_ts') or event.get('ts')
            
            # Create structured payload
            structured_payload = {
                "client_id": self._extract_client_id(text),
                "text": text,
                "attachments": attachments,
                "user_id": user_id,
                "thread_ts": thread_ts,
                "channel_id": event.get('channel', ''),
                "timestamp": event.get('ts', ''),
                "message_type": "slack_thread"
            }
            
            logger.info(f"Transformed message for client_id: {structured_payload['client_id']}")
            return structured_payload
            
        except Exception as e:
            logger.error(f"Message transformation failed: {str(e)}")
            raise
    
    def _extract_client_id(self, text: str) -> str:
        """Attempt to extract a client identifier from a Slack message."""

        client_name_nlp = self._extract_client_id_with_nlp(text)
        if client_name_nlp:
            return client_name_nlp

        client_name_regex = self._extract_client_id_with_regex(text)
        if client_name_regex:
            return client_name_regex

        logger.warning("All extraction methods failed, using fallback.")
        return f"client_{hash(text) % 10000}"

    def _extract_client_id_with_regex(self, text: str) -> Optional[str]:
        """Extract a client ID using simple regex patterns."""
        import re

        client_patterns = [
            r'client[:\s]+([A-Za-z0-9\s]+)',
            r'@([A-Za-z0-9]+)',
            r'#([A-Za-z0-9]+)'
        ]

        for pattern in client_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_client_id_with_nlp(self, text: str) -> Optional[str]:
        """Placeholder for NLP-based client name extraction."""
        # In a real implementation this could call an NLP service.
        return None

class BedrockAgentInvoker:
    """Handles Bedrock Agent invocation and response processing"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.bedrock_runtime = boto3.client('bedrock-runtime')
    
    def invoke_agent(self, structured_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invoke Bedrock Agent with structured client data
        
        Args:
            structured_payload: Structured client data
            
        Returns:
            Dict containing agent response and generated content
        """
        try:
            # Prepare input for Bedrock Agent
            agent_input = {
                "input": {
                    "text": structured_payload['text'],
                    "client_id": structured_payload['client_id'],
                    "attachments": structured_payload['attachments'],
                    "user_id": structured_payload['user_id']
                },
                "sessionId": f"session_{structured_payload['client_id']}_{structured_payload['thread_ts']}"
            }
            
            # Invoke Bedrock Agent
            response = self.bedrock_runtime.invoke_agent(
                agentId=self.agent_id,
                input=json.dumps(agent_input),
                contentType='application/json'
            )
            
            # Parse response
            response_body = json.loads(response['completion'])
            
            # Extract generated content
            generated_content = {
                "missing_fields_checklist": self._extract_missing_fields(response_body),
                "competitive_analysis": self._extract_competitive_analysis(response_body),
                "recommended_tags": self._extract_recommended_tags(response_body),
                "citations": self._extract_citations(response_body),
                "follow_up_questions": self._extract_follow_up_questions(response_body)
            }
            
            logger.info(f"Agent processing completed for client_id: {structured_payload['client_id']}")
            return generated_content
            
        except ClientError as e:
            logger.error(f"Bedrock Agent invocation failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Agent response processing failed: {str(e)}")
            raise
    
    def _extract_missing_fields(self, response_body: Dict[str, Any]) -> list:
        """Extract missing fields checklist from agent response"""
        # TODO: Implement extraction logic based on agent response format
        return response_body.get('missing_fields', [])
    
    def _extract_competitive_analysis(self, response_body: Dict[str, Any]) -> Dict[str, Any]:
        """Extract competitive analysis from agent response"""
        # TODO: Implement extraction logic
        return response_body.get('competitive_analysis', {})
    
    def _extract_recommended_tags(self, response_body: Dict[str, Any]) -> list:
        """Extract recommended tags from agent response"""
        # TODO: Implement extraction logic
        return response_body.get('recommended_tags', [])
    
    def _extract_citations(self, response_body: Dict[str, Any]) -> list:
        """Extract citations from agent response"""
        # TODO: Implement extraction logic
        return response_body.get('citations', [])
    
    def _extract_follow_up_questions(self, response_body: Dict[str, Any]) -> list:
        """Extract follow-up questions from agent response"""
        # TODO: Implement extraction logic
        return response_body.get('follow_up_questions', [])

class SlackMessageBuilder:
    """Builds Slack Block Kit messages for user interaction"""
    
    def build_response_message(self, generated_content: Dict[str, Any], original_message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build Slack Block Kit message with generated content and action buttons
        
        Args:
            generated_content: Content generated by Bedrock Agent
            original_message: Original Slack message
            
        Returns:
            Dict containing Slack Block Kit message structure
        """
        try:
            # Build message blocks
            blocks = []
            
            # Header
            blocks.append({
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🤖 AI Analysis Complete"
                }
            })
            
            # Summary section
            summary_text = self._build_summary_text(generated_content)
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": summary_text
                }
            })
            
            # Divider
            blocks.append({"type": "divider"})
            
            # Missing fields section (if any)
            if generated_content.get('missing_fields_checklist'):
                blocks.extend(self._build_missing_fields_section(generated_content['missing_fields_checklist']))
            
            # Recommended tags section
            if generated_content.get('recommended_tags'):
                blocks.extend(self._build_tags_section(generated_content['recommended_tags']))
            
            # Action buttons
            blocks.extend(self._build_action_buttons())
            
            # Citations link
            if generated_content.get('citations'):
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"📚 <{self._build_citations_url(generated_content['citations'])}|View all citations>"
                    }
                })
            
            return {
                "channel": original_message.get('channel_id'),
                "thread_ts": original_message.get('thread_ts'),
                "blocks": blocks
            }
            
        except Exception as e:
            logger.error(f"Message building failed: {str(e)}")
            raise
    
    def _build_summary_text(self, generated_content: Dict[str, Any]) -> str:
        """Build summary text for the message"""
        summary_parts = []
        
        if generated_content.get('competitive_analysis'):
            summary_parts.append("📊 *Competitive Analysis* completed")
        
        if generated_content.get('missing_fields_checklist'):
            summary_parts.append(f"⚠️ *{len(generated_content['missing_fields_checklist'])} missing fields* identified")
        
        if generated_content.get('recommended_tags'):
            summary_parts.append(f"🏷️ *{len(generated_content['recommended_tags'])} tags* recommended")
        
        return " | ".join(summary_parts) if summary_parts else "Analysis completed"
    
    def _build_missing_fields_section(self, missing_fields: list) -> list:
        """Build section for missing fields"""
        blocks = []
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Missing Required Fields:*"
            }
        })
        
        for field in missing_fields[:5]:  # Limit to top 5
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"• {field}"
                }
            })
        
        return blocks
    
    def _build_tags_section(self, recommended_tags: list) -> list:
        """Build section for recommended tags"""
        blocks = []
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Top Recommended Tags:*"
            }
        })
        
        for tag in recommended_tags[:3]:  # Top 3 tags
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"• `{tag}`"
                }
            })
        
        return blocks
    
    def build_historical_section(self, historical_cases: list) -> list:
        if not historical_cases:
            return []
        blocks = [{
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Historical Records for this Client:*"}
        }]
        for case in historical_cases:
            case_id = case[0]['stringValue']
            status = case[1]['stringValue']
            updated_at = case[2]['stringValue']
            brief_summary = case[3]['stringValue']
            thread_ts = case[4]['stringValue']
            channel_id = case[5]['stringValue']
            thread_url = f"https://slack.com/app_redirect?channel={channel_id}&thread_ts={thread_ts}"
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Status:* {status} | *Updated:* {updated_at}\n*Summary:* {brief_summary}\n< {thread_url} | View Thread >"
                }
            })
        blocks.append({"type": "divider"})
        return blocks
    
    def _build_action_buttons(self) -> list:
        """Build action buttons for user interaction"""
        actions = [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✅ Confirm as Correct"},
                "style": "primary",
                "action_id": "confirm_correct"
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✏️ Adjust Conditions"},
                "action_id": "adjust_conditions"
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "📋 Push to Planner"},
                "action_id": "push_to_planner"
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "⏰ Complete Later"},
                "action_id": "remind_later"
            }
        ]
        return [{"type": "actions", "elements": actions}]
    
    def _build_citations_url(self, citations: list) -> str:
        """Build URL for citations (placeholder)"""
        # TODO: Implement citations URL generation
        return "https://example.com/citations"

# --- Add DatabaseManager for RDS queries ---
class DatabaseManager:
    """Handles RDS database operations for case management and historical lookup"""
    def __init__(self, cluster_arn: str, secret_arn: str, database_name: str):
        self.cluster_arn = cluster_arn
        self.secret_arn = secret_arn
        self.database_name = database_name
        self.rds_client = boto3.client('rds-data')

    def execute_query(self, sql: str, parameters: list) -> dict:
        try:
            response = self.rds_client.execute_statement(
                resourceArn=self.cluster_arn,
                secretArn=self.secret_arn,
                database=self.database_name,
                sql=sql,
                parameters=parameters
            )
            return response
        except Exception as e:
            logger.error(f"RDS query failed: {str(e)}")
            return {}

    def fetch_historical_cases(self, client_id: str) -> list:
        sql = """
            SELECT case_id, status, updated_at, brief_summary, thread_ts, channel_id
            FROM cases
            WHERE client_id = :cid
            ORDER BY updated_at DESC
            LIMIT 5;
        """
        parameters = [{'name': 'cid', 'value': {'stringValue': client_id}}]
        response = self.execute_query(sql, parameters)
        return response.get('records', [])

    def fetch_case_state(self, case_id: str) -> tuple:
        sql = """
            SELECT missing_fields, conversation
            FROM cases
            WHERE case_id = :cid
        """
        parameters = [{'name': 'cid', 'value': {'stringValue': case_id}}]
        response = self.execute_query(sql, parameters)
        if response and response.get('records'):
            mf = json.loads(response['records'][0][0]['stringValue']) if response['records'][0][0]['stringValue'] else []
            conv = json.loads(response['records'][0][1]['stringValue']) if response['records'][0][1]['stringValue'] else []
            return mf, conv
        return [], []

    def persist_case_state(self, case_id, missing_fields, new_msg):
        sql = """
            UPDATE cases
            SET missing_fields = :mf,
                conversation = JSON_ARRAY_APPEND(conversation, '$', :new_msg),
                updated_at = NOW()
            WHERE case_id = :cid;
        """
        parameters = [
            {'name': 'mf', 'value': {'stringValue': json.dumps(missing_fields)}},
            {'name': 'new_msg', 'value': {'stringValue': json.dumps(new_msg)}},
            {'name': 'cid', 'value': {'stringValue': case_id}}
        ]
        self.execute_query(sql, parameters)
# --- End DatabaseManager ---

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda Router function - Main entry point
    
    Expected Input:
        event: {
            "body": "Raw Slack event payload",
            "headers": {
                "x-slack-signature": "Slack signature",
                "x-slack-request-timestamp": "Timestamp"
            }
        }
    
    Expected Output:
        {
            "statusCode": 200,
            "body": "Success response"
        }
    """
    request_id = getattr(context, 'aws_request_id', '-')
    log = get_logger(request_id)
    try:
        # Initialize components
        verifier = SlackSignatureVerifier(os.environ['SLACK_SIGNING_SECRET'])
        transformer = MessageTransformer()
        agent_invoker = BedrockAgentInvoker(os.environ['BEDROCK_AGENT_ID'])
        message_builder = SlackMessageBuilder()
        db_manager = DatabaseManager(
            os.environ['RDS_CLUSTER_ARN'],
            os.environ['RDS_SECRET_ARN'],
            os.environ['RDS_DATABASE_NAME']
        )
        # Parse request
        body = event.get('body', '')
        headers = event.get('headers', {})
        # Verify Slack signature
        if not verifier.verify_signature(body, headers):
            log.error("Invalid Slack signature")
            return {'statusCode': 401, 'body': json.dumps({'error': 'Unauthorized'})}
        # Parse Slack event
        slack_event = json.loads(body)
        # Handle Slack URL verification
        if slack_event.get('type') == 'url_verification':
            return {'statusCode': 200, 'body': slack_event.get('challenge', '')}
        # Transform message
        structured_payload = transformer.transform_slack_message(slack_event)
        client_id = structured_payload['client_id']
        thread_ts = structured_payload['thread_ts']
        case_id = thread_ts  # Use thread_ts as persistent case/session ID
        # --- Feature 1: Historical Case Lookup ---
        historical_cases = db_manager.fetch_historical_cases(client_id)
        # --- Feature 2: State Management & Conversation Memory ---
        stored_missing_fields, stored_conversation = db_manager.fetch_case_state(case_id)
        # --- Feature 2.2: Resuming State ---
        if stored_missing_fields or stored_conversation:
            agent_input = {
                "new_message": structured_payload['text'],
                "context": {
                    "outstanding_fields": stored_missing_fields,
                    "history": stored_conversation
                }
            }
            generated_content = agent_invoker.invoke_agent({
                **structured_payload,
                "agent_input": agent_input,
                "sessionId": thread_ts
            })
        else:
            generated_content = agent_invoker.invoke_agent(structured_payload)
        # --- Feature 3: User-Friendly Interactive Flow ---
        # If missing fields, persist state
        if generated_content.get('missing_fields_checklist'):
            db_manager.persist_case_state(
                case_id,
                generated_content['missing_fields_checklist'],
                structured_payload
            )
        # Build Slack response
        blocks = []
        # Prepend historical section if any
        blocks.extend(message_builder.build_historical_section(historical_cases))
        # Add main AI-generated message blocks
        ai_blocks = message_builder.build_response_message(generated_content, structured_payload)["blocks"]
        blocks.extend(ai_blocks)
        slack_message = {
            "channel": structured_payload.get('channel_id'),
            "thread_ts": structured_payload.get('thread_ts'),
            "blocks": blocks
        }
        # TODO: Implement Slack message sending
        log.info(f"Generated response for thread: {structured_payload['thread_ts']}")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Processing completed',
                'thread_ts': structured_payload['thread_ts']
            })
        }
    except Exception as e:
        log.error(f"Lambda Router failed: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'error': 'Internal server error'})}
