"""
Authentication routes for login, logout, and session management
"""

from flask import Blueprint, request, g
from utils.auth import authenticate_user, generate_jwt_token, create_user_session, get_user_from_token, revoke_user_sessions
from utils.decorators import jwt_required_custom, rate_limit, validate_json_payload, log_activity
from utils.validators import validate_phone, validate_email, validate_password
from utils.helpers import format_response
from utils.auth import get_request_info
from utils.error_handler import (
    error_handler, ValidationError, AuthenticationError, 
    check_user_active, success_response, validate_required_fields
)
from models.user import User
from models.session import Session
from models.audit_log import AuditLog

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
@rate_limit(max_requests=10, window_minutes=15)  # Stricter rate limit for login
@validate_json_payload(required_fields=['password'])
@log_activity('login_attempt', 'authentication')
@error_handler
def login():
    """User login endpoint"""
    data = g.json_data
    password = data['password']
    
    # Handle both 'email' and 'phone_or_email' parameters
    phone_or_email = None
    if 'phone_or_email' in data:
        phone_or_email = data['phone_or_email'].strip()
    elif 'email' in data:
        phone_or_email = data['email'].strip()
    else:
        return format_response(
            success=False,
            message="Missing required field: phone_or_email or email",
            status_code=400
        )
    
    # Validate input format
    is_phone = phone_or_email.startswith('+') or phone_or_email.isdigit()
    
    if is_phone:
        is_valid, error = validate_phone(phone_or_email)
        if not is_valid:
            return format_response(
                success=False,
                message=error,
                status_code=400
            )
    else:
        is_valid, error = validate_email(phone_or_email)
        if not is_valid:
            return format_response(
                success=False,
                message=error,
                status_code=400
            )
    
    # Authenticate user
    auth_result = authenticate_user(phone_or_email, password)
    
    # Unpack the result (user, error_message, additional_data)
    if len(auth_result) == 2:
        user, auth_error = auth_result
        additional_data = None
    else:
        user, auth_error, additional_data = auth_result
    
    if auth_error:
        # Log failed login attempt
        AuditLog.log_action(
            user_id=None,
            action='login_failed',
            resource_type='authentication',
            details={
                'phone_or_email': phone_or_email,
                'reason': auth_error,
                **get_request_info()
            }
        )
        
        # If account is deactivated, include higher role contact details
        if "deactivated" in auth_error.lower() and additional_data:
            return format_response(
                success=False,
                message="Account is deactivated. Please contact your supervisor for assistance.",
                data=additional_data,
                status_code=401
            )
        
        return format_response(
            success=False,
            message=auth_error,
            status_code=401
        )
    
    # Create session
    request_info = get_request_info()
    session = create_user_session(
        user_id=user._id,
        device_info=data.get('device_info', {}),
        ip_address=request_info['ip_address'],
        user_agent=request_info['user_agent']
    )
    
    # Generate JWT token
    token = generate_jwt_token(user._id, session.token_id)
    
    # Log successful login
    AuditLog.log_action(
        user_id=user._id,
        action='login_success',
        resource_type='authentication',
        details={
            'session_id': session.token_id,
            **request_info
        }
    )
    
    # Prepare user data for response (mask sensitive fields)
    user_data = user.to_dict()
    user_data.pop('password_hash', None)
    
    return format_response(
        success=True,
        message="Login successful",
        data={
            'token': token,
            'user': user_data,
            'session': {
                'id': session.token_id,
                'expires_at': session.expires_at.isoformat()
            }
        }
    )

@auth_bp.route('/logout', methods=['POST'])
@jwt_required_custom
@log_activity('logout', 'authentication')
def logout():
    """User logout endpoint"""
    user = g.current_user
    
    # Get current session from token
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        from utils.auth import verify_jwt_token
        payload = verify_jwt_token(token)
        
        if 'session_id' in payload:
            session = Session.find_by_token_id(payload['session_id'])
            if session:
                session.deactivate()
    
    # Log logout
    AuditLog.log_action(
        user_id=user._id,
        action='logout',
        resource_type='authentication',
        details=get_request_info()
    )
    
    return format_response(
        success=True,
        message="Logout successful"
    )

