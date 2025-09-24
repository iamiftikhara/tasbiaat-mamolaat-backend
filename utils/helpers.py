"""
Helper utilities for common operations
"""

from datetime import datetime, date, timedelta
from flask import jsonify, current_app

def format_response(success=True, message="", data=None, status_code=200, **kwargs):
    """Format standardized API response"""
    response = {
        'success': success,
        'message': message,
        'timestamp': datetime.utcnow().isoformat(),
        **kwargs
    }
    
    if data is not None:
        response['data'] = data
    
    return jsonify(response), status_code

def get_current_user():
    """Get current authenticated user from Flask g"""
    from flask import g
    return getattr(g, 'current_user', None)

def calculate_cycle_progress(user):
    """Calculate user's current cycle progress"""
    if not user.level_start_date:
        return {
            'current_day': 0,
            'total_days': user.cycle_days,
            'progress_percentage': 0,
            'days_remaining': user.cycle_days,
            'is_completed': False
        }
    
    start_date = user.level_start_date
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    elif isinstance(start_date, datetime):
        start_date = start_date.date()
    
    today = date.today()
    days_elapsed = (today - start_date).days + 1  # +1 to include start day
    
    current_day = min(days_elapsed, user.cycle_days)
    progress_percentage = (current_day / user.cycle_days) * 100
    days_remaining = max(0, user.cycle_days - days_elapsed)
    is_completed = days_elapsed >= user.cycle_days
    
    return {
        'current_day': current_day,
        'total_days': user.cycle_days,
        'progress_percentage': round(progress_percentage, 2),
        'days_remaining': days_remaining,
        'is_completed': is_completed,
        'start_date': start_date.isoformat(),
        'expected_completion_date': (start_date + timedelta(days=user.cycle_days - 1)).isoformat()
    }

def get_saalik_level_requirements(level):
    """Get requirements for a specific Saalik level"""
    from models.level import Level
    
    level_obj = Level.find_by_level(level)
    if not level_obj:
        return None
    
    return {
        'level': level_obj.level,
        'name_urdu': level_obj.name_urdu,
        'description': level_obj.description,
        'required_fields': level_obj.required_fields
    }

def calculate_zikr_completion_status(entry_data):
    """Calculate Zikr completion status from entry data"""
    categories = entry_data.get('categories', {})
    zikr_data = categories.get('zikr', {})
    
    if not zikr_data:
        return False
    
    # Check if Zikr is marked as completed
    return zikr_data.get('completed', False)

def generate_weekly_summary(entries):
    """Generate weekly summary from daily entries"""
    if not entries:
        return {
            'total_days': 0,
            'completed_days': 0,
            'completion_rate': 0,
            'zikr_completion_rate': 0,
            'categories_summary': {}
        }
    
    total_days = len(entries)
    completed_days = 0
    zikr_completed_days = 0
    categories_summary = {}
    
    for entry in entries:
        # Check if day is completed (all required categories done)
        if entry.get('is_completed', False):
            completed_days += 1
        
        # Check Zikr completion
        if calculate_zikr_completion_status(entry):
            zikr_completed_days += 1
        
        # Aggregate category data
        categories = entry.get('categories', {})
        for category, data in categories.items():
            if category not in categories_summary:
                categories_summary[category] = {
                    'total_days': 0,
                    'completed_days': 0,
                    'completion_rate': 0
                }
            
            categories_summary[category]['total_days'] += 1
            if data.get('completed', False):
                categories_summary[category]['completed_days'] += 1
    
    # Calculate completion rates
    completion_rate = (completed_days / total_days) * 100 if total_days > 0 else 0
    zikr_completion_rate = (zikr_completed_days / total_days) * 100 if total_days > 0 else 0
    
    # Calculate category completion rates
    for category in categories_summary:
        cat_total = categories_summary[category]['total_days']
        cat_completed = categories_summary[category]['completed_days']
        categories_summary[category]['completion_rate'] = (cat_completed / cat_total) * 100 if cat_total > 0 else 0
    
    return {
        'total_days': total_days,
        'completed_days': completed_days,
        'completion_rate': round(completion_rate, 2),
        'zikr_completion_rate': round(zikr_completion_rate, 2),
        'categories_summary': categories_summary
    }

def get_date_range_for_week(year, week):
    """Get start and end dates for a specific week"""
    # Get the first day of the year
    jan_1 = date(year, 1, 1)
    
    # Find the first Monday of the year
    days_to_monday = (7 - jan_1.weekday()) % 7
    first_monday = jan_1 + timedelta(days=days_to_monday)
    
    # Calculate the start of the specified week
    week_start = first_monday + timedelta(weeks=week - 1)
    week_end = week_start + timedelta(days=6)
    
    return week_start, week_end

def get_date_range_for_month(year, month):
    """Get start and end dates for a specific month"""
    from calendar import monthrange
    
    start_date = date(year, month, 1)
    _, last_day = monthrange(year, month)
    end_date = date(year, month, last_day)
    
    return start_date, end_date

def check_zikr_mandatory_rule(user, entry_date):
    """Check if Zikr mandatory rule applies"""
    zikr_mode = user.settings.get('zikr_mode', current_app.config['DEFAULT_ZIKR_MODE'])
    
    if zikr_mode == 'auto_restart':
        return True  # Always mandatory in auto-restart mode
    elif zikr_mode == 'murabi_controlled':
        # Check if Murabi has enabled mandatory Zikr for this user
        return user.settings.get('zikr_mandatory', False)
    
    return False

def should_restart_cycle(user, missed_zikr_date):
    """Determine if cycle should be restarted due to missed Zikr"""
    zikr_mode = user.settings.get('zikr_mode', current_app.config['DEFAULT_ZIKR_MODE'])
    
    if zikr_mode == 'auto_restart':
        return True
    elif zikr_mode == 'murabi_controlled':
        # Only restart if Murabi has enabled this setting
        return user.settings.get('auto_restart_on_missed_zikr', False)
    
    return False

def format_date_for_display(date_obj):
    """Format date for display in API responses"""
    if isinstance(date_obj, str):
        return date_obj
    elif isinstance(date_obj, (date, datetime)):
        return date_obj.isoformat()
    return None

def parse_date_from_string(date_string):
    """Parse date from string in various formats"""
    if not date_string:
        return None
    
    formats = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']
    
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt).date()
        except ValueError:
            continue
    
    return None

def get_user_hierarchy_chain(user):
    """Get the complete hierarchy chain for a user"""
    from models.user import User
    
    chain = []
    current_user = user
    
    while current_user and current_user.murabi_id:
        murabi = User.find_by_id(current_user.murabi_id)
        if murabi:
            chain.append({
                'id': str(murabi._id),
                'name': murabi.name,
                'role': murabi.role,
                'phone': murabi.phone
            })
            current_user = murabi
        else:
            break
    
    return chain

def mask_sensitive_data(data, fields_to_mask=None):
    """Mask sensitive data in API responses"""
    if fields_to_mask is None:
        fields_to_mask = ['password', 'password_hash', 'api_key', 'token']
    
    if isinstance(data, dict):
        masked_data = {}
        for key, value in data.items():
            if key.lower() in [field.lower() for field in fields_to_mask]:
                masked_data[key] = '***masked***'
            elif isinstance(value, (dict, list)):
                masked_data[key] = mask_sensitive_data(value, fields_to_mask)
            else:
                masked_data[key] = value
        return masked_data
    elif isinstance(data, list):
        return [mask_sensitive_data(item, fields_to_mask) for item in data]
    
    return data