"""
Flask extensions initialization
"""

from flask_jwt_extended import JWTManager
import redis
import os

# Initialize extensions
jwt = JWTManager()

# Redis client for session management and nonce storage
redis_client = redis.from_url(
    os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
    decode_responses=True
)