import os
import requests
from supabase import create_client
from typing import Optional, Dict
import time

class VideoStorageService:
    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("Supabase credentials not found")
        
        self.supabase = create_client(self.supabase_url, self.supabase_key)
        self.storage_bucket = 'story-videos'  # The bucket you created in Supabase
    
    def download_and_store_video(self, api_file_id: str, session_id: str) -> Dict:
        """
        Download video from VideoGen and store in Supabase Storage
        
        Args:
            api_file_id: VideoGen API file ID
            session_id: Story session ID for naming
            
        Returns:
            Dict with success status and permanent URL
        """
        try:
            print(f"Starting video download and storage for apiFileId: {api_file_id}")
            
            # Step 1: Get video URL from VideoGen
            video_url = self._get_video_url_from_videogen(api_file_id)
            
            if not video_url:
                return {'success': False, 'error': 'Video not ready yet or failed to get URL'}
            
            print(f"Got video URL from VideoGen: {video_url[:100]}...")
            
            # Step 2: Download video to memory
            video_data = self._download_video(video_url)
            
            if not video_data:
                return {'success': False, 'error': 'Failed to download video'}
            
            # Step 3: Upload to Supabase Storage
            permanent_url = self._upload_to_supabase(video_data, session_id, api_file_id)
            
            if not permanent_url:
                return {'success': False, 'error': 'Failed to upload to storage'}
            
            print(f"Video successfully stored at: {permanent_url}")
            
            return {
                'success': True,
                'permanent_url': permanent_url,
                'api_file_id': api_file_id
            }
            
        except Exception as e:
            print(f"Error in download_and_store_video: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
    
    def _get_video_url_from_videogen(self, api_file_id: str) -> Optional[str]:
        """Get the actual video URL from VideoGen API"""
        try:
            from services.videogen_service import VideoGenService
            videogen = VideoGenService()
            
            print(f"Polling VideoGen API for video status...")
            
            # Poll until video is ready (with timeout)
            max_attempts = 60  # 5 minutes max (60 attempts * 5 seconds)
            for attempt in range(max_attempts):
                print(f"Attempt {attempt + 1}/{max_attempts}")
                
                result = videogen.get_video_file(api_file_id)
                
                print(f"VideoGen response: {result}")
                
                # Check if video is ready - adjust based on actual API response
                # Common response formats:
                # - {'status': 'completed', 'signedUrl': '...'}
                # - {'signedUrl': '...'}
                # - {'url': '...'}
                
                if result.get('status') == 'completed' and result.get('signedUrl'):
                    return result['signedUrl']
                elif result.get('signedUrl'):
                    return result['signedUrl']
                elif result.get('url'):
                    return result['url']
                elif result.get('status') == 'failed':
                    print(f"Video generation failed: {result}")
                    return None
                
                # Wait before next attempt
                if attempt < max_attempts - 1:
                    time.sleep(5)
            
            print(f"Video not ready after {max_attempts} attempts")
            return None
            
        except Exception as e:
            print(f"Error getting video URL: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _download_video(self, video_url: str) -> Optional[bytes]:
        """Download video from URL to memory"""
        try:
            print(f"Downloading video from: {video_url[:100]}...")
            
            # Stream download to handle large files
            response = requests.get(video_url, stream=True, timeout=300)
            response.raise_for_status()
            
            # Read video data
            video_data = response.content
            
            print(f"Downloaded video: {len(video_data)} bytes ({len(video_data) / (1024 * 1024):.2f} MB)")
            return video_data
            
        except requests.exceptions.Timeout:
            print("Video download timed out")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error downloading video: {str(e)}")
            return None
        except Exception as e:
            print(f"Unexpected error downloading video: {str(e)}")
            return None
    
    def _upload_to_supabase(self, video_data: bytes, session_id: str, api_file_id: str) -> Optional[str]:
        """Upload video to Supabase Storage"""
        try:
            # Create filename with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{session_id}_{timestamp}_{api_file_id}.mp4"
            
            print(f"Uploading to Supabase Storage: {filename}")
            print(f"Bucket: {self.storage_bucket}")
            
            # Upload to Supabase Storage
            result = self.supabase.storage.from_(self.storage_bucket).upload(
                path=filename,
                file=video_data,
                file_options={"content-type": "video/mp4"}
            )
            
            print(f"Upload result: {result}")
            
            # Get public URL
            public_url = self.supabase.storage.from_(self.storage_bucket).get_public_url(filename)
            
            print(f"Video uploaded successfully: {public_url}")
            return public_url
            
        except Exception as e:
            print(f"Error uploading to Supabase: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def check_video_ready(self, api_file_id: str) -> Dict:
        """
        Check if a video is ready without downloading
        
        Args:
            api_file_id: VideoGen API file ID
            
        Returns:
            Dict with status information
        """
        try:
            from services.videogen_service import VideoGenService
            videogen = VideoGenService()
            
            result = videogen.get_video_file(api_file_id)
            
            is_ready = (
                result.get('status') == 'completed' or 
                result.get('signedUrl') is not None or 
                result.get('url') is not None
            )
            
            return {
                'success': True,
                'ready': is_ready,
                'status': result.get('status', 'unknown'),
                'result': result
            }
            
        except Exception as e:
            print(f"Error checking video status: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
