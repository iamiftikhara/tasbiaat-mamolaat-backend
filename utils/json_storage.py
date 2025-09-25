"""
JSON file storage utility to replace MongoDB operations
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import uuid
from utils.error_handler import NotFoundError, NoDataError

class JSONStorage:
    def __init__(self, data_dir="data"):
        # Check if we're running on Vercel (read-only filesystem)
        if os.environ.get('VERCEL') == '1':
            # Use /tmp directory for Vercel's serverless environment
            self.data_dir = os.path.join('/tmp', data_dir)
            # Load initial data from the read-only data directory
            self._initialize_tmp_data(data_dir)
        else:
            self.data_dir = data_dir
        
        self.ensure_data_dir()
    
    def _initialize_tmp_data(self, original_data_dir):
        """Initialize /tmp with data from the read-only filesystem"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
            
        # Copy existing data files to tmp if they exist
        if os.path.exists(original_data_dir):
            for filename in os.listdir(original_data_dir):
                if filename.endswith('.json'):
                    try:
                        src_path = os.path.join(original_data_dir, filename)
                        dst_path = os.path.join(self.data_dir, filename)
                        
                        # Only copy if destination doesn't exist
                        if not os.path.exists(dst_path):
                            with open(src_path, 'r', encoding='utf-8') as src:
                                data = src.read()
                            with open(dst_path, 'w', encoding='utf-8') as dst:
                                dst.write(data)
                    except Exception:
                        # Continue even if some files can't be copied
                        pass
    
    def ensure_data_dir(self):
        """Ensure data directory exists"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
    
    def get_file_path(self, collection_name: str) -> str:
        """Get file path for a collection"""
        return os.path.join(self.data_dir, f"{collection_name}.json")
    
    def load_collection(self, collection_name: str) -> List[Dict]:
        """Load data from JSON file"""
        file_path = self.get_file_path(collection_name)
        
        if not os.path.exists(file_path):
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError):
            return []
    
    def save_collection(self, collection_name: str, data: List[Dict]):
        """Save data to JSON file"""
        file_path = self.get_file_path(collection_name)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except IOError as e:
            raise Exception(f"Failed to save data to {file_path}: {str(e)}")
    
    def generate_id(self) -> str:
        """Generate a unique ID"""
        return str(uuid.uuid4()).replace('-', '')[:24]
    
    def find_one(self, collection_name: str, query: Dict) -> Optional[Dict]:
        """Find one document matching the query"""
        data = self.load_collection(collection_name)
        
        for item in data:
            if self._matches_query(item, query):
                return item
        
        return None
    
    def find(self, collection_name: str, query: Dict = None, sort: List = None, 
             skip: int = 0, limit: int = None) -> List[Dict]:
        """Find documents matching the query"""
        data = self.load_collection(collection_name)
        
        # Filter by query
        if query:
            data = [item for item in data if self._matches_query(item, query)]
        
        # Sort
        if sort:
            for sort_field, sort_order in reversed(sort):
                reverse = sort_order == -1
                data.sort(key=lambda x: x.get(sort_field, ''), reverse=reverse)
        
        # Apply skip and limit
        if skip:
            data = data[skip:]
        if limit:
            data = data[:limit]
        
        return data
    
    def count(self, collection_name: str, query: Dict = None) -> int:
        """Count documents matching the query"""
        data = self.load_collection(collection_name)
        
        if query:
            data = [item for item in data if self._matches_query(item, query)]
        
        return len(data)
    
    def insert_one(self, collection_name: str, document: Dict) -> str:
        """Insert a single document"""
        data = self.load_collection(collection_name)
        
        # Generate ID if not provided
        if '_id' not in document:
            document['_id'] = self.generate_id()
        
        # Add timestamps
        now = datetime.utcnow().isoformat() + 'Z'
        if 'created_at' not in document:
            document['created_at'] = now
        document['updated_at'] = now
        
        data.append(document)
        self.save_collection(collection_name, data)
        
        return document['_id']
    
    def update_one(self, collection_name: str, query: Dict, update: Dict) -> bool:
        """Update a single document"""
        data = self.load_collection(collection_name)
        
        for i, item in enumerate(data):
            if self._matches_query(item, query):
                # Handle $set operator
                if '$set' in update:
                    item.update(update['$set'])
                else:
                    item.update(update)
                
                # Update timestamp
                item['updated_at'] = datetime.utcnow().isoformat() + 'Z'
                
                self.save_collection(collection_name, data)
                return True
        
        return False
    
    def delete_one(self, collection_name: str, query: Dict) -> bool:
        """Delete a single document"""
        data = self.load_collection(collection_name)
        
        for i, item in enumerate(data):
            if self._matches_query(item, query):
                data.pop(i)
                self.save_collection(collection_name, data)
                return True
        
        return False
    
    def delete_many(self, collection_name: str, query: Dict) -> int:
        """Delete multiple documents"""
        data = self.load_collection(collection_name)
        original_count = len(data)
        
        data = [item for item in data if not self._matches_query(item, query)]
        
        deleted_count = original_count - len(data)
        if deleted_count > 0:
            self.save_collection(collection_name, data)
        
        return deleted_count
    
    def _matches_query(self, document: Dict, query: Dict) -> bool:
        """Check if document matches query"""
        for key, value in query.items():
            if key.startswith('$'):
                # Handle special operators
                if key == '$or':
                    if not any(self._matches_query(document, condition) for condition in value):
                        return False
                elif key == '$and':
                    if not all(self._matches_query(document, condition) for condition in value):
                        return False
                elif key == '$in':
                    # This should be handled at field level
                    continue
            else:
                doc_value = document.get(key)
                
                if isinstance(value, dict):
                    # Handle operators like $in, $gte, $lte, etc.
                    for op, op_value in value.items():
                        if op == '$in':
                            if doc_value not in op_value:
                                return False
                        elif op == '$gte':
                            if doc_value is None or doc_value < op_value:
                                return False
                        elif op == '$lte':
                            if doc_value is None or doc_value > op_value:
                                return False
                        elif op == '$gt':
                            if doc_value is None or doc_value <= op_value:
                                return False
                        elif op == '$lt':
                            if doc_value is None or doc_value >= op_value:
                                return False
                        elif op == '$ne':
                            if doc_value == op_value:
                                return False
                        elif op == '$regex':
                            import re
                            if not re.search(op_value, str(doc_value or '')):
                                return False
                else:
                    # Direct value comparison
                    if doc_value != value:
                        return False
        
        return True

# Global storage instance
storage = JSONStorage()

# Helper functions to maintain compatibility with existing code
def get_collection(name):
    """Get a collection-like object for compatibility"""
    return CollectionWrapper(name)

class CollectionWrapper:
    """Wrapper to make JSON storage behave like MongoDB collection"""
    
    def __init__(self, collection_name):
        self.collection_name = collection_name
    
    def find_one(self, query=None):
        query = query or {}
        return storage.find_one(self.collection_name, query)
    
    def find(self, query=None):
        query = query or {}
        return storage.find(self.collection_name, query)
    
    def count_documents(self, query=None):
        query = query or {}
        return storage.count(self.collection_name, query)
    
    def insert_one(self, document):
        result_id = storage.insert_one(self.collection_name, document)
        return type('InsertResult', (), {'inserted_id': result_id})()
    
    def update_one(self, query, update):
        success = storage.update_one(self.collection_name, query, update)
        return type('UpdateResult', (), {'modified_count': 1 if success else 0})()
    
    def delete_one(self, query):
        success = storage.delete_one(self.collection_name, query)
        return type('DeleteResult', (), {'deleted_count': 1 if success else 0})()
    
    def delete_many(self, query):
        count = storage.delete_many(self.collection_name, query)
        return type('DeleteResult', (), {'deleted_count': count})()
    
    def aggregate(self, pipeline):
        # Basic aggregation support
        data = storage.load_collection(self.collection_name)
        
        for stage in pipeline:
            if '$match' in stage:
                data = [item for item in data if storage._matches_query(item, stage['$match'])]
            elif '$group' in stage:
                # Basic grouping support
                group_spec = stage['$group']
                if '_id' in group_spec and group_spec['_id'] is None:
                    # Count all
                    result = {'_id': None}
                    for key, value in group_spec.items():
                        if key != '_id' and isinstance(value, dict) and '$sum' in value:
                            if value['$sum'] == 1:
                                result[key] = len(data)
                    data = [result]
            elif '$sort' in stage:
                sort_spec = stage['$sort']
                for field, order in sort_spec.items():
                    data.sort(key=lambda x: x.get(field, ''), reverse=(order == -1))
        
        return data