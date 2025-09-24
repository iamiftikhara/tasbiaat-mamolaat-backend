"""
Authentication utilities for JWT token management and password handling
"""

import jwt
import bcrypt
from datetime import datetime, timedelta
from flask import current_app, request
from models.user import User
from models.session import Session
import secrets

def hash_password(password):
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password, hashed_password):
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def generate_jwt_token(user_id, session_id=None, expires_in_days=30):
    """Generate JWT token with user and session information"""
    payload = {
        'user_id': str(user_id),
        'session_id': session_id,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(days=expires_in_days),
        'jti': secrets.token_urlsafe(16)  # JWT ID for token revocation
    }
    
    return jwt.encode(
        payload,
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256'
    )

def verify_jwt_token(token):
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=['HS256']
        )
        return payload
    except jwt.ExpiredSignatureError:
        return {'error': 'Token has expired'}
    except jwt.InvalidTokenError:
        return {'error': 'Invalid token'}

def create_user_session(user_id, device_info=None, ip_address=None, user_agent=None):
    """Create a new user session"""
    session = Session(
        user_id=user_id,
        device_info=device_info or {},
        ip_address=ip_address,
        user_agent=user_agent
    )
    session.save()
    return session

def authenticate_user(phone_or_email, password):
    """Authenticate user with phone/email and password"""
    # Try to find user by phone first, then by email
    user = User.find_by_phone(phone_or_email)
    if not user:
        user = User.find_by_email(phone_or_email)
    
    if not user:
        return None, "User not found"
    
    if not user.is_active:
        return None, "Account is deactivated"
    
    if not verify_password(password, user.password_hash):
        return None, "Invalid password"
    
    return user, None

def get_user_from_token(token):
    """Get user object from JWT token"""
    payload = verify_jwt_token(token)
    
    if 'error' in payload:
        return None, payload['error']
    
    user_id = payload.get('user_id')
    session_id = payload.get('session_id')
    
    # Verify user exists
    user = User.find_by_id(user_id)
    if not user:
        return None, "User not found"
    
    if not user.is_active:
        return None, "Account is deactivated"
    
    # Verify session if session_id is provided
    if session_id:
        session = Session.find_by_token_id(session_id)
        if not session or not session.is_valid():
            return None, "Invalid or expired session"
        
        # Update session activity
        session.update_activity()
    
    return user, None

def revoke_user_sessions(user_id, exclude_session_id=None):
    """Revoke all user sessions except the specified one"""
    sessions = Session.find_active_by_user_id(user_id)
    
    for session in sessions:
        if exclude_session_id and session.token_id == exclude_session_id:
            continue
        session.deactivate()

def generate_api_key():
    """Generate a secure API key"""
    return secrets.token_urlsafe(32)

def validate_api_key(api_key):
    """Validate API key (for system-to-system communication)"""
    # In a real implementation, you would store API keys in database
    # For now, we'll use a simple check against config
    valid_api_keys = current_app.config.get('VALID_API_KEYS', [])
    return api_key in valid_api_keys

def get_request_info():
    """Extract request information for logging"""
    return {
        'ip_address': request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr),
        'user_agent': request.headers.get('User-Agent', ''),
        'method': request.method,
        'endpoint': request.endpoint,
        'url': request.url
    }

def check_role_hierarchy(current_user_role, target_role):
    """Check if current user can manage target role based on hierarchy"""
    role_hierarchy = current_app.config['ROLE_HIERARCHY']
    
    current_level = role_hierarchy.get(current_user_role, 0)
    target_level = role_hierarchy.get(target_role, 0)
    
    return current_level > target_level

def can_user_create_role(current_user_role, target_role):
    """Check if user can create another user with target role"""
    creation_rules = current_app.config['USER_CREATION_RULES']
    allowed_roles = creation_rules.get(current_user_role, [])
    
    return target_role in allowed_roles