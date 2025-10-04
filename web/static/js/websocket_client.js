/**
 * WebSocket клиент для real-time обновлений админ-панели.
 * 
 * Использует Socket.IO для WebSocket соединения с graceful fallback на long-polling.
 */

class WebSocketClient {
    constructor() {
        this.socket = null;
        this.connected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000; // 1 секунда
        this.currentRoom = null;
        this.editingEntity = null;
        
        // Callbacks
        this.onStatsUpdate = null;
        this.onNewParticipant = null;
        this.onParticipantUpdated = null;
        this.onNewSupportTicket = null;
        this.onOnlineUsersUpdate = null;
        this.onNotification = null;
        this.onEntityBeingEdited = null;
        this.onEntityReleased = null;
        
        this.init();
    }
    
    /**
     * Инициализирует WebSocket соединение.
     */
    init() {
        console.log('[WS] Initializing WebSocket connection...');
        
        // Подключаемся к Socket.IO
        this.socket = io({
            transports: ['websocket', 'polling'], // WebSocket с fallback на polling
            reconnection: true,
            reconnectionDelay: this.reconnectDelay,
            reconnectionAttempts: this.maxReconnectAttempts
        });
        
        this.registerEventHandlers();
    }
    
    /**
     * Регистрирует обработчики событий.
     */
    registerEventHandlers() {
        // Подключение
        this.socket.on('connect', () => {
            console.log('[WS] Connected to server');
            this.connected = true;
            this.reconnectAttempts = 0;
            this.showConnectionStatus('connected');
            
            // Запрашиваем синхронизацию состояния
            this.requestSync();
            
            // Повторно присоединяемся к комнате если была
            if (this.currentRoom) {
                this.joinRoom(this.currentRoom);
            }
            
            // Восстанавливаем редактирование если было
            if (this.editingEntity) {
                const { type, id } = this.editingEntity;
                this.startEditing(type, id);
            }
        });
        
        // Отключение
        this.socket.on('disconnect', (reason) => {
            console.log('[WS] Disconnected:', reason);
            this.connected = false;
            this.showConnectionStatus('disconnected');
        });
        
        // Ошибка подключения
        this.socket.on('connect_error', (error) => {
            console.error('[WS] Connection error:', error);
            this.reconnectAttempts++;
            
            if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                console.error('[WS] Max reconnect attempts reached. Falling back to polling.');
                this.showConnectionStatus('error');
                this.startPolling();
            }
        });
        
        // Обновление статистики
        this.socket.on('stats_update', (data) => {
            console.log('[WS] Stats update received');
            if (this.onStatsUpdate) {
                this.onStatsUpdate(data.stats);
            }
            this.updateDashboardStats(data.stats);
        });
        
        // Новый участник
        this.socket.on('new_participant', (data) => {
            console.log('[WS] New participant:', data.participant);
            if (this.onNewParticipant) {
                this.onNewParticipant(data.participant);
            }
            this.showNotification('Новый участник зарегистрирован!', 'info');
        });
        
        // Обновление участника
        this.socket.on('participant_updated', (data) => {
            console.log('[WS] Participant updated:', data);
            if (this.onParticipantUpdated) {
                this.onParticipantUpdated(data);
            }
            this.updateParticipantRow(data);
        });
        
        // Новый тикет поддержки
        this.socket.on('new_support_ticket', (data) => {
            console.log('[WS] New support ticket:', data.ticket);
            if (this.onNewSupportTicket) {
                this.onNewSupportTicket(data.ticket);
            }
            this.showNotification('Новое обращение в поддержку!', 'warning');
        });
        
        // Обновление онлайн пользователей
        this.socket.on('online_users_update', (data) => {
            console.log('[WS] Online users update:', data.count, 'users');
            if (this.onOnlineUsersUpdate) {
                this.onOnlineUsersUpdate(data.users);
            }
            this.updateOnlineUsers(data);
        });
        
        // Уведомление
        this.socket.on('notification', (data) => {
            console.log('[WS] Notification:', data.message);
            if (this.onNotification) {
                this.onNotification(data);
            }
            this.showNotification(data.message, data.type);
        });
        
        // Сущность редактируется
        this.socket.on('entity_being_edited', (data) => {
            console.log('[WS] Entity being edited:', data);
            if (this.onEntityBeingEdited) {
                this.onEntityBeingEdited(data);
            }
            this.showEditingIndicator(data);
        });
        
        // Сущность освобождена
        this.socket.on('entity_released', (data) => {
            console.log('[WS] Entity released:', data);
            if (this.onEntityReleased) {
                this.onEntityReleased(data);
            }
            this.hideEditingIndicator(data);
        });
        
        // Конфликт редактирования
        this.socket.on('editing_conflict', (data) => {
            console.warn('[WS] Editing conflict:', data);
            this.showNotification(
                `Эту запись уже редактирует ${data.editor}`,
                'warning'
            );
        });
        
