"""
User model for MongoDB and JSON storage
"""

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import re
import os
from bson import ObjectId

class User:
    """User model with role-based hierarchy and relationships"""
    
    ROLES = ['Saalik', 'Murabi', 'Masool', 'Sheikh', 'Admin']
    ZIKR_MODES = ['auto_restart', 'murabi_controlled']
    
    def __init__(self, **kwargs):
        self.name = kwargs.get('name')
        self.phone = kwargs.get('phone')
        self.email = kwargs.get('email')
        self.password_hash = kwargs.get('password_hash')
        self.role = kwargs.get('role')
        self.region = kwargs.get('region')
        self.murabi_id = kwargs.get('murabi_id')
        self.masool_id = kwargs.get('masool_id')
        self.sheikh_id = kwargs.get('sheikh_id')
        self.level = kwargs.get('level', 0)
        self.level_start_date = kwargs.get('level_start_date')
        self.cycle_days = kwargs.get('cycle_days', 40)
        self.settings = kwargs.get('settings', {
            'zikr_mode': 'auto_restart',
            'notifications_enabled': True
        })
        self.is_active = kwargs.get('is_active', True)
        self.created_by = kwargs.get('created_by')
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.updated_at = kwargs.get('updated_at', datetime.utcnow())
    
    @staticmethod
    def validate_phone(phone):
        """Validate phone number format"""
        if not phone:
            return False
        # Basic phone validation - adjust regex as needed
        phone_pattern = r'^\+?[\d\s\-\(\)]{10,15}$'
        return bool(re.match(phone_pattern, phone))
    
    @staticmethod
    def validate_email(email):
        """Validate email format"""
        if not email:
            return True  # Email is optional
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, email))
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self, include_sensitive=False):
        """Convert user to dictionary"""
        user_dict = {
            '_id': str(self._id) if hasattr(self, '_id') else None,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'role': self.role,
            'region': self.region,
            'murabi_id': str(self.murabi_id) if self.murabi_id else None,
            'masool_id': str(self.masool_id) if self.masool_id else None,
            'sheikh_id': str(self.sheikh_id) if self.sheikh_id else None,
            'level': self.level,
            'level_start_date': self.level_start_date.isoformat() if self.level_start_date else None,
            'cycle_days': self.cycle_days,
            'settings': self.settings,
            'is_active': self.is_active,
            'created_by': str(self.created_by) if self.created_by else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_sensitive:
            user_dict['password_hash'] = self.password_hash
        
        return user_dict
    
    @classmethod
    def from_dict(cls, data):
        """Create User instance from dictionary"""
        # Create a copy of data to avoid modifying the original
        data_copy = data.copy()
        
        # Handle date fields
        for date_field in ['created_at', 'updated_at', 'level_start_date']:
            if date_field in data_copy and isinstance(data_copy[date_field], str):
                try:
                    data_copy[date_field] = datetime.fromisoformat(data_copy[date_field].replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    data_copy[date_field] = None
        
        # Create user instance
        user = cls(**data_copy)
        
        # Set _id attribute
        if '_id' in data:
            user._id = data['_id']
            
        return user
    
    def save(self):
        """Save user to database"""
        from models import users_collection
        import os
        
        self.updated_at = datetime.utcnow()
        user_data = self.to_dict(include_sensitive=True)
        
        # Check if we're using MongoDB
        USE_MONGODB = os.environ.get('MONGO_URI') is not None
        
        if hasattr(self, '_id') and self._id:
            # Update existing user
            if USE_MONGODB:
                # Convert string ID to ObjectId if needed
                if isinstance(self._id, str):
                    object_id = ObjectId(self._id)
                else:
                    object_id = self._id
                
                # Remove _id from update data
                update_data = {k: v for k, v in user_data.items() if k != '_id'}
                
                users_collection.update_one(
                    {'_id': object_id},
                    {'$set': update_data}
                )
            else:
                # JSON storage
                users_collection.update_one(
                    {'_id': self._id},
                    {'$set': user_data}
                )
        else:
            # Insert new user
            user_data.pop('_id', None)  # Remove _id for insert
            result = users_collection.insert_one(user_data)
            self._id = result.inserted_id
        
        return self
    
    @classmethod
    def find_by_id(cls, user_id):
        """Find user by ID"""
        from models import users_collection
        import os
        
        # Check if we're using MongoDB
        USE_MONGODB = os.environ.get('MONGO_URI') is not None
        
        if USE_MONGODB:
            try:
                # Convert string ID to ObjectId for MongoDB if it's a string
                if isinstance(user_id, str):
                    object_id = ObjectId(user_id)
                else:
                    object_id = user_id
                
                user_data = users_collection.find_one({'_id': object_id})
                if user_data:
                    # Ensure _id is properly set in the returned object
                    if '_id' in user_data and isinstance(user_data['_id'], ObjectId):
                        user_data['_id'] = user_data['_id']
                    return cls.from_dict(user_data)
            except Exception as e:
                print(f"Error finding user by ID: {e}")
                return None
        else:
            # JSON storage
            user_data = users_collection.find_one({'_id': user_id})
            if user_data:
                return cls.from_dict(user_data)
        
        return None
    
    @classmethod
    def find_by_phone(cls, phone):
        """Find user by phone number"""
        from models import users_collection
        
        user_data = users_collection.find_one({'phone': phone})
        if user_data:
            return cls.from_dict(user_data)
        return None
    
    @classmethod
    def find_by_email(cls, email):
        """Find user by email"""
        from models import users_collection
        
        user_data = users_collection.find_one({'email': email})
        if user_data:
            return cls.from_dict(user_data)
        return None
    
    @classmethod
    def find_by_identifier(cls, identifier):
        """Find user by phone or email"""
        # Try phone first
        user = cls.find_by_phone(identifier)
        if user:
            return user
        
        # Try email if phone lookup failed
        if cls.validate_email(identifier):
            return cls.find_by_email(identifier)
        
        return None
    
    @classmethod
    def find_by_role(cls, role, region=None):
        """Find users by role and optionally by region"""
        from models import users_collection
        
        query = {'role': role, 'is_active': True}
        if region:
            query['region'] = region
        
        users_data = users_collection.find(query)
        return [cls.from_dict(user_data) for user_data in users_data]
    
    @classmethod
    def find_all(cls, query=None, limit=None, skip=None):
        """Find all users with optional query"""
        from models import users_collection
        
        if query is None:
            query = {}
        
        cursor = users_collection.find(query)
        
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        
        return [cls.from_dict(user_data) for user_data in cursor]
    
    @classmethod
    def find_saaliks_by_murabi(cls, murabi_id):
        """Find all Saaliks assigned to a specific Murabi"""
        from models import users_collection
        
        users_data = users_collection.find({
            'role': 'Saalik',
            'murabi_id': murabi_id,
            'is_active': True
        })
        return [cls.from_dict(user_data) for user_data in users_data]
    
    @classmethod
    def find_murabis_by_masool(cls, masool_id):
        """Find all Murabis assigned to a specific Masool"""
        from models import users_collection
        
        users_data = users_collection.find({
            'role': 'Murabi',
            'masool_id': masool_id,
            'is_active': True
        })
        return [cls.from_dict(user_data) for user_data in users_data]
    
    @classmethod
    def find_masools_by_sheikh(cls, sheikh_id):
        """Find all Masools assigned to a specific Sheikh"""
        from models import users_collection
        
        users_data = users_collection.find({
            'role': 'Masool',
            'sheikh_id': sheikh_id,
            'is_active': True
        })
        return [cls.from_dict(user_data) for user_data in users_data]
    
    def can_create_role(self, target_role):
        """Check if user can create another user with target_role"""
        role_hierarchy = {
            'Admin': ['Sheikh', 'Masool', 'Murabi', 'Saalik', 'Admin'],
            'Sheikh': ['Masool', 'Murabi'],
            'Masool': ['Murabi', 'Saalik'],
            'Murabi': ['Saalik']
        }
        
        allowed_roles = role_hierarchy.get(self.role, [])
        return target_role in allowed_roles
    
    @classmethod
    def create_indexes(cls):
        """Create database indexes for optimal performance"""
        from models import users_collection
        import os
        
        # Only create indexes if using MongoDB
        if os.environ.get('MONGO_URI'):
            # Create indexes for frequently queried fields
            users_collection.create_index('email', unique=True, sparse=True)
            users_collection.create_index('phone', unique=True)
            users_collection.create_index('role')
            users_collection.create_index('murabi_id')
            users_collection.create_index('masool_id')
            users_collection.create_index('sheikh_id')
            print("MongoDB indexes created for User collection")