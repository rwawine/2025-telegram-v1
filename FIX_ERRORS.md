🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ
1. Отсутствие валидации callback_data (64 байта)
Проблема: Telegram ограничивает callback_data до 64 байт, но валидации нет
Риск: Полное падение inline-кнопок с ошибкой API
Найдено в: bot/keyboards/main_menu.py, bot/smart_keyboards.py
2. Неполное покрытие callback handlers
Проблема: Есть inline кнопки без соответствующих обработчиков
Риск: "callback query is too old" ошибки
Найдены пропуски:
edit_name, edit_phone, edit_card, edit_photo (keyboards/main_menu.py:54-59)
confirm_registration, cancel_registration (keyboards/main_menu.py:62-65)
Некоторые info callbacks (info_rules, info_prizes, и др.)
3. Потенциальная гонка состояний в FSM
Проблема: В fallback_fixed.py регистрируются динамические handlers внутри методов
Риск: Дублирование или конфликт обработчиков
Код: _register_quick_nav_handlers() в строке 435
🟠 ВЫСОКИЙ ПРИОРИТЕТ
4. Inconsistent File Size Validation
Проблема: Валидация размера файлов не централизована
Места: registration.py:237, support.py:222 - разные подходы
Риск: Некоторые файлы могут пропустить валидацию
5. Missing Error Recovery in Database Operations
Проблема: В repositories.py нет retry логики для занятой БД
Риск: Потеря данных при высокой нагрузке
Код: insert_participants_batch() - только один rollback
6. Rate Limiting Too Lenient
Проблема: 8 событий за 2.5 секунды = очень мягко для спама
Риск: Успешные DDoS атаки через ботов
Файл: middleware/rate_limit.py:20
🟡 СРЕДНИЙ ПРИОРИТЕТ
7. Code Duplication in Handlers
Проблема: Дублированная логика проверки пользователя
Примеры:
get_participant_status() calls в 5+ местах
Дублированный error handling в registration/support
8. Non-Centralized Message Templates
Проблема: Сообщения разбросаны по коду вместо messages.py
Риск: Inconsistent UX, сложность локализации
Примеры: Hardcoded strings в fallback handlers
9. Missing Input Sanitization
Проблема: User input не sanitized перед сохранением в БД
Риск: Потенциальные SQL injections или XSS в админке
Файлы: validators.py - только format validation
🟢 НИЗКИЙ ПРИОРИТЕТ
10. Improvement Opportunities
Context manager sessions не персистентны (пропадают при перезапуске)
Отсутствие graceful shutdown для worker threads
Logs не структурированы (нет JSON format)
Некоторые keyboards можно кешировать