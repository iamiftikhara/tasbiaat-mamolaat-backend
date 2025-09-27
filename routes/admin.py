"""
Admin routes for system management, cycle resets, and administrative functions
"""

from flask import Blueprint, g, request
from utils.decorators import jwt_required_custom, role_required, validate_json_payload, log_activity, rate_limit
from utils.validators import validate_user_role, validate_saalik_level, validate_cycle_days
from utils.helpers import format_response, parse_date_from_string
from utils.auth import revoke_user_sessions, generate_api_key
from models.user import User
from models.entry import Entry
from models.level import Level
from models.session import Session
from models.notification import Notification
from models.audit_log import AuditLog
from datetime import datetime, date, timedelta
from bson import ObjectId
import os

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/system/status', methods=['GET'])
@jwt_required_custom
@role_required('Admin')
def system_status():
    """Get system status and health metrics"""
    current_user = g.current_user
    
    # Calculate system statistics
    total_users = User.count_all()
    active_users = User.count_active()
    total_entries = Entry.count_all()
    
    # Get recent activity (last 7 days)
    week_ago = date.today() - timedelta(days=7)
    recent_entries = Entry.count_all(start_date=week_ago)
    recent_users = User.count_recently_created(days=7)
    
    # Get role distribution
    role_stats = {}
    for role in ['Admin', 'Sheikh', 'Masool', 'Murabi', 'Saalik']:
        role_stats[role] = User.count_by_role(role)
    
    # Get level distribution for Saalik
    level_stats = {}
    for level in range(7):  # Levels 0-6
        level_stats[f"Level {level}"] = User.count_by_level(level)
    
    # Get session statistics
    active_sessions = Session.count_active()
    expired_sessions = Session.count_expired()
    
    # Get notification statistics
    unread_notifications = Notification.count_unread_all()
    
    # Calculate system health score (0-100)
    health_score = 100
    
    # Deduct points for various issues
    if active_users / max(total_users, 1) < 0.8:  # Less than 80% active users
        health_score -= 20
    
    if recent_entries / max(recent_users * 7, 1) < 0.5:  # Low entry rate
        health_score -= 15
    
    if expired_sessions > active_sessions:  # Too many expired sessions
        health_score -= 10
    
    if unread_notifications > total_users * 2:  # Too many unread notifications
        health_score -= 5
    
    health_score = max(0, health_score)
    
    return format_response(
        success=True,
        message="System status retrieved successfully",
        data={
            'system_health': {
                'score': health_score,
                'status': 'healthy' if health_score >= 80 else 'warning' if health_score >= 60 else 'critical'
            },
            'user_statistics': {
                'total_users': total_users,
                'active_users': active_users,
                'recent_registrations': recent_users,
                'role_distribution': role_stats,
                'level_distribution': level_stats
            },
            'entry_statistics': {
                'total_entries': total_entries,
                'recent_entries': recent_entries,
                'daily_average': recent_entries / 7
            },
            'session_statistics': {
                'active_sessions': active_sessions,
                'expired_sessions': expired_sessions
            },
            'notification_statistics': {
                'unread_notifications': unread_notifications
            },
            'timestamp': datetime.utcnow().isoformat()
        }
    )

