"""
Data migration script to transfer data from JSON files to MongoDB
"""

import os
import json
import sys
from dotenv import load_dotenv
from bson import ObjectId
from datetime import datetime
from utils.mongo_db import get_mongo_client, get_db, get_collection

# Load environment variables
load_dotenv()

def load_json_data(file_path):
    """Load data from JSON file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return []

def prepare_data_for_mongodb(data):
    """Prepare data for MongoDB insertion"""
    for item in data:
        # Convert string IDs to ObjectId
        if '_id' in item and isinstance(item['_id'], str):
            try:
                item['_id'] = ObjectId(item['_id'])
            except:
                # If ID can't be converted to ObjectId, remove it to let MongoDB generate one
                del item['_id']
        
        # Convert date strings to datetime objects
        for date_field in ['created_at', 'updated_at', 'level_start_date']:
            if date_field in item and isinstance(item[date_field], str):
                try:
                    item[date_field] = datetime.fromisoformat(item[date_field].replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    item[date_field] = datetime.utcnow()
        
        # Convert reference IDs to ObjectId
        for ref_field in ['murabi_id', 'masool_id', 'sheikh_id', 'created_by', 'user_id']:
            if ref_field in item and item[ref_field] and isinstance(item[ref_field], str):
                try:
                    item[ref_field] = ObjectId(item[ref_field])
                except:
                    # If reference ID can't be converted, keep as string
                    pass
    
    return data

def migrate_collection(collection_name):
    """Migrate a collection from JSON to MongoDB"""
    print(f"\nMigrating {collection_name}...")
    
    # Load JSON data
    json_file = f"data/{collection_name}.json"
    data = load_json_data(json_file)
    
    if not data:
        print(f"No data found in {json_file}")
        return 0
    
    # Prepare data for MongoDB
    mongo_data = prepare_data_for_mongodb(data)
    
    # Get MongoDB collection
    mongo_collection = get_collection(collection_name)
    
    # Check if collection already has data
    existing_count = mongo_collection.count_documents({})
    if existing_count > 0:
        confirm = input(f"Collection '{collection_name}' already has {existing_count} documents. Overwrite? (y/n): ")
        if confirm.lower() != 'y':
            print(f"Skipping {collection_name}")
            return 0
        
        # Clear existing data
        mongo_collection.delete_many({})
    
    # Insert data into MongoDB
    if len(mongo_data) > 0:
        result = mongo_collection.insert_many(mongo_data)
        print(f"✅ Migrated {len(result.inserted_ids)} documents to '{collection_name}' collection")
        return len(result.inserted_ids)
    else:
        print(f"No data to migrate for {collection_name}")
        return 0

def main():
    """Main migration function"""
    if not os.environ.get('MONGO_URI'):
        print("❌ MONGO_URI not found in environment variables")
        sys.exit(1)
    
    # Connect to MongoDB
    client = get_mongo_client()
    db = get_db()
    
    print(f"Connected to MongoDB database: {db.name}")
    
    # Collections to migrate
    # collections = ['users', 'entries', 'levels', 'sessions', 'notifications', 'audit_logs']
    collections = ['users']

    
    total_migrated = 0
    for collection in collections:
        migrated = migrate_collection(collection)
        total_migrated += migrated
    
    print(f"\n===== MIGRATION COMPLETED =====")
    print(f"Total documents migrated: {total_migrated}")

if __name__ == "__main__":
    main()