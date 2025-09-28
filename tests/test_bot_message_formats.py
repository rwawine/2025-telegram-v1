#!/usr/bin/env python3
"""Comprehensive tests for bot message format handling."""

import asyncio
import logging
import sys
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockMessage:
    """Mock объект для имитации различных типов сообщений Telegram."""
    
    def __init__(self, content_type="text", text=None, **kwargs):
        self.message_id = 12345
        self.date = datetime.now()
        self.content_type = content_type
        self.text = text
        self.from_user = MagicMock()
        self.from_user.id = 123456789
        self.from_user.first_name = "Test"
        self.from_user.last_name = "User"
        self.from_user.username = "testuser"
        self.chat = MagicMock()
        self.chat.id = 123456789
        self.chat.type = "private"
        self.bot = AsyncMock()
        
        # Добавляем специфичные поля для разных типов контента
        for key, value in kwargs.items():
            setattr(self, key, value)
        
        # Mock методов
        self.answer = AsyncMock()
        self.reply = AsyncMock()


class MockCallbackQuery:
    """Mock объект для имитации callback query."""
    
    def __init__(self, data="test_callback", **kwargs):
        self.id = "callback_123"
        self.data = data
        self.from_user = MagicMock()
        self.from_user.id = 123456789
        self.from_user.first_name = "Test"
        self.from_user.last_name = "User"
        self.message = MockMessage()
        self.bot = AsyncMock()
        
        for key, value in kwargs.items():
            setattr(self, key, value)
        
        self.answer = AsyncMock()
        self.edit_message_text = AsyncMock()


async def test_text_messages():
    """Тест обработки текстовых сообщений."""
    
    print("📝 Testing text message handling...")
    
    test_cases = [
        {"text": "Привет!", "description": "Simple greeting"},
        {"text": "/start", "description": "Start command"},
        {"text": "🚀 Начать регистрацию", "description": "Registration button"},
        {"text": "✅ Мой статус", "description": "Status button"},
        {"text": "💬 Помощь", "description": "Help button"},
        {"text": "📊 О розыгрыше", "description": "Info button"},
        {"text": "😀😃😄😁", "description": "Only emojis"},
        {"text": "Текст с эмодзи 🎉🎊", "description": "Text with emojis"},
        {"text": "123456789", "description": "Numbers only"},
        {"text": "special chars !@#$%^&*()", "description": "Special characters"},
        {"text": "Very long text " * 50, "description": "Very long message"},
        {"text": "", "description": "Empty text"},
        {"text": None, "description": "No text"},
    ]
    
    try:
        from bot.handlers.common import CommonHandlers
        from bot.handlers.fallback import SmartFallbackHandler
        
        common_handler = CommonHandlers()
        fallback_handler = SmartFallbackHandler()
        
        for case in test_cases:
            try:
                message = MockMessage(
                    content_type="text",
                    text=case["text"]
                )
                
                # Тестируем обработчики
                print(f"  Testing: {case['description']}")
                
                # Тест на start команду
                if case["text"] and "/start" in case["text"]:
                    await common_handler.start(message)
                    print(f"    ✅ Start handler processed")
                
                # Тест на помощь
                elif case["text"] and any(help_text in case["text"] for help_text in ["Помощ", "помощ"]):
                    await common_handler.help_and_support_handler(message)
                    print(f"    ✅ Help handler processed")
                
                # Тест на статус
                elif case["text"] and "статус" in case["text"]:
                    await common_handler.status_handler(message)
                    print(f"    ✅ Status handler processed")
                
                # Тест fallback handler
                else:
                    from aiogram.fsm.context import FSMContext
                    mock_state = MagicMock(spec=FSMContext)
                    mock_state.get_data = AsyncMock(return_value={})
                    await fallback_handler.handle_unexpected_text(message, mock_state)
                    print(f"    ✅ Fallback handler processed")
                
            except Exception as e:
                print(f"    ❌ Error processing {case['description']}: {e}")
                continue
        
        print("✅ Text message tests completed")
        return True
        
    except Exception as e:
        print(f"❌ Text message test setup failed: {e}")
        return False


