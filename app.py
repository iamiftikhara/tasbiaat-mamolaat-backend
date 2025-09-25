"""
Tasbiaat & Mamolaat Web App - Flask REST API
Main application entry point
"""

from flask import Flask, jsonify, render_template_string
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
                .api-info {
                    background-color: #f8f9fa;
                    border-left: 4px solid #28a745;
                    padding: 15px;
                    margin: 20px 0;
                }
                .endpoint {
                    margin: 10px 0;
                    font-family: monospace;
                    background-color: #f1f1f1;
                    padding: 5px;
                    border-radius: 3px;
                }
                footer {
                    margin-top: 30px;
                    text-align: center;
                    font-size: 0.9em;
                    color: #777;
                }
            </style>
        </head>
        <body>
            <h1>Tasbiaat & Mamolaat API</h1>
            <div class="api-info">
                <p>Welcome to the Tasbiaat & Mamolaat API server. This API provides endpoints for managing Islamic practice entries and user progress tracking.</p>
                <p>The API is running successfully. All endpoints are available under the <code>/api/v1</code> prefix.</p>
            </div>
            
            <h2>Main API Endpoints:</h2>
            <div class="endpoint">/api/v1/auth/login</div>
            <div class="endpoint">/api/v1/users/me</div>
            <div class="endpoint">/api/v1/entries</div>
            
            <p>For complete API documentation, please refer to the API documentation provided to developers.</p>
            
            <footer>
                &copy; 2025 Tasbiaat & Mamolaat - All Rights Reserved
            </footer>
        </body>
        </html>
        """
        return render_template_string(html)
    
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