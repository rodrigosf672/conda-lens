import os
from typing import Optional

def explain_error(error_log: str, api_key: Optional[str] = None) -> str:
    """
    Uses an LLM to explain a conda solver error.
    """
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")
    
    if not api_key:
        return "Error: OPENAI_API_KEY not found. Please set it to use the explainer."

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        prompt = f"""
        You are an expert Python environment debugger. 
        Explain the following Conda/Pip error in simple terms and suggest a fix.
        
        Error Log:
        {error_log[:2000]}
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        return response.choices[0].message.content
    except ImportError:
        return "Error: 'openai' package not installed."
    except Exception as e:
        return f"Error calling LLM: {str(e)}"
