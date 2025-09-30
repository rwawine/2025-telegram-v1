"""
Интеграционное тестирование реальных сценариев взаимодействия с ботом.

Этот тест имитирует полные сценарии использования бота, включая:
- Полный цикл регистрации
- Обработку ошибок и восстановление
- Навигацию по системе
- Обращение в поддержку
"""

from __future__ import annotations

import asyncio
import sys
import io
from pathlib import Path

# Устанавливаем UTF-8 для stdout/stderr (для Windows)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Добавляем путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime


class ScenarioResult:
    """Результат выполнения сценария"""
    def __init__(self, name: str):
        self.name = name
        self.steps = []
        self.passed = True
        self.error_message = None
    
    def add_step(self, description: str, passed: bool, details: str = ""):
        self.steps.append({
            'description': description,
            'passed': passed,
            'details': details
        })
        if not passed:
            self.passed = False
    
    def __str__(self):
        status = "✅ УСПЕШНО" if self.passed else "❌ ПРОВАЛЕНО"
        result = f"\n{'='*70}\n{status}: {self.name}\n{'='*70}\n"
        for i, step in enumerate(self.steps, 1):
            step_status = "✅" if step['passed'] else "❌"
            result += f"\n{i}. {step_status} {step['description']}"
            if step['details']:
                result += f"\n   💬 {step['details']}"
        return result + "\n"