@admin_bp.route('/users/bulk-cycle-reset', methods=['POST'])
@jwt_required_custom
@role_required('Admin')
@validate_json_payload()
@log_activity('bulk_cycle_reset', 'system')
def bulk_cycle_reset():
    """Reset cycles for multiple users or all users"""
    current_user = g.current_user
    data = g.json_data
    
    # Get parameters
    user_ids = data.get('user_ids', [])  # If empty, reset all Saalik
    reset_date = data.get('reset_date')  # If not provided, use today
    reason = data.get('reason', 'Admin bulk reset')
    
    # Parse reset date
    if reset_date:
        reset_date_obj = parse_date_from_string(reset_date)
        if not reset_date_obj:
            return format_response(
                success=False,
                message="Invalid reset_date format. Use YYYY-MM-DD",
                status_code=400
            )
    else:
        reset_date_obj = date.today()
    
    # Get target users
    if user_ids:
        # Specific users
        target_users = []
        for user_id in user_ids:
            user = User.find_by_id(user_id)
            if user and user.role == 'Saalik':
                target_users.append(user)
    else:
        # All Saalik users
        target_users = User.find_by_role('Saalik')
    
    if not target_users:
        return format_response(
            success=False,
            message="No valid Saalik users found for cycle reset",
            status_code=400
        )
    
    # Perform bulk reset
    reset_count = 0
    failed_resets = []
    
    for user in target_users:
        try:
            old_start_date = user.level_start_date
            user.level_start_date = reset_date_obj
            user.save()
            
            # Log individual reset
            AuditLog.log_action(
                user_id=current_user._id,
                action='cycle_reset',
                resource_type='user',
                resource_id=str(user._id),
                old_values={'level_start_date': old_start_date.isoformat() if old_start_date else None},
                new_values={'level_start_date': reset_date_obj.isoformat()},
                details={'reason': reason, 'bulk_operation': True}
            )
            
            reset_count += 1
            
        except Exception as e:
            failed_resets.append({
                'user_id': str(user._id),
                'name': user.name,
                'error': str(e)
            })
    
    # Log bulk operation
    AuditLog.log_action(
        user_id=current_user._id,
        action='bulk_cycle_reset',
        resource_type='system',
        details={
            'total_users': len(target_users),
            'successful_resets': reset_count,
            'failed_resets': len(failed_resets),
            'reset_date': reset_date_obj.isoformat(),
            'reason': reason
        }
    )
    
    return format_response(
        success=True,
        message=f"Bulk cycle reset completed. {reset_count} users reset successfully",
        data={
            'successful_resets': reset_count,
            'failed_resets': failed_resets,
            'reset_date': reset_date_obj.isoformat()
        }
    )

@admin_bp.route('/users/bulk-level-update', methods=['POST'])
@jwt_required_custom
@role_required('Admin')
@validate_json_payload(required_fields=['updates'])
@log_activity('bulk_level_update', 'system')
def bulk_level_update():
    """Update levels for multiple users"""
    current_user = g.current_user
    data = g.json_data
    
    updates = data['updates']  # List of {user_id, new_level}
    reason = data.get('reason', 'Admin bulk level update')
    
    if not isinstance(updates, list) or not updates:
        return format_response(
            success=False,
            message="Updates must be a non-empty list",
            status_code=400
        )
    
    successful_updates = 0
    failed_updates = []
    
    for update in updates:
        if not isinstance(update, dict) or 'user_id' not in update or 'new_level' not in update:
            failed_updates.append({
                'update': update,
                'error': 'Invalid update format. Must include user_id and new_level'
            })
            continue
        
        user_id = update['user_id']
        new_level = update['new_level']
        
        # Validate level
        is_valid, error = validate_saalik_level(new_level)
        if not is_valid:
            failed_updates.append({
                'user_id': user_id,
                'error': error
            })
            continue
        
        # Find user
        user = User.find_by_id(user_id)
        if not user:
            failed_updates.append({
                'user_id': user_id,
                'error': 'User not found'
            })
            continue
        
        # Update level
        old_level = user.level
        user.level = new_level
        user.save()
        
        # Log level change
        LevelChangeLog(
            user_id=user._id,
            old_level=old_level,
            new_level=new_level,
            changed_by=current_user._id,
            reason=reason
        ).save()
        
        successful_updates += 1
    
    return format_response(
        success=True,
        message=f"Updated {successful_updates} users successfully",
        data={
            'successful_updates': successful_updates,
            'failed_updates': failed_updates
        }
    )

