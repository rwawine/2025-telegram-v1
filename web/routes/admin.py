"""Admin blueprints with basic views."""
from __future__ import annotations

"""Admin blueprints with basic views."""

import os
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for, send_from_directory, jsonify
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.utils import secure_filename
from io import StringIO
import csv

from database.admin_queries import AdminDatabase
from services import run_coroutine_sync, submit_coroutine
from services.broadcast import BroadcastService
from services.lottery import SecureLottery
from web.auth import AdminCredentials, AdminUser, validate_credentials


admin_bp = Blueprint("admin", __name__)


def _get_admin_db() -> AdminDatabase:
    """Get admin database connection with error handling."""
    try:
        config = current_app.config
        db_path = config.get("DATABASE_PATH", "data/lottery_bot.sqlite")
        return AdminDatabase(db_path=db_path)
    except Exception as e:
        current_app.logger.error(f"Failed to connect to admin database: {e}")
        raise


@admin_bp.route("/")
@login_required
def dashboard():
    try:
        db = _get_admin_db()
        raw = db.get_statistics()
        stats = {
            "total_participants": raw.get("total_participants", 0),
            "total_winners": raw.get("total_winners", 0),
            "open_tickets": raw.get("open_tickets", 0),
            "by_status": {
                "approved": raw.get("approved_participants", 0),
                "pending": raw.get("pending_participants", 0),
                "rejected": raw.get("rejected_participants", 0),
            },
        }
        recent_participants, _ = db.list_participants(page=1, per_page=10)
        # Load a few recent open tickets for dashboard support block
        recent_tickets, _ = db.list_support_tickets(page=1, per_page=3)
        moderation = db.get_moderation_activity()
        top_reasons = db.get_top_rejection_reasons(limit=5)

        return render_template(
            "dashboard.html",
            stats=stats,
            recent_participants=recent_participants,
            recent_tickets=recent_tickets,
            moderation=moderation,
            top_reasons=top_reasons,
        )
    except Exception as e:
        current_app.logger.error(f"Dashboard error: {e}")
        flash("Ошибка загрузки данных панели управления", "error")
        # Return basic dashboard with empty data
        return render_template(
            "dashboard.html",
            stats={"total_participants": 0, "total_winners": 0, "open_tickets": 0, "by_status": {"approved": 0, "pending": 0, "rejected": 0}},
            recent_participants=[],
            recent_tickets=[],
            moderation={"processed_today": 0, "approved_today": 0, "rejected_today": 0},
            top_reasons=[],
        )


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
    raw_stats = db.get_statistics()
    stats = {
        "total_participants": raw_stats.get("total_participants", 0),
        "by_status": {
            "approved": raw_stats.get("approved_participants", 0),
            "pending": raw_stats.get("pending_participants", 0),
            "rejected": raw_stats.get("rejected_participants", 0),
        },
    }
    return render_template(
        "participants.html",
        participants=participants,
        total=total,
        page=page,
        pages=pages,
        per_page=per_page,
        current_status=status,
        search_query=search,
        stats=stats,
    )


@admin_bp.route("/participants/import", methods=["POST"])
@login_required
def import_participants():
    if 'file' not in request.files or not request.files['file'].filename:
        flash("Загрузите CSV файл", "error")
        return redirect(url_for('admin.participants'))
    file = request.files['file']
    try:
        stream = StringIO(file.stream.read().decode('utf-8-sig'))
        reader = csv.DictReader(stream)
        from services.async_runner import run_sync
        from database.repositories import insert_participants_batch
        batch = []
        for row in reader:
            try:
                batch.append({
                    "telegram_id": int(row.get("telegram_id") or 0),
                    "username": row.get("username") or None,
                    "full_name": row.get("full_name") or "",
                    "phone_number": row.get("phone_number") or "",
                    "loyalty_card": row.get("loyalty_card") or "",
                    "photo_path": row.get("photo_path") or None,
                })
            except Exception:
                continue
        if batch:
            run_sync(insert_participants_batch(batch))
            flash(f"Импортировано записей: {len(batch)}", "success")
        else:
            flash("В файле не найдено валидных записей", "warning")
    except Exception as e:
        current_app.logger.exception("Ошибка импорта участников")
        flash(f"Не удалось импортировать: {e}", "error")
    return redirect(url_for('admin.participants'))


@admin_bp.route("/participants/<int:participant_id>/delete", methods=["POST"])
@login_required
def delete_participant(participant_id: int):
    db = _get_admin_db()
    try:
        with db._connect() as conn:
            conn.execute("DELETE FROM participants WHERE id=?", (participant_id,))
            conn.commit()
        flash("Участник удален", "success")
    except Exception as e:
        current_app.logger.exception("Ошибка удаления участника")
        flash(f"Не удалось удалить участника: {e}", "error")
    return redirect(url_for("admin.participants"))


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


