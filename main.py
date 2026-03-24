from datetime import datetime, time
from pathlib import Path
from tempfile import NamedTemporaryFile
from zoneinfo import ZoneInfo

from flask import Flask, render_template, request
from config import ROCK_FORMATIONS
from services.process import process

app = Flask(__name__)
TORONTO_TZ = ZoneInfo("America/Toronto")


def render_index():
    return render_template(
        "index.html",
        formation_options=sorted(ROCK_FORMATIONS.keys())
    )


def build_rock_distribution(form, rock_formations):
    formation_names = form.getlist("formation_name[]")
    start_depths = form.getlist("start_depth[]")
    end_depths = form.getlist("end_depth[]")

    if not formation_names:
        return None, "Please add at least one rock formation section."

    if not (len(formation_names) == len(start_depths) == len(end_depths)):
        return None, "Rock formation inputs are incomplete."

    sections = []
    for idx, (name, start_raw, end_raw) in enumerate(zip(formation_names, start_depths, end_depths), start=1):
        if name not in rock_formations:
            return None, f"Invalid rock formation selected in row {idx}."

        try:
            start_depth = float(start_raw)
            end_depth = float(end_raw)
        except ValueError:
            return None, f"Start and end depth must be numeric values (row {idx})."

        if start_depth < 0:
            return None, f"Start depth cannot be negative (row {idx})."
        if end_depth <= start_depth:
            return None, f"End depth must be greater than start depth (row {idx})."

        sections.append((name, start_depth, end_depth))

    sections.sort(key=lambda item: item[1])
    first_start = sections[0][1]
    if first_start != 0:
        return None, "Rock formation depth must start at 0."

    for i in range(1, len(sections)):
        prev_end = sections[i - 1][2]
        curr_start = sections[i][1]
        if curr_start != prev_end:
            return None, "Rock formation sections must be continuous with no gaps or overlaps."

    distribution = {
        name: {"start_depth": start_depth, "end_depth": end_depth}
        for name, start_depth, end_depth in sections
    }
    return distribution, None

@app.route('/')
def index():
    return render_index()

@app.route('/analyze', methods=['POST'])
def analyze():
    calc_type = request.form['calc_type']
    data_method = request.form['data_method']

    start_date = ""
    end_date = ""
    selected_start_date = ""
    selected_end_date = ""
    csv_filename = ""
    csv_file_path = ""
    temp_file_path = None

    try:
        rock_distribution, rock_error = build_rock_distribution(request.form, ROCK_FORMATIONS)
        if rock_error:
            return render_template(
                'results.html',
                results=rock_error,
                calc_type=calc_type,
                data_method=data_method,
                selected_start_date="",
                selected_end_date="",
                csv_filename=""
            )

        if data_method == "CSV":
            csv_file = request.files.get("csv_file")
            if not csv_file or csv_file.filename == "":
                return render_template(
                    'results.html',
                    results="CSV source selected but no file was uploaded.",
                    calc_type=calc_type,
                    data_method=data_method,
                    selected_start_date="",
                    selected_end_date="",
                    csv_filename=""
                )

            csv_filename = csv_file.filename
            upload_suffix = Path(csv_filename).suffix or ".csv"
            with NamedTemporaryFile(delete=False, suffix=upload_suffix) as temp_file:
                csv_file.save(temp_file.name)
                temp_file_path = temp_file.name
                csv_file_path = temp_file_path
        elif data_method == "API":
            selected_start_date = request.form.get("api_start_date", "")
            selected_end_date = request.form.get("api_end_date", "")
            if not selected_start_date or not selected_end_date:
                return render_template(
                    'results.html',
                    results="API source selected but start/end date was not provided.",
                    calc_type=calc_type,
                    data_method=data_method,
                    selected_start_date="",
                    selected_end_date="",
                    csv_filename=""
                )

            parsed_start_date = datetime.strptime(selected_start_date, "%Y-%m-%d")
            parsed_end_date = datetime.strptime(selected_end_date, "%Y-%m-%d")
            if parsed_start_date > parsed_end_date:
                return render_template(
                    'results.html',
                    results="API start date cannot be after end date.",
                    calc_type=calc_type,
                    data_method=data_method,
                    selected_start_date=selected_start_date,
                    selected_end_date=selected_end_date,
                    csv_filename=""
                )

            start_dt = datetime.combine(parsed_start_date.date(), time.min, tzinfo=TORONTO_TZ)
            end_dt = datetime.combine(parsed_end_date.date(), time.max, tzinfo=TORONTO_TZ)
            start_date = int(start_dt.timestamp() * 1000)
            end_date = int(end_dt.timestamp() * 1000)
        else:
            return render_template(
                'results.html',
                results="Invalid data source selected.",
                calc_type=calc_type,
                data_method=data_method,
                selected_start_date="",
                selected_end_date="",
                csv_filename=""
            )

        results = process(
            calc_type,
            data_method,
            csv_file_path,
            rock_distribution,
            start_date,
            end_date
        )
    finally:
        if temp_file_path:
            import os
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    return render_template(
        'results.html',
        results=results,
        calc_type=calc_type,
        data_method=data_method,
        selected_start_date=selected_start_date,
        selected_end_date=selected_end_date,
        csv_filename=csv_filename
    )

if __name__ == "__main__":
    import os
    
    port = int(os.environ.get("PORT", 5000))
    
    # Add these for better production behavior
    app.run(
        host="0.0.0.0", 
        port=port, 
        debug=False,
        threaded=True  # Handle multiple requests
    )
