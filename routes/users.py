"""
User management routes with role-based creation and hierarchy management
"""

from flask import Blueprint, g
from utils.decorators import jwt_required_custom, role_required, validate_json_payload, log_activity, rate_limit
from utils.validators import validate_phone, validate_email, validate_password, validate_user_role, validate_saalik_level
from utils.helpers import format_response, get_user_hierarchy_chain, mask_sensitive_data
from utils.auth import hash_password, can_user_create_role, check_role_hierarchy
from models.user import User
from models.level import Level
from models.audit_log import AuditLog
from datetime import datetime

users_bp = Blueprint('users', __name__)

@users_bp.route('/', methods=['POST'])
@jwt_required_custom
@rate_limit(max_requests=10, window_minutes=60)
@validate_json_payload(required_fields=['name', 'phone', 'password', 'role'])
@log_activity('create_user', 'user')
def create_user():
    """Create a new user with role-based restrictions"""
    current_user = g.current_user
    data = g.json_data
    
    # Extract and validate data
    name = data['name'].strip()
    phone = data['phone'].strip()
    email = data.get('email', '').strip() if data.get('email') else None
    password = data['password']
    role = data['role']
    level = data.get('level', 0)
    cycle_days = data.get('cycle_days', 40)
    
    # Validate input
    if not name:
        return format_response(
            success=False,
            message="Name is required",
            status_code=400
        )
    
    is_valid, error = validate_phone(phone)
    if not is_valid:
        return format_response(success=False, message=error, status_code=400)
    
    if email:
        is_valid, error = validate_email(email)
        if not is_valid:
            return format_response(success=False, message=error, status_code=400)
    
    is_valid, error = validate_password(password)
    if not is_valid:
        return format_response(success=False, message=error, status_code=400)
    
    is_valid, error = validate_user_role(role)
    if not is_valid:
        return format_response(success=False, message=error, status_code=400)
    
    is_valid, error = validate_saalik_level(level)
    if not is_valid:
        return format_response(success=False, message=error, status_code=400)
    
    # Check if current user can create this role
    if not can_user_create_role(current_user.role, role):
        return format_response(
            success=False,
            message=f"You don't have permission to create users with role: {role}",
            status_code=403
        )
    
    # Check if phone already exists
    existing_user = User.find_by_phone(phone)
    if existing_user:
        return format_response(
            success=False,
            message="Phone number already registered",
            status_code=400
        )
    
    # Check if email already exists (if provided)
    if email:
        existing_user = User.find_by_email(email)
        if existing_user:
            return format_response(
                success=False,
                message="Email already registered",
                status_code=400
            )
    
    # Determine Murabi assignment based on role hierarchy
    murabi_id = None
    if role == 'Saalik':
        # Saalik must be assigned to current user if current user is Murabi or higher
        if current_user.role in ['Murabi', 'Masool', 'Sheikh', 'Admin']:
            murabi_id = current_user._id
        else:
            return format_response(
                success=False,
                message="Only Murabi or higher can create Saalik users",
                status_code=403
            )
    elif role == 'Murabi':
        # Murabi can be assigned to Masool or higher
        if current_user.role in ['Masool', 'Sheikh', 'Admin']:
            murabi_id = current_user._id
    elif role in ['Masool', 'Sheikh']:
        # These roles can be assigned to Sheikh or Admin
        if current_user.role in ['Sheikh', 'Admin']:
            murabi_id = current_user._id
    
    # Create new user
    try:
        new_user = User(
            name=name,
            phone=phone,
            email=email,
            password_hash=hash_password(password),
            role=role,
            murabi_id=murabi_id,
            level=level,
            cycle_days=cycle_days,
            level_start_date=datetime.utcnow().date(),
            created_by=current_user._id
        )
        
        new_user.save()
        
        # Log user creation
        AuditLog.log_action(
            user_id=current_user._id,
            action='user_created',
            resource_type='user',
            resource_id=str(new_user._id),
            new_values={
                'name': name,
                'phone': phone,
                'email': email,
                'role': role,
                'level': level,
                'murabi_id': str(murabi_id) if murabi_id else None
            }
        )
        
        # Return user data without sensitive information
        user_data = new_user.to_dict()
        user_data.pop('password_hash', None)
        
        return format_response(
            success=True,
            message="User created successfully",
            data=user_data,
            status_code=201
        )
        
    except Exception as e:
        return format_response(
            success=False,
            message=f"Failed to create user: {str(e)}",
            status_code=500
        )

