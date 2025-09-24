"""
Centralized error handling system for the Tasbiaat & Mamolaat API
"""
from flask import jsonify
from functools import wraps
import logging

logger = logging.getLogger(__name__)

class APIError(Exception):
    """Base API Error class"""
    def __init__(self, message, status_code=500, error_code=None, details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}

class ValidationError(APIError):
    """Validation error"""
    def __init__(self, message, details=None):
        super().__init__(message, 400, "VALIDATION_ERROR", details)

class AuthenticationError(APIError):
    """Authentication error"""
    def __init__(self, message="Authentication required"):
        super().__init__(message, 401, "AUTHENTICATION_ERROR")

class AuthorizationError(APIError):
    """Authorization error"""
    def __init__(self, message="Insufficient permissions"):
        super().__init__(message, 403, "AUTHORIZATION_ERROR")

class UserDisabledError(APIError):
    """User account disabled error"""
    def __init__(self, message="User account is disabled"):
        super().__init__(message, 403, "USER_DISABLED")

class NotFoundError(APIError):
    """Resource not found error"""
    def __init__(self, message="Resource not found"):
        super().__init__(message, 404, "NOT_FOUND")

class NoDataError(APIError):
    """No data found error (when database exists but no entries)"""
    def __init__(self, message="No data found"):
        super().__init__(message, 204, "NO_DATA")

class ConflictError(APIError):
    """Resource conflict error"""
    def __init__(self, message="Resource conflict"):
        super().__init__(message, 409, "CONFLICT")

class RateLimitError(APIError):
    """Rate limit exceeded error"""
    def __init__(self, message="Rate limit exceeded"):
        super().__init__(message, 429, "RATE_LIMIT_EXCEEDED")

class InternalServerError(APIError):
    """Internal server error"""
    def __init__(self, message="Internal server error"):
        super().__init__(message, 500, "INTERNAL_ERROR")

def handle_api_error(error):
    """Handle API errors and return standardized response"""
    logger.error(f"API Error: {error.message} - Status: {error.status_code}")
    
    response = {
        "success": False,
        "error": {
            "code": error.error_code,
            "message": error.message,
            "details": error.details
        }
    }
    
    # For 204 No Content, return empty response
    if error.status_code == 204:
        return '', 204
    
    return jsonify(response), error.status_code

def handle_generic_error(error):
    """Handle generic Python exceptions"""
    logger.error(f"Unhandled error: {str(error)}", exc_info=True)
    
    response = {
        "success": False,
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "details": {}
        }
    }
    
    return jsonify(response), 500

def error_handler(f):
    """Decorator to handle errors in route functions"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except APIError as e:
            return handle_api_error(e)
        except Exception as e:
            return handle_generic_error(e)
    return decorated_function

def check_user_active(user_data):
    """Check if user is active, raise error if disabled"""
    if not user_data.get('is_active', True):
        raise UserDisabledError("Your account has been disabled. Please contact support.")

def validate_required_fields(data, required_fields):
    """Validate required fields in request data"""
    missing_fields = []
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == '':
            missing_fields.append(field)
    
    if missing_fields:
        raise ValidationError(
            f"Missing required fields: {', '.join(missing_fields)}",
            {"missing_fields": missing_fields}
        )

def validate_saalik_level_data(data, required_fields):
    """Validate Saalik level specific data"""
    errors = {}
    
    # Check numeric fields
    numeric_fields = ['kalma', 'darood', 'istighfar', 'tasbihat', 'tilawat', 'tahajjud', 'muraqaba']
    for field in numeric_fields:
        if field in data:
            try:
                value = int(data[field])
                if value < 0 or value > 10000:
                    errors[field] = "Value must be between 0 and 10000"
            except (ValueError, TypeError):
                errors[field] = "Must be a valid number"
    
    # Check boolean fields
    boolean_fields = ['fikr_e_maut']
    for field in boolean_fields:
        if field in data and not isinstance(data[field], bool):
            errors[field] = "Must be true or false"
    
    # Check required fields are present
    missing_fields = []
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
    
    if missing_fields:
        errors['missing_fields'] = f"Missing required fields for this level: {', '.join(missing_fields)}"
    
    if errors:
        raise ValidationError("Validation failed", errors)

def success_response(data=None, message="Success", status_code=200):
    """Create standardized success response"""
    response = {
        "success": True,
        "message": message
    }
    
    if data is not None:
        response["data"] = data
    
    return jsonify(response), status_code

def paginated_response(data, page, per_page, total_count, message="Success"):
    """Create standardized paginated response"""
    total_pages = (total_count + per_page - 1) // per_page
    
    response = {
        "success": True,
        "message": message,
        "data": data,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    }
    
    return jsonify(response), 200