@admin_bp.route('/system/cleanup', methods=['POST'])
@jwt_required_custom
@role_required('Admin')
@validate_json_payload()
@log_activity('system_cleanup', 'system')
def system_cleanup():
    """Perform system cleanup operations"""
    current_user = g.current_user
    data = g.json_data
    
    cleanup_operations = data.get('operations', ['expired_sessions', 'old_audit_logs', 'expired_notifications'])
    days_to_keep = data.get('days_to_keep', 90)
    
    if days_to_keep < 30:
        return format_response(
            success=False,
            message="days_to_keep must be at least 30",
            status_code=400
        )
    
    cleanup_results = {}
    
    try:
        # Clean up expired sessions
        if 'expired_sessions' in cleanup_operations:
            cleaned_sessions = Session.cleanup_expired()
            cleanup_results['expired_sessions'] = cleaned_sessions
        
        # Clean up old audit logs
        if 'old_audit_logs' in cleanup_operations:
            cleaned_logs = AuditLog.cleanup_old_logs(days=days_to_keep)
            cleanup_results['old_audit_logs'] = cleaned_logs
        
        # Clean up expired notifications
        if 'expired_notifications' in cleanup_operations:
            cleaned_notifications = Notification.cleanup_expired()
            cleanup_results['expired_notifications'] = cleaned_notifications
        
        # Clean up old entries (optional, be careful with this)
        if 'old_entries' in cleanup_operations:
            # Only clean entries older than 2 years
            if days_to_keep >= 730:
                cleaned_entries = Entry.cleanup_old_entries(days=days_to_keep)
                cleanup_results['old_entries'] = cleaned_entries
            else:
                cleanup_results['old_entries'] = 'Skipped - days_to_keep must be at least 730 for entry cleanup'
        
        # Log cleanup operation
        AuditLog.log_action(
            user_id=current_user._id,
            action='system_cleanup',
            resource_type='system',
            details={
                'operations': cleanup_operations,
                'days_to_keep': days_to_keep,
                'results': cleanup_results
            }
        )
        
        return format_response(
            success=True,
            message="System cleanup completed successfully",
            data=cleanup_results
        )
        
    except Exception as e:
        return format_response(
            success=False,
            message=f"System cleanup failed: {str(e)}",
            status_code=500
        )

@admin_bp.route('/system/backup', methods=['POST'])
@jwt_required_custom
@role_required('Admin')
@log_activity('system_backup', 'system')
def create_backup():
    """Create system backup (metadata only, actual backup should be handled by external tools)"""
    current_user = g.current_user
    
    # Generate backup metadata
    backup_info = {
        'backup_id': str(ObjectId()),
        'created_at': datetime.utcnow().isoformat(),
        'created_by': {
            'user_id': str(current_user._id),
            'name': current_user.name
        },
        'statistics': {
            'total_users': User.count_all(),
            'total_entries': Entry.count_all(),
            'total_sessions': Session.count_all(),
            'total_notifications': Notification.count_all(),
            'total_audit_logs': AuditLog.count_all()
        },
        'status': 'initiated'
    }
    
    # Log backup initiation
    AuditLog.log_action(
        user_id=current_user._id,
        action='backup_initiated',
        resource_type='system',
        details=backup_info
    )
    
    return format_response(
        success=True,
        message="Backup initiated successfully. Please use external backup tools for actual data backup.",
        data=backup_info
    )

@admin_bp.route('/users/force-logout', methods=['POST'])
@jwt_required_custom
@role_required('Admin')
@validate_json_payload()
@log_activity('force_logout', 'system')
def force_logout_users():
    """Force logout specific users or all users"""
    current_user = g.current_user
    data = g.json_data
    
    user_ids = data.get('user_ids', [])  # If empty, logout all users except current admin
    reason = data.get('reason', 'Admin forced logout')
    
    logout_count = 0
    failed_logouts = []
    
    if user_ids:
        # Logout specific users
        for user_id in user_ids:
            if user_id == str(current_user._id):
                failed_logouts.append({
                    'user_id': user_id,
                    'error': 'Cannot logout yourself'
                })
                continue
            
            user = User.find_by_id(user_id)
            if not user:
                failed_logouts.append({
                    'user_id': user_id,
                    'error': 'User not found'
                })
                continue
            
            try:
                revoked_sessions = revoke_user_sessions(user._id)
                logout_count += 1
                
                # Log individual logout
                AuditLog.log_action(
                    user_id=current_user._id,
                    action='user_forced_logout',
                    resource_type='user',
                    resource_id=user_id,
                    details={
                        'reason': reason,
                        'revoked_sessions': revoked_sessions
                    }
                )
                
            except Exception as e:
                failed_logouts.append({
                    'user_id': user_id,
                    'error': str(e)
                })
    
    else:
        # Logout all users except current admin
        try:
            all_users = User.find_all()
            for user in all_users:
                if str(user._id) != str(current_user._id):
                    revoke_user_sessions(user._id)
                    logout_count += 1
            
            # Log bulk logout
            AuditLog.log_action(
                user_id=current_user._id,
                action='bulk_forced_logout',
                resource_type='system',
                details={
                    'reason': reason,
                    'total_users_logged_out': logout_count
                }
            )
            
        except Exception as e:
            return format_response(
                success=False,
                message=f"Bulk logout failed: {str(e)}",
                status_code=500
            )
    
    return format_response(
        success=True,
        message=f"Force logout completed. {logout_count} users logged out successfully",
        data={
            'successful_logouts': logout_count,
            'failed_logouts': failed_logouts
        }
    )

