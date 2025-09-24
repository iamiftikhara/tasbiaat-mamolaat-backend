"""
Daily entry routes for Saalik submissions with validation and business logic
"""

from flask import Blueprint, g, request
from utils.decorators import jwt_required_custom, role_required, validate_json_payload, log_activity, rate_limit
from utils.validators import validate_entry_data, validate_date_range, validate_comment
from utils.helpers import (
    format_response, 
    get_saalik_level_requirements, 
    calculate_zikr_completion_status,
    check_zikr_mandatory_rule,
    should_restart_cycle,
    parse_date_from_string,
    format_date_for_display
)
from models.entry import Entry
from models.user import User
from models.level import Level
from models.audit_log import AuditLog
from datetime import datetime, date, timedelta
from bson import ObjectId

entries_bp = Blueprint('entries', __name__)

@entries_bp.route('/', methods=['POST'])
@jwt_required_custom
@rate_limit(max_requests=50, window_minutes=60)
@validate_json_payload(required_fields=['date', 'categories'])
@log_activity('create_entry', 'entry')
def create_entry():
    """Create or update daily entry for current user"""
    current_user = g.current_user
    data = g.json_data
    
    # Only Saalik can create entries
    if current_user.role != 'Saalik':
        return format_response(
            success=False,
            message="Only Saalik users can submit daily entries",
            status_code=403
        )
    
    # Parse and validate date
    entry_date = parse_date_from_string(data['date'])
    if not entry_date:
        return format_response(
            success=False,
            message="Invalid date format. Use YYYY-MM-DD",
            status_code=400
        )
    
    # Check if date is not in future
    if entry_date > date.today():
        return format_response(
            success=False,
            message="Cannot submit entries for future dates",
            status_code=400
        )
    
    # Check if date is not too old (e.g., more than 7 days)
    if (date.today() - entry_date).days > 7:
        return format_response(
            success=False,
            message="Cannot submit entries older than 7 days",
            status_code=400
        )
    
    # Validate entry data based on user's level
    is_valid, error = validate_entry_data(data['categories'], current_user.level)
    if not is_valid:
        return format_response(success=False, message=error, status_code=400)
    
    # Get level requirements
    level_requirements = get_saalik_level_requirements(current_user.level)
    if not level_requirements:
        return format_response(
            success=False,
            message="Invalid Saalik level",
            status_code=400
        )
    
    # Check if entry already exists for this date
    existing_entry = Entry.find_by_user_and_date(current_user._id, entry_date)
    
    # Calculate Zikr completion status
    zikr_completion = calculate_zikr_completion_status(data['categories'], level_requirements)
    
    # Check Zikr mandatory rule
    zikr_mandatory_violated = check_zikr_mandatory_rule(data['categories'], level_requirements)
    
    # Check if cycle should restart due to violations
    cycle_restart_needed = should_restart_cycle(current_user, data['categories'], level_requirements)
    
    if existing_entry:
        # Update existing entry
        old_values = existing_entry.to_dict()
        
        existing_entry.categories = data['categories']
        existing_entry.zikr_completion = zikr_completion
        existing_entry.zikr_mandatory_violated = zikr_mandatory_violated
        existing_entry.updated_at = datetime.utcnow()
        
        # Add comment if provided
        comment = data.get('comment', '').strip()
        if comment:
            is_valid, error = validate_comment(comment)
            if not is_valid:
                return format_response(success=False, message=error, status_code=400)
            
            existing_entry.add_comment(current_user._id, comment)
        
        # Add audit entry
        existing_entry.add_audit_entry(
            user_id=current_user._id,
            action='entry_updated',
            details=f"Entry updated for {entry_date}"
        )
        
        existing_entry.save()
        
        # Log the update
        AuditLog.log_action(
            user_id=current_user._id,
            action='entry_updated',
            resource_type='entry',
            resource_id=str(existing_entry._id),
            old_values=old_values,
            new_values=existing_entry.to_dict()
        )
        
        entry_data = existing_entry.to_dict()
        message = "Entry updated successfully"
        
    else:
        # Create new entry
        new_entry = Entry(
            user_id=current_user._id,
            murabi_id=current_user.murabi_id,
            date=entry_date,
            level=current_user.level,
            categories=data['categories'],
            zikr_completion=zikr_completion,
            zikr_mandatory_violated=zikr_mandatory_violated
        )
        
        # Add comment if provided
        comment = data.get('comment', '').strip()
        if comment:
            is_valid, error = validate_comment(comment)
            if not is_valid:
                return format_response(success=False, message=error, status_code=400)
            
            new_entry.add_comment(current_user._id, comment)
        
        # Add audit entry
        new_entry.add_audit_entry(
            user_id=current_user._id,
            action='entry_created',
            details=f"Entry created for {entry_date}"
        )
        
        new_entry.save()
        
        # Log the creation
        AuditLog.log_action(
            user_id=current_user._id,
            action='entry_created',
            resource_type='entry',
            resource_id=str(new_entry._id),
            new_values=new_entry.to_dict()
        )
        
        entry_data = new_entry.to_dict()
        message = "Entry created successfully"
    
    # Handle cycle restart if needed
    if cycle_restart_needed:
        current_user.level_start_date = date.today()
        current_user.save()
        
        AuditLog.log_action(
            user_id=current_user._id,
            action='cycle_restarted',
            resource_type='user',
            resource_id=str(current_user._id),
            details={
                'reason': 'zikr_mandatory_violation',
                'level_start_date': current_user.level_start_date.isoformat()
            }
        )
        
        entry_data['cycle_restarted'] = True
        message += " (Cycle restarted due to Zikr violation)"
    
    return format_response(
        success=True,
        message=message,
        data=entry_data,
        status_code=201 if not existing_entry else 200
    )

