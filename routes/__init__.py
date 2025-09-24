"""
Routes package initialization
"""

from .auth import auth_bp
from .users import users_bp
from .entries import entries_bp
from .reports import reports_bp
from .admin import admin_bp

def register_blueprints(app):
    """Register all blueprints with the Flask app"""
    app.register_blueprint(auth_bp, url_prefix='/v1/auth')
    app.register_blueprint(users_bp, url_prefix='/v1/users')
    app.register_blueprint(entries_bp, url_prefix='/v1/entries')
    app.register_blueprint(reports_bp, url_prefix='/v1/reports')
    app.register_blueprint(admin_bp, url_prefix='/v1/admin')