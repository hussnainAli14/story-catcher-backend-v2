import requests
import time
import os
import re
from typing import Dict, Optional

class VideoGenService:
    def __init__(self):
        self.api_key = os.getenv('VIDEOGEN_API_KEY', 'b45efa105372a3880ddc2f18464437182597c666')
        self.base_url = 'https://ext.videogen.io/v1'
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def generate_video_from_script(self, script: str) -> str:
        """
        Generate a video from a text script using VideoGen API
        
        Args:
            script (str): The text script to convert to video
            
        Returns:
            str: The apiFileId for the generated video
        """
        try:
            url = f"{self.base_url}/script-to-video"
            
            # Truncate script to ensure max 1 minute duration (approximately 150 words)
            truncated_script = self._truncate_script_for_duration(script)
            
            print(f"VideoGen API Key: {self.api_key[:10]}..." if self.api_key else "No API key")
            print(f"Script length: {len(truncated_script)} characters")
            print(f"Truncated script preview: {truncated_script[:100]}...")
            
            payload = {
                "script": truncated_script,
                "aspectRatio": {
                    "width": 9,
                    "height": 16
                }
            }
            
            print(f"Sending request to VideoGen API: {url}")
            print(f"Payload: {payload}")
            
            # Reduce timeout to prevent worker crashes
            response = requests.post(url, headers=self.headers, json=payload, timeout=15)
            
            print(f"VideoGen API Response Status: {response.status_code}")
            print(f"VideoGen API Response Headers: {dict(response.headers)}")
            
            # Better error handling
            if response.status_code != 200:
                error_detail = response.text
                print(f"VideoGen API Error {response.status_code}: {error_detail}")
                raise Exception(f"VideoGen API request failed with status {response.status_code}: {error_detail}")
            
            response.raise_for_status()
            
            result = response.json()
            print(f"VideoGen API Response: {result}")
            
            api_file_id = result.get('apiFileId')
            
            if not api_file_id:
                raise Exception("No apiFileId returned from VideoGen API")
            
            return api_file_id
            
        except requests.exceptions.Timeout:
            print("VideoGen API request timed out")
            raise Exception("Video generation request timed out")
        except requests.exceptions.RequestException as e:
            print(f"Request exception: {str(e)}")
            raise Exception(f"VideoGen API request failed: {str(e)}")
        except Exception as e:
            print(f"General exception: {str(e)}")
            raise Exception(f"Video generation error: {str(e)}")
    
    def _truncate_script_for_duration(self, script: str, max_words: int = 150) -> str:
        """
        Intelligently truncate script to ensure video duration stays under 1 minute
        while preserving the complete story arc
        
        Args:
            script (str): The original script
            max_words (int): Maximum number of words (default: 150 for ~60 seconds)
            
        Returns:
            str: Truncated script that maintains story completeness
        """
        words = script.split()
        
        if len(words) <= max_words:
            return script
        
        # Split script into sentences to preserve story structure
        sentences = script.split('. ')
        
        # Try to include complete sentences up to word limit
        included_sentences = []
        word_count = 0
        
        for sentence in sentences:
            sentence_words = sentence.split()
            # Add 1 for the period that was removed in split
            sentence_word_count = len(sentence_words) + 1
            
            if word_count + sentence_word_count <= max_words:
                included_sentences.append(sentence)
                word_count += sentence_word_count
            else:
                # If adding this sentence would exceed limit, check if we can fit a partial
                remaining_words = max_words - word_count
                if remaining_words >= 10:  # Only if we have enough words for meaningful content
                    # Try to include a meaningful portion of the sentence
                    partial_sentence = ' '.join(sentence_words[:remaining_words])
                    if partial_sentence.strip():
                        included_sentences.append(partial_sentence)
                break
        
        # Join sentences and ensure proper ending
        if included_sentences:
            truncated_text = '. '.join(included_sentences)
            # Ensure it ends with a period
            if not truncated_text.endswith('.'):
                truncated_text += '.'
            return truncated_text
        
        # Fallback: simple word truncation
        truncated_words = words[:max_words]
        truncated_text = " ".join(truncated_words)
        
        # Find the last complete sentence
        last_period = truncated_text.rfind('.')
        if last_period > len(truncated_text) * 0.8:  # If we have a good sentence ending
            return truncated_text[:last_period + 1]
        
        # If no good sentence ending, add one
        return truncated_text + "."
    
    def get_video_file(self, api_file_id: str) -> Dict:
        """
        Get the video file information using the apiFileId
        
        Args:
            api_file_id (str): The apiFileId from the video generation
            
        Returns:
            Dict: Video file information including signed URL and status
        """
        try:
            url = f"{self.base_url}/get-file"
            params = {
                'apiFileId': api_file_id
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            result = response.json()
            return result
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"VideoGen API request failed: {str(e)}")
        except Exception as e:
            raise Exception(f"Get video file error: {str(e)}")
    
    def generate_video_from_storyboard(self, storyboard: str) -> str:
        """
        Generate a video from a storyboard by converting it to a script
        
        Args:
            storyboard (str): The storyboard text
            
        Returns:
            str: The final video URL or apiFileId for later retrieval
        """
        try:
            print(f"Converting storyboard to script...")
            # Convert storyboard to a script format suitable for VideoGen
            script = self._convert_storyboard_to_script(storyboard)
            print(f"Script conversion complete, length: {len(script)}")
            
            # Generate video
            print(f"Starting video generation...")
            api_file_id = self.generate_video_from_script(script)
            print(f"Video generation initiated, apiFileId: {api_file_id}")
            
            # Return the apiFileId immediately to prevent timeout
            # The frontend will poll for completion
            return f"videogen://{api_file_id}"
            
        except Exception as e:
            print(f"Storyboard to video generation error: {str(e)}")
            raise Exception(f"Storyboard to video generation error: {str(e)}")
    
    def _convert_storyboard_to_script(self, storyboard: str) -> str:
        """
        Convert a storyboard to a narrative script suitable for VideoGen voiceover
        
        Args:
            storyboard (str): The storyboard text
            
        Returns:
            str: A narrative script suitable for video voiceover (optimized for 1-minute duration)
        """
        # Extract the main narrative from the storyboard
        lines = storyboard.split('\n')
        scenes = []
        
        # Extract title if present - with better cleaning
        title = None
        for line in lines:
            if '**Storyboard:' in line and '**' in line:
                # Extract title with better cleaning
                title_raw = line.replace('**Storyboard:', '').replace('**', '').strip()
                # Clean the title by removing special characters and formatting
                title = self._clean_title_for_voiceover(title_raw)
                break
        
        # Parse scenes
        current_scene = {}
        for line in lines:
            line = line.strip()
            
            # Scene header
            if line.startswith('**Scene') and ':' in line:
                if current_scene:  # Save previous scene
                    scenes.append(current_scene)
                
                # Extract scene name
                scene_name_match = re.search(r'(\d+): "([^"]+)"', line)
                if scene_name_match:
                    current_scene = {
                        'number': scene_name_match.group(1),
                        'name': scene_name_match.group(2),
                        'visual': '',
                        'setting': '',
                        'action': '',
                        'mood': ''
                    }
            
            # Extract scene details
            elif current_scene:
                if line.startswith('• **Visual**:'):
                    current_scene['visual'] = line.replace('• **Visual**:', '').strip()
                elif line.startswith('• **Setting**:'):
                    current_scene['setting'] = line.replace('• **Setting**:', '').strip()
                elif line.startswith('• **Action**:'):
                    current_scene['action'] = line.replace('• **Action**:', '').strip()
                elif line.startswith('• **Mood**:'):
                    current_scene['mood'] = line.replace('• **Mood**:', '').strip()
        
        # Add the last scene
        if current_scene:
            scenes.append(current_scene)
        
        # If no structured content found, create a simple narrative
        if not scenes:
            return self._create_simple_narrative(storyboard)
        
        # Create a complete narrative that fits within 1-minute constraint
        return self._create_complete_narrative(scenes, title)
    
    def _create_complete_narrative(self, scenes: list, title: str) -> str:
        """
        Create a complete narrative that tells the full story within 1-minute constraint
        
        Args:
            scenes (list): List of scene dictionaries
            title (str): Story title (cleaned)
            
        Returns:
            str: Complete narrative script optimized for 1-minute duration
        """
        # Target word count for 1-minute video (approximately 150-180 words)
        target_words = 160
        
        # Create different narrative strategies based on number of scenes
        if len(scenes) <= 3:
            # Few scenes - can include more detail per scene
            return self._create_detailed_narrative(scenes, title, target_words)
        elif len(scenes) <= 6:
            # Medium number of scenes - balanced approach
            return self._create_balanced_narrative(scenes, title, target_words)
        else:
            # Many scenes - focus on key story beats
            return self._create_summary_narrative(scenes, title, target_words)
    
    def _create_detailed_narrative(self, scenes: list, title: str, target_words: int) -> str:
        """Create detailed narrative for stories with few scenes - focus on story content"""
        script_parts = []
        
        # Opening - focus on the story, not visual elements
        if title and len(title.strip()) > 0:
            script_parts.append(f"This is my story of {title.lower()}.")
        else:
            script_parts.append("This is my personal story of transformation.")
        
        # Include all scenes with story-focused detail
        for i, scene in enumerate(scenes):
            scene_narrative = self._create_scene_narrative(scene, i + 1, len(scenes))
            script_parts.append(scene_narrative)
        
        # Closing - focus on the lesson learned
        script_parts.append("This experience taught me that challenges can become opportunities for growth.")
        
        # Join and clean
        final_script = self._convert_to_first_person("\n".join(script_parts))
        final_script = self._basic_clean_text(final_script)
        
        # Check word count and adjust if needed
        word_count = len(final_script.split())
        if word_count > target_words:
            return self._truncate_script_for_duration(final_script, target_words)
        
        return final_script
    
    def _create_balanced_narrative(self, scenes: list, title: str, target_words: int) -> str:
        """Create balanced narrative for stories with medium number of scenes"""
        script_parts = []
        
        # Opening
        if title and len(title.strip()) > 0:
            script_parts.append(f"This is my story of {title.lower()}.")
        else:
            script_parts.append("This is my personal story of transformation.")
        
        # Include key scenes with balanced detail
        key_scenes = self._select_key_scenes(scenes)
        
        for i, scene in enumerate(key_scenes):
            scene_narrative = self._create_scene_narrative(scene, i + 1, len(key_scenes))
            script_parts.append(scene_narrative)
        
        # Closing
        script_parts.append("This experience taught me that challenges can become opportunities for growth.")
        
        # Join and clean
        final_script = self._convert_to_first_person("\n".join(script_parts))
        final_script = self._basic_clean_text(final_script)
        
        # Check word count and adjust if needed
        word_count = len(final_script.split())
        if word_count > target_words:
            return self._truncate_script_for_duration(final_script, target_words)
        
        return final_script
    
    def _create_summary_narrative(self, scenes: list, title: str, target_words: int) -> str:
        """Create summary narrative for stories with many scenes"""
        script_parts = []
        
        # Opening
        if title and len(title.strip()) > 0:
            script_parts.append(f"This is my story of {title.lower()}.")
        else:
            script_parts.append("This is my personal story of transformation.")
        
        # Focus on beginning, middle, and end
        if len(scenes) >= 3:
            # Beginning
            if scenes[0]:
                scene_narrative = self._create_scene_narrative(scenes[0], 1, 3)
                script_parts.append(scene_narrative)
            
            # Middle (pick a key scene)
            middle_index = len(scenes) // 2
            if scenes[middle_index]:
                scene_narrative = self._create_scene_narrative(scenes[middle_index], 2, 3)
                script_parts.append(scene_narrative)
            
            # End
            if scenes[-1]:
                scene_narrative = self._create_scene_narrative(scenes[-1], 3, 3)
                script_parts.append(scene_narrative)
        
        # Closing
        script_parts.append("This experience taught me that challenges can become opportunities for growth.")
        
        # Join and clean
        final_script = self._convert_to_first_person("\n".join(script_parts))
        final_script = self._basic_clean_text(final_script)
        
        # Check word count and adjust if needed
        word_count = len(final_script.split())
        if word_count > target_words:
            return self._truncate_script_for_duration(final_script, target_words)
        
        return final_script
    
    def _select_key_scenes(self, scenes: list) -> list:
        """Select the most important scenes for balanced narrative"""
        if len(scenes) <= 4:
            return scenes
        
        # Select beginning, middle, and end scenes
        key_scenes = []
        
        # Beginning
        key_scenes.append(scenes[0])
        
        # Middle scenes (pick 1-2 most important)
        middle_start = len(scenes) // 3
        middle_end = 2 * len(scenes) // 3
        
        for i in range(middle_start, middle_end):
            if i < len(scenes):
                key_scenes.append(scenes[i])
                if len(key_scenes) >= 3:  # Limit to 3 scenes total
                    break
        
        # End
        if len(scenes) > 1:
            key_scenes.append(scenes[-1])
        
        return key_scenes
    
    def _create_scene_narrative(self, scene: dict, scene_num: int, total_scenes: int) -> str:
        """Create a concise first-person narrative description for a single scene - focus on story, not visuals"""
        narrative_parts = []
        
        # Scene transition in first person - keep it brief
        if scene_num == 1:
            narrative_parts.append("I find myself")
        elif scene_num == total_scenes:
            narrative_parts.append("Finally")
        else:
            narrative_parts.append("Then")
        
        # Focus on the story content, not visual descriptions
        # Skip setting descriptions that are just visual environment
        if scene.get('action'):
            action_desc = self._clean_text_for_voiceover(scene['action'])
            if action_desc and not self._is_visual_description(action_desc):
                if action_desc.startswith('I '):
                    narrative_parts.append(f"Here, {action_desc.lower()}")
                else:
                    narrative_parts.append(f"Here, I {action_desc.lower()}")
        
        # Include mood/emotion if it's story-relevant, not visual
        if scene.get('mood'):
            mood_desc = self._clean_text_for_voiceover(scene['mood'])
            if mood_desc and not self._is_visual_description(mood_desc):
                narrative_parts.append(f"feeling {mood_desc.lower()}")
        
        # If no meaningful content, create a simple transition
        if len(narrative_parts) <= 1:
            narrative_parts.append("in this moment of my story")
        
        # Join parts and ensure clean output
        scene_text = ". ".join(narrative_parts) + "."
        
        # Clean the final text and ensure it's first person
        final_text = self._convert_to_first_person(scene_text)
        return self._clean_text_for_voiceover(final_text)
    
    def _is_visual_description(self, text: str) -> bool:
        """Check if text describes visual elements that shouldn't be in voiceover"""
        visual_keywords = [
            'sitting', 'standing', 'looking', 'watching', 'seeing', 'viewing',
            'cozy', 'environment', 'room', 'space', 'setting', 'scene',
            'person', 'individual', 'character', 'figure', 'face',
            'camera', 'shot', 'angle', 'close-up', 'wide', 'focus',
            'lighting', 'shadow', 'color', 'bright', 'dark',
            'background', 'foreground', 'surroundings', 'atmosphere',
            'listening carefully', 'paying attention', 'observing',
            'gesture', 'expression', 'posture', 'position'
        ]
        
        text_lower = text.lower()
        for keyword in visual_keywords:
            if keyword in text_lower:
                return True
        return False
    
    def _convert_to_first_person(self, text: str) -> str:
        """Convert third person pronouns to first person"""
        # Common third person to first person conversions
        conversions = {
            'he ': 'I ',
            'she ': 'I ',
            'him ': 'me ',
            'her ': 'my ',
            'his ': 'my ',
            'himself': 'myself',
            'herself': 'myself',
            'the person': 'I',
            'the individual': 'I',
            'the protagonist': 'I',
            'the main character': 'I',
            'they ': 'I ',
            'them ': 'me ',
            'their ': 'my ',
            'themselves': 'myself',
            'He ': 'I ',
            'She ': 'I ',
            'Him ': 'Me ',
            'Her ': 'My ',
            'His ': 'My ',
            'Himself': 'Myself',
            'Herself': 'Myself',
            'They ': 'I ',
            'Them ': 'Me ',
            'Their ': 'My ',
            'Themselves': 'Myself',
        }
        
        # Apply conversions
        result = text
        for third_person, first_person in conversions.items():
            result = result.replace(third_person, first_person)
        
        # Fix common patterns
        result = re.sub(r'\bI I\b', 'I', result)  # Fix "I I" -> "I"
        result = re.sub(r'\bme me\b', 'me', result)  # Fix "me me" -> "me"
        result = re.sub(r'\bmy my\b', 'my', result)  # Fix "my my" -> "my"
        
        # Fix problematic patterns that might cause "TI" or similar issues
        result = re.sub(r'\btmy\b', 'my', result)  # Fix "tmy" -> "my"
        result = re.sub(r'\bti\b', '', result)  # Remove standalone "ti"
        result = re.sub(r'\bt i\b', '', result)  # Remove "t i"
        
        # Fix "Tmy" -> "This" (common conversion error)
        result = re.sub(r'\bTmy\b', 'This', result)
        result = re.sub(r'\btmy\b', 'this', result)
        
        # Fix "tI" -> "the" (another common conversion error)
        result = re.sub(r'\btI\b', 'the', result)
        result = re.sub(r'\bti\b', 'the', result)
        
        return result
    
    def _clean_title_for_voiceover(self, title: str) -> str:
        """
        Clean a title for safe use in voiceover by removing special characters and formatting
        
        Args:
            title (str): The raw title from storyboard
            
        Returns:
            str: Cleaned title safe for voiceover
        """
        if not title:
            return ""
        
        # Remove common markdown formatting
        cleaned = title.replace('*', '').replace('_', '').replace('`', '')
        
        # Remove quotes and brackets
        cleaned = cleaned.replace('"', '').replace("'", '').replace('[', '').replace(']', '')
        
        # Remove extra whitespace and special characters
        cleaned = re.sub(r'[^\w\s\-]', '', cleaned)
        
        # Clean up multiple spaces
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Ensure it's not empty and has reasonable length
        if len(cleaned) < 2 or len(cleaned) > 50:
            return ""
        
        # Check for common problematic patterns
        if cleaned.lower() in ['ti', 't', 'i', 'story', 'storyboard', 'scene', 'ti a story', 'tmy']:
            return ""
        
        return cleaned
    
    def _clean_text_for_voiceover(self, text: str) -> str:
        """
        Clean text for safe use in voiceover by removing problematic characters and formatting
        
        Args:
            text (str): The raw text to clean
            
        Returns:
            str: Cleaned text safe for voiceover
        """
        if not text:
            return ""
        
        # Remove common markdown formatting
        cleaned = text.replace('*', '').replace('_', '').replace('`', '')
        
        # Remove quotes and brackets
        cleaned = cleaned.replace('"', '').replace("'", '').replace('[', '').replace(']', '')
        cleaned = cleaned.replace('(', '').replace(')', '').replace('{', '').replace('}', '')
        
        # Remove bullet points and special characters
        cleaned = cleaned.replace('•', '').replace('-', ' ').replace('—', ' ').replace('–', ' ')
        
        # Remove extra whitespace and problematic characters
        cleaned = re.sub(r'[^\w\s\.\,\!\?]', ' ', cleaned)
        
        # Clean up multiple spaces
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Ensure it's not empty and has reasonable length
        if len(cleaned) < 2:
            return ""
        
        # Check for common problematic patterns that might cause "TI" or similar issues
        problematic_patterns = ['ti', 't i', 't-i', 't.i', 't/i', 'tmy', 'ti a story', 'tmy is']
        if cleaned.lower().strip() in problematic_patterns:
            return ""
        
        # Additional check for patterns that might appear in the middle of text
        if 'ti a story' in cleaned.lower() or 'tmy is' in cleaned.lower():
            return ""
        
        # Don't filter out legitimate words that contain these patterns
        if cleaned.lower() in ['this', 'that', 'these', 'those', 'their', 'there']:
            return cleaned
        
        return cleaned
    
    def _basic_clean_text(self, text: str) -> str:
        """
        Basic text cleaning for final scripts - less aggressive than _clean_text_for_voiceover
        
        Args:
            text (str): The text to clean
            
        Returns:
            str: Basic cleaned text
        """
        if not text:
            return ""
        
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', text).strip()
        
        # Ensure it's not empty
        if len(cleaned) < 2:
            return ""
        
        return cleaned
    
    def _create_simple_narrative(self, storyboard: str) -> str:
        """Create a simple narrative from unstructured storyboard content"""
        # Extract key phrases and create a basic narrative
        lines = storyboard.split('\n')
        key_phrases = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('**') and not line.startswith('•'):
                # Clean up the line
                clean_line = re.sub(r'[^\w\s]', '', line)
                if len(clean_line.split()) > 3:  # Only meaningful phrases
                    key_phrases.append(clean_line)
        
        if key_phrases:
            narrative = "This is my personal story of transformation. " + " ".join(key_phrases[:3]) + ". "
            narrative += "It's my journey that shows how challenges can become opportunities for growth and understanding."
        else:
            narrative = "This is my personal story of transformation and growth. A journey that demonstrates the power of resilience and the importance of learning from my experiences."
        
        # Convert to first person
        return self._convert_to_first_person(narrative)