@entries_bp.route('/', methods=['GET'])
@jwt_required_custom
def get_entries():
    """Get entries based on user role and permissions"""
    current_user = g.current_user
    
    # Get query parameters
    page = int(request.args.get('page', 1))
    limit = min(int(request.args.get('limit', 20)), 100)  # Max 100 per page
    user_id = request.args.get('user_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    skip = (page - 1) * limit
    
    # Parse dates if provided
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
    
    # Validate date range
    if start_date_obj and end_date_obj:
        is_valid, error = validate_date_range(start_date_obj, end_date_obj)
        if not is_valid:
            return format_response(success=False, message=error, status_code=400)
    
    # Determine which entries to fetch based on role
    if current_user.role == 'Saalik':
        # Saalik can only see their own entries
        if user_id and user_id != str(current_user._id):
            return format_response(
                success=False,
                message="You can only view your own entries",
                status_code=403
            )
        
        entries = Entry.find_by_user(
            current_user._id, 
            start_date=start_date_obj, 
            end_date=end_date_obj,
            skip=skip, 
            limit=limit
        )
        total_count = Entry.count_by_user(current_user._id, start_date_obj, end_date_obj)
        
    elif current_user.role == 'Murabi':
        # Murabi can see entries of their assigned Saalik
        if user_id:
            # Check if the user is assigned to this Murabi
            user = User.find_by_id(user_id)
            if not user or str(user.murabi_id) != str(current_user._id):
                return format_response(
                    success=False,
                    message="You can only view entries of your assigned Saalik",
                    status_code=403
                )
            
            entries = Entry.find_by_user(
                ObjectId(user_id), 
                start_date=start_date_obj, 
                end_date=end_date_obj,
                skip=skip, 
                limit=limit
            )
            total_count = Entry.count_by_user(ObjectId(user_id), start_date_obj, end_date_obj)
        else:
            # Get all entries from assigned Saalik
            entries = Entry.find_by_murabi(
                current_user._id,
                start_date=start_date_obj,
                end_date=end_date_obj,
                skip=skip,
                limit=limit
            )
            total_count = Entry.count_by_murabi(current_user._id, start_date_obj, end_date_obj)
    
    elif current_user.role in ['Masool', 'Sheikh', 'Admin']:
        # Higher roles can see entries based on hierarchy
        if user_id:
            # Check permissions for specific user
            user = User.find_by_id(user_id)
            if not user:
                return format_response(
                    success=False,
                    message="User not found",
                    status_code=404
                )
            
            # Check if user is in hierarchy
            if current_user.role != 'Admin' and not User.is_in_hierarchy(user._id, current_user._id):
                return format_response(
                    success=False,
                    message="You can only view entries of users in your hierarchy",
                    status_code=403
                )
            
            entries = Entry.find_by_user(
                ObjectId(user_id), 
                start_date=start_date_obj, 
                end_date=end_date_obj,
                skip=skip, 
                limit=limit
            )
            total_count = Entry.count_by_user(ObjectId(user_id), start_date_obj, end_date_obj)
        else:
            # Get entries from hierarchy
            if current_user.role == 'Admin':
                entries = Entry.find_all(
                    start_date=start_date_obj,
                    end_date=end_date_obj,
                    skip=skip,
                    limit=limit
                )
                total_count = Entry.count_all(start_date_obj, end_date_obj)
            else:
                entries = Entry.find_by_hierarchy(
                    current_user._id,
                    start_date=start_date_obj,
                    end_date=end_date_obj,
                    skip=skip,
                    limit=limit
                )
                total_count = Entry.count_by_hierarchy(current_user._id, start_date_obj, end_date_obj)
    
    else:
        return format_response(
            success=False,
            message="Invalid user role",
            status_code=403
        )
    
    # Convert entries to dict format
    entries_data = [entry.to_dict() for entry in entries]
    
    return format_response(
        success=True,
        message="Entries retrieved successfully",
        data={
            'entries': entries_data,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total_count,
                'pages': (total_count + limit - 1) // limit
            }
        }
    )

