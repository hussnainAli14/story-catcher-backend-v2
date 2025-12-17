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
        self.max_download_retries = 3  # Number of retry attempts for downloads
    
    def download_and_store_video(self, api_file_id: str, session_id: str) -> Dict:
        """
        Download video from VideoGen and store in Supabase Storage
        
        Args:
            api_file_id: VideoGen API file ID
            session_id: Story session ID for naming
            
        Returns:
            Dict with success status and permanent URL
        """
        temp_file_path = None
        try:
            print(f"Starting video download and storage for apiFileId: {api_file_id}")
            
            # Step 1: Get video URL from VideoGen
            video_url = self._get_video_url_from_videogen(api_file_id)
            
            if not video_url:
                return {'success': False, 'error': 'Video not ready yet or failed to get URL'}
            
            print(f"Got video URL from VideoGen: {video_url[:100]}...")
            
            # Step 2: Download video to temporary file (streamed)
            temp_file_path = self._download_video_to_temp_file(video_url)
            
            if not temp_file_path:
                return {'success': False, 'error': 'Failed to download video'}
            
            # Step 3: Upload to Supabase Storage from file
            upload_result = self._upload_file_to_supabase(temp_file_path, session_id, api_file_id)
            
            if not upload_result:
                return {'success': False, 'error': 'Failed to upload to storage'}
            
            # Extract URLs
            if isinstance(upload_result, dict):
                permanent_url = upload_result.get('public_url')
                download_url = upload_result.get('download_url')
            else:
                # Fallback for legacy behavior
                permanent_url = upload_result
                download_url = upload_result
            
            print(f"Video successfully stored at: {permanent_url}")
            
            return {
                'success': True,
                'permanent_url': permanent_url,
                'download_url': download_url,
                'api_file_id': api_file_id
            }
            
        except Exception as e:
            print(f"Error in download_and_store_video: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    print(f"Cleaned up temporary file: {temp_file_path}")
                except Exception as e:
                    print(f"Error cleaning up temporary file: {e}")
    
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
                
                # Check if loadingState is FULFILLED (actual VideoGen response format)
                if result.get('loadingState') == 'FULFILLED' and result.get('apiFileSignedUrl'):
                    print(f"✅ Video is ready! Loading state: FULFILLED")
                    return result['apiFileSignedUrl']
                
                # Relaxed check: if we have a signed URL, use it (even if status isn't explicitly FULFILLED yet)
                if result.get('apiFileSignedUrl'):
                    print(f"✅ Video URL found (relaxed check): {result.get('apiFileSignedUrl')[:50]}...")
                    return result['apiFileSignedUrl']
                
                # Fallback checks for other possible response formats
                if result.get('status') == 'completed' and result.get('signedUrl'):
                    return result['signedUrl']
                elif result.get('signedUrl'):
                    return result['signedUrl']
                elif result.get('apiFileSignedUrl'):
                    return result['apiFileSignedUrl']
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
    
    def _download_video_to_temp_file(self, video_url: str) -> Optional[str]:
        """Download video from URL to a temporary file with retry logic"""
        import tempfile
        
        for attempt in range(self.max_download_retries):
            temp_file = None
            try:
                print(f"Downloading video from: {video_url[:100]}... (Attempt {attempt + 1}/{self.max_download_retries})")
                
                # Create a temporary file
                temp_fd, temp_path = tempfile.mkstemp(suffix='.mp4')
                os.close(temp_fd)  # Close the file descriptor, we'll open it with requests
                
                # Stream download to handle large files
                with requests.get(video_url, stream=True, timeout=300) as response:
                    response.raise_for_status()
                    
                    # Write to file in chunks
                    with open(temp_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                
                file_size = os.path.getsize(temp_path)
                print(f"Downloaded video to {temp_path}: {file_size} bytes ({file_size / (1024 * 1024):.2f} MB)")
                return temp_path
                
            except requests.exceptions.Timeout:
                print(f"Video download timed out (attempt {attempt + 1})")
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
                    
                if attempt < self.max_download_retries - 1:
                    wait_time = (attempt + 1) * 5  # Exponential backoff
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print("Max retries reached. Download failed.")
                    return None
            except Exception as e:
                print(f"Error downloading video: {str(e)} (attempt {attempt + 1})")
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
                    
                if attempt < self.max_download_retries - 1:
                    wait_time = (attempt + 1) * 5
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print("Max retries reached. Download failed.")
                    return None
        
        return None
    
    def _upload_file_to_supabase(self, file_path: str, session_id: str, api_file_id: str) -> Optional[str]:
        """Upload video file to Supabase Storage"""
        try:
            # Create filename with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{session_id}_{timestamp}_{api_file_id}.mp4"
            
            file_size = os.path.getsize(file_path)
            print(f"Uploading to Supabase Storage: {filename}")
            print(f"Bucket: {self.storage_bucket}")
            print(f"File size: {file_size / (1024 * 1024):.2f} MB")
            
            # Check if file already exists
            try:
                existing_files = self.supabase.storage.from_(self.storage_bucket).list()
                if any(f.get('name') == filename for f in existing_files):
                    print(f"File {filename} already exists, getting existing URL")
                    public_url = self.supabase.storage.from_(self.storage_bucket).get_public_url(filename)
                    return public_url
            except Exception as e:
                print(f"Could not check for existing files: {str(e)}")
                # Continue with upload anyway
            
            # Upload to Supabase Storage
            try:
                with open(file_path, 'rb') as f:
                    result = self.supabase.storage.from_(self.storage_bucket).upload(
                        path=filename,
                        file=f,
                        file_options={"content-type": "video/mp4", "upsert": "true"}
                    )
                print(f"Upload result: {result}")
            except Exception as upload_error:
                print(f"Upload error: {str(upload_error)}")
                # If upload fails due to duplicate, try to get the existing URL
                if "already exists" in str(upload_error).lower() or "duplicate" in str(upload_error).lower():
                    print("File already exists, retrieving existing URL")
                else:
                    raise
            
            # Get public URL
            public_url = self.supabase.storage.from_(self.storage_bucket).get_public_url(filename)
            
            print(f"Video uploaded successfully: {public_url}")
            
            # Generate a signed URL specifically for downloading (valid for 1 hour)
            try:
                signed_url_response = self.supabase.storage.from_(self.storage_bucket).create_signed_url(
                    filename, 
                    3600, 
                    {'download': True}
                )
                # Handle different response formats from Supabase SDK
                if isinstance(signed_url_response, dict) and 'signedURL' in signed_url_response:
                    download_url = signed_url_response['signedURL']
                elif isinstance(signed_url_response, str):
                    download_url = signed_url_response
                else:
                    # Fallback if response format is unexpected
                    download_url = public_url
                    print(f"Unexpected signed URL response format: {signed_url_response}")
            except Exception as e:
                print(f"Error generating signed download URL: {e}")
                download_url = public_url

            return {
                'public_url': public_url,
                'download_url': download_url
            }
            
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