@admin_bp.route("/lottery/history")
@login_required
def lottery_history():
    db = _get_admin_db()
    runs = db.list_lottery_runs(limit=200)
    return render_template("lottery_history.html", runs=runs, stats=db.get_statistics())


@admin_bp.route("/winners")
@login_required
def winners():
    db = _get_admin_db()
    run_id = request.args.get("run_id", type=int)
    winners = db.list_winners(run_id=run_id, limit=1000)
    runs = db.list_lottery_runs(limit=50)
    return render_template("winners.html", winners=winners, runs=runs, selected_run=run_id, stats=db.get_statistics())


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
    # Derive analytics breakdowns
    by_status = {
        'completed': len([b for b in queue if b['status'] == 'completed']),
        'sending': len([b for b in queue if b['status'] == 'sending']),
        'draft': len([b for b in queue if b['status'] == 'draft']),
        'failed': len([b for b in queue if b['status'] == 'failed']),
    }
    by_audience = {}
    for b in queue:
        aud = b.get('media_type') or 'all'
        by_audience[aud] = by_audience.get(aud, 0) + 1
    pages = (total + per_page - 1) // per_page
    return render_template(
        "broadcasts.html",
        broadcasts=queue,
        total=total,
        page=page,
        pages=pages,
        per_page=per_page,
        status=status,
        stats=db.get_statistics(),
        by_status=by_status,
        by_audience=by_audience,
    )


@admin_bp.route("/participants/export")
@login_required
def export_participants():
    db = _get_admin_db()
    status = request.args.get("status")
    participants, _ = db.list_participants(status=status, page=1, per_page=1_000_000)
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["id", "full_name", "phone_number", "username", "telegram_id", "loyalty_card", "status", "registration_date"])
    for p in participants:
        writer.writerow([p.id, p.full_name, p.phone_number, p.username or "", p.telegram_id, p.loyalty_card, p.status, p.registration_date])
    output = si.getvalue().encode("utf-8-sig")
    from flask import make_response
    response = make_response(output)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=participants.csv"
    return response


@admin_bp.route("/winners/export")
@login_required
def export_winners():
    db = _get_admin_db()
    run_id = request.args.get("run_id", type=int)
    winners = db.list_winners(run_id=run_id, limit=100000)
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["winner_id", "run_id", "participant_id", "full_name", "username", "phone_number", "position", "draw_number", "draw_date", "seed_hash"])
    for w in winners:
        writer.writerow([
            w["id"], w["run_id"], w["participant_id"], w["full_name"], w["username"], w["phone_number"], w["position"], w.get("draw_number"), w.get("draw_date"), w.get("seed_hash")
        ])
    output = si.getvalue().encode("utf-8-sig")
    from flask import make_response
    response = make_response(output)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=winners.csv"
    return response


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
        stats=db.get_statistics(),
    )


@admin_bp.route("/support_tickets/<int:ticket_id>/status", methods=["POST"])
@login_required
def update_ticket_status(ticket_id: int):
    wants_json = request.accept_mimetypes.best == "application/json" or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    status = request.form.get("status")
    response_message = request.form.get("response_message")
    if not status:
        msg = "Не выбран статус"
        if wants_json:
            return jsonify({"ok": False, "message": msg}), 400
        flash(msg, "error")
        return redirect(url_for("admin.support_ticket_detail", ticket_id=ticket_id))

    db = _get_admin_db()
    db.update_ticket_status(ticket_id, status)
    sent_to_user = False
    warn_text = None

    if response_message and response_message.strip():
        try:
            with db._connect() as conn:
                conn.execute(
                    "INSERT INTO support_ticket_messages (ticket_id, sender_type, message_text, sent_at) VALUES (?, ?, ?, datetime('now'))",
                    (ticket_id, "admin", response_message.strip())
                )
                ticket_info = conn.execute(
                    "SELECT p.telegram_id FROM support_tickets t JOIN participants p ON t.participant_id = p.id WHERE t.id = ?",
                    (ticket_id,)
                ).fetchone()
                conn.commit()
            bot_service = current_app.config.get("BROADCAST_SERVICE")
            if bot_service and ticket_info and ticket_info[0]:
                submit_coroutine(bot_service.send_broadcast(response_message.strip(), [ticket_info[0]]))
                sent_to_user = True
            elif not ticket_info or not ticket_info[0]:
                warn_text = "Ответ сохранен, но не найден Telegram ID пользователя"
            else:
                warn_text = "Ответ сохранен, но сервис уведомлений недоступен"
        except Exception as e:
            current_app.logger.exception("Ошибка отправки ответа")
            if wants_json:
                return jsonify({"ok": False, "message": f"Ошибка отправки ответа: {e}"}), 500
            flash(f"Ошибка отправки ответа: {e}", "error")
            return redirect(url_for("admin.support_ticket_detail", ticket_id=ticket_id))

    if wants_json:
        return jsonify({
            "ok": True,
            "status": status,
            "sent_to_user": sent_to_user,
            "warning": warn_text,
        })

    if sent_to_user:
        flash("Ответ отправлен пользователю", "success")
    else:
        flash(warn_text or "Статус тикета обновлен", "success" if not warn_text else "warning")
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


