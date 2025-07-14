import json
import importlib
import boto3

class DummyLogger:
    def __init__(self):
        self.infos = []
        self.errors = []
    def info(self, msg):
        self.infos.append(msg)
    def error(self, msg):
        self.errors.append(msg)
    def warning(self, msg):
        self.infos.append(msg)

class DummyRDS:
    def execute_statement(self, **kwargs):
        return {}


def test_database_manager_logs(monkeypatch):
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')
    dummy = DummyRDS()
    monkeypatch.setattr(boto3, 'client', lambda *a, **k: dummy)
    import lambda_actions
    importlib.reload(lambda_actions)
    logger = DummyLogger()
    db = lambda_actions.DatabaseManager('a','b','c', logger)
    assert db.update_case_status('cid','status','uid')
    assert any('status updated' in m for m in logger.infos)


def test_slack_handler_logs(monkeypatch):
    monkeypatch.setattr(boto3, 'client', lambda *a, **k: DummyRDS())
    import lambda_actions
    importlib.reload(lambda_actions)
    logger = DummyLogger()
    handler = lambda_actions.SlackInteractionHandler('token', logger)
    data = {'case_id': 'cid', 'client_id': 'client'}
    assert handler.open_adjust_conditions_modal('t', data)
    assert any('Modal opened' in m for m in logger.infos)


def test_pdf_generator_logs(monkeypatch):
    monkeypatch.setattr(boto3, 'client', lambda *a, **k: DummyRDS())
    import lambda_actions
    importlib.reload(lambda_actions)
    logger = DummyLogger()
    gen = lambda_actions.PDFGenerator('bucket', logger)
    url = gen.generate_pdf({'client_id':'c','type':'planner'}, 'tpl')
    assert url.startswith('https://bucket.s3.amazonaws.com')
    assert any('PDF generated' in m for m in logger.infos)


def test_lambda_handler_passes_logger(monkeypatch):
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')
    for var in ['RDS_CLUSTER_ARN','RDS_SECRET_ARN','RDS_DATABASE_NAME','SLACK_BOT_TOKEN','S3_BUCKET_NAME']:
        monkeypatch.setenv(var, 'x')
    import lambda_actions
    importlib.reload(lambda_actions)

    captured = {}

    class DB:
        def __init__(self, a,b,c, logger):
            captured['db'] = logger
        def update_case_status(self, *a, **k):
            captured['db_called'] = True
            captured['db'].info('db')
            return True

    class Slack:
        def __init__(self, token, logger):
            captured['slack'] = logger
        def send_confirmation_message(self, *a, **k):
            captured['slack_called'] = True
            captured['slack'].info('msg')
            return True

    class Brief:
        def __init__(self, bucket, logger):
            captured['brief'] = logger
        def generate_planner_brief(self, d):
            return {'type':'planner','content':{'client_id':'c','type':'planner'},'template':'t'}
        def generate_manager_brief(self, d):
            return {'type':'manager','content':{'client_id':'c','type':'manager'},'template':'t'}

    class PDF:
        def __init__(self, bucket, logger):
            captured['pdf'] = logger
        def generate_pdf(self, *a, **k):
            captured['pdf_called'] = True
            captured['pdf'].info('pdf')
            return 'url'

    logger = DummyLogger()
    def fake_get_logger(req='-'):
        captured['logger_req'] = req
        return logger
    monkeypatch.setattr(lambda_actions, 'get_logger', fake_get_logger)
    monkeypatch.setattr(lambda_actions, 'DatabaseManager', DB)
    monkeypatch.setattr(lambda_actions, 'SlackInteractionHandler', Slack)
    monkeypatch.setattr(lambda_actions, 'BriefGenerator', Brief)
    monkeypatch.setattr(lambda_actions, 'PDFGenerator', PDF)

    event = {
        'body': json.dumps({'payload': json.dumps({
            'actions':[{'action_id':'confirm_correct'}],
            'user':{'id':'u'},
            'channel':{'id':'c'},
            'message':{'ts':'t','blocks':[{'block_id':'cid'}]}
        })})
    }

    class Ctx:
        aws_request_id = 'req-1'

    resp = lambda_actions.lambda_handler(event, Ctx())
    assert resp['statusCode'] == 200
    assert captured['db'] is logger
    assert captured['slack'] is logger
    assert captured['brief'] is logger
    assert captured['pdf'] is logger
    assert captured['logger_req'] == 'req-1'
    assert logger.infos
