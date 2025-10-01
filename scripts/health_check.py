#!/usr/bin/env python3
"""
Скрипт для автоматизированного тестирования ключевых функций бота.
Запускайте ПОСЛЕ деплоя для проверки критической функциональности.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import load_config
from database import init_db_pool
from utils.callback_validators import callback_registry, validate_callback_data
from utils.file_validators import file_validator

logger = logging.getLogger(__name__)


class BotHealthChecker:
    """Класс для проверки здоровья бота после рефакторинга."""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.passed = []
    
    def add_issue(self, test_name: str, issue: str):
        """Добавить критическую проблему."""
        self.issues.append(f"❌ {test_name}: {issue}")
        logger.error(f"FAILED {test_name}: {issue}")
    
    def add_warning(self, test_name: str, warning: str):
        """Добавить предупреждение."""
        self.warnings.append(f"⚠️ {test_name}: {warning}")
        logger.warning(f"WARNING {test_name}: {warning}")
    
    def add_pass(self, test_name: str, details: str = ""):
        """Добавить успешный тест."""
        message = f"✅ {test_name}"
        if details:
            message += f": {details}"
        self.passed.append(message)
        logger.info(f"PASSED {test_name}")
    
    async def test_database_connection(self):
        """Тест подключения к базе данных."""
        try:
            config = load_config()
            pool = await init_db_pool(
                database_path=config.database_path,
                pool_size=5,  # Меньший пул для тестов
                busy_timeout_ms=config.db_busy_timeout,
            )
            
            # Тестируем простой запрос
            async with pool.connection() as conn:
                cursor = await conn.execute("SELECT COUNT(*) FROM participants")
                count = await cursor.fetchone()
                
            self.add_pass("Database Connection", f"Found {count[0]} participants")
            return True
            
        except Exception as e:
            self.add_issue("Database Connection", str(e))
            return False
    
    def test_callback_data_validation(self):
        """Тест валидации callback_data."""
        test_cases = [
            ("short", "ok"),
            ("normal_length_callback", "ok"),
            ("a" * 63, "ok"),  # Граничное значение
            ("a" * 64, "ok"),  # Точно на границе
            ("a" * 100, "truncated"),  # Должно обрезаться
            ("🎯🚀💫" * 30, "truncated"),  # Unicode symbols
        ]
        
        issues_found = 0
        for test_data, expected in test_cases:
            try:
                result = validate_callback_data(test_data)
                if expected == "truncated" and len(result) >= len(test_data):
                    self.add_issue("Callback Validation", 
                                 f"Failed to truncate: '{test_data}' -> '{result}'")
                    issues_found += 1
                elif expected == "ok" and len(result.encode('utf-8')) > 64:
                    self.add_issue("Callback Validation", 
                                 f"Result too long: '{result}' ({len(result.encode('utf-8'))} bytes)")
                    issues_found += 1
            except Exception as e:
                self.add_issue("Callback Validation", f"Exception on '{test_data}': {e}")
                issues_found += 1
        
        if issues_found == 0:
            self.add_pass("Callback Data Validation", f"All {len(test_cases)} test cases passed")
        
        return issues_found == 0
    
    def test_file_size_limits(self):
        """Тест лимитов размеров файлов."""
        try:
            config = load_config()
            max_size = config.max_file_size
            
            # Тестируем валидацию размера
            test_sizes = [
                (1024, True),  # 1KB - OK
                (max_size - 1, True),  # Чуть меньше лимита - OK
                (max_size, True),  # Точно лимит - OK
                (max_size + 1, False),  # Больше лимита - FAIL
                (max_size * 2, False),  # Сильно больше - FAIL
            ]
            
            issues_found = 0
            for size, should_pass in test_sizes:
                try:
                    from utils.file_validators import validate_file_size
                    validate_file_size(size, "test_file")
                    if not should_pass:
                        self.add_issue("File Size Validation", 
                                     f"Size {size} should have been rejected")
                        issues_found += 1
                except Exception as e:
                    if should_pass:
                        self.add_issue("File Size Validation", 
                                     f"Size {size} should have passed: {e}")
                        issues_found += 1
            
            if issues_found == 0:
                self.add_pass("File Size Validation", f"Max size: {max_size // (1024*1024)}MB")
            
            return issues_found == 0
            
        except Exception as e:
            self.add_issue("File Size Validation", str(e))
            return False
    
    def test_handler_coverage(self):
        """Проверка покрытия callback handlers."""
        # Известные callback_data из кода
        known_callbacks = [
            "edit_name", "edit_phone", "edit_card", "edit_photo",
            "confirm_registration", "cancel_registration",
            "faq_registration", "faq_results", "faq_prizes", "faq_photo", "faq_cards",
            "create_ticket", "back_to_tickets", "back_to_tickets_list",
            "quick_nav_main", "quick_nav_register", "quick_nav_support", "quick_nav_cancel",
            "info_rules", "info_prizes", "info_schedule", "info_fairness", "info_contacts"
        ]
        
        # Проверяем, что все зарегистрированы в реестре
        unhandled = []
        for callback in known_callbacks:
            if callback not in callback_registry._handlers:
                unhandled.append(callback)
        
        if unhandled:
            self.add_warning("Handler Coverage", 
                           f"Potentially unhandled callbacks: {', '.join(unhandled)}")
        else:
            self.add_pass("Handler Coverage", f"All {len(known_callbacks)} callbacks accounted for")
        
        return len(unhandled) == 0
    
    def test_configuration(self):
        """Проверка конфигурации."""
        try:
            config = load_config()
            
            # Критические настройки
            critical_checks = [
                (config.bot_token != "your_bot_token_here", "Bot token is set"),
                (config.secret_key != "production_secret_key_must_be_changed_in_production_environment", "Secret key is changed"),
                (config.admin_password != "123456", "Admin password is secure"),
                (config.db_pool_size >= 10, f"DB pool size adequate ({config.db_pool_size})"),
                (config.max_file_size <= 50 * 1024 * 1024, f"File size limit reasonable ({config.max_file_size // (1024*1024)}MB)"),
            ]
            
            issues_found = 0
            for check, description in critical_checks:
                if not check:
                    self.add_issue("Configuration", f"Failed: {description}")
                    issues_found += 1
            
            if issues_found == 0:
                self.add_pass("Configuration", "All critical settings OK")
            
            return issues_found == 0
            
        except Exception as e:
            self.add_issue("Configuration", str(e))
            return False
    
    async def run_all_tests(self):
        """Запуск всех тестов."""
        logger.info("🧪 Starting bot health check...")
        
        # Синхронные тесты
        self.test_callback_data_validation()
        self.test_file_size_limits()
        self.test_handler_coverage()
        self.test_configuration()
        
        # Асинхронные тесты
        await self.test_database_connection()
        
        # Подведение итогов
        print("\n" + "="*60)
        print("🧪 BOT HEALTH CHECK RESULTS")
        print("="*60)
        
        if self.issues:
            print(f"\n🔴 CRITICAL ISSUES ({len(self.issues)}):")
            for issue in self.issues:
                print(f"  {issue}")
        
        if self.warnings:
            print(f"\n🟡 WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  {warning}")
        
        if self.passed:
            print(f"\n✅ PASSED TESTS ({len(self.passed)}):")
            for passed in self.passed:
                print(f"  {passed}")
        
        # Финальная оценка
        total_tests = len(self.issues) + len(self.warnings) + len(self.passed)
        success_rate = len(self.passed) / total_tests * 100 if total_tests > 0 else 0
        
        print(f"\n📊 SUMMARY:")
        print(f"  Total tests: {total_tests}")
        print(f"  Success rate: {success_rate:.1f}%")
        
        if self.issues:
            print(f"\n🚨 ACTION REQUIRED: Fix {len(self.issues)} critical issues before production!")
            return False
        elif self.warnings:
            print(f"\n⚠️ REVIEW NEEDED: Address {len(self.warnings)} warnings when possible.")
            return True
        else:
            print(f"\n🎉 ALL TESTS PASSED! Bot is ready for production.")
            return True


async def main():
    """Основная функция для запуска тестов."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    checker = BotHealthChecker()
    success = await checker.run_all_tests()
    
    # Возвращаем код выхода для CI/CD
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
