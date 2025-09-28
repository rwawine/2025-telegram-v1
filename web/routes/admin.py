"""Admin blueprints with basic views."""
from __future__ import annotations

"""Admin blueprints with basic views."""

import os
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for, send_from_directory
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.utils import secure_filename

from database.admin_queries import AdminDatabase
from services import run_coroutine_sync, submit_coroutine
from services.broadcast import BroadcastService
from services.lottery import SecureLottery
from web.auth import AdminCredentials, AdminUser, validate_credentials


admin_bp = Blueprint("admin", __name__)


def _get_admin_db() -> AdminDatabase:
    config = current_app.config
    return AdminDatabase(db_path=config["DATABASE_PATH"])


@admin_bp.route("/")
@login_required
def dashboard():
    db = _get_admin_db()
    raw = db.get_statistics()
    stats = {
        "total_participants": raw.get("total_participants", 0),
        "total_winners": raw.get("total_winners", 0),
        "by_status": {
            "approved": raw.get("approved_participants", 0),
            "pending": raw.get("pending_participants", 0),
            "rejected": raw.get("rejected_participants", 0),
        },
    }
    recent_participants, _ = db.list_participants(page=1, per_page=10)
    return render_template("dashboard.html", stats=stats, recent_participants=recent_participants)


@admin_bp.route("/login", methods=["GET", "POST"])
def login_page():
    """Admin login page.
    
    This route handles authentication for the admin panel using simple
    username/password credentials. No participation in lotteries or
    Telegram account is required to access the admin panel.
    """
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        credentials: AdminCredentials = current_app.config["ADMIN_CREDENTIALS"]

        # Validate credentials - no participant or Telegram verification required
        if validate_credentials(credentials, username, password):
            login_user(AdminUser(username=credentials.username))
            return redirect(url_for("admin.dashboard"))
        flash("Неверные учетные данные администратора", "error")

    return render_template("login.html")


@admin_bp.route("/participants")
@login_required
def participants():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    status = request.args.get("status")
    search = request.args.get("search", "").strip()
    db = _get_admin_db()
    participants, total = db.list_participants(status=status, search=search, page=page, per_page=per_page)
    pages = (total + per_page - 1) // per_page
    return render_template(
        "participants.html",
        participants=participants,
        total=total,
        page=page,
        pages=pages,
        per_page=per_page,
        current_status=status,
        search_query=search,
    )


@admin_bp.route("/participants/mass_update", methods=["POST"])
@login_required
def participants_mass_update():
    ids = request.form.getlist("participant_ids") or request.form.get("massParticipantIds", "").split(",")
    ids = [pid for pid in ids if pid]
    status = request.form.get("status")
    notes = request.form.get("notes", "").strip()
    send_notification = request.form.get("send_notification") is not None
    next_url = request.form.get("next")
    if not ids or not status:
        flash("Не выбраны участники или статус", "error")
        return redirect(next_url or url_for("admin.participants"))

    db = _get_admin_db()
    db.update_participants_status((int(pid) for pid in ids), status)
    
    # Update admin notes if provided
    if notes:
        with db._connect() as conn:
            conn.executemany(
                "UPDATE participants SET admin_notes = ? WHERE id = ?",
                [(notes, int(pid)) for pid in ids]
            )
            conn.commit()
    
    # Send notifications if requested
    if send_notification:
        try:
            telegram_ids = db.get_telegram_ids_for_participants([int(pid) for pid in ids])
            if telegram_ids:
                bot_service = current_app.config.get("BROADCAST_SERVICE")
                if bot_service:
                    status_text = {
                        "approved": "одобрен",
                        "rejected": "отклонен", 
                        "pending": "отправлен на рассмотрение"
                    }.get(status, status)
                    
                    message = f"Ваш статус заявки был изменен на: {status_text}"
                    if notes:
                        message += f"\n\nКомментарий администратора: {notes}"
                    
                    submit_coroutine(bot_service.send_broadcast(message, telegram_ids))
                    flash(f"Статус участников обновлен и уведомления отправлены ({len(telegram_ids)} получателей)", "success")
                else:
                    flash("Статус участников обновлен, но сервис уведомлений недоступен", "warning")
            else:
                flash("Статус участников обновлен, но не найдены Telegram ID для уведомлений", "warning")
        except Exception as e:
            current_app.logger.exception("Ошибка отправки уведомлений")
            flash(f"Статус участников обновлен, но произошла ошибка при отправке уведомлений: {e}", "warning")
    else:
        flash("Статус участников обновлен", "success")
    return redirect(next_url or url_for("admin.participants"))


