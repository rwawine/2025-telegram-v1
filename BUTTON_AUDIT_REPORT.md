# 🔍 ПОЛНЫЙ АУДИТ КНОПОК ПРОЕКТА

## 📋 **REPLY KEYBOARD BUTTONS**

### **Главное меню (адаптивное):**
| Кнопка | Состояние | Обработчик | Статус |
|--------|-----------|------------|--------|
| 🚀 Начать регистрацию | Незарегистрированный | ✅ `start_registration` | ✅ OK |
| 🔄 Подать заявку снова | Отклоненный | ✅ `start_registration` | ✅ OK |
| ⏳ Мой статус | На модерации | ✅ `status_handler` | ✅ OK |
| ✅ Мой статус | Одобренный | ✅ `status_handler` | ✅ OK |
| 📊 О розыгрыше | Все | ✅ `show_info_menu` | ✅ OK |
| 💬 Поддержка | Все | ✅ `open_support_menu` | ✅ OK |

### **Система поддержки:**
| Кнопка | Обработчик | Статус |
|--------|------------|--------|
| ❓ Частые вопросы | ✅ `show_faq` | ✅ OK |
| 📝 Написать сообщение | ✅ `ask_new_ticket` | ✅ OK |
| 📞 Мои обращения | ✅ `list_my_tickets` | ✅ OK |
| ⚡ Экстренная помощь | ✅ `handle_emergency_help` | ✅ OK |
| 🔧 Тех.поддержка | ✅ `handle_tech_support` | ✅ OK |

### **Создание тикета:**
| Кнопка | Обработчик | Статус |
|--------|------------|--------|
| 📷 Прикрепить фото | ✅ `handle_attach_photo` | ✅ OK |
| 📄 Прикрепить документ | ✅ `handle_attach_document` | ✅ OK |
| ✅ Отправить обращение | ✅ `handle_send_ticket` | ✅ OK |
| ⬅️ Изменить категорию | ✅ `handle_change_category` | ✅ OK |

### **Регистрация (навигация):**
| Кнопка | Обработчик | Статус |
|--------|------------|--------|
| ⬅️ Назад к имени | ✅ `back_to_name` | ✅ OK |
| ⬅️ Назад к телефону | ✅ `back_to_phone` | ✅ OK |
| ⬅️ Назад к карте | ✅ `back_to_card` | ✅ OK |
| 📞 Отправить мой номер | ✅ `handle_contact` | ✅ OK |
| 📷 Сделать фото | ✅ `ask_take_photo` | ✅ OK |
| 🖼️ Выбрать из галереи | ✅ `ask_choose_gallery` | ✅ OK |
| ❓ Что такое лифлет? | ✅ `explain_leaflet` | ✅ OK |

### **Статус проверка:**
| Кнопка | Обработчик | Статус |
|--------|------------|--------|
| 🔄 Обновить статус | ✅ `status_handler` | ✅ OK |
| 💬 Написать в поддержку | ✅ `open_support_menu` | ✅ OK |

### **Админские кнопки:**
| Кнопка | Обработчик | Статус |
|--------|------------|--------|
| 📊 Статистика | ❌ НЕТ | ⚠️ MISSING |
| 📤 Быстрый экспорт | ❌ НЕТ | ⚠️ MISSING |
| 🎲 Провести розыгрыш | ❌ НЕТ | ⚠️ MISSING |
| 📢 Создать рассылку | ❌ НЕТ | ⚠️ MISSING |
| 🌐 Открыть админку | ❌ НЕТ | ⚠️ MISSING |

---

## 📋 **INLINE KEYBOARD BUTTONS**

