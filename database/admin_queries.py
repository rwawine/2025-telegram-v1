"""Synchronous helper queries for admin web interface."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass
class ParticipantRow:
    id: int
    telegram_id: int
    username: Optional[str]
    full_name: str
    phone_number: str
    loyalty_card: str
    photo_path: Optional[str]
    status: str
    registration_date: str
    admin_notes: Optional[str] = None


class AdminDatabase:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_statistics(self) -> Dict[str, int]:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM participants").fetchone()[0]
            approved = conn.execute(
                "SELECT COUNT(*) FROM participants WHERE status='approved'"
            ).fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM participants WHERE status='pending'"
            ).fetchone()[0]
            rejected = conn.execute(
                "SELECT COUNT(*) FROM participants WHERE status='rejected'"
            ).fetchone()[0]
            tickets_open = conn.execute(
                "SELECT COUNT(*) FROM support_tickets WHERE status='open'"
            ).fetchone()[0]
            total_winners = conn.execute(
                "SELECT COUNT(*) FROM winners"
            ).fetchone()[0]
        return {
            "total_participants": total,
            "approved_participants": approved,
            "pending_participants": pending,
            "rejected_participants": rejected,
            "open_tickets": tickets_open,
            "total_winners": total_winners,
        }

    def list_participants(
        self,
        status: Optional[str] = None,
        search: str = "",
        page: int = 1,
        per_page: int = 50,
    ) -> Tuple[List[ParticipantRow], int]:
        offset = (page - 1) * per_page
        query = "SELECT * FROM participants"
        params: List[object] = []
        conditions = []
        if status:
            conditions.append("status=?")
            params.append(status)
        if search:
            conditions.append("(full_name LIKE ? OR phone_number LIKE ? OR loyalty_card LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like])
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY registration_date DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            count_query = "SELECT COUNT(*) FROM participants"
            count_params: List[object] = []
            if conditions:
                count_query += " WHERE " + " AND ".join(conditions)
                count_params = params[:-2]
            total = conn.execute(count_query, count_params).fetchone()[0]

        participants = [
            ParticipantRow(
                id=row["id"],
                telegram_id=row["telegram_id"],
                username=row["username"],
                full_name=row["full_name"],
                phone_number=row["phone_number"],
                loyalty_card=row["loyalty_card"],
                photo_path=row["photo_path"],
                status=row["status"],
                registration_date=row["registration_date"],
                admin_notes=row["admin_notes"] if "admin_notes" in row.keys() else None,
            )
            for row in rows
        ]
        return participants, total

    def update_participants_status(
        self,
        participant_ids: Iterable[int],
        status: str,
    ) -> None:
        with self._connect() as conn:
            conn.executemany(
                "UPDATE participants SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                [(status, pid) for pid in participant_ids],
            )
            conn.commit()

    def get_telegram_ids_for_participants(
        self,
        participant_ids: Iterable[int],
    ) -> List[int]:
        """Get telegram IDs for given participant IDs."""
        with self._connect() as conn:
            placeholders = ','.join('?' * len(participant_ids))
            query = f"SELECT telegram_id FROM participants WHERE id IN ({placeholders})"
            rows = conn.execute(query, list(participant_ids)).fetchall()
            return [row[0] for row in rows]

    def list_lottery_runs(self, limit: int = 20) -> List[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT id, seed, executed_at, winners_count FROM lottery_runs ORDER BY executed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def list_winners(self, run_id: Optional[int] = None, limit: int = 100) -> List[sqlite3.Row]:
        query = (
            "SELECT w.id, w.run_id, w.participant_id, p.full_name, p.phone_number, p.username, w.position, w.lottery_date, w.prize_description, "
            "lr.seed, lr.executed_at as draw_date, lr.id as draw_number, "
            "substr(lr.seed, 1, 32) as seed_hash "
            "FROM winners w "
            "JOIN participants p ON p.id = w.participant_id "
            "JOIN lottery_runs lr ON lr.id = w.run_id"
        )
        params: List[object] = []
        if run_id:
            query += " WHERE w.run_id=?"
            params.append(run_id)
        query += " ORDER BY w.lottery_date DESC, w.position ASC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            return conn.execute(query, params).fetchall()

    def list_support_tickets(
        self,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> Tuple[List[sqlite3.Row], int]:
        offset = (page - 1) * per_page
        query = """
            SELECT t.*, 
                   p.full_name as participant_name,
                   p.username as telegram_username,
                   ('TICKET-' || printf('%06d', t.id)) as ticket_number,
                   'technical' as category
            FROM support_tickets t 
            LEFT JOIN participants p ON p.id=t.participant_id
        """
        params: List[object] = []
        if status:
            query += " WHERE t.status=?"
            params.append(status)
        query += " ORDER BY t.created_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])

        count_query = "SELECT COUNT(*) FROM support_tickets"
        count_params: List[object] = []
        if status:
            count_query += " WHERE status=?"
            count_params.append(status)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            total = conn.execute(count_query, count_params).fetchone()[0]
        return rows, total

    def create_broadcast(self, message: str, participant_ids: Sequence[int], media_path: str = None, media_type: str = None, media_caption: str = None) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO broadcast_jobs (message_text, total_recipients, media_path, media_type, media_caption) VALUES (?, ?, ?, ?, ?) RETURNING id",
                (message, len(participant_ids), media_path, media_type, media_caption or message),
            )
            job_id = cursor.fetchone()[0]
            conn.executemany(
                """
                INSERT INTO broadcast_queue (job_id, participant_id, message_text, media_path, media_type, media_caption, status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """,
                [(job_id, pid, message, media_path, media_type, media_caption or message) for pid in participant_ids],
            )
            conn.commit()
            return job_id

    def get_broadcast_recipients(self, job_id: int) -> List[int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT participant_id FROM broadcast_queue WHERE job_id=? AND status='pending'",
                (job_id,),
            ).fetchall()
        return [row[0] for row in rows]

    def update_broadcast_status(self, job_id: int, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE broadcast_jobs SET status=? WHERE id=?",
                (status, job_id),
            )
            conn.commit()
            
    def update_broadcast_job(self, job_id: int, title: str = None, target_audience: str = None) -> None:
        """Update broadcast job with additional metadata."""
        updates = []
        params = []
        
        if title:
            # Store title in media_caption field temporarily (we could add a proper title field later)
            updates.append("media_caption = ?")
            params.append(title)
            
        if target_audience:
            # Store target_audience in media_type field temporarily (we could add a proper field later)
            updates.append("media_type = ?")
            params.append(target_audience)
            
        if updates:
            params.append(job_id)
            with self._connect() as conn:
                conn.execute(
                    f"UPDATE broadcast_jobs SET {', '.join(updates)} WHERE id=?",
                    params,
                )
                conn.commit()

    def update_ticket_status(self, ticket_id: int, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE support_tickets SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, ticket_id),
            )
            conn.commit()

    def list_broadcasts(
        self,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> Tuple[List[sqlite3.Row], int]:
        offset = (page - 1) * per_page
        query = """
            SELECT bj.*, 
                   COUNT(bq.id) as total_recipients,
                   SUM(CASE WHEN bq.status = 'sent' THEN 1 ELSE 0 END) as sent_count,
                   SUM(CASE WHEN bq.status = 'failed' THEN 1 ELSE 0 END) as failed_count
            FROM broadcast_jobs bj 
            LEFT JOIN broadcast_queue bq ON bj.id = bq.job_id
        """
        params: List[object] = []
        if status:
            query += " WHERE bj.status=?"
            params.append(status)
        query += " GROUP BY bj.id ORDER BY bj.created_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])

        count_query = "SELECT COUNT(*) FROM broadcast_jobs"
        count_params: List[object] = []
        if status:
            count_query += " WHERE status=?"
            count_params.append(status)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            total = conn.execute(count_query, count_params).fetchone()[0]
        return rows, total