@admin_bp.route("/lottery")
@login_required
def lottery():
    db = _get_admin_db()
    runs = db.list_lottery_runs(limit=50)
    selected_run = request.args.get("run_id", type=int)
    winners = db.list_winners(run_id=selected_run or (runs[0]["id"] if runs else None), limit=200)
    
    # Get lottery statistics
    lottery_stats = {
        "total_draws": len(runs),
        "total_winners": len(winners),
        "win_rate": 0.0
    }
    
    # Get eligible participants count (approved and never won)
    stats = db.get_statistics()
    approved_count = stats.get("approved_participants", 0)
    winners_count = len(set(w["participant_id"] for w in winners))
    eligible_count = max(0, approved_count - winners_count)
    
    if approved_count > 0:
        lottery_stats["win_rate"] = (winners_count / approved_count) * 100
    
    return render_template(
        "lottery.html",
        runs=runs,
        winners=winners,
        selected_run=selected_run,
        lottery_stats=lottery_stats,
        eligible_count=eligible_count,
        stats=stats,
    )


@admin_bp.route("/lottery/run", methods=["POST"])
@login_required
def run_lottery():
    winners_count = request.form.get("winners", type=int)
    if not winners_count or winners_count <= 0:
        flash("Укажите корректное количество победителей", "error")
        return redirect(url_for("admin.lottery"))

    lottery = SecureLottery()
    try:
        run_id, winners = run_coroutine_sync(lottery.select_winners(winners_count))
        flash(f"Розыгрыш #{run_id} завершён. Победителей: {len(winners)}", "success")
    except Exception as exc:
        current_app.logger.exception("Ошибка запуска розыгрыша")
        flash(f"Не удалось провести розыгрыш: {exc}", "error")
    return redirect(url_for("admin.lottery"))


@admin_bp.route("/broadcasts")
@login_required
def broadcasts():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    status = request.args.get("status")
    db = _get_admin_db()
    queue, total = db.list_broadcasts(status=status, page=page, per_page=per_page)
    pages = (total + per_page - 1) // per_page
    return render_template(
        "broadcasts.html",
        broadcasts=queue,
        total=total,
        page=page,
        pages=pages,
        per_page=per_page,
        status=status,
    )


@admin_bp.route("/support_tickets")
@login_required
def support_tickets():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    status = request.args.get("status")
    db = _get_admin_db()
    tickets, total = db.list_support_tickets(status=status, page=page, per_page=per_page)
    pages = (total + per_page - 1) // per_page
    return render_template(
        "support_tickets.html",
        tickets=tickets,
        total=total,
        page=page,
        pages=pages,
        per_page=per_page,
        status=status,
        current_status=status,
    )


@admin_bp.route("/support_tickets/<int:ticket_id>/status", methods=["POST"])
@login_required
def update_ticket_status(ticket_id: int):
    status = request.form.get("status")
    response_message = request.form.get("response_message")
    
    if not status:
        flash("Не выбран статус", "error")
    else:
        db = _get_admin_db()
        db.update_ticket_status(ticket_id, status)
        
        # Send response message if provided
        if response_message and response_message.strip():
            try:
                # Add response message to ticket
                with db._connect() as conn:
                    conn.execute(
                        "INSERT INTO support_ticket_messages (ticket_id, sender_type, message_text, sent_at) VALUES (?, ?, ?, datetime('now'))",
                        (ticket_id, "admin", response_message.strip())
                    )
                    conn.commit()
                
                    # Get user's telegram_id from participants table via ticket
                    ticket_info = conn.execute(
                        "SELECT p.telegram_id FROM support_tickets t JOIN participants p ON t.participant_id = p.id WHERE t.id = ?", 
                        (ticket_id,)
                    ).fetchone()
                    
                # Send to user via Telegram
                bot_service = current_app.config.get("BROADCAST_SERVICE")
                if bot_service and ticket_info and ticket_info[0]:
                    submit_coroutine(bot_service.send_broadcast(response_message.strip(), [ticket_info[0]]))
                    flash("Ответ отправлен пользователю", "success")
                elif not ticket_info or not ticket_info[0]:
                    flash("Ответ сохранен, но не найден Telegram ID пользователя", "warning")
                else:
                    flash("Ответ сохранен, но сервис уведомлений недоступен", "warning")
            except Exception as e:
                current_app.logger.exception("Ошибка отправки ответа")
                flash(f"Ошибка отправки ответа: {e}", "error")
        else:
            flash("Статус тикета обновлен", "success")
    
    return redirect(url_for("admin.support_ticket_detail", ticket_id=ticket_id))


