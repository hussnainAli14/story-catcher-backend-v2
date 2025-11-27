import os
from supabase import create_client, Client

class PromptService:
    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        self.client: Client = None
        self.prompt_key = 'videogen_outline_prompt'
        
        if self.supabase_url and self.supabase_key:
            self.client = create_client(self.supabase_url, self.supabase_key)
        else:
            print("Warning: Supabase credentials not found. PromptService will not work.")

    def get_prompt(self) -> str:
        """
        Fetch the prompt from Supabase.
        Returns None if not found or error.
        """
        if not self.client:
            return None
            
        try:
            response = self.client.table('system_prompts')\
                .select('content')\
                .eq('key', self.prompt_key)\
                .execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]['content']
            return None
            
        except Exception as e:
            print(f"Error fetching prompt from Supabase: {e}")
            return None

    def update_prompt(self, content: str) -> bool:
        """
        Update the prompt in Supabase.
        """
        if not self.client:
            return False
            
        try:
            # We use upsert to ensure it exists
            data = {
                'key': self.prompt_key,
                'content': content,
                'updated_at': 'now()'
            }
            
            self.client.table('system_prompts').upsert(data, on_conflict='key').execute()
            return True
            
        except Exception as e:
            print(f"Error updating prompt in Supabase: {e}")
            return False
