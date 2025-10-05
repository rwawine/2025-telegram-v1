"""Новые маршруты для интеграции расширенной функциональности."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user

from database.connection import get_db_pool
from database.tags_repository import BulkOperationsRepository, TagsRepository
from services.audit_service import AuditService
from services.advanced_analytics_service import advanced_analytics_service, MetricPeriod


# Создаем blueprint
admin_new_bp = Blueprint('admin_new', __name__, url_prefix='/admin')


# Вспомогательная функция для async вызовов
def run_async(coro):
    """Execute async function in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()




# ==================== TAGS MANAGEMENT ====================

@admin_new_bp.route('/tags')
@login_required
def tags_management():
    """Страница управления тегами."""
    all_tags = run_async(TagsRepository.get_all_tags())
    tag_stats = run_async(TagsRepository.get_tag_statistics())
    
    return render_template(
        'tags_management.html',
        tags=all_tags,
        stats=tag_stats
    )


@admin_new_bp.route('/tags/create', methods=['POST'])
@login_required
def create_tag():
    """Создание нового тега."""
    name = request.form.get('name')
    color = request.form.get('color')
    description = request.form.get('description')
    
    try:
        tag_id = run_async(TagsRepository.create_tag(name, color, description))
        
        # Логируем в audit log
        run_async(AuditService.log_action(
            admin_username=current_user.username,
            action_type="CREATE_TAG",
            entity_type="tag",
            entity_id=tag_id,
            new_value=json.dumps({"name": name, "color": color}),
            reason="Создание нового тега",
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        ))
        
        flash(f'Тег "{name}" успешно создан!', 'success')
    except Exception as e:
        flash(f'Ошибка при создании тега: {e}', 'danger')
    
    return redirect(url_for('admin_new.tags_management'))


@admin_new_bp.route('/tags/update', methods=['POST'])
@login_required
def update_tag():
    """Обновление тега."""
    tag_id = int(request.form.get('tag_id'))
    name = request.form.get('name')
    color = request.form.get('color')
    description = request.form.get('description')
    
    try:
        # Получаем старое значение
        old_tag = run_async(TagsRepository.get_tag_by_id(tag_id))
        
        success = run_async(TagsRepository.update_tag(tag_id, name, color, description))
        
        if success:
            # Логируем
            run_async(AuditService.log_action(
                admin_username=current_user.username,
                action_type="UPDATE_TAG",
                entity_type="tag",
                entity_id=tag_id,
                old_value=json.dumps(old_tag),
                new_value=json.dumps({"name": name, "color": color, "description": description}),
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            ))
            
            flash(f'Тег "{name}" обновлен!', 'success')
        else:
            flash('Ошибка при обновлении тега', 'danger')
    except Exception as e:
        flash(f'Ошибка: {e}', 'danger')
    
    return redirect(url_for('admin_new.tags_management'))


@admin_new_bp.route('/tags/delete', methods=['POST'])
@login_required
def delete_tag():
    """Удаление тега."""
    tag_id = int(request.form.get('tag_id'))
    
    try:
        # Получаем данные тега
        tag = run_async(TagsRepository.get_tag_by_id(tag_id))
        
        success = run_async(TagsRepository.delete_tag(tag_id))
        
        if success:
            # Логируем
            run_async(AuditService.log_action(
                admin_username=current_user.username,
                action_type="DELETE_TAG",
                entity_type="tag",
                entity_id=tag_id,
                old_value=json.dumps(tag),
                reason="Удаление тега администратором",
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            ))
            
            flash(f'Тег "{tag["name"]}" удален!', 'success')
        else:
            flash('Ошибка при удалении тега', 'danger')
    except Exception as e:
        flash(f'Ошибка: {e}', 'danger')
    
    return redirect(url_for('admin_new.tags_management'))


# ==================== BULK OPERATIONS ====================

