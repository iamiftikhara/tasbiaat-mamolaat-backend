"""
Validation utilities for user input and business logic
"""

import re
from datetime import datetime, date
from flask import current_app

def validate_phone(phone):
    """Validate Pakistani phone number format"""
    if not phone:
        return False, "Phone number is required"
    
    # Remove spaces and dashes
    phone = re.sub(r'[\s-]', '', phone)
    
    # Pakistani phone number patterns
    patterns = [
        r'^(\+92|0092|92)?3[0-9]{9}$',  # Mobile numbers
        r'^(\+92|0092|92)?[2-9][0-9]{7,10}$'  # Landline numbers
    ]
    
    for pattern in patterns:
        if re.match(pattern, phone):
            return True, None
    
    return False, "Invalid Pakistani phone number format"

def validate_email(email):
    """Validate email format"""
    if not email:
        return False, "Email is required"
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if re.match(pattern, email):
        return True, None
    
    return False, "Invalid email format"

def validate_password(password):
    """Validate password strength"""
    if not password:
        return False, "Password is required"
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if len(password) > 128:
        return False, "Password must be less than 128 characters"
    
    # Check for at least one uppercase, lowercase, digit, and special character
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, None

def validate_user_role(role):
    """Validate user role"""
    valid_roles = current_app.config['USER_ROLES']
    
    if role not in valid_roles:
        return False, f"Invalid role. Must be one of: {', '.join(valid_roles)}"
    
    return True, None

def validate_saalik_level(level):
    """Validate Saalik level"""
    valid_levels = current_app.config['SAALIK_LEVELS']
    
    if level not in valid_levels:
        return False, f"Invalid Saalik level. Must be one of: {', '.join(map(str, valid_levels))}"
    
    return True, None

def validate_entry_data(entry_data, user_level):
    """Validate daily entry data based on user's Saalik level"""
    if not isinstance(entry_data, dict):
        return False, "Entry data must be a dictionary"
    
    # Get required fields for user's level
    from models.level import Level
    level_obj = Level.find_by_level(user_level)
    
    if not level_obj:
        return False, f"Invalid user level: {user_level}"
    
    required_fields = level_obj.required_fields
    categories = entry_data.get('categories', {})
    
    # Check if all required categories are present
    for field in required_fields:
        category = field.replace('categories.', '')
        if category not in categories:
            return False, f"Missing required category: {category}"
        
        # Validate category data
        category_data = categories[category]
        if not isinstance(category_data, dict):
            return False, f"Category {category} must be a dictionary"
        
        # Check for required fields in category
        if 'completed' not in category_data:
            return False, f"Category {category} must have 'completed' field"
        
        if not isinstance(category_data['completed'], bool):
            return False, f"Category {category} 'completed' must be boolean"
    
    # Validate date format
    entry_date = entry_data.get('date')
    if entry_date:
        try:
            datetime.strptime(entry_date, '%Y-%m-%d')
        except ValueError:
            return False, "Invalid date format. Use YYYY-MM-DD"
    
    return True, None

def validate_cycle_days(cycle_days):
    """Validate cycle days"""
    if not isinstance(cycle_days, int):
        return False, "Cycle days must be an integer"
    
    min_days = current_app.config.get('MIN_CYCLE_DAYS', 7)
    max_days = current_app.config.get('MAX_CYCLE_DAYS', 365)
    
    if cycle_days < min_days or cycle_days > max_days:
        return False, f"Cycle days must be between {min_days} and {max_days}"
    
    return True, None

def validate_date_range(start_date, end_date):
    """Validate date range"""
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        return False, "Invalid date format. Use YYYY-MM-DD"
    
    if start > end:
        return False, "Start date must be before end date"
    
    if end > date.today():
        return False, "End date cannot be in the future"
    
    # Limit date range to prevent excessive queries
    max_range_days = current_app.config.get('MAX_DATE_RANGE_DAYS', 365)
    if (end - start).days > max_range_days:
        return False, f"Date range cannot exceed {max_range_days} days"
    
    return True, None

def validate_comment(comment):
    """Validate comment text"""
    if not comment:
        return True, None  # Comments are optional
    
    if not isinstance(comment, str):
        return False, "Comment must be a string"
    
    if len(comment) > 1000:
        return False, "Comment cannot exceed 1000 characters"
    
    # Check for inappropriate content (basic check)
    inappropriate_words = current_app.config.get('INAPPROPRIATE_WORDS', [])
    comment_lower = comment.lower()
    
    for word in inappropriate_words:
        if word.lower() in comment_lower:
            return False, "Comment contains inappropriate content"
    
    return True, None

def validate_notification_type(notification_type):
    """Validate notification type"""
    valid_types = ['info', 'warning', 'error', 'success']
    
    if notification_type not in valid_types:
        return False, f"Invalid notification type. Must be one of: {', '.join(valid_types)}"
    
    return True, None

def validate_priority(priority):
    """Validate priority level"""
    valid_priorities = ['low', 'normal', 'high', 'urgent']
    
    if priority not in valid_priorities:
        return False, f"Invalid priority. Must be one of: {', '.join(valid_priorities)}"
    
    return True, None

def sanitize_input(text):
    """Sanitize user input to prevent XSS and injection attacks"""
    if not isinstance(text, str):
        return text
    
    # Remove potentially dangerous characters
    text = re.sub(r'[<>"\']', '', text)
    
    # Limit length
    if len(text) > 1000:
        text = text[:1000]
    
    return text.strip()