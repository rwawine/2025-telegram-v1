"""Load testing script for the lottery bot system.

Tests system performance under high load (500+ concurrent users).
"""

from __future__ import annotations

import asyncio
import time
import random
import string
from dataclasses import dataclass
from typing import List, Dict, Any
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.connection import get_db_pool, init_db_pool
from database.repositories import (
    insert_participants_batch,
    get_participant_status,
    get_approved_participants,
)
from services.cache import MultiLevelCache
from services.lottery import SecureLottery
from services import (
    AnalyticsService,
    AnalyticsEvent,
    FraudDetectionService,
    RegistrationStateManager,
)
from core import get_logger

logger = get_logger(__name__)


@dataclass
class LoadTestResult:
    """Results from load test."""
    total_operations: int
    successful_operations: int
    failed_operations: int
    duration_seconds: float
    operations_per_second: float
    avg_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    errors: List[str]


class LoadTester:
    """Load testing utility for the lottery bot."""
    
    def __init__(self, db_path: str = "data/lottery_bot_test.sqlite"):
        self.db_path = db_path
        self.cache = MultiLevelCache(
            hot_ttl=60,      # 1 minute for hot cache
            warm_ttl=300,    # 5 minutes for warm cache
            cold_ttl=3600    # 1 hour for cold cache
        )
        self.response_times: List[float] = []
        self.errors: List[str] = []
        
    async def setup(self):
        """Initialize test environment."""
        logger.info("Setting up load test environment...")
        
        # Initialize database pool with high capacity for load testing
        await init_db_pool(
            database_path=self.db_path,
            pool_size=50,  # High pool size for concurrent operations
            busy_timeout_ms=30000  # 30 second timeout
        )
        
        # Run migrations
        from database.migrations import run_migrations
        pool = get_db_pool()
        await run_migrations(pool)
        
        # Ensure required tables
        from services import ensure_analytics_table, ensure_registration_table
        await ensure_analytics_table()
        await ensure_registration_table()
        
        logger.info("Load test environment ready")
    
    async def cleanup(self):
        """Clean up test data."""
        logger.info("Cleaning up test environment...")
        
        try:
            pool = get_db_pool()
        except RuntimeError:
            logger.warning("Database pool not initialized, skipping cleanup")
            return
        async with pool.connection() as conn:
            # Clear test data
            await conn.execute("DELETE FROM participants WHERE phone_number LIKE 'TEST_%'")
            await conn.execute("DELETE FROM analytics_events WHERE user_id >= 100000")
            await conn.execute("DELETE FROM registration_states WHERE user_id >= 100000")
            await conn.execute("DELETE FROM fraud_log WHERE user_id >= 100000")
            await conn.commit()
        
        logger.info("Cleanup complete")
    
    def _generate_test_user(self, user_id: int) -> Dict[str, Any]:
        """Generate random test user data."""
        return {
            "telegram_id": 100000 + user_id,
            "username": f"test_user_{user_id}",
            "full_name": f"Test User {user_id} {''.join(random.choices(string.ascii_uppercase, k=3))}",
            "phone_number": f"TEST_{random.randint(1000000000, 9999999999)}",
            "loyalty_card": f"TEST{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}",
            "photo_path": f"uploads/test_{user_id}.jpg",
        }
    
    async def test_registration_load(self, num_users: int = 500) -> LoadTestResult:
        """Test concurrent user registrations.
        
        Args:
            num_users: Number of users to simulate
            
        Returns:
            Load test results
        """
        logger.info(f"Starting registration load test with {num_users} users...")
        
        start_time = time.time()
        successful = 0
        failed = 0
        
        async def register_user(user_id: int):
            """Register a single user and measure time."""
            op_start = time.time()
            try:
                user_data = self._generate_test_user(user_id)
                
                # Simulate registration steps
                # 1. Save registration state
                await RegistrationStateManager.save_state(
                    user_data["telegram_id"],
                    {
                        "full_name": user_data["full_name"],
                        "phone_number": user_data["phone_number"],
                        "loyalty_card": user_data["loyalty_card"],
                    }
                )
                
                # 2. Track analytics events
                await AnalyticsService.track_event(
                    AnalyticsEvent.REGISTRATION_STARTED,
                    user_id=user_data["telegram_id"]
                )
                
                await AnalyticsService.track_registration_step(
                    user_data["telegram_id"],
                    "name",
                    success=True
                )
                
                await AnalyticsService.track_registration_step(
                    user_data["telegram_id"],
                    "phone",
                    success=True
                )
                
                # 3. Insert participant
                await insert_participants_batch([user_data])
                
                # 4. Clear registration state
                await RegistrationStateManager.clear_state(user_data["telegram_id"])
                
                # 5. Track completion
                await AnalyticsService.track_event(
                    AnalyticsEvent.REGISTRATION_COMPLETED,
                    user_id=user_data["telegram_id"]
                )
                
                response_time = (time.time() - op_start) * 1000
                self.response_times.append(response_time)
                
                return True
                
            except Exception as e:
                error_msg = f"User {user_id} registration failed: {e}"
                self.errors.append(error_msg)
                logger.error(error_msg)
                return False
        
        # Run registrations concurrently in batches
        batch_size = 50
        for i in range(0, num_users, batch_size):
            batch = range(i, min(i + batch_size, num_users))
            results = await asyncio.gather(*[register_user(uid) for uid in batch])
            successful += sum(results)
            failed += len(results) - sum(results)
            
            # Small delay between batches
            await asyncio.sleep(0.1)
        
        duration = time.time() - start_time
        
        # Calculate statistics
        ops_per_sec = num_users / duration if duration > 0 else 0
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        min_response_time = min(self.response_times) if self.response_times else 0
        max_response_time = max(self.response_times) if self.response_times else 0
        
        result = LoadTestResult(
            total_operations=num_users,
            successful_operations=successful,
            failed_operations=failed,
            duration_seconds=duration,
            operations_per_second=ops_per_sec,
            avg_response_time_ms=avg_response_time,
            min_response_time_ms=min_response_time,
            max_response_time_ms=max_response_time,
            errors=self.errors[:10],  # Only first 10 errors
        )
        
        logger.info(f"Registration load test completed: {successful}/{num_users} successful")
        return result
    
    async def test_status_check_load(self, num_requests: int = 1000) -> LoadTestResult:
        """Test concurrent status check requests.
        
        Args:
            num_requests: Number of status check requests
            
        Returns:
            Load test results
        """
        logger.info(f"Starting status check load test with {num_requests} requests...")
        
        self.response_times = []
        self.errors = []
        
        start_time = time.time()
        successful = 0
        failed = 0
        
        async def check_status(request_id: int):
            """Check user status and measure time."""
            op_start = time.time()
            try:
                # Use random telegram ID from test range
                telegram_id = 100000 + random.randint(0, 499)
                
                # Check status (should use cache)
                status = await get_participant_status(telegram_id)
                
                response_time = (time.time() - op_start) * 1000
                self.response_times.append(response_time)
                
                return True
                
            except Exception as e:
                error_msg = f"Request {request_id} failed: {e}"
                self.errors.append(error_msg)
                return False
        
        # Run requests concurrently in batches
        batch_size = 100
        for i in range(0, num_requests, batch_size):
            batch = range(i, min(i + batch_size, num_requests))
            results = await asyncio.gather(*[check_status(req_id) for req_id in batch])
            successful += sum(results)
            failed += len(results) - sum(results)
        
        duration = time.time() - start_time
        
        # Calculate statistics
        ops_per_sec = num_requests / duration if duration > 0 else 0
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        min_response_time = min(self.response_times) if self.response_times else 0
        max_response_time = max(self.response_times) if self.response_times else 0
        
        result = LoadTestResult(
            total_operations=num_requests,
            successful_operations=successful,
            failed_operations=failed,
            duration_seconds=duration,
            operations_per_second=ops_per_sec,
            avg_response_time_ms=avg_response_time,
            min_response_time_ms=min_response_time,
            max_response_time_ms=max_response_time,
            errors=self.errors[:10],
        )
        
        logger.info(f"Status check load test completed: {successful}/{num_requests} successful")
        return result
    
    async def test_lottery_performance(self, num_participants: int = 500) -> LoadTestResult:
        """Test lottery drawing performance.
        
        Args:
            num_participants: Number of approved participants
            
        Returns:
            Load test results
        """
        logger.info(f"Starting lottery performance test with {num_participants} participants...")
        
        self.response_times = []
        self.errors = []
        
        # Ensure we have approved participants
        pool = get_db_pool()
        async with pool.connection() as conn:
            await conn.execute(
                "UPDATE participants SET status = 'approved' WHERE telegram_id >= 100000"
            )
            await conn.commit()
        
        start_time = time.time()
        successful = 0
        failed = 0
        
        try:
            lottery = SecureLottery()
            
            # Get approved participants
            approved = await get_approved_participants()
            
            if len(approved) < 10:
                logger.warning(f"Not enough approved participants: {len(approved)}")
                self.errors.append(f"Insufficient participants: {len(approved)}")
            
            # Run lottery
            op_start = time.time()
            winners = await lottery.draw_winners(num_winners=min(10, len(approved)))
            response_time = (time.time() - op_start) * 1000
            
            self.response_times.append(response_time)
            
            if winners:
                successful = 1
                logger.info(f"Lottery completed: {len(winners)} winners selected")
            else:
                failed = 1
                self.errors.append("No winners selected")
                
        except Exception as e:
            error_msg = f"Lottery test failed: {e}"
            self.errors.append(error_msg)
            logger.error(error_msg)
            failed = 1
        
        duration = time.time() - start_time
        
        result = LoadTestResult(
            total_operations=1,
            successful_operations=successful,
            failed_operations=failed,
            duration_seconds=duration,
            operations_per_second=1 / duration if duration > 0 else 0,
            avg_response_time_ms=self.response_times[0] if self.response_times else 0,
            min_response_time_ms=self.response_times[0] if self.response_times else 0,
            max_response_time_ms=self.response_times[0] if self.response_times else 0,
            errors=self.errors,
        )
        
        logger.info(f"Lottery performance test completed")
        return result
    
    async def test_fraud_detection_performance(self, num_checks: int = 500) -> LoadTestResult:
        """Test fraud detection service performance.
        
        Args:
            num_checks: Number of fraud checks
            
        Returns:
            Load test results
        """
        logger.info(f"Starting fraud detection performance test with {num_checks} checks...")
        
        self.response_times = []
        self.errors = []
        
        start_time = time.time()
        successful = 0
        failed = 0
        
        fraud_service = FraudDetectionService()
        
        async def check_fraud(check_id: int):
            """Perform fraud check and measure time."""
            op_start = time.time()
            try:
                user_data = self._generate_test_user(check_id)
                
                # Run fraud detection
                fraud_score = await fraud_service.check_registration(
                    user_id=user_data["telegram_id"],
                    full_name=user_data["full_name"],
                    phone_number=user_data["phone_number"],
                    loyalty_card=user_data["loyalty_card"],
                    registration_time=random.uniform(10, 300)  # 10-300 seconds
                )
                
                response_time = (time.time() - op_start) * 1000
                self.response_times.append(response_time)
                
                return True
                
            except Exception as e:
                error_msg = f"Check {check_id} failed: {e}"
                self.errors.append(error_msg)
                return False
        
        # Run checks concurrently in batches
        batch_size = 50
        for i in range(0, num_checks, batch_size):
            batch = range(i, min(i + batch_size, num_checks))
            results = await asyncio.gather(*[check_fraud(check_id) for check_id in batch])
            successful += sum(results)
            failed += len(results) - sum(results)
        
        duration = time.time() - start_time
        
        # Calculate statistics
        ops_per_sec = num_checks / duration if duration > 0 else 0
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        min_response_time = min(self.response_times) if self.response_times else 0
        max_response_time = max(self.response_times) if self.response_times else 0
        
        result = LoadTestResult(
            total_operations=num_checks,
            successful_operations=successful,
            failed_operations=failed,
            duration_seconds=duration,
            operations_per_second=ops_per_sec,
            avg_response_time_ms=avg_response_time,
            min_response_time_ms=min_response_time,
            max_response_time_ms=max_response_time,
            errors=self.errors[:10],
        )
        
        logger.info(f"Fraud detection test completed: {successful}/{num_checks} successful")
        return result
    
    def print_results(self, test_name: str, result: LoadTestResult):
        """Print test results in a formatted way."""
        print(f"\n{'='*60}")
        print(f"📊 {test_name}")
        print(f"{'='*60}")
        print(f"Total Operations:     {result.total_operations}")
        print(f"✅ Successful:        {result.successful_operations} ({result.successful_operations/result.total_operations*100:.1f}%)")
        print(f"❌ Failed:            {result.failed_operations} ({result.failed_operations/result.total_operations*100:.1f}%)")
        print(f"⏱️  Duration:          {result.duration_seconds:.2f}s")
        print(f"🚀 Throughput:        {result.operations_per_second:.2f} ops/sec")
        print(f"⏰ Avg Response Time: {result.avg_response_time_ms:.2f}ms")
        print(f"⚡ Min Response Time: {result.min_response_time_ms:.2f}ms")
        print(f"🐌 Max Response Time: {result.max_response_time_ms:.2f}ms")
        
        if result.errors:
            print(f"\n⚠️  Errors (first 10):")
            for error in result.errors:
                print(f"   - {error}")
        
        print(f"{'='*60}\n")


