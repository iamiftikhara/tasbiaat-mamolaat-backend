"""
Tasbiaat & Mamolaat Web App - Flask REST API
Main application entry point
"""

from flask import Flask, jsonify, render_template_string, redirect, request
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
    
    # Add root route
    @app.route('/favicon.png')
    @app.route('/favicon.ico')
    def favicon():
        return app.send_static_file('favicon.svg')
        
    @app.route('/')
    def index():
        html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Tasbiaat & Mamolaat API</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    color: #333;
                }
                h1 {
                    color: #2c3e50;
                    border-bottom: 2px solid #eee;
                    padding-bottom: 10px;
                }
                .endpoint {
                    background-color: #f8f9fa;
                    padding: 10px;
                    border-radius: 4px;
                    margin-bottom: 10px;
                }
                .method {
                    font-weight: bold;
                    color: #e74c3c;
                }
                a {
                    color: #3498db;
                    text-decoration: none;
                }
                a:hover {
                    text-decoration: underline;
                }
            </style>
        </head>
        <body>
            <h1>Tasbiaat & Mamolaat API</h1>
            <p>Welcome to the Tasbiaat & Mamolaat API. This is the backend server for the Tasbiaat & Mamolaat application.</p>
            <p>For API documentation, please refer to the provided documentation or contact the administrator.</p>
            <div class="endpoint">
                <p><span class="method">GET</span> /api/v1/auth/salt - Get salt for password hashing</p>
                <p><span class="method">POST</span> /api/v1/auth/login - User login</p>
                <p><span class="method">POST</span> /api/v1/auth/logout - User logout</p>
                <p><span class="method">GET</span> /api/v1/users/profile - Get user profile</p>
                <p><span class="method">GET</span> /api/v1/entries - Get entries</p>
            </div>
        </body>
        </html>
        """
        return render_template_string(html)
    
    # Add route aliases for backward compatibility (without /api/v1 prefix)
    @app.route('/auth/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    def auth_alias(subpath):
        # Handle OPTIONS requests directly for CORS preflight
        if request.method == 'OPTIONS':
            response = app.make_default_options_response()
            # Add CORS headers
            headers = response.headers
            headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
            headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            headers['Access-Control-Allow-Headers'] = request.headers.get('Access-Control-Request-Headers', '*')
            headers['Access-Control-Max-Age'] = '86400'  # 24 hours
            return response
        return redirect(f"/api/v1/auth/{subpath}", code=307)
        
    @app.route('/users/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    def users_alias(subpath):
        if request.method == 'OPTIONS':
            response = app.make_default_options_response()
            headers = response.headers
            headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
            headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            headers['Access-Control-Allow-Headers'] = request.headers.get('Access-Control-Request-Headers', '*')
            headers['Access-Control-Max-Age'] = '86400'
            return response
        return redirect(f"/api/v1/users/{subpath}", code=307)
        
    @app.route('/entries/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    def entries_alias(subpath):
        if request.method == 'OPTIONS':
            response = app.make_default_options_response()
            headers = response.headers
            headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
            headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            headers['Access-Control-Allow-Headers'] = request.headers.get('Access-Control-Request-Headers', '*')
            headers['Access-Control-Max-Age'] = '86400'
            return response
        return redirect(f"/api/v1/entries/{subpath}", code=307)
        
    @app.route('/reports/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    def reports_alias(subpath):
        if request.method == 'OPTIONS':
            response = app.make_default_options_response()
            headers = response.headers
            headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
            headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            headers['Access-Control-Allow-Headers'] = request.headers.get('Access-Control-Request-Headers', '*')
            headers['Access-Control-Max-Age'] = '86400'
            return response
        return redirect(f"/api/v1/reports/{subpath}", code=307)
        
    @app.route('/admin/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    def admin_alias(subpath):
        if request.method == 'OPTIONS':
            response = app.make_default_options_response()
            headers = response.headers
            headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
            headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            headers['Access-Control-Allow-Headers'] = request.headers.get('Access-Control-Request-Headers', '*')
            headers['Access-Control-Max-Age'] = '86400'
            return response
        return redirect(f"/api/v1/admin/{subpath}", code=307)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    app.register_error_handler(APIError, handle_api_error)
    app.register_error_handler(Exception, handle_generic_error)
    
    # Setup logging
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/tasbiaat_mamolaat.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Tasbiaat & Mamolaat startup')
    
    return app

# Create the Flask app instance for Vercel
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)