@admin_new_bp.route('/participants/bulk-action', methods=['POST'])
@login_required
def bulk_action():
    """Массовые операции над участниками."""
    participant_ids = [int(id) for id in request.form.getlist('participant_ids[]')]
    action = request.form.get('action')
    
    if not participant_ids:
        flash('Не выбрано ни одного участника', 'warning')
        return redirect(request.referrer or url_for('admin.participants'))
    
    try:
        action_logged = False
        action_type = None
        action_details = None
        
        if action == 'add_tags':
            tag_ids = [int(id) for id in request.form.getlist('tag_ids[]')]
            count = run_async(BulkOperationsRepository.add_tags_to_participants(
                participant_ids, tag_ids, current_user.username
            ))
            flash(f'Теги добавлены {count} участникам', 'success')
            action_type = "BULK_ADD_TAGS"
            action_details = f"Добавлены теги {tag_ids} для {count} участников"
            action_logged = True
        
        elif action == 'remove_tags':
            tag_ids = [int(id) for id in request.form.getlist('tag_ids[]')]
            count = run_async(BulkOperationsRepository.remove_tags_from_participants(
                participant_ids, tag_ids, current_user.username
            ))
            flash(f'Теги удалены у {count} участников', 'success')
            action_type = "BULK_REMOVE_TAGS"
            action_details = f"Удалены теги {tag_ids} у {count} участников"
            action_logged = True
        
        elif action == 'approve':
            reason = request.form.get('reason', 'Массовое одобрение')
            count = run_async(BulkOperationsRepository.update_participants_status(
                participant_ids, 'approved', current_user.username, reason
            ))
            flash(f'Одобрено {count} участников', 'success')
            action_type = "BULK_APPROVE_PARTICIPANTS"
            action_details = f"Одобрено {count} участников. Причина: {reason}"
            action_logged = True
        
        elif action == 'reject':
            reason = request.form.get('reason', 'Массовое отклонение')
            count = run_async(BulkOperationsRepository.update_participants_status(
                participant_ids, 'rejected', current_user.username, reason
            ))
            flash(f'Отклонено {count} участников', 'warning')
            action_type = "BULK_REJECT_PARTICIPANTS"
            action_details = f"Отклонено {count} участников. Причина: {reason}"
            action_logged = True
        
        elif action == 'blacklist':
            reason = request.form.get('reason', 'Добавлено в черный список')
            count = run_async(BulkOperationsRepository.add_participants_to_blacklist(
                participant_ids, current_user.username, reason
            ))
            flash(f'{count} участников добавлено в черный список', 'danger')
            action_type = "BULK_BLACKLIST_PARTICIPANTS"
            action_details = f"{count} участников добавлено в ЧС. Причина: {reason}"
            action_logged = True
        
        elif action == 'delete':
            reason = request.form.get('reason', 'Массовое удаление')
            count = run_async(BulkOperationsRepository.delete_participants(
                participant_ids, current_user.username, reason
            ))
            flash(f'Удалено {count} участников', 'info')
            action_type = "BULK_DELETE_PARTICIPANTS"
            action_details = f"Удалено {count} участников. Причина: {reason}"
            action_logged = True
        
        elif action == 'export':
            format = request.form.get('format', 'csv')
            data = run_async(BulkOperationsRepository.export_participants_data(
                participant_ids, format
            ))
            
            # Log export action
            try:
                run_async(AuditService.log_action(
                    admin_username=current_user.username,
                    action_type="BULK_EXPORT_PARTICIPANTS",
                    entity_type="participant",
                    entity_id=0,
                    new_value=f"Экспорт {len(participant_ids)} участников в формате {format}",
                    reason=f"Массовый экспорт данных участников",
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent')
                ))
            except Exception as audit_err:
                current_app.logger.error(f"Failed to log audit action: {audit_err}")
            
            from flask import Response
            return Response(
                data,
                mimetype='text/csv' if format == 'csv' else 'application/json',
                headers={
                    'Content-Disposition': f'attachment; filename=participants_export.{format}'
                }
            )
        
        else:
            flash('Неизвестное действие', 'danger')
        
        # Log action to audit if it was a modifying operation
        if action_logged and action_type and action_details:
            try:
                run_async(AuditService.log_action(
                    admin_username=current_user.username,
                    action_type=action_type,
                    entity_type="participant",
                    entity_id=0,
                    new_value=f"ID участников: {','.join(map(str, participant_ids[:20]))}{'...' if len(participant_ids) > 20 else ''}",
                    reason=action_details,
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent')
                ))
            except Exception as audit_err:
                current_app.logger.error(f"Failed to log audit action: {audit_err}")
    
    except Exception as e:
        flash(f'Ошибка при выполнении операции: {e}', 'danger')
    
    return redirect(request.referrer or url_for('admin.participants'))


# ==================== AUDIT LOG ====================