@admin_bp.route('/system/notifications/broadcast', methods=['POST'])
@jwt_required_custom
@role_required('Admin')
@validate_json_payload(required_fields=['title', 'message'])
@log_activity('broadcast_notification', 'system')
def broadcast_notification():
    """Send notification to all users or specific user groups"""
    current_user = g.current_user
    data = g.json_data
    
    title = data['title'].strip()
    message = data['message'].strip()
    notification_type = data.get('type', 'system')
    priority = data.get('priority', 'medium')
    target_roles = data.get('target_roles', [])  # If empty, send to all users
    target_levels = data.get('target_levels', [])  # For Saalik only
    action_url = data.get('action_url')
    expires_in_days = data.get('expires_in_days', 30)
    
    if not title or not message:
        return format_response(
            success=False,
            message="Title and message are required",
            status_code=400
        )
    
    # Get target users
    target_users = []
    
    if target_roles:
        for role in target_roles:
            is_valid, error = validate_user_role(role)
            if not is_valid:
                return format_response(success=False, message=f"Invalid role: {role}", status_code=400)
            
            role_users = User.find_by_role(role)
            target_users.extend(role_users)
    else:
        target_users = User.find_all()
    
    # Filter by levels if specified (for Saalik only)
    if target_levels:
        filtered_users = []
        for user in target_users:
            if user.role == 'Saalik' and user.level in target_levels:
                filtered_users.append(user)
            elif user.role != 'Saalik':
                filtered_users.append(user)
        target_users = filtered_users
    
    # Remove duplicates
    unique_users = {str(user._id): user for user in target_users}
    target_users = list(unique_users.values())
    
    # Create notifications
    created_count = 0
    failed_count = 0
    
    expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
    
    for user in target_users:
        try:
            notification = Notification.create_notification(
                user_id=user._id,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                action_url=action_url,
                expires_at=expires_at,
                details={
                    'broadcast': True,
                    'sent_by': str(current_user._id)
                }
            )
            created_count += 1
            
        except Exception as e:
            failed_count += 1
    
    # Log broadcast
    AuditLog.log_action(
        user_id=current_user._id,
        action='notification_broadcast',
        resource_type='system',
        details={
            'title': title,
            'target_roles': target_roles,
            'target_levels': target_levels,
            'total_recipients': len(target_users),
            'successful_sends': created_count,
            'failed_sends': failed_count
        }
    )
    
    return format_response(
        success=True,
        message=f"Broadcast notification sent successfully to {created_count} users",
        data={
            'total_recipients': len(target_users),
            'successful_sends': created_count,
            'failed_sends': failed_count
        }
    )

@admin_bp.route('/system/api-keys', methods=['POST'])
@jwt_required_custom
@role_required('Admin')
@validate_json_payload(required_fields=['name'])
@log_activity('create_api_key', 'system')
def create_api_key():
    """Create new API key for system integration"""
    current_user = g.current_user
    data = g.json_data
    
    name = data['name'].strip()
    description = data.get('description', '').strip()
    expires_in_days = data.get('expires_in_days', 365)
    
    if not name:
        return format_response(
            success=False,
            message="API key name is required",
            status_code=400
        )
    
    if expires_in_days < 1 or expires_in_days > 3650:  # Max 10 years
        return format_response(
            success=False,
            message="expires_in_days must be between 1 and 3650",
            status_code=400
        )
    
    # Generate API key
    api_key = generate_api_key()
    expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
    
    # Store API key info (in a real implementation, you'd store this in database)
    api_key_info = {
        'key_id': str(ObjectId()),
        'name': name,
        'description': description,
        'api_key': api_key,  # In production, store hash only
        'created_by': str(current_user._id),
        'created_at': datetime.utcnow().isoformat(),
        'expires_at': expires_at.isoformat(),
        'is_active': True
    }
    
    # Log API key creation
    AuditLog.log_action(
        user_id=current_user._id,
        action='api_key_created',
        resource_type='system',
        details={
            'key_name': name,
            'key_id': api_key_info['key_id'],
            'expires_at': expires_at.isoformat()
        }
    )
    
    return format_response(
        success=True,
        message="API key created successfully",
        data=api_key_info
    )