@auth_bp.route('/logout-all', methods=['POST'])
@jwt_required_custom
@log_activity('logout_all_sessions', 'authentication')
def logout_all():
    """Logout from all sessions"""
    user = g.current_user
    
    # Deactivate all user sessions
    revoke_user_sessions(user._id)
    
    # Log logout from all sessions
    AuditLog.log_action(
        user_id=user._id,
        action='logout_all_sessions',
        resource_type='authentication',
        details=get_request_info()
    )
    
    return format_response(
        success=True,
        message="Logged out from all sessions"
    )

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required_custom
@rate_limit(max_requests=20, window_minutes=60)
def refresh_token():
    """Refresh JWT token"""
    user = g.current_user
    
    # Get current session
    auth_header = request.headers.get('Authorization')
    session_id = None
    
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        from utils.auth import verify_jwt_token
        payload = verify_jwt_token(token)
        session_id = payload.get('session_id')
    
    # Generate new token
    new_token = generate_jwt_token(user._id, session_id)
    
    # Update session activity
    if session_id:
        session = Session.find_by_token_id(session_id)
        if session:
            session.update_activity()
    
    return format_response(
        success=True,
        message="Token refreshed successfully",
        data={
            'token': new_token
        }
    )

@auth_bp.route('/me', methods=['GET'])
@jwt_required_custom
def get_current_user_info():
    """Get current user information"""
    user = g.current_user
    
    # Get user data without sensitive fields
    user_data = user.to_dict()
    user_data.pop('password_hash', None)
    
    # Add cycle progress information
    from utils.helpers import calculate_cycle_progress
    cycle_progress = calculate_cycle_progress(user)
    user_data['cycle_progress'] = cycle_progress
    
    return format_response(
        success=True,
        message="User information retrieved successfully",
        data=user_data
    )

@auth_bp.route('/sessions', methods=['GET'])
@jwt_required_custom
def get_user_sessions():
    """Get all active sessions for current user"""
    user = g.current_user
    
    sessions = Session.find_active_by_user_id(user._id)
    sessions_data = []
    
    for session in sessions:
        session_data = session.to_dict()
        # Remove sensitive information
        session_data.pop('token_id', None)
        sessions_data.append(session_data)
    
    return format_response(
        success=True,
        message="Sessions retrieved successfully",
        data=sessions_data
    )

@auth_bp.route('/sessions/<session_id>', methods=['DELETE'])
@jwt_required_custom
@log_activity('revoke_session', 'authentication')
def revoke_session(session_id):
    """Revoke a specific session"""
    user = g.current_user
    
    # Find the session
    session = Session.find_by_token_id(session_id)
    
    if not session:
        return format_response(
            success=False,
            message="Session not found",
            status_code=404
        )
    
    # Check if session belongs to current user
    if str(session.user_id) != str(user._id):
        return format_response(
            success=False,
            message="Unauthorized to revoke this session",
            status_code=403
        )
    
    # Deactivate session
    session.deactivate()
    
    # Log session revocation
    AuditLog.log_action(
        user_id=user._id,
        action='session_revoked',
        resource_type='authentication',
        resource_id=session_id,
        details=get_request_info()
    )
    
    return format_response(
        success=True,
        message="Session revoked successfully"
    )

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required_custom
@rate_limit(max_requests=5, window_minutes=60)
@validate_json_payload(required_fields=['current_password', 'new_password'])
@log_activity('password_change', 'user')
def change_password():
    """Change user password"""
    user = g.current_user
    data = g.json_data
    
    current_password = data['current_password']
    new_password = data['new_password']
    
    # Verify current password
    from utils.auth import verify_password, hash_password
    if not verify_password(current_password, user.password_hash):
        return format_response(
            success=False,
            message="Current password is incorrect",
            status_code=400
        )
    
    # Validate new password
    is_valid, error = validate_password(new_password)
    if not is_valid:
        return format_response(
            success=False,
            message=error,
            status_code=400
        )
    
    # Check if new password is different from current
    if verify_password(new_password, user.password_hash):
        return format_response(
            success=False,
            message="New password must be different from current password",
            status_code=400
        )
    
    # Update password
    user.password_hash = hash_password(new_password)
    user.save()
    
    # Revoke all other sessions for security
    revoke_user_sessions(user._id, exclude_session_id=None)
    
    # Log password change
    AuditLog.log_action(
        user_id=user._id,
        action='password_changed',
        resource_type='user',
        resource_id=str(user._id),
        details=get_request_info()
    )
    
    return format_response(
        success=True,
        message="Password changed successfully. Please login again."
    )

