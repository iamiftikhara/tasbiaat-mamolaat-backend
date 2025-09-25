"""
Test script for secure password handling between frontend and backend
"""
import os
import base64
import hashlib
import requests
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Base URL for API
BASE_URL = "http://localhost:5000/api/v1"

def simulate_frontend_password_hashing(password, salt, iterations=10000, key_size=32):
    """Simulate the frontend PBKDF2 password hashing"""
    # Convert password to bytes
    password_bytes = password.encode('utf-8')
    salt_bytes = base64.b64decode(salt)
    
    # Generate key using PBKDF2
    key = hashlib.pbkdf2_hmac('sha256', password_bytes, salt_bytes, iterations, key_size)
    
    # Return base64 encoded key
    return base64.b64encode(key).decode('utf-8')

def test_secure_password_flow():
    """Test the secure password flow between frontend and backend"""
    print("Testing secure password flow...")
    
    # Step 1: Get salt from backend
    print("\n1. Getting salt from backend...")
    salt_response = requests.get(f"{BASE_URL}/auth/salt")
    if salt_response.status_code != 200:
        print(f"Error getting salt: {salt_response.text}")
        return False
    
    salt_data = salt_response.json()
    salt = salt_data['data']['salt']
    print(f"Received salt: {salt}")
    
    # Step 2: Create test user with pre-hashed password
    print("\n2. Creating test user with pre-hashed password...")
    test_password = "SecurePassword123!"
    hashed_password = simulate_frontend_password_hashing(test_password, salt)
    
    # Create user payload
    user_data = {
        "name": "Test Secure User",
        "phone": "+1234567890",
        "email": "testsecure@example.com",
        "password": hashed_password,
        "is_pre_hashed": True,
        "salt": salt,
        "role": "Saalik",
        "level": 1
    }
    
    # Get admin token for user creation
    admin_login_data = {
        "phone_or_email": os.getenv("ADMIN_EMAIL", "admin@example.com"),
        "password": os.getenv("ADMIN_PASSWORD", "Admin@123")
    }
    
    admin_login_response = requests.post(f"{BASE_URL}/auth/login", json=admin_login_data)
    if admin_login_response.status_code != 200:
        print(f"Error logging in as admin: {admin_login_response.text}")
        return False
    
    admin_token = admin_login_response.json()['data']['token']
    
    # Create user
    headers = {"Authorization": f"Bearer {admin_token}"}
    create_user_response = requests.post(f"{BASE_URL}/users/", json=user_data, headers=headers)
    
    if create_user_response.status_code != 201:
        print(f"Error creating user: {create_user_response.text}")
        return False
    
    print("User created successfully!")
    
    # Step 3: Login with pre-hashed password
    print("\n3. Testing login with pre-hashed password...")
    
    # Get new salt for login
    login_salt_response = requests.get(f"{BASE_URL}/auth/salt")
    login_salt = login_salt_response.json()['data']['salt']
    
    # Hash password with new salt
    login_hashed_password = simulate_frontend_password_hashing(test_password, login_salt)
    
    # Login data
    login_data = {
        "phone_or_email": "+1234567890",
        "password": login_hashed_password,
        "is_pre_hashed": True
    }
    
    login_response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    
    if login_response.status_code != 200:
        print(f"Error logging in: {login_response.text}")
        return False
    
    print("Login successful!")
    user_token = login_response.json()['data']['token']
    
    # Step 4: Clean up - delete test user
    print("\n4. Cleaning up - deleting test user...")
    user_id = login_response.json()['data']['user']['_id']
    
    delete_response = requests.delete(f"{BASE_URL}/users/{user_id}", headers=headers)
    
    if delete_response.status_code != 200:
        print(f"Warning: Could not delete test user: {delete_response.text}")
    else:
        print("Test user deleted successfully!")
    
    return True

if __name__ == "__main__":
    if test_secure_password_flow():
        print("\n✅ Secure password flow test completed successfully!")
    else:
        print("\n❌ Secure password flow test failed!")