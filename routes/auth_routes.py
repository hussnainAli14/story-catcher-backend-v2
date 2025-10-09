from flask import Blueprint, request, jsonify
from services.auth_service import SupabaseAuthService
from middleware.auth_middleware import require_auth, require_admin

auth_bp = Blueprint('auth', __name__)

# Initialize auth service
auth_service = SupabaseAuthService()

@auth_bp.route('/auth/verify', methods=['POST'])
def verify_token():
    """
    Verify a JWT token
    """
    try:
        data = request.get_json()
        token = data.get('token')
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Token is required'
            }), 400
        
        user_data = auth_service.verify_token(token)
        
        if user_data.get('is_authenticated'):
            return jsonify({
                'success': True,
                'user': user_data
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid token'
            }), 401
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@auth_bp.route('/auth/user/<user_id>', methods=['GET'])
@require_admin
def get_user(user_id):
    """
    Get user data by ID (Admin only)
    """
    try:
        user_data = auth_service.get_user_by_id(user_id)
        
        if user_data:
            return jsonify({
                'success': True,
                'user': user_data
            })
        else:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@auth_bp.route('/auth/users', methods=['GET'])
@require_admin
def list_users():
    """
    List all users (Admin only)
    """
    try:
        result = auth_service.list_users()
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'users': result.get('users', [])
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to list users')
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@auth_bp.route('/auth/create-user', methods=['POST'])
@require_admin
def create_user():
    """
    Create a new user (Admin only)
    """
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({
                'success': False,
                'error': 'Email and password are required'
            }), 400
        
        result = auth_service.create_user(email, password)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'user': {
                    'user_id': result.get('user_id'),
                    'email': result.get('email')
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to create user')
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@auth_bp.route('/auth/delete-user/<user_id>', methods=['DELETE'])
@require_admin
def delete_user(user_id):
    """
    Delete a user (Admin only)
    """
    try:
        result = auth_service.delete_user(user_id)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': 'User deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to delete user')
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@auth_bp.route('/auth/me', methods=['GET'])
@require_auth
def get_current_user():
    """
    Get current authenticated user data
    """
    try:
        user_data = request.user
        return jsonify({
            'success': True,
            'user': user_data
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