@entries_bp.route('/<entry_id>', methods=['GET'])
@jwt_required_custom
def get_entry(entry_id):
    """Get specific entry details"""
    current_user = g.current_user
    
    # Find the entry
    entry = Entry.find_by_id(entry_id)
    if not entry:
        return format_response(
            success=False,
            message="Entry not found",
            status_code=404
        )
    
    # Check permissions
    can_view = False
    
    if current_user.role == 'Saalik':
        # Saalik can only view their own entries
        can_view = str(entry.user_id) == str(current_user._id)
    elif current_user.role == 'Murabi':
        # Murabi can view entries of their assigned Saalik
        can_view = str(entry.murabi_id) == str(current_user._id)
    elif current_user.role in ['Masool', 'Sheikh', 'Admin']:
        # Higher roles can view based on hierarchy
        if current_user.role == 'Admin':
            can_view = True
        else:
            user = User.find_by_id(entry.user_id)
            if user:
                can_view = User.is_in_hierarchy(user._id, current_user._id)
    
    if not can_view:
        return format_response(
            success=False,
            message="Insufficient permissions to view this entry",
            status_code=403
        )
    
    # Get entry data with user information
    entry_data = entry.to_dict()
    
    # Add user information if viewing as Murabi or higher
    if current_user.role != 'Saalik':
        user = User.find_by_id(entry.user_id)
        if user:
            entry_data['user_info'] = {
                'name': user.name,
                'phone': user.phone,
                'level': user.level
            }
    
    return format_response(
        success=True,
        message="Entry details retrieved successfully",
        data=entry_data
    )

@entries_bp.route('/<entry_id>/comment', methods=['POST'])
@jwt_required_custom
@validate_json_payload(required_fields=['comment'])
@log_activity('add_entry_comment', 'entry')
def add_entry_comment(entry_id):
    """Add comment to an entry"""
    current_user = g.current_user
    data = g.json_data
    
    # Find the entry
    entry = Entry.find_by_id(entry_id)
    if not entry:
        return format_response(
            success=False,
            message="Entry not found",
            status_code=404
        )
    
    # Check permissions
    can_comment = False
    
    if current_user.role == 'Saalik':
        # Saalik can comment on their own entries
        can_comment = str(entry.user_id) == str(current_user._id)
    elif current_user.role == 'Murabi':
        # Murabi can comment on entries of their assigned Saalik
        can_comment = str(entry.murabi_id) == str(current_user._id)
    elif current_user.role in ['Masool', 'Sheikh', 'Admin']:
        # Higher roles can comment based on hierarchy
        if current_user.role == 'Admin':
            can_comment = True
        else:
            user = User.find_by_id(entry.user_id)
            if user:
                can_comment = User.is_in_hierarchy(user._id, current_user._id)
    
    if not can_comment:
        return format_response(
            success=False,
            message="Insufficient permissions to comment on this entry",
            status_code=403
        )
    
    # Validate comment
    comment = data['comment'].strip()
    is_valid, error = validate_comment(comment)
    if not is_valid:
        return format_response(success=False, message=error, status_code=400)
    
    # Add comment
    entry.add_comment(current_user._id, comment)
    entry.save()
    
    # Log the comment
    AuditLog.log_action(
        user_id=current_user._id,
        action='entry_comment_added',
        resource_type='entry',
        resource_id=entry_id,
        new_values={'comment': comment}
    )
    
    return format_response(
        success=True,
        message="Comment added successfully",
        data={'comment_id': str(entry.comments[-1]['_id'])}
    )

