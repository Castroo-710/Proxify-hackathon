import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

# Configuration
API_KEY = os.getenv("GOOGLE_API_KEY") # REPLACE WITH YOUR API KEY
PROJECT_ID = "your-project-id" # REPLACE WITH YOUR PROJECT ID
LOCATION = "us-central1" # REPLACE WITH YOUR LOCATION IF NEEDED
MODEL_ID = "gemini-2.5-flash" 

def load_prompt_config(filepath="prompt.json"):
    """Loads the prompt configuration from a JSON file."""
    # Use absolute path relative to the script file to ensure it's found
    script_dir = os.path.dirname(os.path.abspath(__file__))
    abs_filepath = os.path.join(script_dir, filepath)
    
    try:
        with open(abs_filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {abs_filepath} not found.")
        return None

def generate_candidate_summary(candidate_data, prompt_config):
    """
    Generates a summary for a candidate using the Google GenAI SDK.
    
    Args:
        candidate_data (str): The text content of the candidate's profile/CV.
        prompt_config (dict): The prompt configuration loaded from JSON.
    """
    
    # Prepare the system instruction
    system_instruction = f"""
    You are acting as an {prompt_config['system_instruction']['role']}.
    Task: {prompt_config['system_instruction']['task']}
    Tone: {prompt_config['system_instruction']['tone']}
    
    Style Guide:
    - Follow this example structure: "{prompt_config['system_instruction']['style_guide']['example']}"
    - Requirements:
    {chr(10).join(['  * ' + r for r in prompt_config['system_instruction']['style_guide']['requirements']])}
    
    Analyze the provided candidate data and generate a summary.
    """

    # Initialize the client
    client = genai.Client(
        api_key=API_KEY
    )

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7, # Adjust for creativity vs consistency
            ),
            contents=[candidate_data]
        )
        
        return response.text

    except Exception as e:
        return f"Error generating summary: {str(e)}"

if __name__ == "__main__":
    # Example Usage
    config = load_prompt_config()
    
    if config:
        # Simulated Candidate Data (would normally come from a file)
        sample_candidate = """
        Candidate: Bob Smith
        Role Applied For: Marketing Manager
        Experience: 8 years in digital marketing, leading teams of 10+.
        Skills: SEO, Google Analytics, Content Strategy, Team Leadership.
        """
        
        print("--- Generating Summary for Bob Smith ---")
        summary = generate_candidate_summary(sample_candidate, config)
        print(summary)