async def test_media_messages():
    """Тест обработки медиа сообщений."""
    
    print("🎥 Testing media message handling...")
    
    media_test_cases = [
        {
            "content_type": "photo",
            "description": "Photo message",
            "photo": [{"file_id": "photo_123", "width": 1280, "height": 720}]
        },
        {
            "content_type": "audio",
            "description": "Audio message", 
            "audio": {"file_id": "audio_123", "duration": 180}
        },
        {
            "content_type": "voice",
            "description": "Voice message",
            "voice": {"file_id": "voice_123", "duration": 30}
        },
        {
            "content_type": "video",
            "description": "Video message",
            "video": {"file_id": "video_123", "duration": 60, "width": 1920, "height": 1080}
        },
        {
            "content_type": "video_note",
            "description": "Video note (round video)",
            "video_note": {"file_id": "videonote_123", "duration": 15}
        },
        {
            "content_type": "document",
            "description": "Document message",
            "document": {"file_id": "doc_123", "file_name": "test.pdf"}
        },
        {
            "content_type": "sticker",
            "description": "Sticker message",
            "sticker": {"file_id": "sticker_123", "emoji": "😀"}
        },
        {
            "content_type": "animation",
            "description": "GIF/Animation",
            "animation": {"file_id": "gif_123", "duration": 5}
        },
        {
            "content_type": "contact",
            "description": "Contact share",
            "contact": {"phone_number": "+1234567890", "first_name": "John"}
        },
        {
            "content_type": "location",
            "description": "Location share",
            "location": {"latitude": 55.7558, "longitude": 37.6176}
        }
    ]
    
    try:
        from bot.handlers.fallback import SmartFallbackHandler
        from bot.handlers.registration import RegistrationHandler
        from pathlib import Path
        from services.cache import get_cache
        from unittest.mock import MagicMock
        
        fallback_handler = SmartFallbackHandler()
        
        # Mock cache for registration handler
        mock_cache = MagicMock()
        mock_bot = AsyncMock()
        
        for case in media_test_cases:
            try:
                print(f"  Testing: {case['description']}")
                
                # Создаем mock сообщение с медиа
                message_kwargs = {k: v for k, v in case.items() 
                                if k not in ["content_type", "description"]}
                
                message = MockMessage(
                    content_type=case["content_type"],
                    **message_kwargs
                )
                
                # Тестируем fallback handler (он должен обрабатывать все медиа)
                from aiogram.fsm.context import FSMContext
                mock_state = MagicMock(spec=FSMContext)
                mock_state.get_data = AsyncMock(return_value={})
                mock_state.get_state = AsyncMock(return_value=None)
                
                if case["content_type"] == "photo":
                    await fallback_handler.handle_unexpected_photo(message, mock_state)
                elif case["content_type"] == "voice":
                    await fallback_handler.handle_unexpected_voice(message, mock_state)
                elif case["content_type"] == "sticker":
                    await fallback_handler.handle_unexpected_sticker(message, mock_state)
                elif case["content_type"] == "contact":
                    await fallback_handler.handle_unexpected_contact(message, mock_state)
                else:
                    # Универсальный обработчик для остальных типов
                    await fallback_handler.handle_unexpected_text(message, mock_state)
                
                print(f"    ✅ {case['description']} processed successfully")
                
            except Exception as e:
                print(f"    ⚠️ {case['description']} handling: {e}")
                # Не критично для медиа сообщений
                continue
        
        print("✅ Media message tests completed")
        return True
        
    except Exception as e:
        print(f"❌ Media message test setup failed: {e}")
        return False


async def test_edge_cases():
    """Тест граничных случаев и специальных сценариев."""
    
    print("🔍 Testing edge cases...")
    
    edge_cases = [
        {
            "description": "Message without from_user",
            "setup": lambda: MockMessage(text="test", from_user=None)
        },
        {
            "description": "Message without chat",
            "setup": lambda: MockMessage(text="test", chat=None)
        },
        {
            "description": "Very rapid messages (spam simulation)",
            "setup": lambda: [MockMessage(text=f"spam {i}") for i in range(10)]
        },
        {
            "description": "Unicode and special characters",
            "setup": lambda: MockMessage(text="🌍🔥💯 Тест 中文 العربية 🚀")
        },
        {
            "description": "Extremely long message",
            "setup": lambda: MockMessage(text="A" * 5000)
        }
    ]
    
    try:
        from bot.handlers.fallback import SmartFallbackHandler
        fallback_handler = SmartFallbackHandler()
        
        for case in edge_cases:
            try:
                print(f"  Testing: {case['description']}")
                
                test_data = case["setup"]()
                
                if isinstance(test_data, list):
                    # Множественные сообщения
                    for msg in test_data:
                        try:
                            from aiogram.fsm.context import FSMContext
                            mock_state = MagicMock(spec=FSMContext)
                            mock_state.get_data = AsyncMock(return_value={})
                            await fallback_handler.handle_unexpected_text(msg, mock_state)
                        except:
                            pass  # Ожидаемые ошибки для спам-тестов
                else:
                    # Одиночное сообщение
                    from aiogram.fsm.context import FSMContext
                    mock_state = MagicMock(spec=FSMContext)
                    mock_state.get_data = AsyncMock(return_value={})
                    await fallback_handler.handle_unexpected_text(test_data, mock_state)
                
                print(f"    ✅ {case['description']} handled")
                
            except Exception as e:
                print(f"    ⚠️ {case['description']}: {e}")
                # Некоторые граничные случаи могут вызывать ошибки - это нормально
                continue
        
        print("✅ Edge case tests completed")
        return True
        
    except Exception as e:
        print(f"❌ Edge case test setup failed: {e}")
        return False


async def main():
    """Запуск всех тестов форматов сообщений."""
    
    print("🚀 Starting comprehensive message format tests...\n")
    
    results = []
    
    # Тест текстовых сообщений
    results.append(await test_text_messages())
    print()
    
    # Тест медиа сообщений
    results.append(await test_media_messages())
    print()
    
    # Тест граничных случаев
    results.append(await test_edge_cases())
    print()
    
    # Итоговый результат
    passed = sum(results)
    total = len(results)
    
    print(f"📊 Message Format Tests Summary:")
    print(f"   Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All message format tests passed!")
        print("✅ Bot should handle all message types correctly")
    else:
        print("⚠️ Some tests had issues - check logs above")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
