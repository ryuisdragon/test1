import json
import importlib
import types

import boto3

class DummyContext:
    pass

class DummyClient:
    def __getattr__(self, name):
        def _(*args, **kwargs):
            return {}
        return _

def test_invalid_signature_returns_401(monkeypatch):
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')
    monkeypatch.setattr(boto3, 'client', lambda *args, **kwargs: DummyClient())
    monkeypatch.setenv('SLACK_SIGNING_SECRET', 'dummy')
    monkeypatch.setenv('BEDROCK_AGENT_ID', 'agent')
    monkeypatch.setenv('RDS_CLUSTER_ARN', 'arn')
    monkeypatch.setenv('RDS_SECRET_ARN', 'arn')
    monkeypatch.setenv('RDS_DATABASE_NAME', 'db')
    import lambda_router
    importlib.reload(lambda_router)
    event = {
        "body": json.dumps({"event": {"type": "message", "text": "hello"}}),
        "headers": {"x-slack-signature": "", "x-slack-request-timestamp": ""}
    }
    response = lambda_router.lambda_handler(event, DummyContext())
    assert response["statusCode"] == 401