### **Редактирование регистрации:**
| Кнопка | callback_data | Обработчик | Статус |
|--------|---------------|------------|--------|
| ✏️ Изменить имя | edit_name | ✅ `handle_edit_name` | ✅ OK |
| ✏️ Изменить телефон | edit_phone | ✅ `handle_edit_phone` | ✅ OK |
| ✏️ Изменить карту | edit_card | ✅ `handle_edit_card` | ✅ OK |
| ✏️ Изменить фото | edit_photo | ✅ `handle_edit_photo` | ✅ OK |
| ✅ Все верно, зарегистрировать | confirm_registration | ✅ `handle_confirm_registration` | ✅ OK |
| ❌ Отменить регистрацию | cancel_registration | ✅ `handle_cancel_registration` | ✅ OK |

### **FAQ (Частые вопросы):**
| Кнопка | callback_data | Обработчик | Статус |
|--------|---------------|------------|--------|
| 📋 Как подать заявку? | faq_registration | ✅ `handle_faq_callback` | ✅ OK |
| 🕐 Когда будут результаты? | faq_results | ✅ `handle_faq_callback` | ✅ OK |
| 🏆 Что можно выиграть? | faq_prizes | ✅ `handle_faq_callback` | ✅ OK |
| 📱 Проблемы с фото | faq_photo | ✅ `handle_faq_callback` | ✅ OK |
| 💳 Вопросы по картам | faq_cards | ✅ `handle_faq_callback` | ✅ OK |
| 📞 Другой вопрос | create_ticket | ✅ `start_ticket_from_callback` | ✅ OK |

### **Информация о розыгрыше:**
| Кнопка | callback_data | Обработчик | Статус |
|--------|---------------|------------|--------|
| 📋 Правила участия | info_rules | ✅ `handle_info_callback` | ✅ OK |
| 🏆 Призы розыгрыша | info_prizes | ✅ `handle_info_callback` | ✅ OK |
| 📅 Сроки проведения | info_schedule | ✅ `handle_info_callback` | ✅ OK |
| ⚖️ Гарантии честности | info_fairness | ✅ `handle_info_callback` | ✅ OK |
| 📞 Контакты организаторов | info_contacts | ✅ `handle_info_callback` | ✅ OK |

### **Поддержка (навигация):**
| Кнопка | callback_data | Обработчик | Статус |
|--------|---------------|------------|--------|
| ⬅️ Вернуться к списку обращений | back_to_tickets | ✅ `back_to_tickets_list` | ✅ OK |
| ◀️ Назад к списку | back_to_tickets_list | ✅ `back_to_tickets_list` | ✅ OK |
| 💬 Ответить | reply_ticket_{id} | ❌ НЕТ | ⚠️ MISSING |

### **Категории поддержки:**
| Кнопка | callback_data | Обработчик | Статус |
|--------|---------------|------------|--------|
| cat_* (различные категории) | cat_* | ✅ `pick_category` | ✅ OK |
| view_ticket_* | view_ticket_* | ✅ `view_ticket_detail` | ✅ OK |

### **Быстрая навигация (fallback):**
| Кнопка | callback_data | Обработчик | Статус |
|--------|---------------|------------|--------|
| 🏠 Главное меню | quick_nav_main | ✅ `quick_nav_main` | ✅ OK |
| 🚀 К регистрации | quick_nav_register | ✅ `quick_nav_register` | ✅ OK |
| 💬 В поддержку | quick_nav_support | ✅ `quick_nav_support` | ✅ OK |
| ❌ Отменить все | quick_nav_cancel | ✅ `quick_nav_cancel` | ✅ OK |
| ❓ Помощь | quick_nav_help | ✅ `quick_nav_help` | ⚠️ ТОЛЬКО В fallback.py |

---

## 🔴 **НАЙДЕННЫЕ ПРОБЛЕМЫ:**

### **КРИТИЧЕСКИЕ:**
1. **Админские кнопки без обработчиков** - 5 кнопок
2. **Ответ на тикет** - кнопка "💬 Ответить" без обработчика

### **СРЕДНИЕ:**
1. **quick_nav_help** - есть только в старом fallback.py, но не в fallback_fixed.py
2. **Несоответствие callback_data** - "back_to_tickets" vs "back_to_tickets_list"

### **НИЗКИЕ:**
1. **Дублирование** - две версии fallback handlers
