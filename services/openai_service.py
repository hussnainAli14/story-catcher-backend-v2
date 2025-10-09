import openai
import os
import re
import time
import requests
import base64
from typing import List, Dict, Optional
from .videogen_service import VideoGenService

class OpenAIService:
    def __init__(self):
        self.client = None
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.videogen_service = VideoGenService()
    
    def _get_client(self):
        """Lazy initialization of OpenAI client"""
        if self.client is None:
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY environment variable is not set")
            self.client = openai.OpenAI(api_key=self.api_key)
        return self.client
    
    def generate_story_from_formatted_answers(self, formatted_answers: List[Dict]) -> str:
        """
        Generate a visual storyboard based on properly formatted answers
        """
        try:
            print(f"Starting story generation with {len(formatted_answers)} answers")
            
            if not formatted_answers or len(formatted_answers) < 4:
                error_msg = f"I need all four answers to generate your storyboard. Please complete the interview first. Received {len(formatted_answers) if formatted_answers else 0} answers."
                print(error_msg)
                return error_msg
            
            # Format the answers for the prompt
            formatted_text = self._format_formatted_answers_for_prompt(formatted_answers)
            
            # Debug: Print the formatted answers to see what's being passed
            print(f"DEBUG: Formatted answers for storyboard generation:")
            print(formatted_text)
            print("=" * 50)
            
            # Create the prompt for storyboard generation
            prompt = self._create_storyboard_prompt(formatted_text)
            print(f"Prompt length: {len(prompt)} characters")
            
            # Start asynchronous storyboard generation
            print("Starting asynchronous storyboard generation")
            import threading
            import time
            
            # Store the session ID for background processing
            session_id = formatted_answers[0].get('session_id', 'unknown')
            
            # Start background thread for OpenAI API call
            def generate_storyboard_async():
                try:
                    print(f"Background thread: Starting OpenAI API call for session {session_id}")
                    response = self._get_client().chat.completions.create(
                        model="gpt-4o-mini",  # Faster model
                        messages=[
                            {
                                "role": "system",
                                "content": """You are an empathetic interviewer and creative assistant. Your role is to:

1. Create a safe, supportive space for users to share personal stories
2. Ask thoughtful questions that encourage emotional depth
3. Validate and acknowledge the user's experience throughout
4. Collaborate on creative decisions rather than making them alone
5. Maintain a compassionate, encouraging tone at all times

Your tone should be:
- Warm and understanding
- Patient and non-judgmental  
- Encouraging and supportive
- Collaborative rather than directive

When creating storyboards, honor the user's emotional journey and create visuals that respect their experience. Use ONLY their specific details and collaborate with them on creative decisions.

Format storyboards as:

**Storyboard: "[Title]" – [Subtitle]**

**Scene 1: "[Scene Name]"**
• **Visual**: [description]
• **Setting**: [description]
• **Mood**: [description]
• **Sound**: [description]
• **Transition**: [description]

Create 4-5 scenes total that honor their emotional journey."""
                            },
                            {
                                "role": "user",
                                "content": prompt[:2000]  # Truncate for speed
                            }
                        ],
                        max_tokens=800,
                        temperature=0.7,
                        timeout=20
                    )
                    
                    result = response.choices[0].message.content.strip()
                    print(f"Background thread: OpenAI API completed for session {session_id}")
                    
                    # Store the result in a global cache (in production, use Redis or database)
                    if not hasattr(self, '_storyboard_cache'):
                        self._storyboard_cache = {}
                    self._storyboard_cache[session_id] = {
                        'status': 'completed',
                        'storyboard': result,
                        'timestamp': time.time()
                    }
                    
                except Exception as e:
                    print(f"Background thread: OpenAI API failed for session {session_id}: {str(e)}")
                    # Store fallback result
                    if not hasattr(self, '_storyboard_cache'):
                        self._storyboard_cache = {}
                    self._storyboard_cache[session_id] = {
                        'status': 'completed',
                        'storyboard': self._create_fallback_storyboard(formatted_answers),
                        'timestamp': time.time()
                    }
            
            # Start the background thread
            thread = threading.Thread(target=generate_storyboard_async)
            thread.daemon = True
            thread.start()
            
            # Initialize cache entry
            if not hasattr(self, '_storyboard_cache'):
                self._storyboard_cache = {}
            self._storyboard_cache[session_id] = {
                'status': 'generating',
                'storyboard': None,
                'timestamp': time.time()
            }
            
            # Return immediately with generating status
            return "STORYBOARD_GENERATING"
            
        except Exception as e:
            error_msg = f"I apologize, but I encountered an error while generating your storyboard: {str(e)}"
            print(f"OpenAI service error: {error_msg}")
            print(f"Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            # Return fallback storyboard instead of error message
            return self._create_fallback_storyboard(formatted_answers)
    
    def get_storyboard_status(self, session_id: str) -> dict:
        """Get the status of storyboard generation for a session"""
        if not hasattr(self, '_storyboard_cache'):
            return {'status': 'not_found'}
        
        if session_id not in self._storyboard_cache:
            return {'status': 'not_found'}
        
        return self._storyboard_cache[session_id]
    
    def _format_formatted_answers_for_prompt(self, formatted_answers: List[Dict]) -> str:
        """Format properly formatted answers for the story generation prompt"""
        formatted = ""
        for i, answer in enumerate(formatted_answers, 1):
            formatted += f"Question {i}: {answer.get('question', '')}\n"
            formatted += f"Answer: {answer.get('answer', '')}\n\n"
        return formatted
    
    def _create_storyboard_prompt(self, formatted_answers: str) -> str:
        """Create the prompt for storyboard generation"""
        return f"""
I've been honored to listen to this person's deeply personal story. Now I need to help them transform their experience into a visual narrative that honors their emotional journey.

Here are their responses to our thoughtful questions:

{formatted_answers}

**My Role as an Empathetic Creative Assistant:**
I will create a storyboard that:
- Honors their emotional journey with sensitivity and respect
- Uses ONLY their specific details and experiences
- Creates visuals that feel authentic to their story
- Maintains the emotional truth of their experience
- Offers creative collaboration rather than imposing my own vision

**Storyboard Creation Guidelines:**
- Focus on their actual experience, not generic scenarios
- Respect the emotional weight of their story
- Create scenes that feel true to their experience
- Use their exact locations, actions, and feelings
- Honor both the difficulty and the growth in their journey

**Format Requirements:**

**Storyboard: "[Title]" – [Subtitle]**

**Scene 1: "[Scene Name]"**
• **Visual**: [Detailed visual description based on their answer]
• **Setting**: [Location and environment details from their story]
• **Mood**: [Emotional tone and atmosphere from their experience]
• **Sound**: [Audio suggestions relevant to their scene]
• **Transition**: [How this scene connects to the next]

**Scene 2: "[Scene Name]"**
• **Visual**: [Detailed visual description based on their answer]
• **Action**: [Key actions and movements from their story]
• **Mood**: [Emotional tone and atmosphere from their experience]
• **Sound**: [Audio suggestions relevant to their scene]
• **Transition**: [How this scene connects to the next]

**Scene 3: "[Scene Name]"**
• **Visual**: [Detailed visual description based on their answer]
• **Setting**: [Location and environment details from their story]
• **Mood**: [Emotional tone and atmosphere from their experience]
• **Sound**: [Audio suggestions relevant to their scene]
• **Transition**: [How this scene connects to the next]

**Scene 4: "[Scene Name]"**
• **Visual**: [Detailed visual description based on their answer]
• **Action**: [Key actions and movements from their story]
• **Mood**: [Emotional tone and atmosphere from their experience]
• **Sound**: [Audio suggestions relevant to their scene]
• **Transition**: [How this scene connects to the next]

**Scene 5: "[Scene Name]"**
• **Visual**: [Detailed visual description based on their answer]
• **Setting**: [Location and environment details from their story]
• **Mood**: [Emotional tone and atmosphere from their experience]
• **Sound**: [Audio suggestions relevant to their scene]
• **Transition**: [How this scene connects to the next]

**Scene 6: "[Scene Name]"**
• **Visual**: [Detailed visual description based on their answer]
• **Action**: [Key actions and movements from their story]
• **Mood**: [Emotional tone and atmosphere from their experience]
• **Sound**: [Audio suggestions relevant to their scene]
• **Transition**: [Conclusion or final transition]

**Creative Collaboration Approach:**
- Use bullet points (•) for each element
- Keep descriptions vivid but respectful
- Focus on visual storytelling that honors their specific experience
- Include authentic details from their story
- Create emotional resonance through mood and sound
- Make it suitable for video/animation production
- Ensure the storyboard feels like a collaborative creation, not an imposed vision

**Final Requirements:**
- Create 4-6 scenes total that tell their complete story
- Each scene should have Visual, Setting/Action, Mood, Sound, and Transition
- Use ONLY the person's specific experience details from their answers
- Make it visually compelling and emotionally resonant based on their real story
- Format exactly as shown above with proper spacing and bullet points
- Honor their courage in sharing this story by creating something beautiful and meaningful
"""

    def generate_video_from_storyboard(self, storyboard: str) -> str:
        """Generate a video from a storyboard using VideoGen API"""
        try:
            if not storyboard:
                raise Exception("No storyboard provided for video generation")
            
            print(f"Starting video generation from storyboard...")
            print(f"Storyboard length: {len(storyboard)} characters")
            
            # Use VideoGen service to generate video from storyboard
            video_url = self.videogen_service.generate_video_from_storyboard(storyboard)
            
            print(f"Video generation completed successfully: {video_url}")
            return video_url
            
        except Exception as e:
            print(f"Video generation error in OpenAI service: {str(e)}")
            raise Exception(f"Video generation error: {str(e)}")
    
    def generate_next_question(self, conversation_context: str, question_number: int, conversation_history: List[Dict]) -> Optional[Dict]:
        """Generate the next question and reaction using GPT based on conversation history"""
        try:
            print(f"Generating question {question_number} with GPT...")
            
            # Build the prompt for next question generation
            prompt = self._create_next_question_prompt(conversation_context, question_number, conversation_history)
            
            response = self._get_client().chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """This GPT acts as an empathetic interviewer and creative assistant. It asks users four thoughtful questions about a life-changing moment in their life and uses their responses to create a visual storyboard suitable for a short video. The GPT's tone is compassionate, supportive, and encouraging, helping users feel comfortable reflecting on personal and emotional memories. It guides users step-by-step through the storytelling process while subtly encouraging clarity, emotion, and narrative flow.

After gathering the four answers, it synthesizes them into a simple but powerful storyboard layout that includes suggested visuals, scene structure, and transitions. The GPT offers creative options for tone, mood, and pacing while remaining sensitive to the emotional nature of the stories shared. It does not judge or analyze the user's experience but instead uplifts their voice by turning it into a meaningful visual narrative.

If users are unsure how to begin, the GPT gently prompts them with sample questions or examples of life-changing moments. If needed, it offers ideas for how to adapt the storyboard into formats like short films, animated clips, or presentation slides.

IMPORTANT: You are conducting a 4-question interview. For each response, you must:
1. Provide a personalized, empathetic reaction to their specific answer
2. Ask the next question that naturally builds on their story
3. Maintain a warm, supportive tone throughout
4. Make each question feel like a natural conversation, not a template

Format your response as:
REACTION: [Your personalized empathetic reaction to their specific answer]
QUESTION: [The next question that builds naturally on their story]"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=400,
                temperature=0.8,
                timeout=20
            )
            
            result = response.choices[0].message.content.strip()
            print(f"GPT response for question {question_number}: {result}")
            
            # Parse the response to extract reaction and question
            return self._parse_gpt_response(result, question_number)
            
        except Exception as e:
            print(f"Error generating next question with GPT: {e}")
            # Don't use fallback - return None to indicate failure
            # The calling function should handle this error appropriately
            return None

    def _create_next_question_prompt(self, conversation_context: str, question_number: int, conversation_history: List[Dict]) -> str:
        """Create the prompt for generating the next question - completely dynamic, no templates"""
        
        return f"""I'm conducting a 4-question interview about a life-changing moment. Here's our conversation so far:

{conversation_context}

I need to generate Question {question_number} for this interview.

**Your Task:**
1. First, provide a personalized, empathetic reaction to their most recent answer
2. Then, ask the next question that naturally builds on their story
3. Make it feel like a natural conversation, not a template
4. Be specific to their experience, not generic

**Remember:**
- React to their specific story, not generic templates
- Ask questions that build naturally on what they've shared
- Maintain a warm, supportive tone
- Make each question feel personal and connected to their experience
- No predefined responses - be genuinely responsive to their story

Please provide the reaction and question now:"""

    def _parse_gpt_response(self, response: str, question_number: int) -> Dict:
        """Parse GPT response to extract reaction and question"""
        try:
            lines = response.split('\n')
            reaction = ""
            question = ""
            
            for line in lines:
                line = line.strip()
                if line.startswith('REACTION:'):
                    reaction = line.replace('REACTION:', '').strip()
                elif line.startswith('QUESTION:'):
                    question = line.replace('QUESTION:', '').strip()
                elif line.startswith('**REACTION:**'):
                    reaction = line.replace('**REACTION:**', '').strip()
                elif line.startswith('**QUESTION:**'):
                    question = line.replace('**QUESTION:**', '').strip()
            
            # If parsing failed, try to split by common patterns
            if not reaction or not question:
                if 'REACTION:' in response and 'QUESTION:' in response:
                    parts = response.split('QUESTION:')
                    if len(parts) >= 2:
                        reaction = parts[0].replace('REACTION:', '').strip()
                        question = parts[1].strip()
                elif '**REACTION:**' in response and '**QUESTION:**' in response:
                    parts = response.split('**QUESTION:**')
                    if len(parts) >= 2:
                        reaction = parts[0].replace('**REACTION:**', '').strip()
                        question = parts[1].strip()
            
            # Fallback: if still no clear separation, treat first part as reaction, second as question
            if not reaction or not question:
                sentences = response.split('.')
                if len(sentences) >= 2:
                    reaction = sentences[0].strip() + '.'
                    question = '.'.join(sentences[1:]).strip()
                else:
                    # If we can't parse it, return None to indicate failure
                    print(f"Could not parse GPT response into reaction and question: {response}")
                    return None
            
            return {
                "reaction": reaction,
                "question": question
            }
            
        except Exception as e:
            print(f"Error parsing GPT response: {e}")
            # Return None to indicate parsing failure
            return None


    def _create_fallback_storyboard(self, formatted_answers: List[Dict]) -> str:
        """Create a simple fallback storyboard when OpenAI fails"""
        try:
            if not formatted_answers or len(formatted_answers) < 4:
                return """**Storyboard: "Your Personal Journey" – A Story of Courage and Growth**

**Scene 1: "The Beginning"**
• **Visual**: A person in their everyday environment, unaware of what's to come
• **Setting**: The place where their story began, filled with ordinary moments
• **Mood**: Peaceful, perhaps unaware of the transformation ahead
• **Sound**: Gentle, ambient daily sounds
• **Transition**: Focus shifts to the moment of change

**Scene 2: "The Moment"**
• **Visual**: The pivotal moment of realization or change, captured with sensitivity
• **Action**: The key action or decision that changed everything
• **Mood**: Intense, transformative, but handled with care
• **Sound**: Music that builds tension and release, honoring the emotion
• **Transition**: The aftermath begins with gentleness

**Scene 3: "The Processing"**
• **Visual**: The person processing what happened, showing their humanity
• **Setting**: A reflective space, perhaps alone with their thoughts
• **Mood**: Contemplative, processing, showing the courage to feel
• **Sound**: Quieter, more introspective, honoring their journey
• **Transition**: Moving toward understanding and growth

**Scene 4: "The Transformation"**
• **Visual**: The person showing their growth and new understanding
• **Action**: Applying their new wisdom with grace and strength
• **Mood**: Confident, peaceful, or determined - honoring their resilience
• **Sound**: Uplifting, hopeful music that celebrates their journey
• **Transition**: Integration into their new way of being

**Scene 5: "The New Normal"**
• **Visual**: The person in their transformed state, living their truth
• **Setting**: Their daily life, but changed and more authentic
• **Mood**: Content, aligned, at peace with their journey
• **Sound**: Warm, satisfying tones that honor their courage
• **Transition**: The story continues with wisdom and grace

**Scene 6: "The Impact"**
• **Visual**: How this change affects others around them, spreading wisdom
• **Action**: Sharing their story or living their values with others
• **Mood**: Inspiring, meaningful, showing the ripple effect of courage
• **Sound**: Full, rich, complete - honoring the full circle of growth
• **Transition**: The journey continues, inspiring others"""
            
            # Extract key themes from answers
            first_answer = formatted_answers[0].get('answer', '')
            last_answer = formatted_answers[-1].get('answer', '')
            
            # Create a simple storyboard based on the answers
            title = "Personal Transformation"
            if "listening" in first_answer.lower():
                title = "The Power of Listening"
            elif "change" in first_answer.lower():
                title = "A Moment of Change"
            elif "realized" in first_answer.lower():
                title = "A Realization"
            
            return f"""**Storyboard: "{title}" – A Journey of Courage and Growth**

**Scene 1: "The Beginning"**
• **Visual**: A person in their everyday environment, living their normal life
• **Setting**: The place where their story began, filled with familiar moments
• **Mood**: Ordinary, perhaps unaware of the transformation ahead
• **Sound**: Ambient daily sounds, the soundtrack of their life
• **Transition**: Focus shifts to the moment of change

**Scene 2: "The Moment"**
• **Visual**: The pivotal moment of realization or change, captured with sensitivity
• **Action**: The key action or decision that changed everything
• **Mood**: Intense, transformative, handled with care and respect
• **Sound**: Music that builds tension and release, honoring the emotion
• **Transition**: The aftermath begins with gentleness

**Scene 3: "The Processing"**
• **Visual**: The person processing what happened, showing their humanity
• **Setting**: A reflective space, perhaps alone with their thoughts
• **Mood**: Contemplative, processing, showing the courage to feel
• **Sound**: Quieter, more introspective, honoring their journey
• **Transition**: Moving toward understanding and growth

**Scene 4: "The Transformation"**
• **Visual**: The person showing their growth and new understanding
• **Action**: Applying their new wisdom with grace and strength
• **Mood**: Confident, peaceful, or determined - honoring their resilience
• **Sound**: Uplifting, hopeful music that celebrates their journey
• **Transition**: Integration into their new way of being

**Scene 5: "The New Normal"**
• **Visual**: The person in their transformed state, living their truth
• **Setting**: Their daily life, but changed and more authentic
• **Mood**: Content, aligned, at peace with their journey
• **Sound**: Warm, satisfying tones that honor their courage
• **Transition**: The story continues with wisdom and grace

**Scene 6: "The Impact"**
• **Visual**: How this change affects others around them, spreading wisdom
• **Action**: Sharing their story or living their values with others
• **Mood**: Inspiring, meaningful, showing the ripple effect of courage
• **Sound**: Full, rich, complete - honoring the full circle of growth
• **Transition**: The journey continues, inspiring others"""
            
        except Exception as e:
            print(f"Error creating fallback storyboard: {e}")
            return """**Storyboard: "Your Courageous Story" – A Personal Journey of Growth**

**Scene 1: "The Beginning"**
• **Visual**: Your story begins here, in the place where it all started
• **Setting**: The environment where your journey began
• **Mood**: Setting the stage for transformation with gentleness
• **Sound**: The sounds of your experience, honored and respected
• **Transition**: Moving toward the moment with care

**Scene 2: "The Moment"**
• **Visual**: The pivotal experience, captured with sensitivity and respect
• **Action**: The key moment of change, honored for its significance
• **Mood**: The emotions of that time, handled with compassion
• **Sound**: The soundtrack of your story, respecting its weight
• **Transition**: Processing what happened with gentleness

**Scene 3: "The Growth"**
• **Visual**: How you transformed, showing your strength and resilience
• **Setting**: Your new reality, built with courage and wisdom
• **Mood**: The peace of understanding, earned through your journey
• **Sound**: Music of growth and wisdom, celebrating your courage
• **Transition**: Living your new truth with grace and authenticity"""