@users_bp.route('/', methods=['GET'])
@jwt_required_custom
@role_required('Murabi', 'Masool', 'Sheikh', 'Admin')
def get_users():
    """Get users based on current user's role and hierarchy"""
    current_user = g.current_user
    
    # Get query parameters
    from flask import request
    page = int(request.args.get('page', 1))
    limit = min(int(request.args.get('limit', 20)), 100)  # Max 100 per page
    role_filter = request.args.get('role')
    search = request.args.get('search', '').strip()
    
    skip = (page - 1) * limit
    
    # Build query based on user's role
    if current_user.role == 'Admin':
        # Admin can see all users
        users = User.find_all(skip=skip, limit=limit, role_filter=role_filter, search=search)
        total_count = User.count_all(role_filter=role_filter, search=search)
    elif current_user.role == 'Sheikh':
        # Sheikh can see all users in their hierarchy
        users = User.find_by_hierarchy(current_user._id, skip=skip, limit=limit, role_filter=role_filter, search=search)
        total_count = User.count_by_hierarchy(current_user._id, role_filter=role_filter, search=search)
    elif current_user.role == 'Masool':
        # Masool can see Murabi and Saalik in their hierarchy
        users = User.find_by_murabi_hierarchy(current_user._id, skip=skip, limit=limit, role_filter=role_filter, search=search)
        total_count = User.count_by_murabi_hierarchy(current_user._id, role_filter=role_filter, search=search)
    elif current_user.role == 'Murabi':
        # Murabi can see their assigned Saalik
        users = User.find_by_murabi_id(current_user._id, skip=skip, limit=limit, search=search)
        total_count = User.count_by_murabi_id(current_user._id, search=search)
    else:
        return format_response(
            success=False,
            message="Insufficient permissions",
            status_code=403
        )
    
    # Remove sensitive data
    users_data = []
    for user in users:
        user_data = user.to_dict()
        user_data.pop('password_hash', None)
        users_data.append(user_data)
    
    return format_response(
        success=True,
        message="Users retrieved successfully",
        data={
            'users': users_data,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total_count,
                'pages': (total_count + limit - 1) // limit
            }
        }
    )

@users_bp.route('/<user_id>', methods=['GET'])
@jwt_required_custom
def get_user(user_id):
    """Get specific user details"""
    current_user = g.current_user
    
    # Find the user
    user = User.find_by_id(user_id)
    if not user:
        return format_response(
            success=False,
            message="User not found",
            status_code=404
        )
    
    # Check permissions
    can_view = False
    
    if current_user.role == 'Admin':
        can_view = True
    elif str(current_user._id) == user_id:
        can_view = True  # Users can view their own profile
    elif current_user.role in ['Sheikh', 'Masool'] and User.is_in_hierarchy(user._id, current_user._id):
        can_view = True
    elif current_user.role == 'Murabi' and str(user.murabi_id) == str(current_user._id):
        can_view = True
    
    if not can_view:
        return format_response(
            success=False,
            message="Insufficient permissions to view this user",
            status_code=403
        )
    
    # Get user data
    user_data = user.to_dict()
    user_data.pop('password_hash', None)
    
    # Add hierarchy information
    if current_user.role in ['Masool', 'Sheikh', 'Admin']:
        user_data['hierarchy_chain'] = get_user_hierarchy_chain(user)
    
    # Add cycle progress
    from utils.helpers import calculate_cycle_progress
    user_data['cycle_progress'] = calculate_cycle_progress(user)
    
    return format_response(
        success=True,
        message="User details retrieved successfully",
        data=user_data
    )

