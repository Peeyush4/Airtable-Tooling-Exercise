import time
import logging
from google import genai
from config import CONFIG

class LLMClient:
    """
    Wrapper for Gemini LLM API with retry and error handling.
    """
    def __init__(self, api_key: str = None,
                 model: str = None):
        self.api_key = api_key or CONFIG["GEMINI_API_KEY"]
        self.model = model or CONFIG.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.client = genai.Client(api_key=self.api_key)

    def generate_content(self, prompt: str,
                        max_retries: int = 3,
                        backoff_factor: int = 2,
                        max_tokens: int = 512) -> str:
        """
        Generate content from LLM with exponential backoff.
        Returns response text or None on failure.
        max_tokens limits the output length.
        """
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt
                )
                return response.text
            except Exception as e:
                logging.error(
                    f"LLM API call failed (attempt {attempt + 1}/"
                    f"{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    sleep_time = backoff_factor ** attempt
                    logging.info(
                        f"Retrying in {sleep_time} seconds..."
                    )
                    time.sleep(sleep_time)
                else:
                    return None
        return None

    def with_template(self, template: str,
                     **kwargs) -> str:
        """
        Format a prompt template with keyword arguments.
        """
        return template.format(**kwargs)

# Example usage:
# llm = LLMClient()
# prompt = llm.with_template(PROMPT_TEMPLATE,
#                            json_data=json_str)
# response = llm.generate_content(prompt)