@admin_bp.route("/settings")
@login_required
def settings():
    cfg = {
        "BOT_TOKEN_SET": bool(current_app.config.get("BOT_TOKEN")),
        "ADMIN_IDS": current_app.config.get("ADMIN_IDS"),
        "DATABASE_PATH": current_app.config.get("DATABASE_PATH"),
        "WEB_HOST": current_app.config.get("WEB_HOST", "0.0.0.0"),
        "WEB_PORT": current_app.config.get("WEB_PORT", 5000),
        "UPLOAD_FOLDER": current_app.config.get("UPLOAD_FOLDER", "uploads"),
        "EXPORT_FOLDER": current_app.config.get("EXPORT_FOLDER", "exports"),
        "LOG_FOLDER": current_app.config.get("LOG_FOLDER", "logs"),
        "MAX_PARTICIPANTS": current_app.config.get("MAX_PARTICIPANTS", 10000),
    }
    return render_template("settings.html", config=cfg)


@admin_bp.route("/broadcasts", methods=["POST"])
@login_required
def create_broadcast():
    # Get form data
    title = request.form.get("title", "").strip()
    message_text = request.form.get("message_text", "").strip()
    target_audience = request.form.get("target_audience", "approved")
    
    if not message_text:
        flash("Введите текст сообщения", "error")
        return redirect(url_for("admin.broadcasts"))
        
    if not title:
        title = message_text[:50] + "..." if len(message_text) > 50 else message_text

    db = _get_admin_db()
    
    # Get participants based on target audience
    if target_audience == "all":
        participants, _ = db.list_participants(page=1, per_page=1000000)
    elif target_audience == "winners":
        winners = db.list_winners(limit=1000000)
        participant_ids = [w["participant_id"] for w in winners]
        participants = []
        if participant_ids:
            all_participants, _ = db.list_participants(page=1, per_page=1000000)
            participants = [p for p in all_participants if p.id in participant_ids]
    else:
        participants, _ = db.list_participants(status=target_audience, page=1, per_page=1000000)
    
    participant_ids = [p.id for p in participants]
    if not participant_ids:
        flash(f"Нет участников в категории '{target_audience}' для рассылки", "warning")
        return redirect(url_for("admin.broadcasts"))
    
    # Handle media file
    media_path = None
    media_type = None
    media_caption = request.form.get("media_caption", "").strip() or message_text
    
    if 'media_file' in request.files and request.files['media_file'].filename:
        media_file = request.files['media_file']
        filename = secure_filename(media_file.filename)
        file_ext = os.path.splitext(filename)[1].lower()
        
        if file_ext in ['.jpg', '.jpeg', '.png', '.gif']:
            media_type = 'photo'
        elif file_ext in ['.mp4', '.avi', '.mov']:
            media_type = 'video'
        elif file_ext in ['.mp3', '.wav', '.ogg']:
            media_type = 'audio'
        else:
            media_type = 'document'
        
        # Save file
        import uuid
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        media_path = os.path.join(upload_folder, unique_filename)
        media_file.save(media_path)

    # Create broadcast job
    job_id = db.create_broadcast(
        message=message_text,
        participant_ids=participant_ids,
        media_path=media_path,
        media_type=media_type,
        media_caption=media_caption
    )
    
    # Update broadcast job with title and target audience
    db.update_broadcast_job(job_id, title=title, target_audience=target_audience)

    # Start broadcast sending if BroadcastService is available
    try:
        bot_service = current_app.config.get("BROADCAST_SERVICE")
        if bot_service:
            submit_coroutine(bot_service.send_broadcast(
                message_text, 
                participant_ids, 
                media_path=media_path, 
                media_type=media_type, 
                caption=media_caption
            ))
            flash(f"Рассылка '{title}' создана и отправляется ({len(participant_ids)} получателей)", "success")
        else:
            flash(f"Рассылка '{title}' создана ({len(participant_ids)} получателей), но сервис рассылки недоступен", "warning")
    except Exception as e:
        current_app.logger.exception("Ошибка запуска рассылки")
        flash(f"Рассылка '{title}' создана, но произошла ошибка при отправке: {e}", "error")

    return redirect(url_for("admin.broadcasts"))


@admin_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("admin.login_page"))


