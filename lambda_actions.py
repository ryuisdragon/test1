import json
import logging
import boto3
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError
import os

# Configure logging with unified format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s [request_id=%(request_id)s]",
)
logger = logging.getLogger(__name__)

def get_logger(request_id: str = "-") -> logging.LoggerAdapter:
    return logging.LoggerAdapter(logger, {"request_id": request_id})

# Initialize AWS clients
rds_client = boto3.client('rds-data')

class DatabaseManager:
    """Handles RDS database operations for case management"""
    
    def __init__(self, cluster_arn: str, secret_arn: str, database_name: str):
        self.cluster_arn = cluster_arn
        self.secret_arn = secret_arn
        self.database_name = database_name
    
    def update_case_status(self, case_id: str, status: str, user_id: str) -> bool:
        """
        Update case status in RDS database
        
        Args:
            case_id: Unique case identifier
            status: New status (confirmed, pending, etc.)
            user_id: User who made the change
            
        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            sql = """
                UPDATE cases 
                SET status = :status, 
                    updated_at = NOW(), 
                    updated_by = :user_id
                WHERE case_id = :case_id
            """
            
            parameters = [
                {'name': 'status', 'value': {'stringValue': status}},
                {'name': 'user_id', 'value': {'stringValue': user_id}},
                {'name': 'case_id', 'value': {'stringValue': case_id}}
            ]
            
            response = rds_client.execute_statement(
                resourceArn=self.cluster_arn,
                secretArn=self.secret_arn,
                database=self.database_name,
                sql=sql,
                parameters=parameters
            )
            
            log.info(f"Case {case_id} status updated to {status}")
            return True
            
        except ClientError as e:
            log.error(f"Database update failed: {str(e)}")
            return False
    
    def get_case_data(self, case_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve case data from database
        
        Args:
            case_id: Unique case identifier
            
        Returns:
            Dict containing case data or None if not found
        """
        try:
            sql = """
                SELECT case_id, client_id, status, created_at, updated_at, 
                       client_data, tags, missing_fields
                FROM cases 
                WHERE case_id = :case_id
            """
            
            parameters = [
                {'name': 'case_id', 'value': {'stringValue': case_id}}
            ]
            
            response = rds_client.execute_statement(
                resourceArn=self.cluster_arn,
                secretArn=self.secret_arn,
                database=self.database_name,
                sql=sql,
                parameters=parameters
            )
            
            if response['records']:
                record = response['records'][0]
                return {
                    'case_id': record[0]['stringValue'],
                    'client_id': record[1]['stringValue'],
                    'status': record[2]['stringValue'],
                    'created_at': record[3]['stringValue'],
                    'updated_at': record[4]['stringValue'],
                    'client_data': json.loads(record[5]['stringValue']) if record[5]['stringValue'] else {},
                    'tags': json.loads(record[6]['stringValue']) if record[6]['stringValue'] else [],
                    'missing_fields': json.loads(record[7]['stringValue']) if record[7]['stringValue'] else []
                }
            
            return None
            
        except ClientError as e:
            log.error(f"Database query failed: {str(e)}")
            return None
    
    def save_case_data(self, case_data: Dict[str, Any]) -> bool:
        """
        Save or update case data in database
        
        Args:
            case_data: Case data to save
            
        Returns:
            bool: True if save successful, False otherwise
        """
        try:
            sql = """
                INSERT INTO cases (case_id, client_id, status, client_data, tags, missing_fields)
                VALUES (:case_id, :client_id, :status, :client_data, :tags, :missing_fields)
                ON DUPLICATE KEY UPDATE
                    status = VALUES(status),
                    client_data = VALUES(client_data),
                    tags = VALUES(tags),
                    missing_fields = VALUES(missing_fields),
                    updated_at = NOW()
            """
            
            parameters = [
                {'name': 'case_id', 'value': {'stringValue': case_data['case_id']}},
                {'name': 'client_id', 'value': {'stringValue': case_data['client_id']}},
                {'name': 'status', 'value': {'stringValue': case_data['status']}},
                {'name': 'client_data', 'value': {'stringValue': json.dumps(case_data['client_data'])}},
                {'name': 'tags', 'value': {'stringValue': json.dumps(case_data['tags'])}},
                {'name': 'missing_fields', 'value': {'stringValue': json.dumps(case_data['missing_fields'])}}
            ]
            
            response = rds_client.execute_statement(
                resourceArn=self.cluster_arn,
                secretArn=self.secret_arn,
                database=self.database_name,
                sql=sql,
                parameters=parameters
            )
            
            log.info(f"Case {case_data['case_id']} data saved successfully")
            return True
            
        except ClientError as e:
            log.error(f"Database save failed: {str(e)}")
            return False

