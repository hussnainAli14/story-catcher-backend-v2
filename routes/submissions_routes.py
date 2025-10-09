from flask import Blueprint, request, jsonify
from services.auth_service import SupabaseAuthService
from middleware.auth_middleware import require_admin
import os
from supabase import create_client

submissions_bp = Blueprint('submissions', __name__)

# Initialize auth service
auth_service = SupabaseAuthService()

@submissions_bp.route('/submissions', methods=['GET'])
@require_admin
def get_submissions():
    """
    Get all story submissions (Admin only)
    """
    try:
        # Get Supabase client
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        supabase = create_client(supabase_url, supabase_key)
        
        # Query submissions
        response = supabase.table('story_submissions').select('*').order('created_at', desc=True).execute()
        
        submissions = []
        for row in response.data:
            submissions.append({
                'id': row['id'],
                'email': row['email'],
                'video_url': row['video_url'],
                'created_at': row['created_at']
            })
        
        return jsonify({
            'success': True,
            'submissions': submissions
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@submissions_bp.route('/submissions/<int:submission_id>', methods=['DELETE'])
@require_admin
def delete_submission(submission_id):
    """
    Delete a story submission (Admin only)
    """
    try:
        # Get Supabase client
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        supabase = create_client(supabase_url, supabase_key)
        
        # Delete submission
        response = supabase.table('story_submissions').delete().eq('id', submission_id).execute()
        
        return jsonify({
            'success': True,
            'message': 'Submission deleted successfully'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
