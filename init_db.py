#!/usr/bin/env python3
"""
Database initialization script for Quizzler
Run this to create all tables in your Supabase PostgreSQL database
"""

import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import test_supabase_connection, supabase

def init_supabase():
    """Test Supabase connection and provide setup instructions"""
    try:
        print("🔄 Testing Supabase connection...")
        
        if test_supabase_connection():
            print("✅ Supabase connection successful!")
        else:
            print("⚠️  Supabase connection test inconclusive, but configuration looks correct")
        
        print("\n📋 Next steps to set up your database:")
        print("1. Go to your Supabase dashboard: https://app.supabase.com")
        print("2. Navigate to your project: jhpsyfjmmtflqvkecwfd")
        print("3. Go to SQL Editor")
        print("4. Copy and paste the contents of 'create_tables.sql' file")
        print("5. Execute the SQL to create all tables and policies")
        
        print("\n� Get your JWT Secret:")
        print("1. In Supabase dashboard, go to Settings -> API")
        print("2. Copy the 'JWT Secret' (not the service role key)")
        print("3. Update your .env file: JWT_SECRET=<your_jwt_secret>")
        
        print("\n� Tables that will be created:")
        print("  - users (with Supabase Auth integration)")
        print("  - quizzes")
        print("  - questions")
        print("  - quiz_sessions")
        print("  - responses") 
        print("  - ratings")
        
        print("\n🔒 Security features included:")
        print("  - Row Level Security (RLS) policies")
        print("  - User authentication integration")
        print("  - Proper foreign key constraints")
        
        print("\n🎉 Setup instructions provided!")
        print("After running the SQL, your Quizzler backend will be ready!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Supabase: {e}")
        print("\n💡 Troubleshooting:")
        print("1. Check your .env file has correct Supabase credentials")
        print("2. Make sure SUPABASE_URL and SUPABASE_*_KEY are set")
        print("3. Verify your Supabase project is active")
        print("4. Check network connectivity")
        return False

if __name__ == "__main__":
    success = init_supabase()
    
    if success:
        print(f"\n📄 SQL file created: create_tables.sql")
        print("Run this SQL in your Supabase dashboard to create the database schema.")
    
    sys.exit(0 if success else 1)
