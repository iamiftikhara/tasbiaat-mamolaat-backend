"""
MongoDB connection utility for database operations
"""

import os
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from flask import current_app

# MongoDB client instance
_mongo_client = None
_db = None

def get_mongo_client():
    """Get MongoDB client instance (singleton)"""
    global _mongo_client
    
    if _mongo_client is None:
        uri = os.environ.get('MONGO_URI')
        if not uri:
            raise ValueError("MongoDB URI not configured in environment variables")
        
        _mongo_client = MongoClient(uri, server_api=ServerApi('1'))
        
        # Test connection
        try:
            _mongo_client.admin.command('ping')
            print("Successfully connected to MongoDB!")
        except Exception as e:
            print(f"MongoDB connection error: {e}")
            raise
    
    return _mongo_client

def get_db():
    """Get MongoDB database instance"""
    global _db
    
    if _db is None:
        client = get_mongo_client()
        db_name = os.environ.get('MONGO_DB_NAME', 'tasbiaat_mamolaat')
        _db = client[db_name]
    
    return _db

def get_collection(collection_name):
    """Get MongoDB collection by name"""
    db = get_db()
    return db[collection_name]

def close_mongo_connection():
    """Close MongoDB connection"""
    global _mongo_client, _db
    
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None
        _db = None