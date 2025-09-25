"""
Tasbiaat & Mamolaat Web App - Flask REST API
Main application entry point
"""

from flask import Flask
from flask_cors import CORS
from config import Config
from extensions import redis_client, jwt
from routes import register_blueprints
from utils.error_handler import APIError, handle_api_error, handle_generic_error
import logging
from logging.handlers import RotatingFileHandler
import os

def create_app(config_class=Config):
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    jwt.init_app(app)
    CORS(app, origins=app.config.get('CORS_ORIGINS', ['http://localhost:3000']))
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    app.register_error_handler(APIError, handle_api_error)
    app.register_error_handler(Exception, handle_generic_error)
    
    # Setup logging
    if not app.debug and not app.testing:
        # Use stream handler instead of file handler for Vercel's read-only filesystem
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        stream_handler.setLevel(logging.INFO)
        app.logger.addHandler(stream_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Tasbiaat Mamolaat API startup')
    
    return app

# Create the app instance for Vercel
app = create_app()

# For Vercel serverless functions - app variable is sufficient
# Do not define a handler variable as it causes conflicts

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)