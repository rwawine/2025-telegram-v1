"""Сервис для логирования действий администраторов (Audit Log)."""

from typing import Dict, List, Optional, Any
from datetime import datetime
import json
from database.connection import get_db_pool


class AuditService:
    """Сервис для работы с audit log."""
    
    @staticmethod
    async def log_action(
        admin_username: str,
        action_type: str,
        entity_type: str,
        entity_id: Optional[int] = None,
        old_value: Optional[Any] = None,
        new_value: Optional[Any] = None,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> int:
        """
        Логирует действие администратора.
        
        Args:
            admin_username: Имя администратора
            action_type: Тип действия (create, update, delete, approve, reject и т.д.)
            entity_type: Тип сущности (participant, tag, lottery и т.д.)
            entity_id: ID сущности
            old_value: Старое значение (для update)
            new_value: Новое значение
            reason: Причина действия
            ip_address: IP адрес
            user_agent: User agent браузера
            
        Returns:
            ID созданной записи в audit log
        """
        pool = get_db_pool()
        
        # Сериализуем сложные объекты в JSON
        old_value_str = json.dumps(old_value) if old_value else None
        new_value_str = json.dumps(new_value) if new_value else None
        
        async with pool.connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO audit_log (
                    admin_username, action_type, entity_type, entity_id,
                    old_value, new_value, reason, ip_address, user_agent, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    admin_username,
                    action_type,
                    entity_type,
                    entity_id,
                    old_value_str,
                    new_value_str,
                    reason,
                    ip_address,
                    user_agent,
                    datetime.now()
                )
            )
            await conn.commit()
            return cursor.lastrowid
    
    @staticmethod
    async def get_audit_logs(
        limit: int = 100,
        offset: int = 0,
        admin_username: Optional[str] = None,
        action_type: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Получает логи с фильтрами.
        
        Args:
            limit: Количество записей
            offset: Смещение
            admin_username: Фильтр по админу
            action_type: Фильтр по типу действия
            entity_type: Фильтр по типу сущности
            entity_id: Фильтр по ID сущности
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            Список записей audit log
        """
        pool = get_db_pool()
        
        # Строим SQL запрос с фильтрами
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        
        if admin_username:
            query += " AND admin_username = ?"
            params.append(admin_username)
        
        if action_type:
            query += " AND action_type = ?"
            params.append(action_type)
        
        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        
        if entity_id:
            query += " AND entity_id = ?"
            params.append(entity_id)
        
        if start_date:
            query += " AND created_at >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND created_at <= ?"
            params.append(end_date)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        async with pool.connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            
            logs = []
            for row in rows:
                log = {key: row[key] for key in row.keys()}
                # Парсим JSON обратно
                if log.get('old_value'):
                    try:
                        log['old_value'] = json.loads(log['old_value'])
                    except:
                        pass
                if log.get('new_value'):
                    try:
                        log['new_value'] = json.loads(log['new_value'])
                    except:
                        pass
                logs.append(log)
            
            return logs
    
    @staticmethod
    async def get_logs_count(
        admin_username: Optional[str] = None,
        action_type: Optional[str] = None,
        entity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> int:
        """Получает количество логов с учетом фильтров."""
        pool = get_db_pool()
        
        query = "SELECT COUNT(*) FROM audit_log WHERE 1=1"
        params = []
        
        if admin_username:
            query += " AND admin_username = ?"
            params.append(admin_username)
        
        if action_type:
            query += " AND action_type = ?"
            params.append(action_type)
        
        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        
        if start_date:
            query += " AND created_at >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND created_at <= ?"
            params.append(end_date)
        
        async with pool.connection() as conn:
            cursor = await conn.execute(query, params)
            row = await cursor.fetchone()
            return row[0] if row else 0
    
    @staticmethod
    async def get_entity_history(entity_type: str, entity_id: int) -> List[Dict]:
        """Получает историю изменений конкретной сущности."""
        pool = get_db_pool()
        
        async with pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM audit_log
                WHERE entity_type = ? AND entity_id = ?
                ORDER BY created_at DESC
                """,
                (entity_type, entity_id)
            )
            rows = await cursor.fetchall()
            
            history = []
            for row in rows:
                log = {key: row[key] for key in row.keys()}
                if log.get('old_value'):
                    try:
                        log['old_value'] = json.loads(log['old_value'])
                    except:
                        pass
                if log.get('new_value'):
                    try:
                        log['new_value'] = json.loads(log['new_value'])
                    except:
                        pass
                history.append(log)
            
            return history
    
    @staticmethod
    async def get_admin_stats() -> List[Dict]:
        """Получает статистику действий по администраторам."""
        pool = get_db_pool()
        
        async with pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT 
                    admin_username,
                    COUNT(*) as total_actions,
                    COUNT(DISTINCT action_type) as action_types_count,
                    MAX(created_at) as last_action,
                    COUNT(CASE WHEN action_type IN ('approve', 'create') THEN 1 END) as positive_actions,
                    COUNT(CASE WHEN action_type IN ('reject', 'delete') THEN 1 END) as negative_actions
                FROM audit_log
                GROUP BY admin_username
                ORDER BY total_actions DESC
                """
            )
            rows = await cursor.fetchall()
            return [{key: row[key] for key in row.keys()} for row in rows]
    
    @staticmethod
    async def get_action_types_stats() -> List[Dict]:
        """Получает статистику по типам действий."""
        pool = get_db_pool()
        
        async with pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT 
                    action_type,
                    entity_type,
                    COUNT(*) as count,
                    COUNT(DISTINCT admin_username) as admins_count,
                    MAX(created_at) as last_occurrence
                FROM audit_log
                GROUP BY action_type, entity_type
                ORDER BY count DESC
                """
            )
            rows = await cursor.fetchall()
            return [{key: row[key] for key in row.keys()} for row in rows]
    
    @staticmethod
    async def detect_suspicious_activity(admin_username: Optional[str] = None) -> List[Dict]:
        """
        Обнаруживает подозрительную активность администраторов.
        
        Критерии:
        - Более 100 действий за последний час
        - Массовые удаления (более 10 за раз)
        - Действия в нерабочее время (с 00:00 до 06:00)
        """
        pool = get_db_pool()
        suspicious = []
        
        async with pool.connection() as conn:
            # Проверка на слишком много действий за час
            query = """
                SELECT 
                    admin_username,
                    COUNT(*) as actions_count,
                    MAX(created_at) as last_action
                FROM audit_log
                WHERE created_at >= datetime('now', '-1 hour')
            """
            params = []
            
            if admin_username:
                query += " AND admin_username = ?"
                params.append(admin_username)
            
            query += """
                GROUP BY admin_username
                HAVING actions_count > 100
            """
            
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            for row in rows:
                suspicious.append({
                    "type": "high_activity",
                    "admin": row[0],
                    "details": f"{row[1]} действий за последний час",
                    "severity": "high"
                })
            
            # Проверка на массовые удаления
            cursor = await conn.execute(
                """
                SELECT 
                    admin_username,
                    action_type,
                    COUNT(*) as delete_count,
                    MAX(created_at) as last_delete
                FROM audit_log
                WHERE action_type = 'delete' 
                  AND created_at >= datetime('now', '-1 hour')
                GROUP BY admin_username
                HAVING delete_count > 10
                """
            )
            rows = await cursor.fetchall()
            for row in rows:
                suspicious.append({
                    "type": "mass_deletion",
                    "admin": row[0],
                    "details": f"{row[2]} удалений за час",
                    "severity": "critical"
                })
            
            # Проверка действий в нерабочее время
            cursor = await conn.execute(
                """
                SELECT 
                    admin_username,
                    action_type,
                    entity_type,
                    created_at
                FROM audit_log
                WHERE strftime('%H', created_at) BETWEEN '00' AND '06'
                  AND created_at >= datetime('now', '-24 hours')
                ORDER BY created_at DESC
                LIMIT 20
                """
            )
            rows = await cursor.fetchall()
            for row in rows:
                suspicious.append({
                    "type": "off_hours_activity",
                    "admin": row[0],
                    "details": f"{row[1]} -> {row[2]} в {row[3]}",
                    "severity": "medium"
                })
        
        return suspicious
    
    @staticmethod
    async def can_rollback(log_id: int) -> bool:
        """Проверяет, можно ли откатить действие."""
        pool = get_db_pool()
        
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT action_type, entity_type FROM audit_log WHERE id = ?",
                (log_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return False
            
            action_type, entity_type = row[0], row[1]
            
            # Можно откатить только определенные типы действий
            rollbackable_actions = {
                'update': True,
                'delete': True,
                'approve': True,
                'reject': True,
            }
            
            return rollbackable_actions.get(action_type, False)
    
    @staticmethod
    async def rollback_action(log_id: int, rollback_by: str) -> bool:
        """
        Откатывает действие администратора.
        
        Note: Это сложная операция, которая требует специфичной логики
        для каждого типа сущности и действия.
        """
        pool = get_db_pool()
        
        async with pool.connection() as conn:
            # Получаем лог
            cursor = await conn.execute(
                "SELECT * FROM audit_log WHERE id = ?",
                (log_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return False
            
            log = {key: row[key] for key in row.keys()}
            
            # Логируем откат
            await AuditService.log_action(
                admin_username=rollback_by,
                action_type="rollback",
                entity_type=log['entity_type'],
                entity_id=log['entity_id'],
                old_value=log['new_value'],
                new_value=log['old_value'],
                reason=f"Rollback of action #{log_id}"
            )
            
            # TODO: Реализовать специфичную логику отката для каждого типа сущности
            # Например, для update участника - вернуть старые значения
            # Для delete - восстановить запись и т.д.
            
            return True


# Глобальный экземпляр
audit_service = AuditService()