@admin_bp.route('/audit-logs', methods=['GET'])
@jwt_required_custom
@role_required('Admin')
def get_audit_logs():
    """Get system audit logs with filtering"""
    current_user = g.current_user
    
    # Get query parameters
    page = int(request.args.get('page', 1))
    limit = min(int(request.args.get('limit', 50)), 200)  # Max 200 per page
    user_id = request.args.get('user_id')
    action = request.args.get('action')
    resource_type = request.args.get('resource_type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    skip = (page - 1) * limit
    
    # Parse dates
    start_date_obj = None
    end_date_obj = None
    
    if start_date:
        start_date_obj = parse_date_from_string(start_date)
        if not start_date_obj:
            return format_response(
                success=False,
                message="Invalid start_date format. Use YYYY-MM-DD",
                status_code=400
            )
    
    if end_date:
        end_date_obj = parse_date_from_string(end_date)
        if not end_date_obj:
            return format_response(
                success=False,
                message="Invalid end_date format. Use YYYY-MM-DD",
                status_code=400
            )
    
    # Get audit logs
    logs = AuditLog.find_logs(
        user_id=ObjectId(user_id) if user_id else None,
        action=action,
        resource_type=resource_type,
        start_date=start_date_obj,
        end_date=end_date_obj,
        skip=skip,
        limit=limit
    )
    
    total_count = AuditLog.count_logs(
        user_id=ObjectId(user_id) if user_id else None,
        action=action,
        resource_type=resource_type,
        start_date=start_date_obj,
        end_date=end_date_obj
    )
    
    # Convert logs to dict format
    logs_data = [log.to_dict() for log in logs]
    
    return format_response(
        success=True,
        message="Audit logs retrieved successfully",
        data={
            'logs': logs_data,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total_count,
                'pages': (total_count + limit - 1) // limit
            }
        }
    )


@admin_bp.route('/categories', methods=['GET'])
@jwt_required_custom
@role_required('Admin')
def list_categories():
    """List all categories"""
    categories = Category.find_all()
    return format_response(
        success=True,
        message="Categories retrieved successfully",
        data=categories
    )

@admin_bp.route('/categories', methods=['POST'])
@jwt_required_custom
@role_required('Admin')
@validate_json_payload
def create_category():
    """Create a new category"""
    data = g.json_data
    
    # Validate required fields
    if 'name' not in data:
        return format_response(
            success=False,
            message="Category name is required",
            status_code=400
        )
    
    # Create category
    category = Category(
        name=data['name'],
        description=data.get('description', ''),
        order=data.get('order', 0)
    )
    
    category.save()
    
    return format_response(
        success=True,
        message="Category created successfully",
        data=category,
        status_code=201
    )

@admin_bp.route('/categories', methods=['PUT'])
@jwt_required_custom
@role_required('Admin')
@validate_json_payload
def update_category():
    """Update a category"""
    data = g.json_data
    
    # Get category_id from payload
    category_id = g.payload.get('category_id')
    
    if not category_id:
        return format_response(
            success=False,
            message="Category ID is required",
            status_code=400
        )
    
    # Find category
    category = Category.find_by_id(category_id)
    if not category:
        return format_response(
            success=False,
            message="Category not found",
            status_code=404
        )
    
    # Update fields
    if 'name' in data:
        category.name = data['name']
    if 'description' in data:
        category.description = data['description']
    if 'order' in data:
        category.order = data['order']
    
    category.save()
    
    return format_response(
        success=True,
        message="Category updated successfully",
        data=category
    )

@admin_bp.route('/categories', methods=['DELETE'])
@jwt_required_custom
@role_required('Admin')
def delete_category():
    """Delete a category"""
    # Get category_id from payload
    category_id = g.payload.get('category_id')
    
    if not category_id:
        return format_response(
            success=False,
            message="Category ID is required",
            status_code=400
        )
    
    # Find category
    category = Category.find_by_id(category_id)
    if not category:
        return format_response(
            success=False,
            message="Category not found",
            status_code=404
        )
    
    # Delete category
    category.delete()
    
    return format_response(
        success=True,
        message="Category deleted successfully"
    )
