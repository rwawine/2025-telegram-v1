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
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,  # 30 second timeout
            isolation_level=None  # Autocommit mode for better performance
        )
        conn.row_factory = sqlite3.Row
        # Apply performance optimizations
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
        return conn

    def get_statistics(self) -> Dict[str, int]:
        """Get system statistics with optimized single query."""
        with self._connect() as conn:
            # Single optimized query for participant stats
            participant_stats = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected
                FROM participants
            """).fetchone()
            
            # Single query for ticket stats  
            ticket_stats = conn.execute("""
                SELECT 
                    SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_tickets,
                    SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_tickets,
                    SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed_tickets
                FROM support_tickets
            """).fetchone()
            
            # Single query for other stats
            other_stats = conn.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM broadcast_jobs WHERE status='failed') as failed_broadcasts,
                    (SELECT COUNT(*) FROM winners) as total_winners
            """).fetchone()
            
        return {
            "total_participants": participant_stats["total"] or 0,
            "approved_participants": participant_stats["approved"] or 0,
            "pending_participants": participant_stats["pending"] or 0,
            "rejected_participants": participant_stats["rejected"] or 0,
            "open_tickets": ticket_stats["open_tickets"] or 0,
            "tickets_in_progress": ticket_stats["in_progress_tickets"] or 0,
            "tickets_closed": ticket_stats["closed_tickets"] or 0,
            "failed_broadcasts": other_stats["failed_broadcasts"] or 0,
            "total_winners": other_stats["total_winners"] or 0,
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

    def iter_winners(self, run_id: Optional[int] = None, chunk_size: int = 5000):
        """Yield winners rows in chunks to support streaming exports."""
        base_query = (
            "SELECT w.id, w.run_id, w.participant_id, p.full_name, p.phone_number, p.username, w.position, w.lottery_date, w.prize_description, "
            "lr.seed, lr.executed_at as draw_date, lr.id as draw_number, "
            "substr(lr.seed, 1, 32) as seed_hash "
            "FROM winners w "
            "JOIN participants p ON p.id = w.participant_id "
            "JOIN lottery_runs lr ON lr.id = w.run_id"
        )
        where_clause = " WHERE w.run_id=?" if run_id else ""
        offset = 0
        with self._connect() as conn:
            while True:
                rows = conn.execute(
                    f"{base_query}{where_clause} ORDER BY w.lottery_date DESC, w.position ASC LIMIT ? OFFSET ?",
                    ((run_id,) + (chunk_size, offset)) if run_id else (chunk_size, offset),
                ).fetchall()
                if not rows:
                    break
                for row in rows:
                    yield row
                offset += chunk_size

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
                "INSERT INTO broadcast_jobs (message_text, total_recipients, media_path, media_type, media_caption) VALUES (?, ?, ?, ?, ?)",
                (message, len(participant_ids), media_path, media_type, media_caption or message),
            )
            job_id = cursor.lastrowid

            # Resolve telegram_ids for participant_ids
            if participant_ids:
                placeholders = ",".join("?" for _ in participant_ids)
                rows = conn.execute(
                    f"SELECT id, telegram_id FROM participants WHERE id IN ({placeholders})",
                    list(participant_ids),
                ).fetchall()
                id_to_telegram = {row[0]: row[1] for row in rows}
            else:
                id_to_telegram = {}

            # Insert into queue with telegram_id for faster sending
            conn.executemany(
                """
                INSERT INTO broadcast_queue (job_id, participant_id, telegram_id, message_text, media_path, media_type, media_caption, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                [
                    (
                        job_id,
                        pid,
                        id_to_telegram.get(pid),
                        message,
                        media_path,
                        media_type,
                        media_caption or message,
                    )
                    for pid in participant_ids
                ],
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

    def get_broadcast_recipient_telegram_ids(self, job_id: int) -> List[int]:
        """Return pending recipient telegram IDs for a given job."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT telegram_id FROM broadcast_queue WHERE job_id=? AND status='pending' AND telegram_id IS NOT NULL",
                (job_id,),
            ).fetchall()
        return [row[0] for row in rows]

    def mark_broadcast_sent(self, job_id: int, telegram_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE broadcast_queue SET status='sent' WHERE job_id=? AND telegram_id=?",
                (job_id, telegram_id),
            )
            conn.commit()

    def mark_broadcast_failed(self, job_id: int, telegram_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE broadcast_queue SET status='failed', attempts=COALESCE(attempts,0)+1 WHERE job_id=? AND telegram_id=?",
                (job_id, telegram_id),
            )
            conn.commit()

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

    def delete_ticket(self, ticket_id: int) -> None:
        """Delete a support ticket and its messages."""
        with self._connect() as conn:
            conn.execute("DELETE FROM support_ticket_messages WHERE ticket_id=?", (ticket_id,))
            conn.execute("DELETE FROM support_tickets WHERE id=?", (ticket_id,))
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

    def delete_participants_cascade(self, participant_ids: Sequence[int]) -> int:
        """Delete participants and all related data safely.
        Returns number of participants deleted.
        """
        if not participant_ids:
            return 0
        placeholders = ','.join('?' * len(participant_ids))
        with self._connect() as conn:
            # Delete support ticket messages for tickets of these participants
            ticket_rows = conn.execute(
                f"SELECT id FROM support_tickets WHERE participant_id IN ({placeholders})",
                list(participant_ids),
            ).fetchall()
            ticket_ids = [row[0] for row in ticket_rows]
            if ticket_ids:
                ticket_ph = ','.join('?' * len(ticket_ids))
                conn.execute(
                    f"DELETE FROM support_ticket_messages WHERE ticket_id IN ({ticket_ph})",
                    ticket_ids,
                )
                conn.execute(
                    f"DELETE FROM support_tickets WHERE id IN ({ticket_ph})",
                    ticket_ids,
                )
            # Delete winners referencing these participants
            conn.execute(f"DELETE FROM winners WHERE participant_id IN ({placeholders})", list(participant_ids))
            # Delete broadcast queue rows for these participants (by participant_id)
            conn.execute(f"DELETE FROM broadcast_queue WHERE participant_id IN ({placeholders})", list(participant_ids))
            # Finally delete participants
            conn.execute(f"DELETE FROM participants WHERE id IN ({placeholders})", list(participant_ids))
            conn.commit()
        return len(participant_ids)

    def clear_participants(self) -> None:
        """Dangerous: wipe participants and related data (winners, queues, tickets)."""
        with self._connect() as conn:
            # Order matters due to foreign keys
            conn.execute("DELETE FROM winners")
            conn.execute("DELETE FROM support_ticket_messages")
            conn.execute("DELETE FROM support_tickets")
            conn.execute("DELETE FROM broadcast_queue")
            # Keep broadcast_jobs history, but reset aggregated counts if needed
            conn.execute("UPDATE broadcast_jobs SET total_recipients=0, started_at=NULL, finished_at=NULL, status='draft'")
            conn.execute("DELETE FROM participants")
            conn.commit()
    
    def clear_all_database(self) -> None:
        """EXTREMELY DANGEROUS: Полная очистка всей базы данных."""
        with self._connect() as conn:
            # Удаляем все данные из всех таблиц (только существующие)
            conn.execute("DELETE FROM winners")
            conn.execute("DELETE FROM support_ticket_messages")
            conn.execute("DELETE FROM support_tickets")
            conn.execute("DELETE FROM broadcast_queue")
            conn.execute("DELETE FROM broadcast_jobs")
            conn.execute("DELETE FROM lottery_runs")
            conn.execute("DELETE FROM participants")
            conn.commit()

    def get_moderation_activity(self) -> Dict[str, int]:
        with self._connect() as conn:
            processed_today = conn.execute(
                "SELECT COUNT(*) FROM participants WHERE date(updated_at)=date('now') AND status IN ('approved','rejected')"
            ).fetchone()[0]
            approved_today = conn.execute(
                "SELECT COUNT(*) FROM participants WHERE date(updated_at)=date('now') AND status='approved'"
            ).fetchone()[0]
            rejected_today = conn.execute(
                "SELECT COUNT(*) FROM participants WHERE date(updated_at)=date('now') AND status='rejected'"
            ).fetchone()[0]
        return {
            "processed_today": processed_today,
            "approved_today": approved_today,
            "rejected_today": rejected_today,
        }

    def get_top_rejection_reasons(self, limit: int = 5) -> List[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT admin_notes as reason, COUNT(*) as cnt
                FROM participants
                WHERE status='rejected' AND admin_notes IS NOT NULL AND TRIM(admin_notes)<>''
                GROUP BY admin_notes
                ORDER BY cnt DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