async def run_all_load_tests():
    """Run all load tests."""
    tester = LoadTester()
    
    try:
        # Setup
        await tester.setup()
        
        # Test 1: Registration load (500 users)
        result1 = await tester.test_registration_load(num_users=500)
        tester.print_results("Registration Load Test (500 users)", result1)
        
        # Test 2: Status check load (1000 requests)
        result2 = await tester.test_status_check_load(num_requests=1000)
        tester.print_results("Status Check Load Test (1000 requests)", result2)
        
        # Test 3: Fraud detection performance
        result3 = await tester.test_fraud_detection_performance(num_checks=500)
        tester.print_results("Fraud Detection Performance Test (500 checks)", result3)
        
        # Test 4: Lottery performance
        result4 = await tester.test_lottery_performance(num_participants=500)
        tester.print_results("Lottery Performance Test", result4)
        
        # Summary
        print(f"\n{'='*60}")
        print(f"📈 LOAD TEST SUMMARY")
        print(f"{'='*60}")
        total_ops = sum([r.total_operations for r in [result1, result2, result3, result4]])
        total_successful = sum([r.successful_operations for r in [result1, result2, result3, result4]])
        total_failed = sum([r.failed_operations for r in [result1, result2, result3, result4]])
        
        print(f"Total Operations:  {total_ops}")
        print(f"✅ Total Success:  {total_successful} ({total_successful/total_ops*100:.1f}%)")
        print(f"❌ Total Failed:   {total_failed} ({total_failed/total_ops*100:.1f}%)")
        
        if total_failed / total_ops > 0.05:  # More than 5% failure rate
            print(f"\n⚠️  WARNING: High failure rate detected!")
            print(f"   System may not be ready for production load.")
        else:
            print(f"\n✅ System passed load tests!")
            print(f"   Ready for production with {total_ops} simulated operations.")
        
        print(f"{'='*60}\n")
        
    except Exception as e:
        logger.error(f"Load test failed: {e}", exc_info=True)
        print(f"\n❌ Load test failed: {e}")
    
    finally:
        # Cleanup
        await tester.cleanup()


if __name__ == "__main__":
    print("🔥 Starting Load Tests for Lottery Bot System")
    print("Testing with 500+ concurrent users...\n")
    
    asyncio.run(run_all_load_tests())

