"""Централизованная валидация файлов для всех модулей."""

import logging
from pathlib import Path
from typing import Optional, Tuple, Union

from aiogram.types import PhotoSize, Document

logger = logging.getLogger(__name__)

# Константы лимитов (берем из config, но с fallback)
DEFAULT_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
SUPPORTED_IMAGE_TYPES = ['.jpg', '.jpeg', '.png', '.webp']
SUPPORTED_DOCUMENT_TYPES = ['.pdf', '.doc', '.docx', '.txt']


class FileValidationError(Exception):
    """Ошибка валидации файла."""
    pass


def get_max_file_size() -> int:
    """Получить лимит размера файла из конфигурации."""
    try:
        from config import load_config
        return load_config().max_file_size
    except Exception:
        logger.warning("Failed to load max_file_size from config, using default")
        return DEFAULT_MAX_FILE_SIZE


def validate_file_size(file_size: Optional[int], file_type: str = "file") -> None:
    """
    Валидирует размер файла.
    
    Args:
        file_size: Размер файла в байтах
        file_type: Тип файла для сообщения об ошибке
        
    Raises:
        FileValidationError: Если файл слишком большой
    """
    if not file_size:
        return  # Telegram не всегда предоставляет размер
    
    max_size = get_max_file_size()
    
    if file_size > max_size:
        max_mb = max_size // (1024 * 1024)
        current_mb = file_size // (1024 * 1024)
        raise FileValidationError(
            f"📁 {file_type.capitalize()} слишком большой ({current_mb} МБ). "
            f"Максимальный размер: {max_mb} МБ."
        )


def validate_image_file(photo: Union[PhotoSize, list[PhotoSize]]) -> PhotoSize:
    """
    Валидирует изображение от пользователя.
    
    Args:
        photo: PhotoSize или список PhotoSize от Telegram
        
    Returns:
        PhotoSize: Наибольший размер фото
        
    Raises:
        FileValidationError: Если фото не прошло валидацию
    """
    if not photo:
        raise FileValidationError("📸 Фото не получено")
    
    # Если список - берем наибольший размер
    if isinstance(photo, list):
        if not photo:
            raise FileValidationError("📸 Фото не получено")
        largest_photo = max(photo, key=lambda p: p.file_size or 0)
    else:
        largest_photo = photo
    
    # Валидируем размер
    validate_file_size(largest_photo.file_size, "фото")
    
    return largest_photo


def validate_document_file(document: Document) -> Document:
    """
    Валидирует документ от пользователя.
    
    Args:
        document: Document от Telegram
        
    Returns:
        Document: Валидный документ
        
    Raises:
        FileValidationError: Если документ не прошел валидацию
    """
    if not document:
        raise FileValidationError("📄 Документ не получен")
    
    # Валидируем размер
    validate_file_size(document.file_size, "документ")
    
    # Валидируем тип файла (опционально)
    if document.file_name:
        file_path = Path(document.file_name)
        file_ext = file_path.suffix.lower()
        
        # Проверяем только если есть ограничения по типам
        # (можно расширить в будущем)
        if file_ext and len(file_ext) > 10:  # Подозрительное расширение
            logger.warning(f"Suspicious file extension: {file_ext}")
    
    return document


def get_safe_filename(original_name: Optional[str], file_id: str) -> str:
    """
    Создает безопасное имя файла.
    
    Args:
        original_name: Оригинальное имя файла
        file_id: ID файла в Telegram
        
    Returns:
        str: Безопасное имя файла
    """
    if not original_name:
        return f"{file_id}.unknown"
    
    # Очищаем имя файла от опасных символов
    safe_name = "".join(c for c in original_name if c.isalnum() or c in ".-_")
    
    # Ограничиваем длину
    if len(safe_name) > 100:
        path = Path(safe_name)
        name_part = path.stem[:80]
        ext_part = path.suffix[:20]
        safe_name = f"{name_part}{ext_part}"
    
    # Добавляем file_id для уникальности
    path = Path(safe_name)
    return f"{file_id}_{path.stem}{path.suffix}"


def format_file_size(size_bytes: int) -> str:
    """
    Форматирует размер файла в человекочитаемый вид.
    
    Args:
        size_bytes: Размер в байтах
        
    Returns:
        str: Отформатированный размер
    """
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} КБ"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} МБ"


class FileValidator:
    """Класс для валидации файлов с кешированием настроек."""
    
    def __init__(self):
        self._max_size = None
        self._last_config_check = 0
    
    def _update_limits(self):
        """Обновляет лимиты из конфигурации."""
        import time
        now = time.time()
        
        # Проверяем конфиг раз в минуту
        if now - self._last_config_check > 60:
            self._max_size = get_max_file_size()
            self._last_config_check = now
    
    def validate_photo(self, photo: Union[PhotoSize, list[PhotoSize]]) -> Tuple[PhotoSize, str]:
        """
        Валидирует фото и возвращает результат с сообщением.
        
        Returns:
            Tuple[PhotoSize, str]: (фото, сообщение об успехе/ошибке)
        """
        try:
            self._update_limits()
            validated_photo = validate_image_file(photo)
            size_str = format_file_size(validated_photo.file_size or 0)
            return validated_photo, f"✅ Фото принято ({size_str})"
        except FileValidationError as e:
            return None, str(e)
    
    def validate_document(self, document: Document) -> Tuple[Optional[Document], str]:
        """
        Валидирует документ и возвращает результат с сообщением.
        
        Returns:
            Tuple[Optional[Document], str]: (документ, сообщение об успехе/ошибке)
        """
        try:
            self._update_limits()
            validated_doc = validate_document_file(document)
            size_str = format_file_size(validated_doc.file_size or 0)
            return validated_doc, f"✅ Документ принят ({size_str})"
        except FileValidationError as e:
            return None, str(e)


# Глобальный экземпляр валидатора
file_validator = FileValidator()