@admin_bp.route("/settings", methods=["POST"])
@login_required
def save_settings():
    # Caution: For demo, allow updating only a few runtime config values
    try:
        web_host = request.form.get("WEB_HOST")
        web_port = request.form.get("WEB_PORT", type=int)
        upload_folder = request.form.get("UPLOAD_FOLDER")
        export_folder = request.form.get("EXPORT_FOLDER")
        max_participants = request.form.get("MAX_PARTICIPANTS", type=int)
        app = current_app
        if web_host:
            app.config["WEB_HOST"] = web_host
        if web_port:
            app.config["WEB_PORT"] = web_port
        if upload_folder:
            app.config["UPLOAD_FOLDER"] = upload_folder
        if export_folder:
            app.config["EXPORT_FOLDER"] = export_folder
        if max_participants:
            app.config["MAX_PARTICIPANTS"] = max_participants
        flash("Настройки сохранены (в памяти процесса)", "success")
    except Exception as e:
        app.logger.exception("Ошибка сохранения настроек")
        flash(f"Не удалось сохранить: {e}", "error")
    return redirect(url_for('admin.settings'))


@admin_bp.route("/analytics")
@login_required
def analytics():
    db = _get_admin_db()
    stats = db.get_statistics()
    # Broadcast audience success/error breakdown
    broadcasts, _ = db.list_broadcasts(page=1, per_page=1000000)
    audience_breakdown = {}
    for b in broadcasts:
        aud = (b.get("media_type") or "all")
        succ = int(b.get("sent_count") or 0)
        fail = int(b.get("failed_count") or 0)
        agg = audience_breakdown.setdefault(aud, {"success": 0, "failed": 0})
        agg["success"] += succ
        agg["failed"] += fail
    return render_template("analytics.html", stats=stats, broadcast_audience_breakdown=audience_breakdown)


@admin_bp.route("/moderation")
@login_required
def moderation():
    db = _get_admin_db()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    participants, total = db.list_participants(status="pending", page=page, per_page=per_page)
    pages = (total + per_page - 1) // per_page
    return render_template(
        "moderation.html",
        participants=participants,
        total=total,
        page=page,
        pages=pages,
        per_page=per_page,
        stats=db.get_statistics(),
    )


