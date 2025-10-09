from functools import wraps
from flask import request, jsonify
import os
from supabase import create_client
from jose import jwt, JWTError

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        
        # Check for token in Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]  # Bearer <token>
            except IndexError:
                return jsonify({'success': False, 'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'success': False, 'error': 'Token is missing'}), 401
        
        try:
            # Get Supabase client
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
            supabase = create_client(supabase_url, supabase_key)
            
            # Verify token
            user_data = supabase.auth.get_user(token)
            
            if not user_data.user:
                return jsonify({'success': False, 'error': 'Invalid token'}), 401
            
            # Add user data to request
            request.user = user_data.user
            
        except Exception as e:
            return jsonify({'success': False, 'error': 'Token verification failed'}), 401
        
        return f(*args, **kwargs)
    
    return decorated_function

def require_admin(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        
        # Check for token in Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]  # Bearer <token>
            except IndexError:
                return jsonify({'success': False, 'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'success': False, 'error': 'Token is missing'}), 401
        
        try:
            # Get Supabase client
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
            supabase = create_client(supabase_url, supabase_key)
            
            # Verify token
            user_data = supabase.auth.get_user(token)
            
            if not user_data.user:
                return jsonify({'success': False, 'error': 'Invalid token'}), 401
            
            # Check if user is admin (you can customize this logic)
            # For now, we'll assume all authenticated users are admins
            # In production, you might want to check user roles/metadata
            
            # Add user data to request
            request.user = user_data.user
            
        except Exception as e:
            return jsonify({'success': False, 'error': 'Token verification failed'}), 401
        
        return f(*args, **kwargs)
    
    return decorated_function
