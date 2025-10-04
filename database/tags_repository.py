"""Репозиторий для работы с тегами участников."""

from typing import List, Dict, Optional
from datetime import datetime
from database.connection import get_db_pool


class TagsRepository:
    """Репозиторий для управления тегами."""
    
    @staticmethod
    async def create_tag(name: str, color: str, description: str = "") -> int:
        """Создать новый тег."""
        pool = get_db_pool()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO tags (name, color, description, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (name, color, description, datetime.now())
            )
            await conn.commit()
            return cursor.lastrowid
    
    @staticmethod
    async def get_all_tags() -> List[Dict]:
        """Получить все теги."""
        pool = get_db_pool()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT t.*, COUNT(pt.participant_id) as usage_count
                FROM tags t
                LEFT JOIN participant_tags pt ON t.id = pt.tag_id
                GROUP BY t.id
                ORDER BY t.name
                """
            )
            rows = await cursor.fetchall()
            return [{key: row[key] for key in row.keys()} for row in rows]
    
    @staticmethod
    async def get_tag_by_id(tag_id: int) -> Optional[Dict]:
        """Получить тег по ID."""
        pool = get_db_pool()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM tags WHERE id = ?",
                (tag_id,)
            )
            row = await cursor.fetchone()
            return {key: row[key] for key in row.keys()} if row else None
    
    @staticmethod
    async def update_tag(tag_id: int, name: str, color: str, description: str = "") -> bool:
        """Обновить тег."""
        pool = get_db_pool()
        async with pool.connection() as conn:
            await conn.execute(
                """
                UPDATE tags
                SET name = ?, color = ?, description = ?
                WHERE id = ?
                """,
                (name, color, description, tag_id)
            )
            await conn.commit()
            return True
    
    @staticmethod
    async def delete_tag(tag_id: int) -> bool:
        """Удалить тег."""
        pool = get_db_pool()
        async with pool.connection() as conn:
            # Удаляем связи
            await conn.execute("DELETE FROM participant_tags WHERE tag_id = ?", (tag_id,))
            # Удаляем сам тег
            await conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
            await conn.commit()
            return True
    
    @staticmethod
    async def add_tag_to_participant(participant_id: int, tag_id: int, added_by: str = "admin") -> bool:
        """Добавить тег участнику."""
        pool = get_db_pool()
        async with pool.connection() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO participant_tags (participant_id, tag_id, added_at, added_by)
                    VALUES (?, ?, ?, ?)
                    """,
                    (participant_id, tag_id, datetime.now(), added_by)
                )
                await conn.commit()
                return True
            except Exception:
                # Тег уже добавлен
                return False
    
    @staticmethod
    async def remove_tag_from_participant(participant_id: int, tag_id: int) -> bool:
        """Удалить тег у участника."""
        pool = get_db_pool()
        async with pool.connection() as conn:
            await conn.execute(
                "DELETE FROM participant_tags WHERE participant_id = ? AND tag_id = ?",
                (participant_id, tag_id)
            )
            await conn.commit()
            return True
    
    @staticmethod
    async def get_participant_tags(participant_id: int) -> List[Dict]:
        """Получить все теги участника."""
        pool = get_db_pool()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT t.*, pt.added_at, pt.added_by
                FROM tags t
                JOIN participant_tags pt ON t.id = pt.tag_id
                WHERE pt.participant_id = ?
                ORDER BY t.name
                """,
                (participant_id,)
            )
            rows = await cursor.fetchall()
            return [{key: row[key] for key in row.keys()} for row in rows]
    
    @staticmethod
    async def get_participants_by_tag(tag_id: int) -> List[int]:
        """Получить ID всех участников с тегом."""
        pool = get_db_pool()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT participant_id FROM participant_tags WHERE tag_id = ?",
                (tag_id,)
            )
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
    
    @staticmethod
    async def bulk_add_tags(participant_ids: List[int], tag_ids: List[int], added_by: str = "admin") -> int:
        """Массово добавить теги участникам."""
        pool = get_db_pool()
        count = 0
        async with pool.connection() as conn:
            for participant_id in participant_ids:
                for tag_id in tag_ids:
                    try:
                        await conn.execute(
                            """
                            INSERT OR IGNORE INTO participant_tags (participant_id, tag_id, added_at, added_by)
                            VALUES (?, ?, ?, ?)
                            """,
                            (participant_id, tag_id, datetime.now(), added_by)
                        )
                        count += 1
                    except Exception:
                        continue
            await conn.commit()
        return count
    
    @staticmethod
    async def get_tag_statistics() -> Dict:
        """Получить статистику по тегам."""
        pool = get_db_pool()
        async with pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT 
                    t.id,
                    t.name,
                    t.color,
                    COUNT(pt.participant_id) as total_participants,
                    COUNT(CASE WHEN p.status = 'approved' THEN 1 END) as approved_count,
                    COUNT(CASE WHEN p.status = 'pending' THEN 1 END) as pending_count,
                    COUNT(CASE WHEN p.status = 'rejected' THEN 1 END) as rejected_count
                FROM tags t
                LEFT JOIN participant_tags pt ON t.id = pt.tag_id
                LEFT JOIN participants p ON pt.participant_id = p.id
                GROUP BY t.id
                ORDER BY total_participants DESC
                """
            )
            rows = await cursor.fetchall()
            return [{key: row[key] for key in row.keys()} for row in rows]


