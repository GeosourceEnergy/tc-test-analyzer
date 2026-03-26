import os
import json
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from dotenv import load_dotenv

from services.process import process

load_dotenv()

#initialize flask application
app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


#home page
@app.route('/')
def home():
    return render_template('index.html')

#handles form submissions (communication w/ backend)
@app.route('/analyze', methods=['POST'])
def analyze(): 
    try:
        #process() parameters
        data_method = request.form.get('data_method')
        bh_depth = float(request.form.get('bh_depth'))
        overburden_depth = float(request.form.get('overburden_depth'))
        loop_od = float(request.form.get('loop_od'))
        
        #rock segments
        segment_count = int(request.form.get('segment_count', 0))
        sections = []
        
        for i in range(segment_count):
            name = request.form.get(f'segment_{i}_name')
            start_depth = request.form.get(f'segment_{i}_start')
            end_depth = request.form.get(f'segment_{i}_end')
            tc_btu = request.form.get(f'segment_{i}_tc')
            
            if name and start_depth and end_depth and tc_btu:
                sections.append({
                    'name': name,
                    'start_depth': float(start_depth),
                    'end_depth': float(end_depth),
                    'tc_btu': float(tc_btu)
                })
        
        #CSV handling
        if data_method == 'CSV':
            
            if 'csv_file' not in request.files:
                return jsonify({'error: no file uploaded'}), 400
        
            file = request.files['csv_file']
            
            if file.filename == '':
                return jsonify({'error: no file selected'}), 400
            
            if file:
                # delete old files before saving new one
                for old_file in os.listdir(app.config['UPLOAD_FOLDER']):
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], old_file)
                    
                    try:
                        os.remove(old_path)
                    except:
                        pass
                
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(filepath)
                
                results = process(
                    data_method='CSV',
                    csv_file_path=filepath,
                    rock_formation_segments=sections,
                    BH_DEPTH=bh_depth,
                    LOOP_OD=loop_od,
                    OVERBURDEN_DEPTH=overburden_depth,
                    START_DATE=None,
                    END_DATE=None
                )
            
                if isinstance(results, str):
                    return jsonify({'error': results}), 400
                        
                return jsonify({
                    'success': True,
                    'method': 'CSV',
                    'results': results
                })
            
        elif data_method == 'API':
            #get dates form user 
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')
                
            if not start_date or not end_date:
                return jsonify({'error': 'Start date and end date are required'}), 400
            #convert datetime-local strings to timestamps (milliseconds)
            from datetime import datetime
            from zoneinfo import ZoneInfo
            
            toronto = ZoneInfo('America/Toronto')
            
            start_dt = datetime.fromisoformat(start_date).replace(tzinfo=toronto)
            end_dt = datetime.fromisoformat(end_date).replace(tzinfo=toronto)
            
            start_timestamp = int(start_dt.timestamp() * 1000)
            end_timestamp = int(end_dt.timestamp() * 1000)
            
            # Call your process function with API
            results = process(
                data_method='API',
                csv_file_path=None,
                rock_formation_segments=sections,
                BH_DEPTH=bh_depth,
                LOOP_OD=loop_od,
                OVERBURDEN_DEPTH=overburden_depth,
                START_DATE=start_timestamp,
                END_DATE=end_timestamp
            )
            
            # Check if results is an error message
            if isinstance(results, str):
                return jsonify({'error': results}), 400
            
            return jsonify({
                'success': True,
                'method': 'API',
                'results': results
            })
        
        return jsonify({'error': 'Invalid data method'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        


if __name__ == "__main__":
    app.run(debug=True)