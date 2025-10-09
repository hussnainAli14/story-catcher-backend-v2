import os
from supabase import create_client
from typing import Dict, Optional

class SupabaseAuthService:
    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("Supabase credentials not found")
        
        self.supabase = create_client(self.supabase_url, self.supabase_key)
    
    def verify_token(self, token: str) -> Dict:
        """Verify a JWT token"""
        try:
            user_data = self.supabase.auth.get_user(token)
            
            if user_data.user:
                return {
                    'is_authenticated': True,
                    'user_id': user_data.user.id,
                    'email': user_data.user.email,
                    'user_metadata': user_data.user.user_metadata
                }
            else:
                return {'is_authenticated': False}
                
        except Exception as e:
            print(f"Token verification error: {str(e)}")
            return {'is_authenticated': False, 'error': str(e)}
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user data by ID"""
        try:
            response = self.supabase.auth.admin.get_user_by_id(user_id)
            
            if response.user:
                return {
                    'user_id': response.user.id,
                    'email': response.user.email,
                    'created_at': response.user.created_at,
                    'last_sign_in': response.user.last_sign_in_at,
                    'user_metadata': response.user.user_metadata
                }
            return None
            
        except Exception as e:
            print(f"Error getting user by ID: {str(e)}")
            return None
    
    def list_users(self) -> Dict:
        """List all users"""
        try:
            response = self.supabase.auth.admin.list_users()
            
            users = []
            for user in response.users:
                users.append({
                    'user_id': user.id,
                    'email': user.email,
                    'created_at': user.created_at,
                    'last_sign_in': user.last_sign_in_at
                })
            
            return {
                'success': True,
                'users': users
            }
            
        except Exception as e:
            print(f"Error listing users: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_user(self, email: str, password: str) -> Dict:
        """Create a new user"""
        try:
            response = self.supabase.auth.admin.create_user({
                'email': email,
                'password': password,
                'email_confirm': True
            })
            
            if response.user:
                return {
                    'success': True,
                    'user_id': response.user.id,
                    'email': response.user.email
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to create user'
                }
                
        except Exception as e:
            print(f"Error creating user: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def delete_user(self, user_id: str) -> Dict:
        """Delete a user"""
        try:
            response = self.supabase.auth.admin.delete_user(user_id)
            
            return {
                'success': True,
                'message': 'User deleted successfully'
            }
            
        except Exception as e:
            print(f"Error deleting user: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