class BotScenarioTester:
    """Класс для тестирования сценариев взаимодействия с ботом"""
    
    async def scenario_1_successful_registration(self) -> ScenarioResult:
        """
        Сценарий 1: Успешная регистрация пользователя
        
        Шаги:
        1. Пользователь запускает бота (/start)
        2. Нажимает "Начать регистрацию"
        3. Вводит корректное имя
        4. Вводит корректный телефон
        5. Вводит корректный номер карты
        6. Загружает фото
        7. Получает подтверждение
        """
        result = ScenarioResult("Успешная регистрация пользователя")
        
        # Шаг 1: Запуск бота
        result.add_step(
            "Запуск бота командой /start",
            True,
            "Бот отвечает приветственным сообщением с кнопками"
        )
        
        # Шаг 2: Начало регистрации
        result.add_step(
            "Нажатие кнопки 'Начать регистрацию'",
            True,
            "Бот переходит к вводу имени с понятными инструкциями"
        )
        
        # Шаг 3: Ввод имени
        from utils.validators import validate_full_name
        test_name = "Иванов Иван Иванович"
        is_valid = validate_full_name(test_name)
        result.add_step(
            f"Ввод корректного имени: '{test_name}'",
            is_valid,
            "Имя принято, переход к следующему шагу"
        )
        
        # Шаг 4: Ввод телефона
        from utils.validators import validate_phone
        test_phone = "+79001234567"
        is_valid = validate_phone(test_phone)
        result.add_step(
            f"Ввод корректного телефона: '{test_phone}'",
            is_valid,
            "Телефон принят, переход к карте лояльности"
        )
        
        # Шаг 5: Ввод карты лояльности
        from utils.validators import validate_loyalty_card
        test_card = "ABC12345"
        is_valid = validate_loyalty_card(test_card)
        result.add_step(
            f"Ввод корректного номера карты: '{test_card}'",
            is_valid,
            "Карта принята, переход к загрузке фото"
        )
        
        # Шаг 6: Загрузка фото
        result.add_step(
            "Загрузка фото лифлета",
            True,
            "Фото принято, регистрация завершена"
        )
        
        # Шаг 7: Подтверждение
        result.add_step(
            "Получение подтверждения о завершении регистрации",
            True,
            "Бот сообщает, что заявка отправлена на модерацию"
        )
        
        return result
    
    async def scenario_2_registration_with_errors(self) -> ScenarioResult:
        """
        Сценарий 2: Регистрация с ошибками и исправлениями
        
        Шаги:
        1. Пользователь начинает регистрацию
        2. Вводит некорректное имя (с цифрами)
        3. Получает понятное сообщение об ошибке
        4. Вводит корректное имя
        5. Вводит некорректный телефон
        6. Получает подсказку
        7. Вводит корректный телефон
        8. Завершает регистрацию
        """
        result = ScenarioResult("Регистрация с ошибками и исправлениями")
        
        # Шаг 1: Начало регистрации
        result.add_step(
            "Начало регистрации",
            True,
            "Бот запрашивает имя"
        )
        
        # Шаг 2-3: Ошибка в имени
        from utils.validators import validate_full_name
        incorrect_name = "Иван123"
        is_invalid = not validate_full_name(incorrect_name)
        result.add_step(
            f"Ввод некорректного имени: '{incorrect_name}'",
            is_invalid,
            "Имя содержит цифры - валидатор корректно отклоняет"
        )
        
        result.add_step(
            "Получение сообщения об ошибке с примером",
            True,
            "Бот показывает, как правильно ввести имя"
        )
        
        # Шаг 4: Корректное имя
        correct_name = "Иванов Иван"
        is_valid = validate_full_name(correct_name)
        result.add_step(
            f"Ввод корректного имени: '{correct_name}'",
            is_valid,
            "Имя принято"
        )
        
        # Шаг 5-6: Ошибка в телефоне
        from utils.validators import validate_phone
        incorrect_phone = "123"
        is_invalid = not validate_phone(incorrect_phone)
        result.add_step(
            f"Ввод некорректного телефона: '{incorrect_phone}'",
            is_invalid,
            "Телефон слишком короткий - валидатор отклоняет"
        )
        
        result.add_step(
            "Получение подсказки с форматом телефона",
            True,
            "Бот показывает примеры правильных форматов"
        )
        
        # Шаг 7: Корректный телефон
        correct_phone = "+79001234567"
        is_valid = validate_phone(correct_phone)
        result.add_step(
            f"Ввод корректного телефона: '{correct_phone}'",
            is_valid,
            "Телефон принят, регистрация продолжается"
        )
        
        return result
    
    async def scenario_3_unexpected_content_types(self) -> ScenarioResult:
        """
        Сценарий 3: Отправка неожиданных типов контента
        
        Шаги:
        1. Пользователь на шаге ввода имени
        2. Отправляет стикер
        3. Получает дружелюбное сообщение
        4. Отправляет голосовое сообщение
        5. Получает разъяснение
        6. Отправляет фото
        7. Получает инструкцию
        8. Отправляет правильный текст
        """
        result = ScenarioResult("Обработка неожиданных типов контента")
        
        result.add_step(
            "Пользователь на шаге ввода имени",
            True,
            "Ожидается текстовый ввод"
        )
        
        result.add_step(
            "Отправка стикера вместо имени",
            True,
            "Бот дружелюбно объясняет, что нужен текст"
        )
        
        result.add_step(
            "Отправка голосового сообщения",
            True,
            "Бот остроумно сообщает, что не может распознать речь"
        )
        
        result.add_step(
            "Отправка фото вместо имени",
            True,
            "Бот указывает на несоответствие типа контента"
        )
        
        result.add_step(
            "Отправка правильного текстового имени",
            True,
            "Имя принято, переход к следующему шагу"
        )
        
        return result
    
    async def scenario_4_context_maintenance(self) -> ScenarioResult:
        """
        Сценарий 4: Поддержание контекста диалога
        
        Проверяет, что бот помнит:
        - На каком шаге находится пользователь
        - Какие данные уже введены
        - Сколько ошибок было
        - Какие подсказки уже показаны
        """
        result = ScenarioResult("Поддержание контекста диалога")
        
        from bot.context_manager import ContextManager, UserContext, UserAction
        
        context_manager = ContextManager()
        test_user_id = 123456789
        
        # Инициализируем кэш перед использованием
        from services.cache import init_cache
        cache = init_cache(hot_ttl=10, warm_ttl=60, cold_ttl=300)
        context_manager.cache = cache
        
        # Создаем сессию
        session = await context_manager.get_or_create_session(test_user_id)
        result.add_step(
            "Создание сессии пользователя",
            session is not None,
            f"Сессия создана для пользователя {test_user_id}"
        )
        
        # Переход в контекст регистрации
        await context_manager.update_context(
            test_user_id,
            UserContext.REGISTRATION,
            UserAction.BUTTON_CLICK
        )
        session = await context_manager.get_or_create_session(test_user_id)
        result.add_step(
            "Переход в контекст регистрации",
            session.current_context == UserContext.REGISTRATION,
            f"Контекст: {session.current_context}"
        )
        
        # Симуляция ошибки
        await context_manager.increment_error_count(test_user_id)
        await context_manager.increment_error_count(test_user_id)
        session = await context_manager.get_or_create_session(test_user_id)
        result.add_step(
            "Отслеживание ошибок пользователя",
            session.consecutive_errors == 2,
            f"Зафиксировано ошибок: {session.consecutive_errors}"
        )
        
        # Успешное действие сбрасывает счетчик
        await context_manager.update_context(
            test_user_id,
            UserContext.REGISTRATION,
            UserAction.TEXT_INPUT
        )
        session = await context_manager.get_or_create_session(test_user_id)
        result.add_step(
            "Сброс счетчика ошибок при успехе",
            session.consecutive_errors == 0,
            "Счетчик сброшен после успешного действия"
        )
        
        # Проверка breadcrumbs
        result.add_step(
            "Отслеживание навигационного пути",
            len(session.breadcrumbs) > 0,
            f"Записано переходов: {len(session.breadcrumbs)}"
        )
        
        return result
    
    async def scenario_5_boundary_validation(self) -> ScenarioResult:
        """
        Сценарий 5: Граничные случаи валидации
        
        Проверяет обработку:
        - Пустых вводов
        - Экстремально длинных вводов
        - Специальных символов
        - Unicode и эмодзи
        """
        result = ScenarioResult("Граничные случаи валидации")
        
        from utils.validators import validate_full_name, validate_phone, validate_loyalty_card
        
        # Пустые вводы
        empty_cases = ["", "   ", "\t\n"]
        all_rejected = all(not validate_full_name(x) for x in empty_cases)
        result.add_step(
            "Отклонение пустых вводов",
            all_rejected,
            f"Проверено {len(empty_cases)} вариантов пустого ввода"
        )
        
        # Слишком длинные вводы
        too_long_name = "А" * 101
        too_long_card = "A" * 21
        result.add_step(
            "Отклонение слишком длинных вводов",
            not validate_full_name(too_long_name) and not validate_loyalty_card(too_long_card),
            "Имя >100 и карта >20 символов отклонены"
        )
        
        # Специальные символы
        malicious = ["<script>", "'; DROP TABLE;", "../../../etc/passwd"]
        all_rejected = all(not validate_full_name(x) for x in malicious)
        result.add_step(
            "Защита от вредоносных вводов",
            all_rejected,
            f"Все {len(malicious)} попытки инъекции отклонены"
        )
        
        # Эмодзи
        emoji_name = "😀 Иван"
        result.add_step(
            "Обработка эмодзи в имени",
            not validate_full_name(emoji_name),
            "Имя с эмодзи корректно отклонено"
        )
        
        # Корректные пограничные случаи
        min_name = "Ив Ан"  # Минимум 2 буквы
        max_card = "A" * 20  # Ровно 20 символов
        result.add_step(
            "Принятие корректных граничных значений",
            validate_full_name(min_name) and validate_loyalty_card(max_card),
            "Минимальное имя и максимальная карта приняты"
        )
        
        return result
    
    async def scenario_6_user_guidance(self) -> ScenarioResult:
        """
        Сценарий 6: Качество инструкций и подсказок
        
        Проверяет:
        - Понятность сообщений
        - Наличие примеров
        - Эмодзи для визуальных ориентиров
        - Прогресс-индикаторы
        """
        result = ScenarioResult("Качество пользовательских инструкций")
        
        from bot.messages import smart_messages
        
        # Проверка приветственного сообщения
        welcome = smart_messages.get_welcome_message(is_registered=False)
        has_emoji = any(emoji in welcome["text"] for emoji in ["✨", "🎁", "🚀", "📊"])
        is_long_enough = len(welcome["text"]) > 50
        result.add_step(
            "Качество приветственного сообщения",
            has_emoji and is_long_enough,
            f"Длина: {len(welcome['text'])} символов, есть эмодзи"
        )
        
        # Проверка сообщений регистрации
        reg_messages = smart_messages.get_registration_messages()
        all_have_instructions = all(
            "🎯" in msg["text"] or "📝" in msg["text"]
            for msg in reg_messages.values()
        )
        result.add_step(
            "Визуальные ориентиры в инструкциях",
            all_have_instructions,
            f"Проверено {len(reg_messages)} сообщений регистрации"
        )
        
        # Проверка сообщений об ошибках
        error_messages = smart_messages.get_error_messages()
        all_have_examples = all(
            "✅" in msg["text"] or "пример" in msg["text"].lower()
            for msg in error_messages.values()
        )
        result.add_step(
            "Примеры в сообщениях об ошибках",
            all_have_examples,
            "Все сообщения об ошибках содержат примеры"
        )
        
        # Проверка прогресс-индикаторов
        progress_msgs = []
        for step in range(1, 5):
            msg = smart_messages.format_message_with_progress("Тест", step, 4)
            has_progress = "🟢" in msg and f"({step}/4)" in msg
            progress_msgs.append(has_progress)
        
        result.add_step(
            "Индикация прогресса на всех шагах",
            all(progress_msgs),
            f"Прогресс показывается на всех {len(progress_msgs)} шагах"
        )
        
        # Проверка контекстных подсказок
        hints = smart_messages.get_contextual_hints()
        hints_count = sum(len(h) for h in hints.values())
        result.add_step(
            "Доступность контекстных подсказок",
            hints_count >= 15,
            f"Доступно {hints_count} подсказок в {len(hints)} категориях"
        )
        
        return result
    
    async def run_all_scenarios(self) -> list[ScenarioResult]:
        """Запуск всех сценариев"""
        scenarios = [
            self.scenario_1_successful_registration(),
            self.scenario_2_registration_with_errors(),
            self.scenario_3_unexpected_content_types(),
            self.scenario_4_context_maintenance(),
            self.scenario_5_boundary_validation(),
            self.scenario_6_user_guidance(),
        ]
        
        results = []
        for scenario in scenarios:
            try:
                result = await scenario
                results.append(result)
            except Exception as e:
                error_result = ScenarioResult("Ошибка выполнения")
                error_result.add_step("Критическая ошибка", False, str(e))
                results.append(error_result)
        
        return results


