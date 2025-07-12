import json
import importlib
import boto3

class DummyContext:
    aws_request_id = 'req-123'

class DummyBedrock:
    def invoke_agent(self, **kwargs):
        return {"completion": json.dumps({
            "missing_fields": ["field1"],
            "recommended_tags": ["tag1"]
        })}

class DummyRDS:
    def __init__(self, response):
        self.response = response
        self.received = None
    def execute_statement(self, **kwargs):
        self.received = kwargs
        return self.response

def test_message_transformer(monkeypatch):
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')
    import lambda_router
    importlib.reload(lambda_router)
    transformer = lambda_router.MessageTransformer()
    slack_event = {
        "event": {
            "user": "U1",
            "text": "client: ABC Corp",
            "files": [{"url_private": "http://file"}],
            "ts": "123.456",
            "channel": "C1"
        }
    }
    result = transformer.transform_slack_message(slack_event)
    assert result["client_id"] == "ABC Corp"
    assert result["attachments"] == ["http://file"]
    assert result["thread_ts"] == "123.456"

def test_bedrock_agent_invoker(monkeypatch):
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')
    monkeypatch.setattr(boto3, 'client', lambda *args, **kwargs: DummyBedrock())
    import lambda_router
    importlib.reload(lambda_router)
    invoker = lambda_router.BedrockAgentInvoker('agent')
    payload = {
        "text": "hi",
        "client_id": "123",
        "attachments": [],
        "user_id": "u",
        "thread_ts": "t"
    }
    result = invoker.invoke_agent(payload)
    assert result["missing_fields_checklist"] == ["field1"]
    assert result["recommended_tags"] == ["tag1"]

def test_database_manager_fetch(monkeypatch):
    response = {"records": [[
        {"stringValue": json.dumps(["f1"])},
        {"stringValue": json.dumps(["msg"])}
    ]]}
    dummy = DummyRDS(response)
    monkeypatch.setattr(boto3, 'client', lambda *args, **kwargs: dummy)
    import lambda_router
    importlib.reload(lambda_router)
    db = lambda_router.DatabaseManager('a','b','c')
    mf, conv = db.fetch_case_state('cid')
    assert mf == ["f1"]
    assert conv == ["msg"]