class BulkOperationsRepository:
    """Репозиторий для массовых операций."""
    
    @staticmethod
    async def bulk_approve(participant_ids: List[int], approved_by: str = "admin") -> int:
        """Массово одобрить участников."""
        pool = get_db_pool()
        async with pool.connection() as conn:
            placeholders = ','.join('?' * len(participant_ids))
            await conn.execute(
                f"""
                UPDATE participants
                SET status = 'approved', updated_at = ?
                WHERE id IN ({placeholders}) AND status = 'pending'
                """,
                (datetime.now(), *participant_ids)
            )
            await conn.commit()
            return conn.total_changes
    
    @staticmethod
    async def bulk_reject(participant_ids: List[int], reason: str = "", rejected_by: str = "admin") -> int:
        """Массово отклонить участников."""
        pool = get_db_pool()
        async with pool.connection() as conn:
            placeholders = ','.join('?' * len(participant_ids))
            await conn.execute(
                f"""
                UPDATE participants
                SET status = 'rejected', rejection_reason = ?, updated_at = ?
                WHERE id IN ({placeholders}) AND status = 'pending'
                """,
                (reason, datetime.now(), *participant_ids)
            )
            await conn.commit()
            return conn.total_changes
    
    @staticmethod
    async def bulk_delete(participant_ids: List[int]) -> int:
        """Массово удалить участников."""
        pool = get_db_pool()
        async with pool.connection() as conn:
            placeholders = ','.join('?' * len(participant_ids))
            await conn.execute(
                f"DELETE FROM participant_tags WHERE participant_id IN ({placeholders})",
                participant_ids
            )
            await conn.execute(
                f"DELETE FROM participants WHERE id IN ({placeholders})",
                participant_ids
            )
            await conn.commit()
            return conn.total_changes
    
    @staticmethod
    async def bulk_add_to_blacklist(
        participant_ids: List[int],
        reason: str = "",
        added_by: str = "admin"
    ) -> int:
        """Массово добавить в черный список."""
        pool = get_db_pool()
        count = 0
        async with pool.connection() as conn:
            for participant_id in participant_ids:
                # Получаем данные участника
                cursor = await conn.execute(
                    "SELECT telegram_id, phone_number FROM participants WHERE id = ?",
                    (participant_id,)
                )
                row = await cursor.fetchone()
                if row:
                    await conn.execute(
                        """
                        INSERT OR IGNORE INTO blacklist (telegram_id, phone_number, reason, added_by, added_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (row[0], row[1], reason, added_by, datetime.now())
                    )
                    count += 1
            await conn.commit()
        return count
    
    @staticmethod
    async def bulk_export(participant_ids: List[int], format: str = "csv") -> Dict:
        """Массово экспортировать данные участников."""
        pool = get_db_pool()
        async with pool.connection() as conn:
            placeholders = ','.join('?' * len(participant_ids))
            cursor = await conn.execute(
                f"""
                SELECT 
                    p.*,
                    GROUP_CONCAT(t.name, ', ') as tags
                FROM participants p
                LEFT JOIN participant_tags pt ON p.id = pt.participant_id
                LEFT JOIN tags t ON pt.tag_id = t.id
                WHERE p.id IN ({placeholders})
                GROUP BY p.id
                """,
                participant_ids
            )
            rows = await cursor.fetchall()
            return {
                "data": [{key: row[key] for key in row.keys()} for row in rows],
                "count": len(rows),
                "format": format
            }