@admin_bp.route("/participants/<int:participant_id>")
@login_required
def participant_detail(participant_id: int):
    db = _get_admin_db()
    participants, _ = db.list_participants(page=1, per_page=1000)
    participant = next((p for p in participants if p.id == participant_id), None)
    if not participant:
        flash("Участник не найден", "error")
        return redirect(url_for("admin.participants"))
    return render_template("participant_detail.html", participant=participant)


@admin_bp.route("/participants/<int:participant_id>/status", methods=["POST"])
@login_required
def update_single_participant_status(participant_id: int):
    status = request.form.get("status")
    notes = request.form.get("notes", "").strip()
    send_notification = request.form.get("send_notification") is not None
    
    if not status:
        flash("Не выбран статус", "error")
        return redirect(url_for("admin.participant_detail", participant_id=participant_id))
    
    db = _get_admin_db()
    
    # Update participant status
    db.update_participants_status([participant_id], status)
    
    # Update admin notes if provided
    if notes:
        with db._connect() as conn:
            conn.execute(
                "UPDATE participants SET admin_notes = ? WHERE id = ?",
                (notes, participant_id)
            )
            conn.commit()
    
    # Send notification if requested
    if send_notification:
        try:
            telegram_ids = db.get_telegram_ids_for_participants([participant_id])
            if telegram_ids:
                bot_service = current_app.config.get("BROADCAST_SERVICE")
                if bot_service:
                    status_text = {
                        "approved": "одобрен",
                        "rejected": "отклонен", 
                        "pending": "отправлен на рассмотрение"
                    }.get(status, status)
                    
                    message = f"Ваш статус заявки был изменен на: {status_text}"
                    if notes:
                        message += f"\n\nКомментарий администратора: {notes}"
                    
                    submit_coroutine(bot_service.send_broadcast(message, telegram_ids))
                    flash(f"Статус участника {status_text} и уведомление отправлено", "success")
                else:
                    flash(f"Статус участника {status_text}, но сервис уведомлений недоступен", "warning")
            else:
                flash(f"Статус участника {status_text}, но не найден Telegram ID для уведомления", "warning")
        except Exception as e:
            current_app.logger.exception("Ошибка отправки уведомления")
            flash(f"Статус участника {status_text}, но произошла ошибка при отправке уведомления: {e}", "warning")
    else:
        status_text = {
            "approved": "одобрен",
            "rejected": "отклонен", 
            "pending": "отправлен на рассмотрение"
        }.get(status, status)
        flash(f"Статус участника {status_text}", "success")
    return redirect(url_for("admin.participant_detail", participant_id=participant_id))


@admin_bp.route("/support_tickets/<int:ticket_id>")
@login_required
def support_ticket_detail(ticket_id: int):
    db = _get_admin_db()
    tickets, _ = db.list_support_tickets(page=1, per_page=1000)
    ticket = next((t for t in tickets if t["id"] == ticket_id), None)
    if not ticket:
        flash("Тикет не найден", "error")
        return redirect(url_for("admin.support_tickets"))
    # Load messages
    with db._connect() as conn:
        messages = conn.execute(
            "SELECT sender_type, message_text, attachment_path, attachment_file_id, sent_at FROM support_ticket_messages WHERE ticket_id=? ORDER BY sent_at ASC",
            (ticket_id,),
        ).fetchall()
    return render_template("support_ticket_detail.html", ticket=ticket, messages=messages)


@admin_bp.route("/winners/<int:winner_id>")
@login_required
def winner_detail(winner_id: int):
    db = _get_admin_db()
    winners = db.list_winners(limit=1000)
    winner = next((w for w in winners if w["id"] == winner_id), None)
    if not winner:
        flash("Победитель не найден", "error")
        return redirect(url_for("admin.lottery"))
    return render_template("winner_detail.html", winner=winner)


@admin_bp.route("/lottery/reroll/<int:winner_id>", methods=["POST"])
@login_required
def reroll_winner(winner_id: int):
    # Placeholder for reroll functionality
    flash("Функция перерозыгрыша в разработке", "warning")
    return redirect(url_for("admin.lottery"))


@admin_bp.route("/lottery/delete_winner/<int:winner_id>", methods=["POST"])
@login_required
def delete_winner(winner_id: int):
    # Placeholder for delete winner functionality
    flash("Функция удаления победителя в разработке", "warning")
    return redirect(url_for("admin.lottery"))