@admin_new_bp.route('/audit-log')
@login_required
def audit_log():
    """Страница журнала аудита."""
    try:
        # Фильтры
        admin_username = request.args.get('admin')
        action_type = request.args.get('action')
        entity_type = request.args.get('entity')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = int(request.args.get('page', 1))
        per_page = 50
        
        # Парсим даты
        start_datetime = datetime.fromisoformat(start_date) if start_date else None
        end_datetime = datetime.fromisoformat(end_date) if end_date else None
        
        # Получаем логи
        logs = run_async(AuditService.get_audit_logs(
            admin_username=admin_username,
            action_type=action_type,
            entity_type=entity_type,
            start_date=start_datetime,
            end_date=end_datetime,
            limit=per_page,
            offset=(page - 1) * per_page
        ))
        
        # Подозрительная активность
        suspicious = []
        if admin_username:
            suspicious = run_async(AuditService.detect_suspicious_activity(admin_username))
        
        # Статистика
        hour_ago = datetime.now() - timedelta(hours=1)
        recent_logs = run_async(AuditService.get_audit_logs(
            start_date=hour_ago,
            limit=1000
        ))
        
        active_admins = len(set(log['admin_username'] for log in recent_logs))
        
        return render_template(
            'audit_log.html',
            logs=logs,
            total_logs=len(logs),
            last_hour_logs=len(recent_logs),
            active_admins=active_admins,
            suspicious_count=len(suspicious),
            current_page=page,
            total_pages=(len(logs) + per_page - 1) // per_page,
            current_filters={
                'admin': admin_username,
                'action': action_type,
                'entity': entity_type,
                'start_date': start_date,
                'end_date': end_date
            }
        )
    except Exception as e:
        import traceback
        flash(f'Ошибка загрузки audit log: {str(e)}', 'danger')
        print(f"Audit log error: {e}")
        print(traceback.format_exc())
        return redirect(url_for('admin.dashboard'))


@admin_new_bp.route('/audit-log/export')
@login_required
def export_audit_log():
    """Экспорт журнала аудита."""
    logs = run_async(AuditService.get_audit_logs(limit=10000))
    
    # Конвертируем в CSV
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Заголовки
    writer.writerow(['Время', 'Администратор', 'Действие', 'Сущность', 'ID', 'IP'])
    
    # Данные
    for log in logs:
        writer.writerow([
            log['created_at'],
            log['admin_username'],
            log['action_type'],
            log['entity_type'],
            log['entity_id'] or '',
            log['ip_address'] or ''
        ])
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': 'attachment; filename=audit_log_export.csv'
        }
    )


# ==================== ADVANCED ANALYTICS ====================

@admin_new_bp.route('/analytics/advanced')
@login_required
def analytics_advanced():
    """Страница расширенной аналитики."""
    
    try:
        # Получаем все метрики
        conversion = run_async(advanced_analytics_service.get_conversion_metrics(30))
        retention = run_async(advanced_analytics_service.get_retention_metrics(30))
        funnel = run_async(advanced_analytics_service.get_conversion_funnel())
        time_series = run_async(advanced_analytics_service.get_time_series(
            "registrations",
            MetricPeriod.DAILY,
            30
        ))
        heatmap = run_async(advanced_analytics_service.get_activity_heatmap(30))
        cohorts = run_async(advanced_analytics_service.get_cohort_analysis())
        real_time = run_async(advanced_analytics_service.get_real_time_stats())
        
        # Преобразуем time_series для JSON
        time_series_data = [
            {'label': point.label, 'value': point.value}
            for point in time_series
        ]
        
        # Вычисляем максимальное значение для heatmap
        heatmap_max = 0
        if heatmap:
            for day_hours in heatmap.values():
                if day_hours:
                    day_max = max(day_hours.values())
                    heatmap_max = max(heatmap_max, day_max)
        
        return render_template(
            'analytics_advanced.html',
            conversion=conversion.__dict__,
            retention=retention.__dict__,
            funnel=funnel,
            time_series=time_series_data,
            heatmap=heatmap,
            heatmap_max=heatmap_max,
            cohorts=cohorts,
            real_time=real_time,
            best_day='Н/Д',
            peak_hour='Н/Д',
            avg_retention='Н/Д'
        )
    except Exception as e:
        import traceback
        flash(f'Ошибка загрузки аналитики: {str(e)}', 'danger')
        print(f"Analytics error: {e}")
        print(traceback.format_exc())
        return redirect(url_for('admin.dashboard'))


@admin_new_bp.route('/api/stats/realtime')
@login_required
def api_realtime_stats():
    """API для WebSocket polling fallback."""
    stats = run_async(advanced_analytics_service.get_real_time_stats())
    return jsonify(stats)


@admin_new_bp.route('/analytics/export')
@login_required
def export_analytics_report():
    """Экспорт полного аналитического отчета."""
    report = run_async(advanced_analytics_service.export_analytics_report(format="json"))
    
    from flask import Response
    return Response(
        json.dumps(report, indent=2, ensure_ascii=False),
        mimetype='application/json',
        headers={
            'Content-Disposition': 'attachment; filename=analytics_report.json'
        }
    )

