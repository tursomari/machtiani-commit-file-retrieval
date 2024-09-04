from flask import Flask, render_template, request, redirect, url_for                                              
import requests                                                                                                   
                                                                                                                  
app = Flask(__name__)                                                                                             
                                                                                                                  
# Replace this with your FastAPI server URL                                                                       
FASTAPI_URL = 'http://localhost:5070/fetch-and-checkout/'                                                         
                                                                                                                  
@app.route('/')                                                                                                   
def index():                                                                                                      
    return render_template('index.html')                                                                          
                                                                                                                  
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
            response = requests.post(FASTAPI_URL, json=data)                                                      
            response.raise_for_status()  # Raise an error for bad responses                                       
            return render_template('result.html', message=response.json()['message'])                             
        except requests.exceptions.RequestException as e:                                                         
            return render_template('result.html', message=f"Error: {e}")                                          
                                                                                                                  
if __name__ == '__main__':                                                                                        
    app.run(debug=True, port=5072)  
