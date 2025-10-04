"""Визуальный трекер прогресса регистрации."""

from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class RegistrationStep:
    """Информация о шаге регистрации."""
    number: int
    name: str
    icon: str
    description: str
    estimated_time: str


class ProgressTracker:
    """Система визуального отображения прогресса регистрации."""
    
    STEPS = [
        RegistrationStep(1, "Имя", "👤", "Введите ваше полное имя", "10 сек"),
        RegistrationStep(2, "Телефон", "📱", "Укажите контактный номер", "10 сек"),
        RegistrationStep(3, "Карта", "💳", "Номер карты лояльности", "20 сек"),
        RegistrationStep(4, "Фото", "📸", "Загрузите фото лифлета", "1 мин"),
    ]
    
    @classmethod
    def get_progress_message(
        cls,
        current_step: int,
        completed_steps: List[int] = None,
        show_next: bool = True
    ) -> str:
        """
        Создает визуальное сообщение о прогрессе.
        
        Args:
            current_step: Текущий шаг (1-4)
            completed_steps: Список завершенных шагов
            show_next: Показывать ли следующий шаг
            
        Returns:
            Отформатированное сообщение с прогрессом
        """
        if completed_steps is None:
            completed_steps = list(range(1, current_step))
        
        # Заголовок с процентами
        total = len(cls.STEPS)
        completed_count = len([s for s in completed_steps if s <= total])
        percentage = int((completed_count / total) * 100)
        
        message = f"📊 *Прогресс регистрации:* {percentage}%\n\n"
        
        # Визуальный прогресс-бар
        filled = int(percentage / 10)
        bar = "█" * filled + "░" * (10 - filled)
        message += f"┌{'─' * 12}┐\n"
        message += f"│ {bar} │\n"
        message += f"└{'─' * 12}┘\n\n"
        
        # Список шагов с чекбоксами
        message += "*Этапы регистрации:*\n"
        for step in cls.STEPS:
            if step.number < current_step or step.number in completed_steps:
                # Завершенный шаг
                status = "✅"
                text_style = "~"
            elif step.number == current_step:
                # Текущий шаг
                status = "▶️"
                text_style = "*"
            else:
                # Будущий шаг
                status = "⬜"
                text_style = ""
            
            if text_style:
                message += f"{status} {step.icon} {text_style}{step.name}{text_style} - {step.description}\n"
            else:
                message += f"{status} {step.icon} {step.name} - {step.description}\n"
        
        # Показываем текущий и следующий шаги
        message += f"\n*Сейчас:* {cls.STEPS[current_step - 1].icon} {cls.STEPS[current_step - 1].name}\n"
        
        if show_next and current_step < total:
            next_step = cls.STEPS[current_step]
            message += f"*Далее:* {next_step.icon} {next_step.name}\n"
        
        # Оставшееся время
        remaining_time = cls._calculate_remaining_time(current_step)
        if remaining_time:
            message += f"\n⏱ *Осталось:* ~{remaining_time}\n"
        
        return message
    
    @classmethod
    def get_compact_progress(cls, current_step: int, completed_steps: List[int] = None) -> str:
        """Компактная версия прогресса для встраивания в сообщения."""
        if completed_steps is None:
            completed_steps = list(range(1, current_step))
        
        total = len(cls.STEPS)
        completed_count = len([s for s in completed_steps if s <= total])
        percentage = int((completed_count / total) * 100)
        
        # Компактный прогресс-бар
        icons = []
        for step in cls.STEPS:
            if step.number < current_step or step.number in completed_steps:
                icons.append("✅")
            elif step.number == current_step:
                icons.append("▶️")
            else:
                icons.append("⬜")
        
        return f"{''.join(icons)} ({completed_count}/{total}) - {percentage}%"
    
    @classmethod
    def get_step_header(cls, step_number: int) -> str:
        """Заголовок для шага с прогрессом."""
        step = cls.STEPS[step_number - 1]
        progress = cls.get_compact_progress(step_number)
        
        return (
            f"{step.icon} *Шаг {step_number} из {len(cls.STEPS)}: {step.name}*\n"
            f"{progress}\n"
            f"⏱ Примерно {step.estimated_time}\n"
        )
    
    @classmethod
    def _calculate_remaining_time(cls, current_step: int) -> str:
        """Вычисляет примерное оставшееся время."""
        if current_step >= len(cls.STEPS):
            return ""
        
        # Суммируем время оставшихся шагов
        time_map = {
            "30 сек": 30,
            "20 сек": 20,
            "1 мин": 60
        }
        
        total_seconds = 0
        for step in cls.STEPS[current_step:]:
            total_seconds += time_map.get(step.estimated_time, 30)
        
        if total_seconds < 60:
            return f"{total_seconds} сек"
        else:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            if seconds == 0:
                return f"{minutes} мин"
            return f"{minutes} мин {seconds} сек"
    
    @classmethod
    def get_completion_summary(cls, registration_time_seconds: float = None) -> str:
        """Сообщение о завершении регистрации."""
        message = (
            "🎉 *Регистрация завершена!*\n\n"
            "✅ Все шаги пройдены:\n"
        )
        
        for step in cls.STEPS:
            message += f"✅ {step.icon} {step.name}\n"
        
        message += "\n"
        
        if registration_time_seconds:
            minutes = int(registration_time_seconds // 60)
            seconds = int(registration_time_seconds % 60)
            if minutes > 0:
                time_str = f"{minutes} мин {seconds} сек"
            else:
                time_str = f"{seconds} сек"
            message += f"⚡ Время регистрации: {time_str}\n\n"
        
        message += (
            "🎯 *Что дальше:*\n"
            "• Ваша заявка отправлена на модерацию\n"
            "• Вы получите уведомление о результате\n"
            "• Проверяйте статус: 📋 Мой статус\n\n"
            "⏰ Модерация обычно занимает до 24 часов\n\n"
            "🍀 *Удачи в розыгрыше!*"
        )
        
        return message
    
    @classmethod
    def can_go_back(cls, current_step: int) -> bool:
        """Проверяет, можно ли вернуться на предыдущий шаг."""
        return current_step > 1
    
    @classmethod
    def get_back_button_text(cls, current_step: int) -> str:
        """Текст кнопки возврата."""
        if current_step <= 1:
            return ""
        
        prev_step = cls.STEPS[current_step - 2]
        return f"◀️ Вернуться к {prev_step.name}"


# Глобальный экземпляр
progress_tracker = ProgressTracker()

