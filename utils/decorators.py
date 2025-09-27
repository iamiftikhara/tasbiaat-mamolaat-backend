"""
Decorators for authentication, authorization, and rate limiting
"""

from functools import wraps, update_wrapper
from flask import request, jsonify, current_app, g
from utils.auth import get_user_from_token, validate_api_key, get_request_info
from utils.helpers import format_response
import time
from collections import defaultdict
import uuid

# Simple in-memory rate limiting (in production, use Redis)
rate_limit_storage = defaultdict(list)

def jwt_required_custom(f):
    """Custom JWT authentication decorator"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = None
        
        # Check for token in request payload first
        if request.is_json:
            payload = request.get_json()
            if payload and 'token' in payload:
                token = payload.get('token')
                
                # Store the entire payload in g for easy access
                g.payload = payload
                
                # Extract path parameters from payload if they exist
                for param_key in kwargs.keys():
                    if param_key in payload:
                        kwargs[param_key] = payload[param_key]
                
                # Extract required_roles from payload if it exists
                if 'required_roles' in payload:
                    g.required_roles = payload['required_roles']
        
        # Fallback to Authorization header for backward compatibility
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return format_response(
                success=False,
                message="Authentication token is missing",
                status_code=401
            )
        
        user, error = get_user_from_token(token)
        if error:
            return format_response(
                success=False,
                message=f"Authentication failed: {error}",
                status_code=401
            )
        
        # Store user in Flask's g object for use in the request
        g.current_user = user
        g.request_info = get_request_info()
        
        return f(*args, **kwargs)
    
    # Preserve the original function name to avoid Flask endpoint conflicts
    wrapper.__name__ = f.__name__
    return wrapper

def role_required(*allowed_roles):
    """Decorator to check if user has required role"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not hasattr(g, 'current_user') or not g.current_user:
                return format_response(
                    success=False,
                    message="Authentication required",
                    status_code=401
                )
            
            # Check if required_roles is in the payload and use that instead
            required_roles = None
            if hasattr(g, 'required_roles') and g.required_roles:
                required_roles = g.required_roles
            
            # If no required_roles in payload, use the ones passed to the decorator
            roles_to_check = required_roles if required_roles else allowed_roles
            
            if g.current_user.role not in roles_to_check:
                return format_response(
                    success=False,
                    message=f"Access denied. Required roles: {', '.join(roles_to_check)}",
                    status_code=403
                )
            
            return f(*args, **kwargs)
        
        # Preserve the original function name to avoid Flask endpoint conflicts
        wrapper.__name__ = f.__name__
        return wrapper
    
    # Generate a unique name for the decorator function to avoid Flask endpoint conflicts
    decorator.__name__ = f"role_required_{uuid.uuid4().hex[:8]}"
    return decorator

def api_key_required(f):
    """Decorator for API key authentication (for system-to-system calls)"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        api_key = None
        
        # Check for API key in request payload first
        if request.is_json:
            payload = request.get_json()
            if payload and 'api_key' in payload:
                api_key = payload.get('api_key')
        
        # Fallback to header for backward compatibility
        if not api_key:
            api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return format_response(
                success=False,
                message="API key is missing",
                status_code=401
            )
        
        if not validate_api_key(api_key):
            return format_response(
                success=False,
                message="Invalid API key",
                status_code=401
            )
        
        g.api_authenticated = True
        g.request_info = get_request_info()
        
        return f(*args, **kwargs)
    
    # Preserve the original function name to avoid Flask endpoint conflicts
    wrapper.__name__ = f.__name__
    return wrapper

def rate_limit(max_requests=100, window_minutes=60):
    """Simple rate limiting decorator"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_app.config.get('ENABLE_RATE_LIMITING', True):
                return f(*args, **kwargs)
            
            # Get client identifier
            client_id = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            if hasattr(g, 'current_user') and g.current_user:
                client_id = f"user_{g.current_user._id}"
            
            current_time = time.time()
            window_start = current_time - (window_minutes * 60)
            
            # Clean old requests
            rate_limit_storage[client_id] = [
                req_time for req_time in rate_limit_storage[client_id]
                if req_time > window_start
            ]
            
            # Check if limit exceeded
            if len(rate_limit_storage[client_id]) >= max_requests:
                return format_response(
                    success=False,
                    message="Rate limit exceeded. Please try again later.",
                    status_code=429
                )
            
            # Add current request
            rate_limit_storage[client_id].append(current_time)
            
            return f(*args, **kwargs)
        
        # Preserve the original function name to avoid Flask endpoint conflicts
        wrapper.__name__ = f.__name__
        return wrapper
    
    # Generate a unique name for the decorator function to avoid Flask endpoint conflicts
    decorator.__name__ = f"rate_limit_{uuid.uuid4().hex[:8]}"
    return decorator

def validate_json_payload(required_fields=None, optional_fields=None):
    """Decorator to validate JSON payload"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return format_response(
                    success=False,
                    message="Request must be JSON",
                    status_code=400
                )
            
            data = request.get_json()
            if not data:
                return format_response(
                    success=False,
                    message="Invalid JSON payload",
                    status_code=400
                )
            
            # Check required fields
            if required_fields:
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    return format_response(
                        success=False,
                        message=f"Missing required fields: {', '.join(missing_fields)}",
                        status_code=400
                    )
            
            # Store validated data in g
            g.json_data = data
            
            return f(*args, **kwargs)
        
        # Preserve the original function name to avoid Flask endpoint conflicts
        wrapper.__name__ = f.__name__
        return wrapper
    
    # Generate a unique name for the decorator function to avoid Flask endpoint conflicts
    decorator.__name__ = f"validate_json_{uuid.uuid4().hex[:8]}"
    return decorator

def log_activity(action, resource_type):
    """Decorator to log user activities"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Execute the function first
            result = f(*args, **kwargs)
            
            # Log the activity if user is authenticated
            if hasattr(g, 'current_user') and g.current_user:
                from models.audit_log import AuditLog
                
                request_info = getattr(g, 'request_info', {})
                
                AuditLog.log_action(
                    user_id=g.current_user._id,
                    action=action,
                    resource_type=resource_type,
                    ip_address=request_info.get('ip_address'),
                    user_agent=request_info.get('user_agent'),
                    metadata={
                        'endpoint': request_info.get('endpoint'),
                        'method': request_info.get('method')
                    }
                )
            
            return result
        
        # Preserve the original function name to avoid Flask endpoint conflicts
        wrapper.__name__ = f.__name__
        return wrapper
    
    # Generate a unique name for the decorator function to avoid Flask endpoint conflicts
    decorator.__name__ = f"log_activity_{uuid.uuid4().hex[:8]}"
    return decorator

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not hasattr(g, 'current_user') or not g.current_user:
            return format_response(
                success=False,
                message="Authentication required",
                status_code=401
            )
        
        if g.current_user.role != 'Admin':
            return format_response(
                success=False,
                message="Admin access required",
                status_code=403
            )
        
        return f(*args, **kwargs)
    
    # Preserve the original function name to avoid Flask endpoint conflicts
    wrapper.__name__ = f.__name__
    return wrapper