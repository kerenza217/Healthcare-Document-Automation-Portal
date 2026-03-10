from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
import os
from werkzeug.utils import secure_filename
from datetime import datetime

# ---------------- CONFIG ----------------
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Root!234',
    'database': 'picture_upload'
}

UPLOAD_FOLDER = 'static/uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Session timeout in seconds (e.g., 5 minutes)
SESSION_TIMEOUT = 5 * 60

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ---------------- HELPERS ----------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def check_session_timeout():
    """Redirect to index if session expired"""
    last_active = session.get('last_active')
    if last_active:
        elapsed = datetime.now().timestamp() - last_active
        if elapsed > SESSION_TIMEOUT:
            session.clear()
            flash("Session timed out due to inactivity.")
            return redirect(url_for('index'))
    # Update last active timestamp
    session['last_active'] = datetime.now().timestamp()
    return None

# ---------------- ROUTES ----------------
@app.route('/test')
def test():
    return "Flask is working!"

# 1. Index / Search by phone number
@app.route('/', methods=['GET','POST'])
def index():
    if request.method == 'POST':
        phone = request.form.get('phone')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM members WHERE phone_number=%s", (phone,))
        member = cursor.fetchone()
        conn.close()
        if member:
            # store membership in session for timeout
            session['last_active'] = datetime.now().timestamp()
            session['membership_number'] = member['membership_number']
            if member['member_type'] == 'Principal':
                return redirect(url_for('principal_dashboard', membership_number=member['membership_number']))
            else:
                return redirect(url_for('dependent_dashboard', membership_number=member['membership_number']))
        else:
            flash("Phone number not found.")
            return redirect(url_for('index'))
    return render_template('index.html')

# 2. Principal dashboard
@app.route('/principal/<membership_number>', methods=['GET','POST'])
def principal_dashboard(membership_number):
    # Check session timeout
    timeout_redirect = check_session_timeout()
    if timeout_redirect:
        return timeout_redirect

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Principal info
    cursor.execute("SELECT * FROM members WHERE membership_number=%s", (membership_number,))
    principal = cursor.fetchone()
    # Dependents
    cursor.execute(
        "SELECT * FROM members WHERE principal_membership_number=%s AND membership_number != %s",
        (membership_number, membership_number)
    )
    dependents = cursor.fetchall()
    # Regions
    cursor.execute("SELECT * FROM regions ORDER BY region_name")
    regions = cursor.fetchall()
    conn.close()
    return render_template('principal_dashboard.html', principal=principal, dependents=dependents, regions=regions)

# 3. Dependent dashboard
@app.route('/dependent/<membership_number>', methods=['GET','POST'])
def dependent_dashboard(membership_number):
    # Check session timeout
    timeout_redirect = check_session_timeout()
    if timeout_redirect:
        return timeout_redirect

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM members WHERE membership_number=%s", (membership_number,))
    member = cursor.fetchone()
    # Regions
    cursor.execute("SELECT * FROM regions ORDER BY region_name")
    regions = cursor.fetchall()
    conn.close()
    return render_template('dependent_dashboard.html', member=member, regions=regions)

# 4. Upload picture + region
@app.route('/upload_picture/<membership_number>', methods=['POST'])
def upload_picture(membership_number):
    # Check session timeout
    timeout_redirect = check_session_timeout()
    if timeout_redirect:
        return timeout_redirect

    if 'picture' not in request.files:
        flash('No file part.')
        return redirect(request.referrer)
    
    file = request.files['picture']
    if file.filename == '':
        flash('No selected file.')
        return redirect(request.referrer)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{membership_number}_{timestamp}.{filename.rsplit('.',1)[1]}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Get region and cast to INT
        region_id = request.form.get('region')
        if region_id and region_id.isdigit():
            region_id = int(region_id)
        else:
            region_id = None

        # Update database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "UPDATE members SET picture_url=%s, region_id=%s WHERE membership_number=%s",
            (filename, region_id, membership_number)
        )
        conn.commit()
        conn.close()

        flash('Picture and region updated successfully. You will be redirected to the homepage.')
        return redirect(url_for('index'))  # redirect to index after successful upload
    
    flash('Invalid file type. Only jpg, jpeg, png allowed.')
    return redirect(request.referrer)

@app.route('/upload_all', methods=['POST'])
def upload_all():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Loop over all POSTed fields
    for key in request.files:
        if key.startswith("picture_"):
            membership_number = key.replace("picture_", "")
            file = request.files[key]

            # Get region for this member
            region_id = request.form.get(f"region_{membership_number}")
            region_id = int(region_id) if region_id and region_id.isdigit() else None

            filename = None
            if file and allowed_file(file.filename):
                # Save picture
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                ext = file.filename.rsplit('.',1)[1]
                filename = f"{membership_number}_{timestamp}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            # Update DB
            if filename:
                cursor.execute(
                    "UPDATE members SET picture_url=%s, region_id=%s WHERE membership_number=%s",
                    (filename, region_id, membership_number)
                )
            else:
                cursor.execute(
                    "UPDATE members SET region_id=%s WHERE membership_number=%s",
                    (region_id, membership_number)
                )

    conn.commit()
    conn.close()
    flash("All members updated successfully!")
    return redirect(url_for('index'))


# ---------------- MAIN ----------------
if __name__ == '__main__':
    # Make sure upload folder exists
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True, port=8000)
