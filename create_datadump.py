import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
CB_QUERY_URL = os.getenv("CB_QUERY_URL", "http://localhost:8093/query/service")
CB_USER = os.getenv("CB_USER", "Administrator")
CB_PASSWORD = os.getenv("CB_PASSWORD", "password")
BUCKET_NAME = os.getenv("BUCKET_NAME", "hackathon")

def run_query(stmt):
    auth = (CB_USER, CB_PASSWORD)
    response = requests.post(CB_QUERY_URL, json={"statement": stmt}, auth=auth)
    if response.status_code != 200:
        raise Exception(f"Query failed: {response.text}")
    return response.json().get('results', [])

def create_dump():
    try:
        print("Fetching data from Couchbase...")
        
        # Fetch data from all known collections based on server.py structure
        skills = run_query(f"SELECT VALUE t FROM `{BUCKET_NAME}`._default.Skill t")
        candidates = run_query(f"SELECT VALUE t FROM `{BUCKET_NAME}`._default.Candidate t")
        candidate_skills = run_query(f"SELECT VALUE t FROM `{BUCKET_NAME}`._default.CandidateSkill t")
        ads = run_query(f"SELECT VALUE t FROM `{BUCKET_NAME}`._default.Ad t")
        ad_skills = run_query(f"SELECT VALUE t FROM `{BUCKET_NAME}`._default.AdSkill t")

        data = {
            "skills": skills,
            "candidates": candidates,
            "candidate_skills": candidate_skills,
            "ads": ads,
            "ad_skills": ad_skills
        }

        filename = "datadump.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        
        print(f"Successfully created {filename}")

    except Exception as e:
        print(f"Error creating dump: {e}")

if __name__ == "__main__":
    create_dump()
