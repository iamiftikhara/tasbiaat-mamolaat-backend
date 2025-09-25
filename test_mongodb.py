"""
Test script for MongoDB connection and basic operations
"""

import os
import sys
from dotenv import load_dotenv
from utils.mongo_db import get_mongo_client, get_db, get_collection
from models.user import User

# Load environment variables
load_dotenv()

def test_connection():
    """Test MongoDB connection"""
    try:
        client = get_mongo_client()
        print("✅ MongoDB connection successful!")
        return client
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        return None

def test_database():
    """Test MongoDB database access"""
    try:
        db = get_db()
        print(f"✅ Connected to database: {db.name}")
        return db
    except Exception as e:
        print(f"❌ Database access failed: {e}")
        return None

def test_collections():
    """Test MongoDB collections access"""
    collections = ['users', 'entries', 'levels', 'sessions', 'notifications', 'audit_logs']
    
    for collection_name in collections:
        try:
            collection = get_collection(collection_name)
            count = collection.count_documents({})
            print(f"✅ Collection '{collection_name}' accessible - contains {count} documents")
        except Exception as e:
            print(f"❌ Collection '{collection_name}' access failed: {e}")

def test_user_model():
    """Test User model with MongoDB"""
    try:
        # Create test user
        test_user = User(
            name="Test MongoDB User",
            phone="+1234567890",
            email="mongodb_test@example.com",
            role="Saalik",
            region="Test Region"
        )
        test_user.set_password("testpassword")
        
        # Save user to MongoDB
        saved_user = test_user.save()
        print(f"✅ User saved to MongoDB with ID: {saved_user._id}")
        
        # Retrieve user by ID
        retrieved_user = User.find_by_id(saved_user._id)
        if retrieved_user and retrieved_user.name == test_user.name:
            print(f"✅ User retrieved successfully: {retrieved_user.name}")
        else:
            print("❌ User retrieval failed")
        
        # Clean up - delete test user
        from models import users_collection
        users_collection.delete_one({'_id': saved_user._id})
        print("✅ Test user deleted")
        
    except Exception as e:
        print(f"❌ User model test failed: {e}")

if __name__ == "__main__":
    print("\n===== TESTING MONGODB CONNECTION =====\n")
    
    if not os.environ.get('MONGO_URI'):
        print("❌ MONGO_URI not found in environment variables")
        sys.exit(1)
    
    client = test_connection()
    if not client:
        sys.exit(1)
    
    db = test_database()
    if db is None:
        sys.exit(1)
    
    print("\n===== TESTING COLLECTIONS =====\n")
    test_collections()
    
    print("\n===== TESTING USER MODEL =====\n")
    test_user_model()
    
    print("\n===== ALL TESTS COMPLETED =====\n")