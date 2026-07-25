import requests
import time
import os
import re
from typing import Dict, Optional

class VideoGenService:
    def __init__(self):
        self.api_key = os.getenv('VIDEOGEN_API_KEY')
        self.base_url = 'https://api.videogen.io/v1'
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        # workflowRunId -> {projectId, exportId, downloadUrl}
        self._workflow_cache: Dict[str, Dict] = {}

    def generate_outline_from_prompt(self, prompt: str) -> Dict:
        """
        Deprecated: VideoGen no longer provides a prompt-to-outline API.
        Outline generation is now handled by OpenAI in story_service.
        This stub returns a single-section outline as fallback.
        """
        return {'sections': [{'text': prompt}]}

    def generate_video_from_outline(self, outline: Dict) -> str:
        """
        Generate a video from an outline by combining sections into a script
        and submitting to the script-to-video workflow.

        Args:
            outline (Dict): Outline with 'sections' list, each having 'text'

        Returns:
            str: workflowRunId for polling status
        """
        sections = outline.get('sections', [])
        if not sections:
            raise Exception("No sections found in outline")

        script_parts = [s.get('text', '').strip() for s in sections if s.get('text')]
        script = ' '.join(script_parts)

        if not script:
            raise Exception("Could not extract script text from outline")

        return self.generate_video_from_script(script)

    def generate_video_from_script(self, script: str) -> str:
        """
        Submit a script-to-video workflow to VideoGen.

        Args:
            script (str): The narrative script

        Returns:
            str: workflowRunId for polling status
        """
        try:
            truncated_script = self._truncate_script_for_duration(script)
            url = f"{self.base_url}/workflows/script-to-video"

            print(f"VideoGen API Key: {self.api_key[:10]}..." if self.api_key else "No API key")
            print(f"Script length: {len(truncated_script)} characters")
            print(f"Sending request to VideoGen API: {url}")

            payload = {
                "script": truncated_script,
                "visualStyle": {"type": "STOCK"},
                "quality": "HIGH"
            }

            response = requests.post(url, headers=self.headers, json=payload, timeout=30)

            print(f"VideoGen API Response Status: {response.status_code}")

            if response.status_code not in (200, 202):
                error_detail = response.text
                print(f"VideoGen API Error {response.status_code}: {error_detail}")
                raise Exception(f"VideoGen script-to-video failed with status {response.status_code}: {error_detail}")

            result = response.json()
            print(f"VideoGen API Response: {result}")

            workflow_run_id = result.get('workflowRunId')
            project_id = result.get('projectId')

            if not workflow_run_id:
                raise Exception("No workflowRunId returned from VideoGen API")

            # Cache projectId so we can trigger export later
            self._workflow_cache[workflow_run_id] = {
                'projectId': project_id,
                'exportId': None,
                'downloadUrl': None
            }

            print(f"Workflow started: workflowRunId={workflow_run_id}, projectId={project_id}")
            return workflow_run_id

        except requests.exceptions.Timeout:
            raise Exception("VideoGen script-to-video request timed out")
        except Exception as e:
            raise Exception(f"Video generation error: {str(e)}")

    def get_video_file(self, workflow_run_id: str) -> Dict:
        """
        Poll workflow status and handle the export phase.
        Returns a dict with loadingState, progressPercentage, and apiFileSignedUrl
        to maintain compatibility with existing callers.

        loadingState values: LOADING | FULFILLED | REJECTED
        """
        try:
            cached = self._workflow_cache.get(workflow_run_id, {})

            # Return immediately if we already have a download URL
            if cached.get('downloadUrl'):
                return {
                    'loadingState': 'FULFILLED',
                    'progressPercentage': 100,
                    'apiFileSignedUrl': cached['downloadUrl']
                }

            # Poll the workflow run
            url = f"{self.base_url}/workflows/runs/{workflow_run_id}"
            response = requests.get(url, headers=self.headers, timeout=30)

            if response.status_code != 200:
                raise Exception(f"Get workflow run failed {response.status_code}: {response.text}")

            result = response.json()
            status = result.get('status', '')
            progress = result.get('progressPercentage', 0)
            project_id = result.get('projectId') or cached.get('projectId')

            print(f"Workflow {workflow_run_id} status: {status} ({progress}%)")

            # Keep projectId in cache
            if workflow_run_id not in self._workflow_cache:
                self._workflow_cache[workflow_run_id] = {'projectId': project_id, 'exportId': None, 'downloadUrl': None}
            elif project_id:
                self._workflow_cache[workflow_run_id]['projectId'] = project_id

            if status in ('pending', 'running'):
                return {
                    'loadingState': 'LOADING',
                    'progressPercentage': progress,
                    'apiFileSignedUrl': None
                }

            elif status == 'succeeded':
                # Trigger export if not already started
                export_id = self._workflow_cache[workflow_run_id].get('exportId')
                if not export_id and project_id:
                    export_id = self._trigger_export(project_id)
                    if export_id:
                        self._workflow_cache[workflow_run_id]['exportId'] = export_id

                if not export_id:
                    return {
                        'loadingState': 'LOADING',
                        'progressPercentage': 95,
                        'apiFileSignedUrl': None
                    }

                # Check export status
                export_result = self._get_export_status(project_id, export_id)
                export_status = export_result.get('status', '')

                if export_status == 'succeeded':
                    download_url = export_result.get('downloadUrl')
                    self._workflow_cache[workflow_run_id]['downloadUrl'] = download_url
                    return {
                        'loadingState': 'FULFILLED',
                        'progressPercentage': 100,
                        'apiFileSignedUrl': download_url
                    }
                elif export_status == 'failed':
                    return {
                        'loadingState': 'REJECTED',
                        'progressPercentage': progress,
                        'errorDisplayMessage': 'Export failed',
                        'apiFileSignedUrl': None
                    }
                else:
                    export_progress = export_result.get('progressPercentage', 0)
                    return {
                        'loadingState': 'LOADING',
                        'progressPercentage': max(95, export_progress),
                        'apiFileSignedUrl': None
                    }

            elif status in ('failed', 'cancelled'):
                error_msg = ''
                if isinstance(result.get('error'), dict):
                    error_msg = result['error'].get('message', 'Video generation failed')
                return {
                    'loadingState': 'REJECTED',
                    'progressPercentage': progress,
                    'errorDisplayMessage': error_msg or status,
                    'apiFileSignedUrl': None
                }

            else:
                return {
                    'loadingState': 'LOADING',
                    'progressPercentage': progress,
                    'apiFileSignedUrl': None
                }

        except Exception as e:
            raise Exception(f"Get video status error: {str(e)}")

    def _trigger_export(self, project_id: str) -> Optional[str]:
        """Trigger MP4 export for a completed project."""
        try:
            url = f"{self.base_url}/projects/{project_id}/export"
            payload = {"quality": "HIGH"}
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)

            if response.status_code not in (200, 202):
                print(f"Export trigger failed {response.status_code}: {response.text}")
                return None

            result = response.json()
            export_id = result.get('exportId')
            print(f"Export triggered for project {project_id}: exportId={export_id}")
            return export_id

        except Exception as e:
            print(f"Error triggering export: {e}")
            return None

    def _get_export_status(self, project_id: str, export_id: str) -> Dict:
        """Poll export status, returns dict with 'status' and optionally 'downloadUrl'."""
        try:
            url = f"{self.base_url}/projects/{project_id}/exports/{export_id}"
            response = requests.get(url, headers=self.headers, timeout=30)

            if response.status_code != 200:
                print(f"Get export status failed {response.status_code}: {response.text}")
                return {'status': 'failed'}

            return response.json()

        except Exception as e:
            print(f"Error getting export status: {e}")
            return {'status': 'unknown'}

    def _truncate_script_for_duration(self, script: str, max_words: int = 150) -> str:
        """
        Truncate script to approximately 1 minute of speech (~150 words)
        while preserving complete sentences.
        """
        words = script.split()

        if len(words) <= max_words:
            return script

        sentences = script.split('. ')
        included_sentences = []
        word_count = 0

        for sentence in sentences:
            sentence_words = sentence.split()
            sentence_word_count = len(sentence_words) + 1

            if word_count + sentence_word_count <= max_words:
                included_sentences.append(sentence)
                word_count += sentence_word_count
            else:
                remaining_words = max_words - word_count
                if remaining_words >= 10:
                    partial_sentence = ' '.join(sentence_words[:remaining_words])
                    if partial_sentence.strip():
                        included_sentences.append(partial_sentence)
                break

        if included_sentences:
            truncated_text = '. '.join(included_sentences)
            if not truncated_text.endswith('.'):
                truncated_text += '.'
            return truncated_text

        truncated_words = words[:max_words]
        truncated_text = " ".join(truncated_words)
        last_period = truncated_text.rfind('.')
        if last_period > len(truncated_text) * 0.8:
            return truncated_text[:last_period + 1]
        return truncated_text + "."

    def generate_video_from_storyboard(self, storyboard: str) -> str:
        """
        Generate a video from a storyboard by converting it to a script.

        Args:
            storyboard (str): The storyboard text

        Returns:
            str: videogen:// prefixed workflowRunId
        """
        try:
            print(f"Converting storyboard to script...")
            script = self._convert_storyboard_to_script(storyboard)
            print(f"Script conversion complete, length: {len(script)}")

            workflow_run_id = self.generate_video_from_script(script)
            print(f"Video generation initiated, workflowRunId: {workflow_run_id}")

            return f"videogen://{workflow_run_id}"

        except Exception as e:
            print(f"Storyboard to video generation error: {str(e)}")
            raise Exception(f"Storyboard to video generation error: {str(e)}")

    def _convert_storyboard_to_script(self, storyboard: str) -> str:
        """Convert a storyboard to a narrative script suitable for VideoGen voiceover."""
        lines = storyboard.split('\n')
        scenes = []

        title = None
        for line in lines:
            if '**Storyboard:' in line and '**' in line:
                title_raw = line.replace('**Storyboard:', '').replace('**', '').strip()
                title = self._clean_title_for_voiceover(title_raw)
                break

        current_scene = {}
        for line in lines:
            line = line.strip()

            if (line.startswith('**Scene') or line.startswith('Scene')) and ':' in line:
                if current_scene:
                    scenes.append(current_scene)

                scene_name_match = re.search(r'(\d+): "([^"]+)"', line)
                if not scene_name_match:
                    scene_name_match = re.search(r'(\d+): ([^\n]+)', line)

                if scene_name_match:
                    current_scene = {
                        'number': scene_name_match.group(1),
                        'name': scene_name_match.group(2).strip(),
                        'text_overlay': '',
                        'visual': '',
                        'setting': '',
                        'action': '',
                        'mood': '',
                        'sound': ''
                    }

            elif current_scene:
                if line.startswith('Text overlay:') or line.startswith('**Text overlay:**'):
                    overlay_text = line.replace('Text overlay:', '').replace('**Text overlay:**', '').strip()
                    overlay_text = overlay_text.strip('"').strip()
                    current_scene['text_overlay'] = overlay_text
                elif line.startswith('Visual:') or line.startswith('**Visual:**'):
                    current_scene['visual'] = line.replace('Visual:', '').replace('**Visual:**', '').strip()
                elif line.startswith('• **Visual**:'):
                    current_scene['visual'] = line.replace('• **Visual**:', '').strip()
                elif line.startswith('• **Setting**:') or line.startswith('Setting:'):
                    current_scene['setting'] = line.replace('• **Setting**:', '').replace('Setting:', '').strip()
                elif line.startswith('• **Action**:') or line.startswith('Action:'):
                    current_scene['action'] = line.replace('• **Action**:', '').replace('Action:', '').strip()
                elif line.startswith('• **Mood**:') or line.startswith('Mood:'):
                    current_scene['mood'] = line.replace('• **Mood**:', '').replace('Mood:', '').strip()
                elif line.startswith('• **Sound**:') or line.startswith('Sound:'):
                    current_scene['sound'] = line.replace('• **Sound**:', '').replace('Sound:', '').strip()

        if current_scene:
            scenes.append(current_scene)

        closing_message = None
        for i, line in enumerate(lines):
            if 'Closing Screen:' in line or '**Closing Screen:**' in line:
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith('**') and not next_line.startswith('Text on'):
                        closing_message = next_line.strip('"').strip()
                        if '—' in closing_message:
                            closing_message = closing_message.split('—')[0].strip()
                        break
                break

        if not scenes:
            return self._create_simple_narrative(storyboard)

        return self._create_complete_narrative(scenes, title, closing_message)

    def _create_complete_narrative(self, scenes: list, title: str, closing_message: str = None) -> str:
        target_words = 160

        if len(scenes) <= 3:
            return self._create_detailed_narrative(scenes, title, target_words, closing_message)
        elif len(scenes) <= 6:
            return self._create_balanced_narrative(scenes, title, target_words, closing_message)
        else:
            return self._create_summary_narrative(scenes, title, target_words, closing_message)

    def _create_detailed_narrative(self, scenes: list, title: str, target_words: int, closing_message: str = None) -> str:
        script_parts = []

        if title and len(title.strip()) > 0:
            script_parts.append(f"This is my story of {title.lower()}.")
        else:
            script_parts.append("This is my personal story of transformation.")

        for i, scene in enumerate(scenes):
            scene_narrative = self._create_scene_narrative(scene, i + 1, len(scenes))
            if scene_narrative:
                script_parts.append(scene_narrative)

        if closing_message and len(closing_message.strip()) > 0:
            script_parts.append(closing_message)
        else:
            script_parts.append("This experience taught me that challenges can become opportunities for growth.")

        final_script = " ".join(script_parts)
        final_script = self._convert_to_first_person(final_script)
        final_script = self._basic_clean_text(final_script)

        if len(final_script.split()) > target_words:
            return self._truncate_script_for_duration(final_script, target_words)

        return final_script

    def _create_balanced_narrative(self, scenes: list, title: str, target_words: int, closing_message: str = None) -> str:
        script_parts = []

        if title and len(title.strip()) > 0:
            script_parts.append(f"This is my story of {title.lower()}.")
        else:
            script_parts.append("This is my personal story of transformation.")

        key_scenes = self._select_key_scenes(scenes)

        for i, scene in enumerate(key_scenes):
            scene_narrative = self._create_scene_narrative(scene, i + 1, len(key_scenes))
            if scene_narrative:
                script_parts.append(scene_narrative)

        if closing_message and len(closing_message.strip()) > 0:
            script_parts.append(closing_message)
        else:
            script_parts.append("This experience taught me that challenges can become opportunities for growth.")

        final_script = " ".join(script_parts)
        final_script = self._convert_to_first_person(final_script)
        final_script = self._basic_clean_text(final_script)

        if len(final_script.split()) > target_words:
            return self._truncate_script_for_duration(final_script, target_words)

        return final_script

    def _create_summary_narrative(self, scenes: list, title: str, target_words: int, closing_message: str = None) -> str:
        script_parts = []

        if title and len(title.strip()) > 0:
            script_parts.append(f"This is my story of {title.lower()}.")
        else:
            script_parts.append("This is my personal story of transformation.")

        if len(scenes) >= 3:
            scene_narrative = self._create_scene_narrative(scenes[0], 1, 3)
            if scene_narrative:
                script_parts.append(scene_narrative)

            middle_index = len(scenes) // 2
            scene_narrative = self._create_scene_narrative(scenes[middle_index], 2, 3)
            if scene_narrative:
                script_parts.append(scene_narrative)

            scene_narrative = self._create_scene_narrative(scenes[-1], 3, 3)
            if scene_narrative:
                script_parts.append(scene_narrative)

        if closing_message and len(closing_message.strip()) > 0:
            script_parts.append(closing_message)
        else:
            script_parts.append("This experience taught me that challenges can become opportunities for growth.")

        final_script = " ".join(script_parts)
        final_script = self._convert_to_first_person(final_script)
        final_script = self._basic_clean_text(final_script)

        if len(final_script.split()) > target_words:
            return self._truncate_script_for_duration(final_script, target_words)

        return final_script

    def _select_key_scenes(self, scenes: list) -> list:
        if len(scenes) <= 4:
            return scenes

        key_scenes = [scenes[0]]
        middle_start = len(scenes) // 3
        middle_end = 2 * len(scenes) // 3

        for i in range(middle_start, middle_end):
            if i < len(scenes):
                key_scenes.append(scenes[i])
                if len(key_scenes) >= 3:
                    break

        if len(scenes) > 1:
            key_scenes.append(scenes[-1])

        return key_scenes

    def _create_scene_narrative(self, scene: dict, scene_num: int, total_scenes: int) -> str:
        if scene.get('text_overlay') and len(scene['text_overlay'].strip()) > 0:
            return self._clean_text_for_voiceover(scene['text_overlay'].strip())

        narrative_parts = []

        if scene_num == 1:
            narrative_parts.append("I find myself")
        elif scene_num == total_scenes:
            narrative_parts.append("Finally")
        else:
            narrative_parts.append("Then")

        if scene.get('action'):
            action_desc = self._clean_text_for_voiceover(scene['action'])
            if action_desc and not self._is_visual_description(action_desc):
                if action_desc.startswith('I '):
                    narrative_parts.append(f"{action_desc}")
                else:
                    narrative_parts.append(f"I {action_desc.lower()}")

        if scene.get('mood'):
            mood_desc = self._clean_text_for_voiceover(scene['mood'])
            if mood_desc and not self._is_visual_description(mood_desc):
                narrative_parts.append(f"feeling {mood_desc.lower()}")

        if len(narrative_parts) <= 1:
            narrative_parts.append("in this moment of my story")

        scene_text = " ".join(narrative_parts) + "."
        final_text = self._convert_to_first_person(scene_text)
        return self._clean_text_for_voiceover(final_text)

    def _is_visual_description(self, text: str) -> bool:
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
        return any(keyword in text_lower for keyword in visual_keywords)

    def _convert_to_first_person(self, text: str) -> str:
        conversions = {
            'he ': 'I ', 'she ': 'I ', 'him ': 'me ', 'her ': 'my ', 'his ': 'my ',
            'himself': 'myself', 'herself': 'myself',
            'the person': 'I', 'the individual': 'I', 'the protagonist': 'I', 'the main character': 'I',
            'they ': 'I ', 'them ': 'me ', 'their ': 'my ', 'themselves': 'myself',
            'He ': 'I ', 'She ': 'I ', 'Him ': 'Me ', 'Her ': 'My ', 'His ': 'My ',
            'Himself': 'Myself', 'Herself': 'Myself',
            'They ': 'I ', 'Them ': 'Me ', 'Their ': 'My ', 'Themselves': 'Myself',
        }

        result = text
        for third_person, first_person in conversions.items():
            result = result.replace(third_person, first_person)

        result = re.sub(r'\bI I\b', 'I', result)
        result = re.sub(r'\bme me\b', 'me', result)
        result = re.sub(r'\bmy my\b', 'my', result)
        result = re.sub(r'\btmy\b', 'my', result)
        result = re.sub(r'\bTmy\b', 'This', result)
        result = re.sub(r'\btI\b', 'the', result)
        result = re.sub(r'\bti\b', 'the', result)

        return result

    def _clean_title_for_voiceover(self, title: str) -> str:
        if not title:
            return ""

        cleaned = title.replace('*', '').replace('_', '').replace('`', '')
        cleaned = cleaned.replace('"', '').replace("'", '').replace('[', '').replace(']', '')
        cleaned = re.sub(r'[^\w\s\-]', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        if len(cleaned) < 2 or len(cleaned) > 50:
            return ""

        if cleaned.lower() in ['ti', 't', 'i', 'story', 'storyboard', 'scene', 'ti a story', 'tmy']:
            return ""

        return cleaned

    def _clean_text_for_voiceover(self, text: str) -> str:
        if not text:
            return ""

        cleaned = text.replace('*', '').replace('_', '').replace('`', '')
        cleaned = cleaned.replace('"', '').replace("'", '').replace('[', '').replace(']', '')
        cleaned = cleaned.replace('(', '').replace(')', '').replace('{', '').replace('}', '')
        cleaned = cleaned.replace('•', '').replace('-', ' ').replace('—', ' ').replace('–', ' ')
        cleaned = re.sub(r'[^\w\s\.\,\!\?]', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        if len(cleaned) < 2:
            return ""

        problematic_patterns = ['ti', 't i', 't-i', 't.i', 't/i', 'tmy', 'ti a story', 'tmy is']
        if cleaned.lower().strip() in problematic_patterns:
            return ""

        if 'ti a story' in cleaned.lower() or 'tmy is' in cleaned.lower():
            return ""

        if cleaned.lower() in ['this', 'that', 'these', 'those', 'their', 'there']:
            return cleaned

        return cleaned

    def _basic_clean_text(self, text: str) -> str:
        if not text:
            return ""
        cleaned = re.sub(r'\s+', ' ', text).strip()
        if len(cleaned) < 2:
            return ""
        return cleaned

    def _create_simple_narrative(self, storyboard: str) -> str:
        lines = storyboard.split('\n')
        key_phrases = []

        for line in lines:
            line = line.strip()
            if line and not line.startswith('**') and not line.startswith('•'):
                clean_line = re.sub(r'[^\w\s]', '', line)
                if len(clean_line.split()) > 3:
                    key_phrases.append(clean_line)

        if key_phrases:
            narrative = "This is my personal story of transformation. " + " ".join(key_phrases[:3]) + ". "
            narrative += "It's my journey that shows how challenges can become opportunities for growth and understanding."
        else:
            narrative = "This is my personal story of transformation and growth. A journey that demonstrates the power of resilience and the importance of learning from my experiences."

        return self._convert_to_first_person(narrative)