@entries_bp.route('/summary', methods=['GET'])
@jwt_required_custom
def get_entry_summary():
    """Get entry summary for current user or specified user"""
    current_user = g.current_user
    
    # Get query parameters
    user_id = request.args.get('user_id')
    period = request.args.get('period', 'week')  # week, month, custom
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Determine target user
    if user_id:
        # Check permissions
        if current_user.role == 'Saalik' and user_id != str(current_user._id):
            return format_response(
                success=False,
                message="You can only view your own summary",
                status_code=403
            )
        
        target_user = User.find_by_id(user_id)
        if not target_user:
            return format_response(
                success=False,
                message="User not found",
                status_code=404
            )
        
        # Check hierarchy permissions
        if current_user.role == 'Murabi':
            if str(target_user.murabi_id) != str(current_user._id):
                return format_response(
                    success=False,
                    message="You can only view summaries of your assigned Saalik",
                    status_code=403
                )
        elif current_user.role in ['Masool', 'Sheikh'] and current_user.role != 'Admin':
            if not User.is_in_hierarchy(target_user._id, current_user._id):
                return format_response(
                    success=False,
                    message="You can only view summaries of users in your hierarchy",
                    status_code=403
                )
    else:
        target_user = current_user
    
    # Calculate date range
    if period == 'custom':
        if not start_date or not end_date:
            return format_response(
                success=False,
                message="start_date and end_date are required for custom period",
                status_code=400
            )
        
        start_date_obj = parse_date_from_string(start_date)
        end_date_obj = parse_date_from_string(end_date)
        
        if not start_date_obj or not end_date_obj:
            return format_response(
                success=False,
                message="Invalid date format. Use YYYY-MM-DD",
                status_code=400
            )
        
        is_valid, error = validate_date_range(start_date_obj, end_date_obj)
        if not is_valid:
            return format_response(success=False, message=error, status_code=400)
    
    elif period == 'week':
        from utils.helpers import get_date_range_for_week
        start_date_obj, end_date_obj = get_date_range_for_week()
    
    elif period == 'month':
        from utils.helpers import get_date_range_for_month
        start_date_obj, end_date_obj = get_date_range_for_month()
    
    else:
        return format_response(
            success=False,
            message="Invalid period. Use 'week', 'month', or 'custom'",
            status_code=400
        )
    
    # Generate summary
    from utils.helpers import generate_weekly_summary, calculate_cycle_progress
    
    summary = generate_weekly_summary(target_user, start_date_obj, end_date_obj)
    cycle_progress = calculate_cycle_progress(target_user)
    
    return format_response(
        success=True,
        message="Entry summary retrieved successfully",
        data={
            'user_info': {
                'name': target_user.name,
                'level': target_user.level,
                'cycle_days': target_user.cycle_days
            },
            'period': {
                'type': period,
                'start_date': start_date_obj.isoformat(),
                'end_date': end_date_obj.isoformat()
            },
            'summary': summary,
            'cycle_progress': cycle_progress
        }
    )

@entries_bp.route('/<entry_id>', methods=['DELETE'])
@jwt_required_custom
@role_required('Masool', 'Sheikh', 'Admin')
@log_activity('delete_entry', 'entry')
def delete_entry(entry_id):
    """Delete an entry (Masool and above only)"""
    current_user = g.current_user
    
    # Find the entry
    entry = Entry.find_by_id(entry_id)
    if not entry:
        return format_response(
            success=False,
            message="Entry not found",
            status_code=404
        )
    
    # Check permissions
    can_delete = False
    
    if current_user.role == 'Admin':
        can_delete = True
    elif current_user.role in ['Masool', 'Sheikh']:
        user = User.find_by_id(entry.user_id)
        if user:
            can_delete = User.is_in_hierarchy(user._id, current_user._id)
    
    if not can_delete:
        return format_response(
            success=False,
            message="Insufficient permissions to delete this entry",
            status_code=403
        )
    
    # Store entry data for audit log
    entry_data = entry.to_dict()
    
    # Delete the entry
    from pymongo import MongoClient
    from config import Config
    
    client = MongoClient(Config.MONGO_URI)
    db = client[Config.MONGO_DB_NAME]
    result = db.entries.delete_one({'_id': entry._id})
    
    if result.deleted_count == 0:
        return format_response(
            success=False,
            message="Failed to delete entry",
            status_code=500
        )
    
    # Log the deletion
    AuditLog.log_action(
        user_id=current_user._id,
        action='entry_deleted',
        resource_type='entry',
        resource_id=entry_id,
        old_values=entry_data
    )
    
    return format_response(
        success=True,
        message="Entry deleted successfully"
    )