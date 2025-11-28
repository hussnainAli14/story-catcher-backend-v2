from flask import Blueprint, request, jsonify
from services.story_service import StoryService
from services.openai_service import OpenAIService
from services.videogen_service import VideoGenService
from models.story_models import StorySession, Question, StoryResponse
import json

story_bp = Blueprint('story', __name__)

# Initialize services
story_service = StoryService()
openai_service = OpenAIService()
videogen_service = VideoGenService()

@story_bp.route('/story/start', methods=['POST'])
def start_story_session():
    """
    Start a new story session with dynamic GPT conversation
    """
    try:
        # Start new session with dynamic conversation flow
        result = story_service.start_session()
        
        return jsonify({
            'success': True,
            'session_id': result['session_id'],
            'message': result['message'],
            'question': result['question'],
            'question_id': result['question_id'],
            'question_number': 1,
            'total_questions': 4,
            'session_complete': False
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@story_bp.route('/story/answer', methods=['POST'])
def submit_answer():
    """
    Submit an answer and get the next question from GPT
    """
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        answer = data.get('answer')
        
        if not session_id or not answer:
            return jsonify({
                'success': False,
                'message': 'Session ID and answer are required'
            }), 400
        
        # Submit answer and get next question from GPT
        result = story_service.submit_answer(session_id, answer)
        
        if 'error' in result:
            return jsonify({
                'success': False,
                'message': result['error']
            }), 400
        
        if result.get('is_complete', False):
            # All questions completed - Generate VideoGen outline for display and editing
            try:
                # Generate outline using VideoGen
                outline_result = story_service.generate_videogen_outline_for_display(session_id)
                
                if outline_result['success']:
                    # Format the outline as a readable storyboard for display
                    formatted_storyboard = story_service.format_outline_as_storyboard(outline_result['outline'])
                    
                    return jsonify({
                        'success': True,
                        'message': result['message'],
                        'storyboard': formatted_storyboard,
                        'session_complete': True,
                        'question_number': 4,
                        'total_questions': 4
                    })
                else:
                    # If outline generation fails, return without storyboard
                    return jsonify({
                        'success': True,
                        'message': result['message'],
                        'storyboard': None,
                        'session_complete': True,
                        'question_number': 4,
                        'total_questions': 4,
                        'outline_error': outline_result.get('error', 'Failed to generate outline')
                    })
            except Exception as e:
                print(f"Error generating outline after Q4: {str(e)}")
                # Return without storyboard if outline generation fails
                return jsonify({
                    'success': True,
                    'message': result['message'],
                    'storyboard': None,
                    'session_complete': True,
                    'question_number': 4,
                    'total_questions': 4,
                    'outline_error': str(e)
                })
        else:
            # Return next question and reaction from GPT
            return jsonify({
                'success': True,
                'message': result['message'],
                'question': result['question'],
                'question_id': result['question_id'],
                'question_number': int(result['question_id'].replace('q', '')),
                'total_questions': 4,
                'session_complete': False
            })
    
    except Exception as e:
        print(f"Error in submit_answer: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@story_bp.route('/story/current-question/<session_id>', methods=['GET'])
def get_current_question(session_id):
    """
    Get the current question for a session
    """
    try:
        session = story_service.get_session(session_id)
        
        if not session:
            return jsonify({
                'success': False,
                'message': 'Session not found'
            }), 404
        
        if session.is_complete:
            return jsonify({
                'success': True,
                'message': 'All questions have been answered',
                'session_complete': True,
                'question_number': 4,
                'total_questions': 4
            })
        
        # Get current question based on session state
        current_question_number = session.current_question
        if current_question_number == 1:
            question_text = "What was the life-changing moment that you'd like to share with me?"
        else:
            # For questions 2-4, we need to get them from conversation history
            conversation_history = story_service.conversation_history.get(session_id, [])
            if current_question_number <= len(conversation_history) + 1:
                question_text = f"Question {current_question_number}"
            else:
                question_text = "What was the life-changing moment that you'd like to share with me?"
        
        return jsonify({
            'success': True,
            'question': question_text,
            'question_number': current_question_number,
            'total_questions': 4,
            'session_complete': False
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@story_bp.route('/story/session/<session_id>', methods=['GET'])
def get_session_status(session_id):
    """
    Get the current status of a story session
    """
    try:
        session = story_service.get_session(session_id)
        
        if not session:
            return jsonify({
                'success': False,
                'message': 'Session not found'
            }), 404
        
        # Convert session to dictionary format
        session_data = {
            'session_id': session.session_id,
            'created_at': session.created_at.isoformat() if session.created_at else None,
            'answers': [{'question_id': a.question_id, 'answer_text': a.answer_text, 'timestamp': a.timestamp.isoformat() if a.timestamp else None} for a in session.answers],
            'current_question': session.current_question,
            'is_complete': session.is_complete,
            'generated_story': session.generated_story,
            'user_email': session.user_email
        }
        
        return jsonify({
            'success': True,
            'session_data': session_data
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@story_bp.route('/video/generate-with-edited-storyboard', methods=['POST'])
def generate_video_with_edited_storyboard():
    """
    Generate video from EDITED storyboard text
    Parses the edited markdown back to outline format and generates video
    """
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        edited_storyboard = data.get('storyboard')
        email = data.get('email', '')
        
        if not session_id:
            return jsonify({
                'success': False,
                'message': 'Session ID is required'
            }), 400
        
        if not edited_storyboard:
            return jsonify({
                'success': False,
                'message': 'Storyboard text is required'
            }), 400
        
        # Store email if provided
        if email:
            story_service.save_user_email(session_id, email)
        
        # Parse the edited storyboard text back to outline format
        outline = story_service.parse_storyboard_to_outline(edited_storyboard)
        print(f"Parsed edited storyboard into outline with {len(outline.get('sections', []))} sections")
        
        # Generate video from the parsed outline
        try:
            api_file_id = videogen_service.generate_video_from_outline(outline)
            video_url = f"videogen://{api_file_id}"
            
            return jsonify({
                'success': True,
                'video_url': video_url,
                'outline': outline,
                'message': 'Video generation started with edited storyboard'
            })
        except Exception as e:
            print(f"Error generating video from edited storyboard: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    except Exception as e:
        print(f"Error in generate_video_with_edited_storyboard: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@story_bp.route('/video/generate-with-videogen-outline', methods=['POST'])
def generate_video_with_videogen_outline():
    """
    Generate video using VideoGen's Prompt-to-Outline and Outline-to-Video APIs
    This bypasses GPT storyboard generation entirely
    """
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        email = data.get('email', '')
        
        if not session_id:
            return jsonify({
                'success': False,
                'message': 'Session ID is required'
            }), 400
        
        # Store email if provided
        if email:
            story_service.save_user_email(session_id, email)
        
        # Generate video using VideoGen outline APIs
        result = story_service.generate_video_with_videogen_outline(session_id)
        
        if not result['success']:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error')
            }), 500
        
        # Return the outline as the "storyboard" and video URL
        api_file_id = result['api_file_id']
        video_url = f"videogen://{api_file_id}"
        
        return jsonify({
            'success': True,
            'video_url': video_url,
            'outline': result['outline'],
            'message': 'Video generation started with VideoGen outline'
        })
    
    except Exception as e:
        print(f"Error in generate_video_with_videogen_outline: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@story_bp.route('/video/generate-from-session', methods=['POST'])
def generate_video_from_session():
    """
    Generate a video from a completed story session
    """
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        email = data.get('email', '')  # Optional email
        
        if not session_id:
            return jsonify({
                'success': False,
                'message': 'Session ID is required'
            }), 400
        
        # Get the stored storyboard from the session
        storyboard = story_service.get_generated_storyboard(session_id)
        if not storyboard:
            return jsonify({
                'success': False,
                'message': 'No storyboard found for this session'
            }), 404
        
        # Generate video from storyboard
        video_url = None
        try:
            print(f"Generating video for session {session_id}")
            video_url = openai_service.generate_video_from_storyboard(storyboard)
            print(f"Video generation initiated: {video_url}")
        except Exception as e:
            print(f"Video generation failed: {e}")
            import traceback
            traceback.print_exc()
            video_url = None
        
        # Store email and video info in session for later saving to Supabase
        if email:
            story_service.save_user_email(session_id, email)
        
        # Save to Supabase when video is ready
        if video_url and video_url.startswith('videogen://'):
            # Video is still processing, will save when ready
            pass
        elif video_url:
            # Video is ready, save to Supabase
            story_service.save_to_supabase(session_id, video_url)
        
        return jsonify({
            'success': True,
            'video_url': video_url,
            'message': 'Video generation started'
        })
    
    except Exception as e:
        print(f"Error in generate_video_from_session: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@story_bp.route('/video/generate-from-storyboard', methods=['POST'])
def generate_video_from_storyboard():
    """
    Generate a video from a storyboard using VideoGen API
    """
    try:
        data = request.get_json()
        storyboard = data.get('storyboard')
        email = data.get('email', '')  # Optional email
        session_id = data.get('session_id', '')  # Session ID
        
        if not storyboard:
            return jsonify({
                'success': False,
                'message': 'Storyboard is required'
            }), 400
        
        # Generate video using VideoGen
        video_url = openai_service.generate_video_from_storyboard(storyboard)
        
        # Store email temporarily in session (don't save to Supabase yet)
        if email and session_id:
            try:
                print(f"Storing email {email} temporarily for session {session_id}")
                story_service.save_user_email(session_id, email)
                
                # If video is ready (not videogen://), save to Supabase immediately
                if video_url and not video_url.startswith('videogen://'):
                    print(f"Saving video {video_url} and email to Supabase for session {session_id}")
                    story_service.save_to_supabase(session_id, video_url)
            except Exception as e:
                print(f"Failed to store email or save to Supabase: {e}")
        
        return jsonify({
            'success': True,
            'video_url': video_url,
            'message': 'Video generated successfully from storyboard'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@story_bp.route('/video/save-to-supabase', methods=['POST'])
def save_video_to_supabase():
    """
    Save final video URL to Supabase
    """
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        video_url = data.get('video_url')
        
        if not session_id or not video_url:
            return jsonify({
                'success': False,
                'message': 'Session ID and video URL are required'
            }), 400
        
        # Save to Supabase
        try:
            print(f"Saving final video {video_url} to Supabase for session {session_id}")
            success = story_service.save_to_supabase(session_id, video_url)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'Video saved to Supabase successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Failed to save video to Supabase'
                }), 500
                
        except Exception as e:
            print(f"Failed to save to Supabase: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@story_bp.route('/video/status/<api_file_id>', methods=['GET'])
def get_video_status(api_file_id):
    """
    Get the status of a video generation using VideoGen API
    """
    try:
        if not api_file_id:
            return jsonify({
                'success': False,
                'message': 'API file ID is required'
            }), 400
        
        # Get video status from VideoGen
        result = videogen_service.get_video_file(api_file_id)
        
        return jsonify({
            'success': True,
            'result': result
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@story_bp.route('/storyboard/status/<session_id>', methods=['GET'])
def get_storyboard_status(session_id):
    """
    Get the status of storyboard generation for a session
    """
    try:
        status = openai_service.get_storyboard_status(session_id)
        
        if status['status'] == 'completed':
            # Store the completed storyboard in the session
            story_service.save_generated_storyboard(session_id, status['storyboard'])
        
        return jsonify({
            'success': True,
            'status': status['status'],
            'storyboard': status.get('storyboard'),
            'timestamp': status.get('timestamp')
        })
    
    except Exception as e:
        print(f"Error checking storyboard status: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@story_bp.route('/video/process-and-store/<api_file_id>', methods=['POST'])
def process_and_store_video(api_file_id):
    """
    Background task to download and store video
    This should be called after video generation is complete
    """
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({
                'success': False,
                'message': 'Session ID is required'
            }), 400
        
        # Download and store video
        from services.video_storage_service import VideoStorageService
        storage_service = VideoStorageService()
        
        print(f"Starting video download and storage for apiFileId: {api_file_id}, session: {session_id}")
        result = storage_service.download_and_store_video(api_file_id, session_id)
        
        if result['success']:
            # Update Supabase with permanent URL
            print(f"Video stored successfully, updating Supabase...")
            story_service.save_to_supabase(
                session_id, 
                f"videogen://{api_file_id}",
                permanent_url=result['permanent_url']
            )
            
            return jsonify({
                'success': True,
                'permanent_url': result['permanent_url'],
                'message': 'Video downloaded and stored successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error')
            }), 500
            
    except Exception as e:
        print(f"Error in process_and_store_video: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@story_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    """
    return jsonify({
        'status': 'healthy',
        'message': 'Story Catcher Backend V2 is running'
    })
