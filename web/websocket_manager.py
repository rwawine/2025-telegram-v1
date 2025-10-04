"""WebSocket менеджер для real-time обновлений админ-панели."""

from typing import Dict, Set, Optional, Any
from datetime import datetime
import json
import asyncio
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
from functools import wraps


class WebSocketManager:
    """
    Менеджер WebSocket соединений для real-time обновлений.
    
    Возможности:
    - Real-time обновление статистики
    - Live notifications о новых заявках
    - Показ онлайн администраторов
    - Индикатор редактирования записи
    - Синхронизация между вкладками
    """
    
    def __init__(self, socketio: SocketIO):
        """
        Инициализирует WebSocket менеджер.
        
        Args:
            socketio: Экземпляр Flask-SocketIO
        """
        self.socketio = socketio
        
        # Онлайн пользователи: {session_id: {username, connected_at}}
        self.online_users: Dict[str, Dict] = {}
        
        # Редактируемые сущности: {entity_type:entity_id: {username, session_id, started_at}}
        self.editing_entities: Dict[str, Dict] = {}
        
        # Комнаты для broadcast: {room_name: set(session_ids)}
        self.rooms: Dict[str, Set[str]] = {}
        
        # Регистрируем обработчики событий
        self._register_handlers()
    
    def _register_handlers(self):
        """Регистрирует обработчики WebSocket событий."""
        
        @self.socketio.on('connect')
        def handle_connect(auth):
            """Обработка подключения пользователя."""
            from flask import request, session
            from flask_login import current_user
            
            if not current_user.is_authenticated:
                return False  # Отклоняем неаутентифицированных
            
            session_id = request.sid
            username = current_user.username
            
            # Добавляем пользователя в онлайн
            self.online_users[session_id] = {
                'username': username,
                'connected_at': datetime.now().isoformat(),
                'rooms': set()
            }
            
            # Присоединяем к общей комнате
            join_room('admin_dashboard')
            self.online_users[session_id]['rooms'].add('admin_dashboard')
            
            # Уведомляем всех о новом пользователе
            self.broadcast_online_users()
            
            print(f"[WS] User {username} connected (session: {session_id})")
            
            return True
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Обработка отключения пользователя."""
            from flask import request
            
            session_id = request.sid
            
            if session_id in self.online_users:
                username = self.online_users[session_id]['username']
                
                # Освобождаем редактируемые сущности
                self._release_user_edits(session_id)
                
                # Удаляем из онлайн
                del self.online_users[session_id]
                
                # Уведомляем всех
                self.broadcast_online_users()
                
                print(f"[WS] User {username} disconnected (session: {session_id})")
        
        @self.socketio.on('join_room')
        def handle_join_room(data):
            """Присоединение к комнате."""
            from flask import request
            
            room_name = data.get('room')
            if room_name:
                session_id = request.sid
                join_room(room_name)
                
                if session_id in self.online_users:
                    self.online_users[session_id]['rooms'].add(room_name)
                
                print(f"[WS] Session {session_id} joined room {room_name}")
        
        @self.socketio.on('leave_room')
        def handle_leave_room(data):
            """Выход из комнаты."""
            from flask import request
            
            room_name = data.get('room')
            if room_name:
                session_id = request.sid
                leave_room(room_name)
                
                if session_id in self.online_users:
                    self.online_users[session_id]['rooms'].discard(room_name)
                
                print(f"[WS] Session {session_id} left room {room_name}")
        
        @self.socketio.on('start_editing')
        def handle_start_editing(data):
            """Начало редактирования сущности."""
            from flask import request
            from flask_login import current_user
            
            entity_type = data.get('entity_type')
            entity_id = data.get('entity_id')
            
            if entity_type and entity_id:
                session_id = request.sid
                username = current_user.username
                key = f"{entity_type}:{entity_id}"
                
                # Проверяем, не редактирует ли кто-то уже
                if key in self.editing_entities:
                    existing = self.editing_entities[key]
                    emit('editing_conflict', {
                        'entity_type': entity_type,
                        'entity_id': entity_id,
                        'editor': existing['username']
                    })
                    return
                
                # Помечаем как редактируемую
                self.editing_entities[key] = {
                    'username': username,
                    'session_id': session_id,
                    'started_at': datetime.now().isoformat()
                }
                
                # Уведомляем других в этой комнате
                self.socketio.emit('entity_being_edited', {
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'editor': username
                }, room=f"{entity_type}s", include_self=False)
                
                print(f"[WS] {username} started editing {entity_type}:{entity_id}")
        
        @self.socketio.on('stop_editing')
        def handle_stop_editing(data):
            """Окончание редактирования сущности."""
            entity_type = data.get('entity_type')
            entity_id = data.get('entity_id')
            
            if entity_type and entity_id:
                key = f"{entity_type}:{entity_id}"
                
                if key in self.editing_entities:
                    username = self.editing_entities[key]['username']
                    del self.editing_entities[key]
                    
                    # Уведомляем других
                    self.socketio.emit('entity_released', {
                        'entity_type': entity_type,
                        'entity_id': entity_id
                    }, room=f"{entity_type}s", include_self=False)
                    
                    print(f"[WS] {username} stopped editing {entity_type}:{entity_id}")
        
        @self.socketio.on('request_sync')
        def handle_request_sync():
            """Запрос синхронизации состояния."""
            from flask import request
            
            session_id = request.sid
            
            # Отправляем текущее состояние
            emit('sync_state', {
                'online_users': self._get_online_users_list(),
                'editing_entities': self._get_editing_entities_list(),
                'timestamp': datetime.now().isoformat()
            })
    
    def _release_user_edits(self, session_id: str):
        """Освобождает все редактируемые сущности пользователя."""
        to_release = []
        
        for key, edit_info in self.editing_entities.items():
            if edit_info['session_id'] == session_id:
                to_release.append(key)
        
        for key in to_release:
            entity_type, entity_id = key.split(':', 1)
            del self.editing_entities[key]
            
            # Уведомляем других
            self.socketio.emit('entity_released', {
                'entity_type': entity_type,
                'entity_id': entity_id
            }, room=f"{entity_type}s")
    
    def _get_online_users_list(self) -> list:
        """Получает список онлайн пользователей."""
        return [
            {
                'username': info['username'],
                'connected_at': info['connected_at']
            }
            for info in self.online_users.values()
        ]
    
    def _get_editing_entities_list(self) -> list:
        """Получает список редактируемых сущностей."""
        result = []
        for key, edit_info in self.editing_entities.items():
            entity_type, entity_id = key.split(':', 1)
            result.append({
                'entity_type': entity_type,
                'entity_id': entity_id,
                'editor': edit_info['username'],
                'started_at': edit_info['started_at']
            })
        return result
    
    def broadcast_online_users(self):
        """Рассылает обновленный список онлайн пользователей."""
        self.socketio.emit('online_users_update', {
            'users': self._get_online_users_list(),
            'count': len(self.online_users),
            'timestamp': datetime.now().isoformat()
        }, room='admin_dashboard')
    
    def broadcast_stats_update(self, stats: Dict[str, Any]):
        """
        Рассылает обновление статистики в real-time.
        
        Args:
            stats: Словарь со статистикой
        """
        self.socketio.emit('stats_update', {
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        }, room='admin_dashboard')
    
    def broadcast_new_participant(self, participant_data: Dict[str, Any]):
        """
        Уведомляет о новом участнике.
        
        Args:
            participant_data: Данные участника
        """
        self.socketio.emit('new_participant', {
            'participant': participant_data,
            'timestamp': datetime.now().isoformat()
        }, room='admin_dashboard')
    
    def broadcast_participant_updated(
        self,
        participant_id: int,
        old_status: str,
        new_status: str,
        updated_by: str
    ):
        """
        Уведомляет об изменении статуса участника.
        
        Args:
            participant_id: ID участника
            old_status: Старый статус
            new_status: Новый статус
            updated_by: Кто изменил
        """
        self.socketio.emit('participant_updated', {
            'participant_id': participant_id,
            'old_status': old_status,
            'new_status': new_status,
            'updated_by': updated_by,
            'timestamp': datetime.now().isoformat()
        }, room='admin_dashboard')
    
    def broadcast_new_support_ticket(self, ticket_data: Dict[str, Any]):
        """
        Уведомляет о новом тикете поддержки.
        
        Args:
            ticket_data: Данные тикета
        """
        self.socketio.emit('new_support_ticket', {
            'ticket': ticket_data,
            'timestamp': datetime.now().isoformat()
        }, room='admin_dashboard')
    
    def notify_user(self, username: str, message: str, type: str = 'info'):
        """
        Отправляет уведомление конкретному пользователю.
        
        Args:
            username: Имя пользователя
            message: Текст сообщения
            type: Тип уведомления (info, success, warning, error)
        """
        # Находим все сессии пользователя
        for session_id, user_info in self.online_users.items():
            if user_info['username'] == username:
                self.socketio.emit('notification', {
                    'message': message,
                    'type': type,
                    'timestamp': datetime.now().isoformat()
                }, room=session_id)
    
    def broadcast_to_room(self, room: str, event: str, data: Dict[str, Any]):
        """
        Отправляет событие в комнату.
        
        Args:
            room: Название комнаты
            event: Название события
            data: Данные события
        """
        self.socketio.emit(event, data, room=room)
    
    def get_online_count(self) -> int:
        """Возвращает количество онлайн пользователей."""
        return len(self.online_users)
    
    def is_entity_being_edited(self, entity_type: str, entity_id: int) -> Optional[Dict]:
        """
        Проверяет, редактируется ли сущность.
        
        Args:
            entity_type: Тип сущности
            entity_id: ID сущности
            
        Returns:
            Информация о редакторе или None
        """
        key = f"{entity_type}:{entity_id}"
        return self.editing_entities.get(key)
    
    def start_background_tasks(self):
        """Запускает фоновые задачи для WebSocket."""
        
        def send_periodic_stats():
            """Периодически отправляет обновления статистики."""
            while True:
                self.socketio.sleep(30)  # Каждые 30 секунд
                
                # Получаем свежую статистику
                try:
                    import asyncio
                    from services.advanced_analytics_service import advanced_analytics_service
                    
                    # Запускаем в event loop
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    stats = loop.run_until_complete(
                        advanced_analytics_service.get_real_time_stats()
                    )
                    loop.close()
                    
                    # Отправляем обновление
                    self.broadcast_stats_update(stats)
                except Exception as e:
                    print(f"[WS] Error sending periodic stats: {e}")
        
        # Запускаем в фоновом потоке
        self.socketio.start_background_task(send_periodic_stats)
        print("[WS] Background tasks started")


# Глобальный экземпляр (будет инициализирован в app.py)
websocket_manager: Optional[WebSocketManager] = None


def init_websocket_manager(socketio: SocketIO) -> WebSocketManager:
    """
    Инициализирует WebSocket менеджер.
    
    Args:
        socketio: Экземпляр Flask-SocketIO
        
    Returns:
        Инициализированный WebSocketManager
    """
    global websocket_manager
    websocket_manager = WebSocketManager(socketio)
    websocket_manager.start_background_tasks()
    return websocket_manager


def get_websocket_manager() -> WebSocketManager:
    """Получает глобальный экземпляр WebSocketManager."""
    if websocket_manager is None:
        raise RuntimeError("WebSocketManager not initialized. Call init_websocket_manager first.")
    return websocket_manager

