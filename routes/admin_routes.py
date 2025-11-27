from flask import Blueprint, request, jsonify
from services.prompt_service import PromptService

admin_bp = Blueprint('admin', __name__)
prompt_service = PromptService()

@admin_bp.route('/admin/prompt', methods=['GET'])
def get_prompt():
    """Get the current storyboard generation prompt"""
    try:
        content = prompt_service.get_prompt()
        
        if content:
            return jsonify({
                'success': True,
                'content': content
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Prompt not found in database'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/admin/prompt', methods=['POST'])
def update_prompt():
    """Update the storyboard generation prompt"""
    try:
        data = request.get_json()
        content = data.get('content')
        
        if not content:
            return jsonify({
                'success': False,
                'message': 'Content is required'
            }), 400
            
        success = prompt_service.update_prompt(content)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Prompt updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to update prompt'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
