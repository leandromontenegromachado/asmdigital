import hashlib
import hmac
import unittest
from datetime import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.modules.fala_ai.models import FalaAiReminder
from app.modules.fala_ai.scheduler import _send_reminder
from app.modules.fala_ai.schemas import FalaAiCheckinCreate
from app.modules.fala_ai.service import create_checkin, process_teams_webhook_payload
from app.modules.fala_ai.teams_integration import validate_teams_request


class _FakeReminderQuery:
    def __init__(self, reminder):
        self.reminder = reminder

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.reminder


class _FakeUserQuery:
    def __init__(self, users):
        self.users = users

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self.users


class _FakeDB:
    def __init__(self, reminder, users):
        self._reminder = reminder
        self._users = users

    def query(self, model):
        if model is FalaAiReminder:
            return _FakeReminderQuery(self._reminder)
        return _FakeUserQuery(self._users)


class _FakeSessionLocal:
    def __init__(self, db):
        self.db = db

    def __call__(self):
        return self

    def __enter__(self):
        return self.db

    def __exit__(self, exc_type, exc, tb):
        return False


class FalaAiTests(unittest.TestCase):
    def test_create_checkin_success(self):
        db = MagicMock()
        actor = SimpleNamespace(id=10, role='viewer')
        target_user = SimpleNamespace(id=10)

        with patch('app.modules.fala_ai.service.resolve_user', return_value=target_user):
            checkin = create_checkin(
                db,
                FalaAiCheckinCreate(user_id=10, tipo='manual', origem='web'),
                actor=actor,
                allow_impersonation=False,
            )

        self.assertEqual(checkin.user_id, 10)
        self.assertEqual(checkin.tipo, 'manual')
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_send_reminder_runs_delivery(self):
        reminder = SimpleNamespace(id=1, mensagem='Lembrete rapido', ativo=True, horario=time(hour=9, minute=0))
        users = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
        fake_db = _FakeDB(reminder, users)

        with patch('app.modules.fala_ai.scheduler.SessionLocal', new=_FakeSessionLocal(fake_db)):
            with patch('app.modules.fala_ai.scheduler.register_log') as register_log_mock:
                with patch('app.modules.fala_ai.scheduler.send_teams_message') as send_teams_message_mock:
                    with patch(
                        'app.modules.fala_ai.scheduler.settings',
                        SimpleNamespace(
                            fala_ai_teams_outgoing_webhook='https://example.org/webhook',
                            fala_ai_teams_bot_app_id=None,
                            fala_ai_teams_bot_app_secret=None,
                            fala_ai_teams_bot_tenant_id='botframework.com',
                            fala_ai_teams_default_service_url=None,
                            fala_ai_teams_default_conversation_id=None,
                            fala_ai_teams_default_bot_id=None,
                        ),
                    ):
                        _send_reminder(1)

        send_teams_message_mock.assert_called_once()
        register_log_mock.assert_called_once()

    def test_process_teams_webhook_registers_checkin_on_confirmation_message(self):
        db = MagicMock()
        payload = {'text': 'sim'}
        user = SimpleNamespace(id=7, email='ana@company.com')
        checkin = SimpleNamespace(id=99)

        with patch(
            'app.modules.fala_ai.service.extract_teams_identity',
            return_value={
                'user_id': None,
                'email': 'ana@company.com',
                'name': 'Ana',
                'message': 'sim',
                'activity_type': 'message',
                'normalized_message': 'sim',
                'reaction_types': [],
                'conversation_id': 'conv-1',
                'channel_id': 'webchat',
            },
        ):
            with patch('app.modules.fala_ai.service.resolve_user', return_value=user):
                with patch('app.modules.fala_ai.service._resolve_active_dispatch', return_value={'dispatch_id': 'd1', 'conversation_id': 'conv-1'}):
                    with patch('app.modules.fala_ai.service._checkin_already_recorded_for_dispatch', return_value=False):
                        with patch('app.modules.fala_ai.service.create_checkin', return_value=checkin):
                            with patch('app.modules.fala_ai.service.register_log'):
                                created, reply = process_teams_webhook_payload(db, payload)

        self.assertIsNotNone(created)
        self.assertEqual(created.id, 99)
        self.assertIn('Check-in', reply)

    def test_process_teams_webhook_without_confirmation_does_not_register(self):
        db = MagicMock()
        payload = {'text': 'bom dia'}
        user = SimpleNamespace(id=7, email='ana@company.com')

        with patch(
            'app.modules.fala_ai.service.extract_teams_identity',
            return_value={
                'user_id': None,
                'email': 'ana@company.com',
                'name': 'Ana',
                'message': 'bom dia',
                'activity_type': 'message',
                'normalized_message': 'bom dia',
                'reaction_types': [],
                'conversation_id': 'conv-1',
                'channel_id': 'webchat',
            },
        ):
            with patch('app.modules.fala_ai.service.resolve_user', return_value=user):
                with patch('app.modules.fala_ai.service.register_log'):
                    created, reply = process_teams_webhook_payload(db, payload)

        self.assertIsNone(created)
        self.assertIn("responde com 'sim'", reply)

    def test_validate_teams_signature(self):
        body = b'{"text":"hello"}'
        secret = 'my-secret'
        digest = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
        signature = f'sha256={digest}'
        ok = validate_teams_request(body, {'x-fala-ai-signature': signature}, secret)
        self.assertTrue(ok)


if __name__ == '__main__':
    unittest.main()