@auth_bp.route('/verify-token', methods=['POST'])
@rate_limit(max_requests=50, window_minutes=60)
def verify_token():
    """Verify if a token is valid"""
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return format_response(
            success=False,
            message="Token is missing",
            status_code=400
        )
    
    token = auth_header.split(' ')[1]
    user, error = get_user_from_token(token)
    
    if error:
        return format_response(
            success=False,
            message=f"Token verification failed: {error}",
            status_code=401
        )
    
    return format_response(
        success=True,
        message="Token is valid",
        data={
            'user_id': str(user._id),
            'role': user.role,
            'is_active': user.is_active
        }
    )

@auth_bp.route('/forgot-password', methods=['POST'])
@rate_limit(max_requests=5, window_minutes=15)
@validate_json_payload(required_fields=['phone_or_email'])
@log_activity('forgot_password_request', 'authentication')
@error_handler
def forgot_password():
    """
    Forgot password endpoint that returns higher role contact details
    instead of allowing direct password reset
    """
    data = g.json_data
    phone_or_email = data['phone_or_email'].strip()
    
    # Validate input format
    is_phone = phone_or_email.startswith('+') or phone_or_email.isdigit()
    
    if is_phone:
        is_valid, error = validate_phone(phone_or_email)
        if not is_valid:
            return format_response(
                success=False,
                message=error,
                status_code=400
            )
    else:
        is_valid, error = validate_email(phone_or_email)
        if not is_valid:
            return format_response(
                success=False,
                message=error,
                status_code=400
            )
    
    # Find user by phone or email
    user = None
    if is_phone:
        user = User.find_by_phone(phone_or_email)
    else:
        user = User.find_by_email(phone_or_email)
    
    if not user:
        return format_response(
            success=False,
            message="No account found with this phone number or email",
            status_code=404
        )
    
    # Get higher role contact based on user's role
    higher_role_contact = None
    
    if user.role == 'Saalik' and user.murabi_id:
        murabi = User.find_by_id(user.murabi_id)
        if murabi:
            higher_role_contact = {
                'name': murabi.name,
                'role': 'Murabi',
                'contact': {
                    'email': murabi.email,
                    'phone': murabi.phone
                }
            }
    elif user.role == 'Murabi' and user.masool_id:
        masool = User.find_by_id(user.masool_id)
        if masool:
            higher_role_contact = {
                'name': masool.name,
                'role': 'Masool',
                'contact': {
                    'email': masool.email,
                    'phone': masool.phone
                }
            }
    elif user.role == 'Masool' and user.sheikh_id:
        sheikh = User.find_by_id(user.sheikh_id)
        if sheikh:
            higher_role_contact = {
                'name': sheikh.name,
                'role': 'Sheikh',
                'contact': {
                    'email': sheikh.email,
                    'phone': sheikh.phone
                }
            }
    elif user.role in ['Sheikh', 'Admin']:
        # For highest roles, return admin contact or system message
        admin = User.find_one({'role': 'Admin'})
        if admin and admin._id != user._id:
            higher_role_contact = {
                'name': admin.name,
                'role': 'Admin',
                'contact': {
                    'email': admin.email,
                    'phone': admin.phone
                }
            }
        else:
            # If user is the admin or no other admin found
            return format_response(
                success=False,
                message="Please contact system administrator for password assistance",
                status_code=400
            )
    
    if not higher_role_contact:
        return format_response(
            success=False,
            message="Unable to find your supervisor's contact information. Please contact the administrator.",
            status_code=404
        )
    
    # Log the forgot password request
    AuditLog.log_action(
        user_id=user._id,
        action='forgot_password_request',
        resource_type='authentication',
        details={
            'requested_by': phone_or_email,
            'higher_role_contacted': higher_role_contact['role'],
            **get_request_info()
        }
    )
    
    return format_response(
        success=True,
        message="Please contact your supervisor to reset your password",
        data={
            'user': {
                'name': user.name,
                'role': user.role
            },
            'contact': higher_role_contact
        }
    )