@admin_bp.route("/system")
@login_required
def system_page():
    app = current_app
    cfg = {
        "WEB_HOST": app.config.get("WEB_HOST", "0.0.0.0"),
        "WEB_PORT": app.config.get("WEB_PORT", 5000),
        "UPLOAD_FOLDER": app.config.get("UPLOAD_FOLDER", "uploads"),
        "EXPORT_FOLDER": app.config.get("EXPORT_FOLDER", "exports"),
        "LOG_FOLDER": app.config.get("LOG_FOLDER", "logs"),
        "DATABASE_PATH": app.config.get("DATABASE_PATH"),
    }
    import os, time
    health = {
        "database_exists": os.path.exists(cfg["DATABASE_PATH"]) if cfg.get("DATABASE_PATH") else False,
        "uploads_exists": os.path.isdir(cfg["UPLOAD_FOLDER"]),
        "exports_exists": os.path.isdir(cfg["EXPORT_FOLDER"]),
        "logs_exists": os.path.isdir(cfg["LOG_FOLDER"]),
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    # List logs
    logs = []
    try:
        for name in sorted(os.listdir(cfg["LOG_FOLDER"])):
            path = os.path.join(cfg["LOG_FOLDER"], name)
            if os.path.isfile(path):
                stat = os.stat(path)
                logs.append({
                    "name": name,
                    "size": stat.st_size,
                    "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                })
    except Exception:
        pass
    return render_template("system.html", config=cfg, health=health, logs=logs)


@admin_bp.route("/system/log/<path:log_name>")
@login_required
def view_log(log_name: str):
    from werkzeug.utils import secure_filename as _sec
    safe = _sec(os.path.basename(log_name))
    app = current_app
    folder = app.config.get("LOG_FOLDER", "logs")
    path = os.path.join(folder, safe)
    lines = request.args.get("lines", 500, type=int)
    content = ""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            # Read last N lines efficiently
            from collections import deque
            content = "".join(deque(f, maxlen=lines))
    except Exception as e:
        flash(f"Не удалось прочитать лог: {e}", "error")
        return redirect(url_for("admin.system_page"))
    return render_template("log_view.html", log_name=safe, content=content)


@admin_bp.route("/system/log/<path:log_name>/download")
@login_required
def download_log(log_name: str):
    from werkzeug.utils import secure_filename as _sec
    safe = _sec(os.path.basename(log_name))
    folder = current_app.config.get("LOG_FOLDER", "logs")
    return send_from_directory(folder, safe, as_attachment=True, download_name=safe)


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

    # If request expects JSON (AJAX), return JSON for better UX
    if request.headers.get('Accept', '').lower().startswith('application/json'):
        from flask import jsonify
        return jsonify({"message": "Рассылка создана", "redirect": url_for("admin.broadcasts")})
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
    # Prefer a targeted query when available; fallback to search in list
    try:
        winners = db.list_winners(limit=1000)
        winner = next((w for w in winners if w["id"] == winner_id), None)
    except Exception:
        winner = None
    if not winner:
        flash("Победитель не найден", "error")
        return redirect(url_for("admin.lottery"))
    return render_template("winner_detail.html", winner=winner)


@admin_bp.route("/lottery/reroll/<int:winner_id>", methods=["POST"])
@login_required
def reroll_winner(winner_id: int):
    db = _get_admin_db()
    # Get the winner to reroll
    winners = db.list_winners(limit=1000)
    target = next((w for w in winners if w["id"] == winner_id), None)
    if not target:
        flash("Победитель не найден", "error")
        return redirect(url_for("admin.lottery"))

    try:
        # Policy: require reason and limit reroll within 24h of draw
        reason = (request.form.get('reason') or '').strip()
        if not reason:
            flash("Укажите причину перерозыгрыша", "error")
            return redirect(url_for("admin.winner_detail", winner_id=winner_id))
        from datetime import datetime, timedelta
        draw_dt_raw = target.get("draw_date")
        # draw_date is usually a string; try to parse
        window_ok = True
        try:
            draw_dt = datetime.fromisoformat(str(draw_dt_raw))
            window_ok = datetime.utcnow() - draw_dt <= timedelta(hours=24)
        except Exception:
            window_ok = True  # if cannot parse, allow
        if not window_ok:
            flash("Перерозыгрыш возможен только в течение 24 часов после розыгрыша", "warning")
            return redirect(url_for("admin.winner_detail", winner_id=winner_id))

        # Simple reroll: pick another approved participant who is not already a winner in this run
        from database.repositories import get_approved_participants
        from services import run_coroutine_sync
        approved = run_coroutine_sync(get_approved_participants())
        approved_ids = [pid for pid, _ in approved]
        run_winners = {w["participant_id"] for w in db.list_winners(run_id=target["run_id"], limit=10000)}
        candidates = [pid for pid in approved_ids if pid not in run_winners]
        if not candidates:
            flash("Нет доступных кандидатов для перерозыгрыша", "warning")
            return redirect(url_for("admin.lottery"))

        import random
        new_participant_id = random.choice(candidates)
        # Update winner record to point to new participant
        with db._connect() as conn:
            conn.execute(
                "UPDATE winners SET participant_id=?, lottery_date=CURRENT_TIMESTAMP WHERE id=?",
                (new_participant_id, winner_id),
            )
            # Optionally, store audit log
            try:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS reroll_audit (id INTEGER PRIMARY KEY, winner_id INT, reason TEXT, at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
                )
                conn.execute(
                    "INSERT INTO reroll_audit (winner_id, reason) VALUES (?, ?)",
                    (winner_id, reason),
                )
            except Exception:
                pass
            conn.commit()
        flash("Победитель переопределен", "success")
    except Exception as e:
        current_app.logger.exception("Ошибка перерозыгрыша")
        flash(f"Ошибка перерозыгрыша: {e}", "error")
    return redirect(url_for("admin.lottery"))


@admin_bp.route("/lottery/delete_winner/<int:winner_id>", methods=["POST"])
@login_required
def delete_winner(winner_id: int):
    db = _get_admin_db()
    try:
        with db._connect() as conn:
            conn.execute("DELETE FROM winners WHERE id=?", (winner_id,))
            conn.commit()
        flash("Победитель удален", "success")
    except Exception as e:
        current_app.logger.exception("Ошибка удаления победителя")
        flash(f"Не удалось удалить победителя: {e}", "error")
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


@admin_bp.route("/backups")
@login_required
def backups():
    """Backup management page."""
    backup_service = current_app.config.get("BACKUP_SERVICE")
    
    if backup_service:
        backup_info = backup_service.get_backup_info()
    else:
        backup_info = {"error": "Backup service not available"}
    
    return render_template("backups.html", backup_info=backup_info)


@admin_bp.route("/backups/create", methods=["POST"])
@login_required
def create_manual_backup():
    """Create backup manually."""
    backup_service = current_app.config.get("BACKUP_SERVICE")
    
    if not backup_service:
        flash("Backup service not available", "error")
        return redirect(url_for("admin.backups"))
    
    try:
        success = backup_service.create_full_backup()
        if success:
            flash("Backup created successfully", "success")
        else:
            flash("Failed to create backup", "error")
    except Exception as e:
        current_app.logger.exception("Manual backup failed")
        flash(f"Backup failed: {e}", "error")
    
    return redirect(url_for("admin.backups"))


@admin_bp.route("/backups/download/<filename>")
@login_required
def download_backup(filename: str):
    """Download backup file."""
    from werkzeug.utils import secure_filename
    from pathlib import Path
    
    safe_filename = secure_filename(filename)
    backup_dir = Path(current_app.config.get("BACKUP_FOLDER", "backups"))
    backup_path = backup_dir / safe_filename
    
    if not backup_path.exists() or not backup_path.is_file():
        flash("Backup file not found", "error")
        return redirect(url_for("admin.backups"))
    
    # Security check - ensure file is in backup directory
    try:
        backup_path.resolve().relative_to(backup_dir.resolve())
    except ValueError:
        flash("Access denied", "error")
        return redirect(url_for("admin.backups"))
    
    return send_from_directory(str(backup_dir), safe_filename, as_attachment=True)


@admin_bp.route("/backups/cleanup", methods=["POST"])
@login_required
def cleanup_old_backups():
    """Cleanup old backup files."""
    backup_service = current_app.config.get("BACKUP_SERVICE")
    
    if not backup_service:
        flash("Backup service not available", "error")
        return redirect(url_for("admin.backups"))
    
    try:
        backup_service.cleanup_old_backups()
        flash("Old backups cleaned up successfully", "success")
    except Exception as e:
        current_app.logger.exception("Backup cleanup failed")
        flash(f"Cleanup failed: {e}", "error")
    
    return redirect(url_for("admin.backups"))


@admin_bp.route("/api/search")
@login_required
def api_search():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"results": []})
    db = _get_admin_db()
    results = {"participants": [], "tickets": [], "winners": []}
    try:
        # Participants
        participants, _ = db.list_participants(search=q, page=1, per_page=10)
        results["participants"] = [
            {
                "type": "participant",
                "id": p.id,
                "title": p.full_name,
                "subtitle": p.phone_number,
                "url": url_for('admin.participant_detail', participant_id=p.id),
            }
            for p in participants
        ]
        # Tickets
        tickets, _ = db.list_support_tickets(page=1, per_page=200)
        q_lower = q.lower()
        ticket_hits = [t for t in tickets if q_lower in (t["subject"] or "").lower() or q_lower in (t["message"] or "").lower()]
        results["tickets"] = [
            {
                "type": "ticket",
                "id": t["id"],
                "title": t["subject"] or f"Тикет #{t['id']}",
                "subtitle": t["category"],
                "url": url_for('admin.support_ticket_detail', ticket_id=t["id"]),
            }
            for t in ticket_hits[:10]
        ]
        # Winners
        winners = db.list_winners(limit=200)
        winner_hits = [w for w in winners if q_lower in (w["full_name"] or "").lower() or q_lower in str(w["participant_id"]) ]
        results["winners"] = [
            {
                "type": "winner",
                "id": w["id"],
                "title": w["full_name"] or f"ID {w['participant_id']}",
                "subtitle": f"Розыгрыш #{w['draw_number']}",
                "url": url_for('admin.winner_detail', winner_id=w["id"]) ,
            }
            for w in winner_hits[:10]
        ]
    except Exception as e:
        current_app.logger.exception("Ошибка поиска")
        return jsonify({"error": str(e)}), 500
    return jsonify({"results": results})

