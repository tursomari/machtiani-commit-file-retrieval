from flask import Flask, render_template, request, redirect, url_for
import requests
import logging
import os

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Replace this with your FastAPI server URL
FASTAPI_URL = 'http://localhost:5070'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/load', methods=['GET', 'POST'])
def load():
    if request.method == 'POST':
        api_key = request.form['api_key']
        # Call the FastAPI /load endpoint with the API key
        try:
            response = requests.post(f'{FASTAPI_URL}/load/', json={"api_key": api_key})
            response.raise_for_status()
            return render_template('result.html', message="Projects loaded successfully.")
        except requests.exceptions.RequestException as e:
            return render_template('result.html', message=f"Error loading projects: {e}")

    # Prepopulate the API key from environment variables
    openai_api_key = os.getenv('OPENAI_API_KEY', '')
    return render_template('load.html', api_key=openai_api_key)

@app.route('/fetch-git-repo', methods=['GET', 'POST'])
def fetch_git_repo():
    if request.method == 'POST':
        project_name = request.form['project']

        # Call the get-project-info endpoint
        try:
            response = requests.get(f'{FASTAPI_URL}/get-project-info/', params={'project': project_name})
            response.raise_for_status()
            project_info = response.json()
            project_info["project"] = project_name  # Add project name to the response
            logger.debug(f"Project info fetched successfully: {project_info}")
        except requests.exceptions.RequestException as e:
            return render_template('index.html', message=f"Error fetching project info: {e}")

        return render_template('index.html', project_info=project_info)

    return render_template('fetch-git-repo.html')

@app.route('/submit', methods=['POST'])
def submit():
    if request.method == 'POST':
        codehost_url = request.form['codehost_url']
        project_name = request.form['project_name']
        branch_name = request.form['branch_name']
        api_key = request.form['api_key']

        data = {
            "codehost_url": codehost_url,
            "project_name": project_name,
            "branch_name": branch_name,
            "vcs_type": "git",
            "api_key": api_key
        }

        try:
            response = requests.post(f'{FASTAPI_URL}/fetch-and-checkout/', json=data)
            response.raise_for_status()  # Raise an error for bad responses
            return render_template('result.html', message=response.json()['message'])
        except requests.exceptions.RequestException as e:
            return render_template('result.html', message=f"Error: {e}")

if __name__ == '__main__':
    app.run(debug=True, port=5072)