@admin_bp.route("/broadcasts/<int:broadcast_id>/send", methods=["POST"])
@login_required
def send_broadcast(broadcast_id: int):
    db = _get_admin_db()
    
    # Get broadcast details
    broadcasts, _ = db.list_broadcasts(page=1, per_page=1000)
    broadcast = next((b for b in broadcasts if b["id"] == broadcast_id), None)
    
    if not broadcast:
        flash("Рассылка не найдена", "error")
        return redirect(url_for("admin.broadcasts"))
    
    if broadcast["status"] != "pending":
        flash("Можно отправить только рассылки в статусе 'ожидание'", "error")
        return redirect(url_for("admin.broadcasts"))
    
    try:
        # Update status to sending
        db.update_broadcast_status(broadcast_id, "sending")
        
        # Get recipients
        participant_ids = db.get_broadcast_recipients(broadcast_id)
        
        if participant_ids:
            # Start broadcast sending if BroadcastService is available
            bot_service = current_app.config.get("BROADCAST_SERVICE")
            if bot_service:
                submit_coroutine(bot_service.send_broadcast(
                    broadcast["message_text"], 
                    participant_ids, 
                    media_path=broadcast.get("media_path"), 
                    media_type=broadcast.get("media_type"), 
                    caption=broadcast.get("media_caption")
                ))
                flash(f"Рассылка начала отправку ({len(participant_ids)} получателей)", "success")
            else:
                db.update_broadcast_status(broadcast_id, "failed")
                flash("Сервис рассылки недоступен", "error")
        else:
            db.update_broadcast_status(broadcast_id, "failed")
            flash("Нет получателей для рассылки", "error")
            
    except Exception as e:
        current_app.logger.exception("Ошибка отправки рассылки")
        db.update_broadcast_status(broadcast_id, "failed")
        flash(f"Ошибка отправки рассылки: {e}", "error")
    
    return redirect(url_for("admin.broadcasts"))


@admin_bp.route("/broadcasts/<int:broadcast_id>/delete", methods=["POST"])
@login_required
def delete_broadcast(broadcast_id: int):
    db = _get_admin_db()
    
    try:
        # Delete broadcast and its queue entries
        with db._connect() as conn:
            conn.execute("DELETE FROM broadcast_queue WHERE job_id = ?", (broadcast_id,))
            conn.execute("DELETE FROM broadcast_jobs WHERE id = ?", (broadcast_id,))
            conn.commit()
        
        flash("Рассылка удалена", "success")
    except Exception as e:
        current_app.logger.exception("Ошибка удаления рассылки")
        flash(f"Ошибка удаления рассылки: {e}", "error")
    
    return redirect(url_for("admin.broadcasts"))


@admin_bp.route("/api/broadcast/<int:broadcast_id>")
@login_required
def get_broadcast_api(broadcast_id: int):
    from flask import jsonify
    db = _get_admin_db()
    
    broadcasts, _ = db.list_broadcasts(page=1, per_page=1000)
    broadcast = next((b for b in broadcasts if b["id"] == broadcast_id), None)
    
    if not broadcast:
        return jsonify({"error": "Рассылка не найдена"}), 404
    
    return jsonify({
        "id": broadcast["id"],
        "title": broadcast.get("media_caption", "Рассылка"),
        "target_audience": broadcast.get("media_type", "all"),
        "message_text": broadcast["message_text"],
        "status": broadcast["status"],
        "created_at": broadcast["created_at"],
        "total_recipients": broadcast.get("total_recipients", 0),
        "sent_count": broadcast.get("sent_count", 0),
        "failed_count": broadcast.get("failed_count", 0)
    })


@admin_bp.route("/uploads/<path:filename>")
def serve_upload(filename: str):
    import os
    import logging
    from pathlib import Path
    
    logger = logging.getLogger(__name__)
    logger.info(f"Attempting to serve upload: {filename}")

    # Security: serve only base filename from configured upload folder
    safe_name = os.path.basename(filename)
    logger.info(f"Safe filename: {safe_name}")
    
    upload_dir = current_app.config.get("UPLOAD_FOLDER", "uploads")
    logger.info(f"Upload directory: {upload_dir}")
    
    # Convert to Path object and resolve to handle cross-platform issues
    base_path = Path(upload_dir).resolve()
    full_path = base_path / safe_name
    logger.info(f"Full path: {full_path}")
    logger.info(f"File exists: {full_path.exists()}")
    
    if not full_path.exists():
        logger.error(f"File not found: {full_path}")
        from flask import abort
        abort(404)
    
    # Use send_from_directory with proper path handling
    import flask
    return flask.send_from_directory(str(base_path), safe_name)

