# Story Catcher Backend V2

This is the second version of the Story Catcher backend with updated GPT prompt formatting.

## Environment Variables

Create a `.env` file with the following variables:

```
SECRET_KEY=your-secret-key
OPENAI_API_KEY=your-openai-api-key
VIDEOGEN_API_KEY=your-videogen-api-key
SUPABASE_URL=your-supabase-url
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
```

## Installation

```bash
pip install -r requirements.txt
```

## Running

```bash
python app.py
```

## API Endpoints

- `/api/health` - Health check
- `/api/story/start` - Start a new story session
- `/api/story/answer` - Submit an answer
- `/api/story/current-question/<session_id>` - Get current question
- `/api/story/session/<session_id>` - Get session status
- `/api/video/generate-from-session` - Generate video from session
- `/api/video/generate-from-storyboard` - Generate video from storyboard
- `/api/video/save-to-supabase` - Save video to Supabase
- `/api/video/status/<api_file_id>` - Check video status
- `/api/storyboard/status/<session_id>` - Check storyboard status
