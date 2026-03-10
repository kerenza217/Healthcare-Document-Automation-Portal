import os
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'your_db_user'),
    'password': os.environ.get('DB_PASS', 'your_secure_password'),
    'database': os.environ.get('DB_NAME', 'insurance_db')
}


UPLOAD_FOLDER = 'static/uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
