"""Tests for admin panel functionality."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import pytest

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from web.app import create_app


class AdminPanelTestCase(unittest.TestCase):
    """Test case for admin panel functionality."""

    def setUp(self):
        """Set up test environment."""
        self.app = create_app(testing=True)
        self.app.config['WTF_CSRF_ENABLED'] = False  # Отключаем CSRF для тестов
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Создаем моки для сервисов
        self.broadcast_service_mock = MagicMock()
        self.app.config['BROADCAST_SERVICE'] = self.broadcast_service_mock
        
        # Имитируем авторизацию
        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['username'] = 'admin'

    def tearDown(self):
        """Tear down test environment."""
        self.app_context.pop()

    def test_dashboard_access(self):
        """Test dashboard page access."""
        response = self.client.get('/admin/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Dashboard', response.data)

    def test_login_page(self):
        """Test login page access."""
        # Сбрасываем сессию для проверки страницы логина
        with self.client.session_transaction() as session:
            session.clear()
            
        response = self.client.get('/admin/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Login', response.data)

    def test_login_functionality(self):
        """Test login functionality."""
        # Сбрасываем сессию
        with self.client.session_transaction() as session:
            session.clear()
            
        with patch('web.auth.check_password') as mock_check_password:
            mock_check_password.return_value = True
            
            response = self.client.post('/admin/login', data={
                'username': 'admin',
                'password': 'password'
            }, follow_redirects=True)
            
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Dashboard', response.data)

    def test_participants_page(self):
        """Test participants page access."""
        response = self.client.get('/admin/participants')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Participants', response.data)

    def test_lottery_page(self):
        """Test lottery page access."""
        response = self.client.get('/admin/lottery')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Lottery', response.data)

    def test_broadcasts_page(self):
        """Test broadcasts page access."""
        response = self.client.get('/admin/broadcasts')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Broadcasts', response.data)

    def test_create_broadcast(self):
        """Test broadcast creation."""
        with patch('web.routes.admin._get_admin_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.list_participants.return_value = ([MagicMock(id=1), MagicMock(id=2)], 2)
            mock_db.create_broadcast.return_value = 1
            mock_get_db.return_value = mock_db
            
            with patch('web.routes.admin.submit_coroutine') as mock_submit:
                response = self.client.post('/admin/broadcasts', data={
                    'message_text': 'Test broadcast message'
                }, follow_redirects=True)
                
                self.assertEqual(response.status_code, 200)
                mock_db.create_broadcast.assert_called_once()
                mock_submit.assert_called_once()

    def test_create_broadcast_with_media(self):
        """Test broadcast creation with media."""
        with patch('web.routes.admin._get_admin_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.list_participants.return_value = ([MagicMock(id=1), MagicMock(id=2)], 2)
            mock_db.create_broadcast.return_value = 1
            mock_get_db.return_value = mock_db
            
            with patch('web.routes.admin.submit_coroutine') as mock_submit:
                with patch('web.routes.admin.os.path.join', return_value='/tmp/test.jpg'):
                    with patch('web.routes.admin.os.makedirs'):
                        with patch('werkzeug.datastructures.FileStorage.save'):
                            from io import BytesIO
                            test_file = (BytesIO(b'test file content'), 'test.jpg')
                            
                            response = self.client.post('/admin/broadcasts', data={
                                'message_text': 'Test broadcast message',
                                'media_file': test_file,
                                'media_caption': 'Test caption'
                            }, follow_redirects=True, content_type='multipart/form-data')
                            
                            self.assertEqual(response.status_code, 200)
                            mock_db.create_broadcast.assert_called_once()
                            mock_submit.assert_called_once()

    def test_support_tickets_page(self):
        """Test support tickets page access."""
        response = self.client.get('/admin/support-tickets')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Support Tickets', response.data)


@pytest.fixture
def client():
    """Create a test client for the app."""
    # Создаем тестовую конфигурацию
    from dataclasses import dataclass
    
    @dataclass
    class TestConfig:
        secret_key: str = "test_secret_key"
        max_file_size: int = 16 * 1024 * 1024
        database_path: str = ":memory:"
        admin_username: str = "admin"
        admin_password: str = "password"
    
    config = TestConfig()
    app = create_app(config, testing=True)
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.test_client() as client:
        with app.app_context():
            # Имитируем авторизацию
            with client.session_transaction() as session:
                session['user_id'] = 1
                session['username'] = 'admin'
            yield client


@pytest.mark.parametrize('endpoint', [
    '/admin/dashboard',
    '/admin/participants',
    '/admin/lottery',
    '/admin/broadcasts',
    '/admin/support-tickets',
    '/admin/settings',
])
def test_admin_endpoints(client, endpoint):
    """Test all admin endpoints."""
    response = client.get(endpoint)
    assert response.status_code == 200


if __name__ == '__main__':
    unittest.main()