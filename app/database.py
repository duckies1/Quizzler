import sys
import importlib.util
from types import ModuleType

if 'websockets.asyncio' not in sys.modules:
    asyncio_module = ModuleType('websockets.asyncio')
    client_module = ModuleType('websockets.asyncio.client')
    
    class ClientConnection:
        pass
    
    client_module.ClientConnection = ClientConnection
    asyncio_module.client = client_module
    
    sys.modules['websockets.asyncio'] = asyncio_module
    sys.modules['websockets.asyncio.client'] = client_module

from supabase import create_client, Client
from app.config import settings
import logging

# Supabase Client Setup
def get_supabase_client() -> Client:
    """Get Supabase client for authentication operations"""
    return create_client(
        settings.supabase_url, 
        settings.supabase_anon_key.get_secret_value()
    )

def get_supabase_admin_client() -> Client:
    """Get Supabase admin client for admin operations"""
    return create_client(
        settings.supabase_url, 
        settings.supabase_service_role_key.get_secret_value()
    )

# Global Supabase client instances
supabase: Client = get_supabase_client()
supabase_admin: Client = get_supabase_admin_client()

def test_supabase_connection():
    """Test Supabase connection"""
    try:
        response = supabase.table('_realtime').select('*').limit(1).execute()
        return True
    except Exception as e:
        logging.error(f"Supabase connection test failed: {e}")
        try:
            supabase.auth.get_session()
            return True
        except Exception as e2:
            logging.error(f"Supabase auth test also failed: {e2}")
            return False

class Database:
    """Database operations using Supabase REST API"""
    
    @staticmethod
    def insert(table: str, data: dict):
        """Insert data into table"""
        try:
            result = supabase_admin.table(table).insert(data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logging.error(f"Insert error in {table}: {e}")
            raise e
    
    @staticmethod
    def select(table: str, columns: str = "*", filters: dict = None, limit: int = None):
        """Select data from table"""
        try:
            query = supabase_admin.table(table).select(columns)
            
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            
            if limit:
                query = query.limit(limit)
            
            result = query.execute()
            return result.data
        except Exception as e:
            logging.error(f"Select error in {table}: {e}")
            raise e
    
    @staticmethod
    def update(table: str, data: dict, filters: dict):
        """Update data in table"""
        try:
            query = supabase_admin.table(table).update(data)
            
            for key, value in filters.items():
                query = query.eq(key, value)
            
            result = query.execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logging.error(f"Update error in {table}: {e}")
            raise e
    
    @staticmethod
    def delete(table: str, filters: dict):
        """Delete data from table"""
        try:
            query = supabase_admin.table(table).delete()
            
            for key, value in filters.items():
                query = query.eq(key, value)
            
            result = query.execute()
            return result.data
        except Exception as e:
            logging.error(f"Delete error in {table}: {e}")
            raise e

# Global database instance
db = Database()