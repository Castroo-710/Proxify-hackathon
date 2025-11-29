from flask import Flask, request, jsonify, send_from_directory
import os
import summarize_genai

app = Flask(__name__, static_folder='.')

# Load config ONCE at startup
prompt_config = summarize_genai.load_prompt_config()

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

if __name__ == '__main__':
    print("Starting server at http://localhost:5000")
    app.run(debug=True, port=5000)