@users_bp.route('/<user_id>', methods=['PUT'])
@jwt_required_custom
@validate_json_payload()
@log_activity('update_user', 'user')
def update_user(user_id):
    """Update user information"""
    current_user = g.current_user
    data = g.json_data
    
    # Find the user
    user = User.find_by_id(user_id)
    if not user:
        return format_response(
            success=False,
            message="User not found",
            status_code=404
        )
    
    # Check permissions
    can_edit = False
    
    if current_user.role == 'Admin':
        can_edit = True
    elif str(current_user._id) == user_id:
        can_edit = True  # Users can edit their own profile (limited fields)
    elif current_user.role in ['Sheikh', 'Masool'] and User.is_in_hierarchy(user._id, current_user._id):
        can_edit = True
    elif current_user.role == 'Murabi' and str(user.murabi_id) == str(current_user._id):
        can_edit = True  # Murabi can edit their Saalik (limited fields)
    
    if not can_edit:
        return format_response(
            success=False,
            message="Insufficient permissions to update this user",
            status_code=403
        )
    
    # Store old values for audit log
    old_values = user.to_dict()
    old_values.pop('password_hash', None)
    
    # Define editable fields based on role
    if str(current_user._id) == user_id:
        # Users editing their own profile
        editable_fields = ['name', 'email']
    elif current_user.role == 'Murabi':
        # Murabi editing their Saalik
        editable_fields = ['name', 'email', 'level', 'cycle_days', 'settings']
    else:
        # Higher roles can edit more fields
        editable_fields = ['name', 'email', 'role', 'level', 'cycle_days', 'settings', 'is_active']
    
    # Update allowed fields
    updated_fields = {}
    
    for field in editable_fields:
        if field in data:
            if field == 'name' and data[field]:
                user.name = data[field].strip()
                updated_fields['name'] = user.name
            elif field == 'email':
                if data[field]:
                    is_valid, error = validate_email(data[field])
                    if not is_valid:
                        return format_response(success=False, message=error, status_code=400)
                    
                    # Check if email already exists
                    existing_user = User.find_by_email(data[field])
                    if existing_user and str(existing_user._id) != user_id:
                        return format_response(
                            success=False,
                            message="Email already registered",
                            status_code=400
                        )
                    
                    user.email = data[field].strip()
                    updated_fields['email'] = user.email
                else:
                    user.email = None
                    updated_fields['email'] = None
            elif field == 'role':
                is_valid, error = validate_user_role(data[field])
                if not is_valid:
                    return format_response(success=False, message=error, status_code=400)
                
                # Check if current user can assign this role
                if not can_user_create_role(current_user.role, data[field]):
                    return format_response(
                        success=False,
                        message=f"You don't have permission to assign role: {data[field]}",
                        status_code=403
                    )
                
                user.role = data[field]
                updated_fields['role'] = user.role
            elif field == 'level':
                is_valid, error = validate_saalik_level(data[field])
                if not is_valid:
                    return format_response(success=False, message=error, status_code=400)
                
                user.level = data[field]
                updated_fields['level'] = user.level
            elif field == 'cycle_days':
                from utils.validators import validate_cycle_days
                is_valid, error = validate_cycle_days(data[field])
                if not is_valid:
                    return format_response(success=False, message=error, status_code=400)
                
                user.cycle_days = data[field]
                updated_fields['cycle_days'] = user.cycle_days
            elif field == 'settings' and isinstance(data[field], dict):
                user.settings.update(data[field])
                updated_fields['settings'] = user.settings
            elif field == 'is_active' and current_user.role in ['Sheikh', 'Admin']:
                user.is_active = bool(data[field])
                updated_fields['is_active'] = user.is_active
    
    # Save changes
    try:
        user.save()
        
        # Log the update
        AuditLog.log_action(
            user_id=current_user._id,
            action='user_updated',
            resource_type='user',
            resource_id=user_id,
            old_values=old_values,
            new_values=updated_fields
        )
        
        # Return updated user data
        user_data = user.to_dict()
        user_data.pop('password_hash', None)
        
        return format_response(
            success=True,
            message="User updated successfully",
            data=user_data
        )
        
    except Exception as e:
        return format_response(
            success=False,
            message=f"Failed to update user: {str(e)}",
            status_code=500
        )

