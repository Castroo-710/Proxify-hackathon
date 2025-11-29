from flask import Flask, request, jsonify, send_from_directory
import os
import subprocess
import requests
import json
import summarize_genai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='.')

# Load config ONCE at startup
prompt_config = summarize_genai.load_prompt_config()

# Configuration (Ideally from env vars)
CB_QUERY_URL = os.getenv("CB_QUERY_URL", "http://localhost:8093/query/service")
CB_USER = os.getenv("CB_USER", "Administrator")
CB_PASSWORD = os.getenv("CB_PASSWORD", "password")
BUCKET_NAME = os.getenv("BUCKET_NAME", "hackathon")
# Place your API KEY here for the hackathon session
GITHUB_API_KEY = os.getenv("GITHUB_API_KEY")

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route('/api/summary', methods=['POST'])
def generate_summary():
    data = request.json
    candidate_data = data.get('candidate_data')
    
    if not candidate_data:
        return jsonify({'error': 'No candidate data provided'}), 400
    
    if not prompt_config:
         return jsonify({'error': 'Prompt config could not be loaded'}), 500

    summary = summarize_genai.generate_candidate_summary(candidate_data, prompt_config)
    return jsonify({'summary': summary})

@app.route('/api/candidates', methods=['POST'])
def add_candidate():
    try:
        data = request.json
        c_id = data.get('id')
        name = data.get('name')
        email = data.get('email')
        cv_text = data.get('cvText')

        if not all([c_id, name, email, cv_text]):
            return jsonify({'error': 'Missing required fields'}), 400

        # 1. Insert Basic Candidate Record into Couchbase via REST
        insert_query = f'INSERT INTO `{BUCKET_NAME}`._default.Candidate (KEY, VALUE) VALUES ("candidate::{c_id}", {{ "ID": {c_id}, "Name": $name, "Email": $email, "CVText": $cvText }})'
        
        payload = {
            "statement": insert_query,
            "$name": name,
            "$email": email,
            "$cvText": cv_text # Note: The C# tool will update this again/process it, but good to have initial
        }

        auth = (CB_USER, CB_PASSWORD)
        response = requests.post(CB_QUERY_URL, json=payload, auth=auth)
        
        if response.status_code != 200:
            return jsonify({'error': 'Failed to insert candidate to DB', 'details': response.text}), 500

        # 2. Run C# Tool to Extract Skills (Process CV)
        # cmd: dotnet run --project process_cv_csharp -- "cvText" id "key"
        # We pass the raw text as the first argument
        
        # Ensure text is safe for CommandLine (subprocess handles arg escaping usually, but huge text might hit limits)
        # For hackathon, we assume it fits.
        
        process = subprocess.run(
            ["dotnet", "run", "--project", "process_cv_csharp", "--", cv_text, str(c_id), GITHUB_API_KEY],
            capture_output=True,
            text=True
        )

        if process.returncode != 0:
            print(f"C# Tool Output: {process.stdout}")
            print(f"C# Tool Error: {process.stderr}")
            return jsonify({'warning': 'Candidate saved, but skill extraction failed', 'details': process.stderr}), 201

        return jsonify({'message': 'Candidate added and processed successfully'})

    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/data', methods=['GET'])
def get_all_data():
    try:
        auth = (CB_USER, CB_PASSWORD)
        
        def run_query(stmt):
            response = requests.post(CB_QUERY_URL, json={"statement": stmt}, auth=auth)
            if response.status_code != 200:
                raise Exception(f"Query failed: {response.text}")
            return response.json().get('results', [])

        # Use SELECT VALUE t to get just the object content, avoiding the wrapping table name
        skills = run_query(f"SELECT VALUE t FROM `{BUCKET_NAME}`._default.Skill t")
        candidates = run_query(f"SELECT VALUE t FROM `{BUCKET_NAME}`._default.Candidate t")
        candidate_skills = run_query(f"SELECT VALUE t FROM `{BUCKET_NAME}`._default.CandidateSkill t")
        ads = run_query(f"SELECT VALUE t FROM `{BUCKET_NAME}`._default.Ad t")
        ad_skills = run_query(f"SELECT VALUE t FROM `{BUCKET_NAME}`._default.AdSkill t")

        return jsonify({
            "skills": skills,
            "candidates": candidates,
            "candidate_skills": candidate_skills,
            "ads": ads,
            "ad_skills": ad_skills
        })

    except Exception as e:
        print(f"Error fetching data: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Starting server at http://localhost:5000")
    app.run(debug=True, port=5000)