        // Синхронизация состояния
        this.socket.on('sync_state', (data) => {
            console.log('[WS] State synced');
            this.updateOnlineUsers({ users: data.online_users, count: data.online_users.length });
            
            // Обновляем индикаторы редактирования
            data.editing_entities.forEach(entity => {
                this.showEditingIndicator(entity);
            });
        });
    }
    
    /**
     * Присоединяется к комнате.
     */
    joinRoom(roomName) {
        if (this.connected) {
            console.log('[WS] Joining room:', roomName);
            this.socket.emit('join_room', { room: roomName });
            this.currentRoom = roomName;
        }
    }
    
    /**
     * Покидает комнату.
     */
    leaveRoom(roomName) {
        if (this.connected) {
            console.log('[WS] Leaving room:', roomName);
            this.socket.emit('leave_room', { room: roomName });
            if (this.currentRoom === roomName) {
                this.currentRoom = null;
            }
        }
    }
    
    /**
     * Начинает редактирование сущности.
     */
    startEditing(entityType, entityId) {
        if (this.connected) {
            console.log('[WS] Starting editing:', entityType, entityId);
            this.socket.emit('start_editing', {
                entity_type: entityType,
                entity_id: entityId
            });
            this.editingEntity = { type: entityType, id: entityId };
        }
    }
    
    /**
     * Заканчивает редактирование сущности.
     */
    stopEditing(entityType, entityId) {
        if (this.connected) {
            console.log('[WS] Stopping editing:', entityType, entityId);
            this.socket.emit('stop_editing', {
                entity_type: entityType,
                entity_id: entityId
            });
            this.editingEntity = null;
        }
    }
    
    /**
     * Запрашивает синхронизацию состояния.
     */
    requestSync() {
        if (this.connected) {
            console.log('[WS] Requesting sync');
            this.socket.emit('request_sync');
        }
    }
    
    /**
     * Показывает статус подключения.
     */
    showConnectionStatus(status) {
        const indicator = document.getElementById('ws-connection-status');
        if (indicator) {
            indicator.className = `ws-status ws-status-${status}`;
            indicator.title = status === 'connected' ? 'Подключено' : 
                            status === 'disconnected' ? 'Отключено' : 'Ошибка';
        }
    }
    
    /**
     * Обновляет статистику на dashboard.
     */
    updateDashboardStats(stats) {
        // Обновляем счетчики на dashboard
        const todayTotal = document.getElementById('today-total');
        if (todayTotal) todayTotal.textContent = stats.today.total;
        
        const todayPending = document.getElementById('today-pending');
        if (todayPending) todayPending.textContent = stats.today.pending;
        
        const lastHour = document.getElementById('last-hour');
        if (lastHour) lastHour.textContent = stats.last_hour;
        
        // Добавляем анимацию обновления
        document.querySelectorAll('.stat-value').forEach(el => {
            el.classList.add('updated');
            setTimeout(() => el.classList.remove('updated'), 1000);
        });
    }
    
    /**
     * Обновляет строку участника в таблице.
     */
    updateParticipantRow(data) {
        const row = document.querySelector(`tr[data-participant-id="${data.participant_id}"]`);
        if (row) {
            const statusCell = row.querySelector('.status-badge');
            if (statusCell) {
                statusCell.className = `status-badge status-${data.new_status}`;
                statusCell.textContent = this.getStatusText(data.new_status);
                
                // Анимация
                row.classList.add('row-updated');
                setTimeout(() => row.classList.remove('row-updated'), 2000);
            }
        }
    }
    
    /**
     * Обновляет список онлайн пользователей.
     */
    updateOnlineUsers(data) {
        const onlineCount = document.getElementById('online-admins-count');
        if (onlineCount) {
            onlineCount.textContent = data.count;
        }
        
        const onlineList = document.getElementById('online-admins-list');
        if (onlineList) {
            onlineList.innerHTML = data.users.map(user => `
                <div class="online-user">
                    <span class="online-indicator"></span>
                    <span>${user.username}</span>
                </div>
            `).join('');
        }
    }
    
    /**
     * Показывает индикатор редактирования.
     */
    showEditingIndicator(data) {
        const element = document.querySelector(
            `[data-${data.entity_type}-id="${data.entity_id}"]`
        );
        
        if (element) {
            const indicator = document.createElement('div');
            indicator.className = 'editing-indicator';
            indicator.innerHTML = `
                <i class="fas fa-pencil-alt"></i>
                <span>Редактирует ${data.editor}</span>
            `;
            indicator.id = `editing-${data.entity_type}-${data.entity_id}`;
            
            element.appendChild(indicator);
        }
    }
    
    /**
     * Скрывает индикатор редактирования.
     */
    hideEditingIndicator(data) {
        const indicator = document.getElementById(
            `editing-${data.entity_type}-${data.entity_id}`
        );
        
        if (indicator) {
            indicator.remove();
        }
    }
    
    /**
     * Показывает уведомление.
     */
    showNotification(message, type = 'info') {
        // Можно использовать любую библиотеку для уведомлений
        // Здесь простая реализация
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.classList.add('show');
        }, 100);
        
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }
    
    /**
     * Получает текст статуса.
     */
    getStatusText(status) {
        const statusMap = {
            'pending': 'Ожидает',
            'approved': 'Одобрено',
            'rejected': 'Отклонено'
        };
        return statusMap[status] || status;
    }
    
    /**
     * Запускает polling как fallback.
     */
    startPolling() {
        console.log('[WS] Starting polling fallback');
        
        // Polling каждые 10 секунд
        this.pollingInterval = setInterval(() => {
            fetch('/api/stats/realtime')
                .then(res => res.json())
                .then(data => {
                    this.updateDashboardStats(data);
                })
                .catch(err => console.error('[Polling] Error:', err));
        }, 10000);
    }
    
    /**
     * Останавливает polling.
     */
    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }
    
    /**
     * Отключается от WebSocket.
     */
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
        }
        this.stopPolling();
    }
}

// Инициализируем WebSocket клиент при загрузке страницы
let wsClient = null;

document.addEventListener('DOMContentLoaded', function() {
    console.log('[App] Initializing WebSocket client');
    wsClient = new WebSocketClient();
    
    // Экспортируем для глобального доступа
    window.wsClient = wsClient;
});

// Автоматическое управление редактированием при навигации
window.addEventListener('beforeunload', function() {
    if (wsClient && wsClient.editingEntity) {
        const { type, id } = wsClient.editingEntity;
        wsClient.stopEditing(type, id);
    }
});

