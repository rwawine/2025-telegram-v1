"""Pytest configuration and fixtures."""

import pytest
import asyncio
from pathlib import Path


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db():
    """Create test database."""
    # TODO: Implement test database setup
    test_db_path = Path("data/test_lottery_bot.sqlite")
    
    # Setup
    # ...
    
    yield test_db_path
    
    # Teardown
    if test_db_path.exists():
        test_db_path.unlink()


@pytest.fixture
def mock_pool():
    """Mock database pool."""
    class MockPool:
        async def connection(self):
            class MockConnection:
                async def execute(self, query, params=None):
                    class MockCursor:
                        async def fetchone(self):
                            return None
                        async def fetchall(self):
                            return []
                        @property
                        def rowcount(self):
                            return 0
                        @property
                        def lastrowid(self):
                            return 1
                    return MockCursor()
                
                async def commit(self):
                    pass
                
                async def __aenter__(self):
                    return self
                
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass
            
            return MockConnection()
    
    return MockPool()


@pytest.fixture
def mock_audit_service():
    """Mock audit service."""
    class MockAuditService:
        async def log_action(self, **kwargs):
            pass
        
        async def get_audit_logs(self, **kwargs):
            return []
        
        async def detect_suspicious_activity(self, admin_username):
            return []
    
    return MockAuditService()

