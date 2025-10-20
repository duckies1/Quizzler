"""
Unit tests for database operations
"""
import pytest
from unittest.mock import patch, MagicMock
from app.database import Database


class TestDatabase:
    """Test cases for Database class"""

    @pytest.mark.asyncio
    async def test_insert_record_success(self):
        """Test successful record insertion"""
        mock_data = {"id": "test-id", "name": "Test Record"}
        
        with patch('app.database.supabase') as mock_supabase:
            mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [mock_data]
            
            result = Database.insert("test_table", {"name": "Test Record"})
            
            assert result == [mock_data]

    @pytest.mark.asyncio
    async def test_insert_record_failure(self):
        """Test record insertion failure"""
        with patch('app.database.supabase') as mock_supabase:
            mock_supabase.table.return_value.insert.return_value.execute.side_effect = Exception("Database error")
            
            with pytest.raises(Exception):
                Database.insert("test_table", {"name": "Test Record"})

    @pytest.mark.asyncio
    async def test_select_with_filters(self):
        """Test select with filters"""
        mock_data = [{"id": "test-id", "name": "Test Record"}]
        
        with patch('app.database.supabase') as mock_supabase:
            mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = mock_data
            
            result = Database.select("test_table", filters={"id": "test-id"})
            
            assert result == mock_data

    @pytest.mark.asyncio
    async def test_select_no_results(self):
        """Test select with no results"""
        with patch('app.database.supabase') as mock_supabase:
            mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
            
            result = Database.select("test_table", filters={"id": "non-existing-id"})
            
            assert result == []

    @pytest.mark.asyncio
    async def test_update_record_success(self):
        """Test successful record update"""
        mock_data = [{"id": "test-id", "name": "Updated Record"}]
        
        with patch('app.database.supabase') as mock_supabase:
            mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = mock_data
            
            result = Database.update("test_table", {"name": "Updated Record"}, {"id": "test-id"})
            
            assert result == mock_data

    @pytest.mark.asyncio
    async def test_delete_record_success(self):
        """Test successful record deletion"""
        with patch('app.database.supabase') as mock_supabase:
            mock_supabase.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = []
            
            result = Database.delete("test_table", {"id": "test-id"})
            
            # Delete should return the data from execution
            assert result == []

    @pytest.mark.asyncio
    async def test_select_with_limit(self):
        """Test select with limit"""
        mock_data = [{"id": "1", "name": "Record 1"}, {"id": "2", "name": "Record 2"}]
        
        with patch('app.database.supabase') as mock_supabase:
            mock_supabase.table.return_value.select.return_value.limit.return_value.execute.return_value.data = mock_data
            
            result = Database.select("test_table", limit=2)
            
            assert result == mock_data
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_select_with_columns(self):
        """Test select with specific columns"""
        mock_data = [{"id": "test-id", "name": "Test Record"}]
        
        with patch('app.database.supabase') as mock_supabase:
            mock_supabase.table.return_value.select.return_value.execute.return_value.data = mock_data
            
            result = Database.select("test_table", columns="id,name")
            
            assert result == mock_data