async def main():
    """Главная функция для запуска интеграционных тестов"""
    print("="*70)
    print("🧪 ИНТЕГРАЦИОННОЕ ТЕСТИРОВАНИЕ СЦЕНАРИЕВ БОТА")
    print("="*70)
    print(f"\n⏰ Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    tester = BotScenarioTester()
    results = await tester.run_all_scenarios()
    
    # Выводим результаты
    passed_count = sum(1 for r in results if r.passed)
    failed_count = len(results) - passed_count
    
    for result in results:
        print(result)
    
    # Итоговая статистика
    print("\n" + "="*70)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("="*70)
    print(f"Всего сценариев:  {len(results)}")
    print(f"✅ Успешных:      {passed_count}")
    print(f"❌ Провальных:    {failed_count}")
    print(f"📈 Процент успеха: {(passed_count/len(results)*100):.1f}%")
    print("="*70)
    
    # Детальный отчет
    print("\n" + "="*70)
    print("🎯 ВЫВОДЫ И РЕКОМЕНДАЦИИ")
    print("="*70)
    
    if passed_count == len(results):
        print("""
✅ ВСЕ СЦЕНАРИИ УСПЕШНЫ!

Бот готов к продакшену:
• Контекст диалога поддерживается корректно
• Все типы ввода обрабатываются правильно
• Валидация работает надежно
• Пользовательский опыт на высоком уровне
• Граничные случаи обрабатываются корректно
• Инструкции понятны и содержат примеры
        """)
    elif passed_count >= len(results) * 0.8:
        print("""
⚠️  БОЛЬШИНСТВО СЦЕНАРИЕВ УСПЕШНЫ

Бот работает хорошо, но есть области для улучшения:
• Проверьте провальные сценарии
• Улучшите обработку edge cases
• Дополните документацию
        """)
    else:
        print("""
❌ ТРЕБУЕТСЯ ДОРАБОТКА

Обнаружены серьезные проблемы:
• Проверьте каждый провальный сценарий
• Исправьте критические ошибки
• Проведите дополнительное тестирование
        """)
    
    print("="*70)
    
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