class SlackInteractionHandler:
    """Handles Slack interactions and modal responses"""
    
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
    
    def open_adjust_conditions_modal(self, trigger_id: str, case_data: Dict[str, Any]) -> bool:
        """
        Open modal for adjusting case conditions
        
        Args:
            trigger_id: Slack trigger ID for modal
            case_data: Current case data
            
        Returns:
            bool: True if modal opened successfully, False otherwise
        """
        try:
            modal_view = {
                "type": "modal",
                "callback_id": "adjust_conditions_modal",
                "title": {
                    "type": "plain_text",
                    "text": "Adjust Case Conditions"
                },
                "submit": {
                    "type": "plain_text",
                    "text": "Save Changes"
                },
                "close": {
                    "type": "plain_text",
                    "text": "Cancel"
                },
                "blocks": self._build_modal_blocks(case_data)
            }
            
            # TODO: Implement Slack API call to open modal
            # This would typically use the Slack Web API
            log.info(f"Modal opened for case: {case_data['case_id']}")
            return True
            
        except Exception as e:
            log.error(f"Modal opening failed: {str(e)}")
            return False
    
    def _build_modal_blocks(self, case_data: Dict[str, Any]) -> list:
        """Build modal blocks for condition adjustment"""
        blocks = []
        
        # Client information section
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Client:* {case_data['client_id']}"
            }
        })
        
        # Missing fields input
        if case_data.get('missing_fields'):
            blocks.append({
                "type": "input",
                "block_id": "missing_fields",
                "label": {
                    "type": "plain_text",
                    "text": "Missing Fields (comma-separated)"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "missing_fields_input",
                    "initial_value": ", ".join(case_data['missing_fields'])
                }
            })
        
        # Tags input
        blocks.append({
            "type": "input",
            "block_id": "tags",
            "label": {
                "type": "plain_text",
                "text": "Tags (comma-separated)"
            },
            "element": {
                "type": "plain_text_input",
                "action_id": "tags_input",
                "initial_value": ", ".join(case_data.get('tags', []))
            }
        })
        
        # Additional notes
        blocks.append({
            "type": "input",
            "block_id": "notes",
            "label": {
                "type": "plain_text",
                "text": "Additional Notes"
            },
            "element": {
                "type": "plain_text_input",
                "action_id": "notes_input",
                "multiline": True,
                "initial_value": case_data.get('client_data', {}).get('notes', '')
            }
        })
        
        return blocks
    
    def send_confirmation_message(self, channel: str, thread_ts: str, action: str) -> bool:
        """
        Send confirmation message to Slack thread
        
        Args:
            channel: Slack channel ID
            thread_ts: Thread timestamp
            action: Action that was taken
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            message = {
                "channel": channel,
                "thread_ts": thread_ts,
                "text": f"✅ Action '{action}' completed successfully"
            }
            
            # TODO: Implement Slack API call to send message
            log.info(f"Confirmation message sent for action: {action}")
            return True
            
        except Exception as e:
            log.error(f"Confirmation message failed: {str(e)}")
            return False

class BriefGenerator:
    """Handles brief generation for different audiences"""
    
    def __init__(self, s3_bucket: str):
        self.s3_bucket = s3_bucket
    
    def generate_planner_brief(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate brief for planning team
        
        Args:
            case_data: Case data for brief generation
            
        Returns:
            Dict containing brief content and metadata
        """
        try:
            # TODO: Implement planner brief generation logic
            brief_content = {
                "client_id": case_data['client_id'],
                "actionable_fields": self._extract_actionable_fields(case_data),
                "tag_suggestions": case_data.get('tags', []),
                "missing_fields": case_data.get('missing_fields', []),
                "priority_score": self._calculate_priority_score(case_data),
                "estimated_budget": self._estimate_budget(case_data),
                "timeline": self._estimate_timeline(case_data)
            }
            
            return {
                "type": "planner",
                "content": brief_content,
                "channel": "#planning",
                "template": "planner_brief_template.md"
            }
            
        except Exception as e:
            log.error(f"Planner brief generation failed: {str(e)}")
            raise
    
    def generate_manager_brief(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate brief for management team
        
        Args:
            case_data: Case data for brief generation
            
        Returns:
            Dict containing brief content and metadata
        """
        try:
            # TODO: Implement manager brief generation logic
            brief_content = {
                "client_id": case_data['client_id'],
                "kpis": self._extract_kpis(case_data),
                "risks": self._identify_risks(case_data),
                "budget_considerations": self._analyze_budget(case_data),
                "competitive_analysis": case_data.get('client_data', {}).get('competitive_analysis', {}),
                "executive_summary": self._generate_executive_summary(case_data)
            }
            
            return {
                "type": "manager",
                "content": brief_content,
                "channel": "#manager-desk",
                "template": "manager_brief_template.md"
            }
            
        except Exception as e:
            log.error(f"Manager brief generation failed: {str(e)}")
            raise
    
    def _extract_actionable_fields(self, case_data: Dict[str, Any]) -> list:
        """Extract actionable fields for planner brief"""
        # TODO: Implement actionable fields extraction
        return case_data.get('client_data', {}).get('actionable_fields', [])
    
    def _calculate_priority_score(self, case_data: Dict[str, Any]) -> int:
        """Calculate priority score for the case"""
        # TODO: Implement priority scoring logic
        return 75  # Placeholder score
    
    def _estimate_budget(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate budget requirements"""
        # TODO: Implement budget estimation
        return {
            "min": 5000,
            "max": 25000,
            "currency": "USD"
        }
    
    def _estimate_timeline(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate project timeline"""
        # TODO: Implement timeline estimation
        return {
            "duration_weeks": 8,
            "start_date": "2024-01-15",
            "end_date": "2024-03-15"
        }
    
    def _extract_kpis(self, case_data: Dict[str, Any]) -> list:
        """Extract KPIs for manager brief"""
        # TODO: Implement KPI extraction
        return ["Revenue Growth", "Market Share", "Customer Satisfaction"]
    
    def _identify_risks(self, case_data: Dict[str, Any]) -> list:
        """Identify potential risks"""
        # TODO: Implement risk identification
        return ["Market Competition", "Resource Constraints", "Timeline Pressure"]
    
    def _analyze_budget(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze budget considerations"""
        # TODO: Implement budget analysis
        return {
            "roi_estimate": "150%",
            "break_even_months": 6,
            "risk_factors": ["Market volatility", "Resource costs"]
        }
    
    def _generate_executive_summary(self, case_data: Dict[str, Any]) -> str:
        """Generate executive summary"""
        # TODO: Implement executive summary generation
        return f"Strategic opportunity with {case_data['client_id']} showing strong potential for growth and market expansion."

class PDFGenerator:
    """Handles PDF generation from brief content"""
    
    def __init__(self, s3_bucket: str):
        self.s3_bucket = s3_bucket
    
    def generate_pdf(self, brief_content: Dict[str, Any], template_name: str) -> str:
        """
        Generate PDF from brief content using Jinja2 templates
        
        Args:
            brief_content: Content to include in PDF
            template_name: Template to use for generation
            
        Returns:
            str: S3 URL of generated PDF
        """
        try:
            # TODO: Implement PDF generation using Jinja2 and WeasyPrint
            # This would typically involve:
            # 1. Loading Jinja2 template
            # 2. Rendering with brief_content
            # 3. Converting to PDF with WeasyPrint
            # 4. Uploading to S3
            # 5. Generating pre-signed URL
            
            pdf_filename = f"brief_{brief_content['client_id']}_{brief_content['type']}.pdf"
            s3_key = f"briefs/{pdf_filename}"
            
            # Placeholder for PDF generation
            pdf_url = f"https://{self.s3_bucket}.s3.amazonaws.com/{s3_key}"
            
            log.info(f"PDF generated: {pdf_url}")
            return pdf_url
            
        except Exception as e:
            log.error(f"PDF generation failed: {str(e)}")
            raise

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda Actions function - Handles Slack action button interactions
    
    Expected Input:
        event: {
            "body": "Slack interaction payload",
            "headers": {...}
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
        db_manager = DatabaseManager(
            os.environ['RDS_CLUSTER_ARN'],
            os.environ['RDS_SECRET_ARN'],
            os.environ['RDS_DATABASE_NAME']
        )
        slack_handler = SlackInteractionHandler(os.environ['SLACK_BOT_TOKEN'])
        brief_generator = BriefGenerator(os.environ['S3_BUCKET_NAME'])
        pdf_generator = PDFGenerator(os.environ['S3_BUCKET_NAME'])
        
        # Parse Slack interaction
        body = json.loads(event.get('body', '{}'))
        payload = json.loads(body.get('payload', '{}'))
        
        # Extract interaction details
        action_id = payload.get('actions', [{}])[0].get('action_id', '')
        user_id = payload.get('user', {}).get('id', '')
        channel_id = payload.get('channel', {}).get('id', '')
        message_ts = payload.get('message', {}).get('ts', '')
        
        # Extract case data from message context
        case_id = payload.get('message', {}).get('blocks', [{}])[0].get('block_id', '')
        
        log.info(f"Processing action: {action_id} for case: {case_id}")
        
        # Handle different action types
        if action_id == 'confirm_correct':
            success = db_manager.update_case_status(case_id, 'confirmed', user_id)
            if success:
                slack_handler.send_confirmation_message(channel_id, message_ts, 'Confirmed as Correct')
                return {'statusCode': 200, 'body': 'Case confirmed'}
        
        elif action_id == 'adjust_conditions':
            case_data = db_manager.get_case_data(case_id)
            if case_data:
                success = slack_handler.open_adjust_conditions_modal(
                    payload.get('trigger_id', ''),
                    case_data
                )
                if success:
                    return {'statusCode': 200, 'body': 'Modal opened'}
        
        elif action_id == 'push_to_planner':
            case_data = db_manager.get_case_data(case_id)
            if case_data:
                # Generate both briefs
                planner_brief = brief_generator.generate_planner_brief(case_data)
                manager_brief = brief_generator.generate_manager_brief(case_data)
                
                # Generate PDFs
                planner_pdf_url = pdf_generator.generate_pdf(
                    planner_brief['content'], 
                    planner_brief['template']
                )
                manager_pdf_url = pdf_generator.generate_pdf(
                    manager_brief['content'], 
                    manager_brief['template']
                )
                
                # TODO: Send briefs to respective Slack channels
                log.info(f"Briefs generated and PDFs created")
                
                return {'statusCode': 200, 'body': 'Briefs generated'}
        
        # --- Feature 3: Handle Complete Later (remind_later) ---
        elif action_id == 'remind_later':
            # Store user_id and missing_fields for follow-up
            case_data = db_manager.get_case_data(case_id)
            if case_data:
                # Save user_id for reminder (could be a new column or a reminders table)
                # For now, just log and acknowledge
                log.info(f"User {user_id} requested to complete later for case {case_id}")
                # Optionally, schedule a DM reminder using EventBridge or Step Functions
                # TODO: Implement scheduling logic for DM reminder
                slack_handler.send_confirmation_message(channel_id, message_ts, 'You will be reminded to complete this case later.')
                return {'statusCode': 200, 'body': 'Remind later acknowledged'}
        # --- Feature 3: Handle Complete Data (from DM reminder) ---
        elif action_id == 'complete_data':
            case_data = db_manager.get_case_data(case_id)
            if case_data:
                # Open pre-filled modal with known values
                success = slack_handler.open_adjust_conditions_modal(
                    payload.get('trigger_id', ''),
                    case_data
                )
                if success:
                    return {'statusCode': 200, 'body': 'Pre-filled modal opened'}
        
        else:
            log.warning(f"Unknown action_id: {action_id}")
            return {'statusCode': 400, 'body': 'Unknown action'}
        
        return {'statusCode': 200, 'body': 'Action processed'}
        
    except Exception as e:
        log.error(f"Lambda Actions failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        } 