@users_bp.route('/<user_id>/reset-cycle', methods=['POST'])
@jwt_required_custom
@role_required('Murabi', 'Masool', 'Sheikh', 'Admin')
@log_activity('reset_user_cycle', 'user')
def reset_user_cycle(user_id):
    """Reset user's cycle (Murabi and above only)"""
    current_user = g.current_user
    
    # Find the user
    user = User.find_by_id(user_id)
    if not user:
        return format_response(
            success=False,
            message="User not found",
            status_code=404
        )
    
    # Check permissions
    can_reset = False
    
    if current_user.role == 'Admin':
        can_reset = True
    elif current_user.role in ['Sheikh', 'Masool'] and User.is_in_hierarchy(user._id, current_user._id):
        can_reset = True
    elif current_user.role == 'Murabi' and str(user.murabi_id) == str(current_user._id):
        can_reset = True
    
    if not can_reset:
        return format_response(
            success=False,
            message="Insufficient permissions to reset this user's cycle",
            status_code=403
        )
    
    # Reset cycle
    old_start_date = user.level_start_date
    user.level_start_date = datetime.utcnow().date()
    user.save()
    
    # Log the cycle reset
    AuditLog.log_action(
        user_id=current_user._id,
        action='cycle_reset',
        resource_type='user',
        resource_id=user_id,
        old_values={'level_start_date': old_start_date.isoformat() if old_start_date else None},
        new_values={'level_start_date': user.level_start_date.isoformat()}
    )
    
    return format_response(
        success=True,
        message="User cycle reset successfully",
        data={
            'new_start_date': user.level_start_date.isoformat(),
            'cycle_days': user.cycle_days
        }
    )

@users_bp.route('/<user_id>/deactivate', methods=['POST'])
@jwt_required_custom
@role_required('Sheikh', 'Admin')
@log_activity('deactivate_user', 'user')
def deactivate_user(user_id):
    """Deactivate user account (Sheikh and Admin only)"""
    current_user = g.current_user
    
    # Find the user
    user = User.find_by_id(user_id)
    if not user:
        return format_response(
            success=False,
            message="User not found",
            status_code=404
        )
    
    # Cannot deactivate yourself
    if str(current_user._id) == user_id:
        return format_response(
            success=False,
            message="Cannot deactivate your own account",
            status_code=400
        )
    
    # Check role hierarchy
    if not check_role_hierarchy(current_user.role, user.role):
        return format_response(
            success=False,
            message="Cannot deactivate user with equal or higher role",
            status_code=403
        )
    
    # Deactivate user
    user.is_active = False
    user.save()
    
    # Revoke all user sessions
    from utils.auth import revoke_user_sessions
    revoke_user_sessions(user._id)
    
    # Log the deactivation
    AuditLog.log_action(
        user_id=current_user._id,
        action='user_deactivated',
        resource_type='user',
        resource_id=user_id,
        old_values={'is_active': True},
        new_values={'is_active': False}
    )
    
    return format_response(
        success=True,
        message="User deactivated successfully"
    )

@users_bp.route('/<user_id>/activate', methods=['POST'])
@jwt_required_custom
@role_required('Sheikh', 'Admin')
@log_activity('activate_user', 'user')
def activate_user(user_id):
    """Activate user account (Sheikh and Admin only)"""
    current_user = g.current_user
    
    # Find the user
    user = User.find_by_id(user_id)
    if not user:
        return format_response(
            success=False,
            message="User not found",
            status_code=404
        )
    
    # Activate user
    user.is_active = True
    user.save()
    
    # Log the activation
    AuditLog.log_action(
        user_id=current_user._id,
        action='user_activated',
        resource_type='user',
        resource_id=user_id,
        old_values={'is_active': False},
        new_values={'is_active': True}
    )
    
    return format_response(
        success=True,
        message="User activated successfully"
    )
