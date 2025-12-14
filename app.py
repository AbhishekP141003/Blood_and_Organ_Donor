import sqlite3
import random  # NEW: For generating numbers
from flask import Flask, render_template, request, g, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = 'campus_secret_key_123' # NEW: Required for session storage
DB_NAME = "campus_donor.db"

# --- Database Helper Functions (Same as before) ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_NAME)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        # Donors Table
        db.execute('''
            CREATE TABLE IF NOT EXISTS donors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT NOT NULL,
                area TEXT,
                donor_type TEXT NOT NULL,
                blood_group TEXT,
                blood_available TEXT,
                organs TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Search Logs (Updated to store phone)
        db.execute('''
            CREATE TABLE IF NOT EXISTS search_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seeker_name TEXT,
                seeker_id TEXT,
                seeker_phone TEXT,
                search_type TEXT,
                criteria TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.commit()

# --- Routes ---
@app.route('/')
def home():
    db = get_db()
    
    # 1. Count Blood Donors (Includes 'blood' and 'both')
    res_blood = db.execute("SELECT COUNT(*) FROM donors WHERE donor_type IN ('blood', 'both')").fetchone()
    blood_count = res_blood[0] if res_blood else 0

    # 2. Count Organ Donors (Includes 'organ' and 'both')
    res_organ = db.execute("SELECT COUNT(*) FROM donors WHERE donor_type IN ('organ', 'both')").fetchone()
    organ_count = res_organ[0] if res_organ else 0

    return render_template('index.html', blood_count=blood_count, organ_count=organ_count)
# ... (Keep existing imports and DB setup) ...

@app.route('/register', methods=['GET', 'POST'])
def register():
    error_message = None

    if request.method == 'POST':
        # 1. Verify OTP first
        user_otp = request.form.get('otp')
        phone = request.form.get('phone')
        
        server_otp = session.get('current_otp')
        server_phone = session.get('otp_phone')
        
        # Validation Logic
        if not server_otp or not user_otp:
            error_message = "OTP verification is required."
        elif user_otp != server_otp:
            error_message = "Invalid OTP code."
        elif phone != server_phone:
            error_message = "Phone number changed after OTP was sent."
        else:
            # 2. OTP is Valid -> Save to Database
            db = get_db()
            name = request.form.get('name')
            email = request.form.get('email')
            area = request.form.get('area')
            donor_type = request.form.get('donor_type')
            
            blood_group = request.form.get('blood_group') if donor_type in ['blood', 'both'] else None
            blood_available = request.form.get('blood_available') if donor_type in ['blood', 'both'] else None
            
            organs_list = request.form.getlist('organs')
            organs_str = ",".join(organs_list) if donor_type in ['organ', 'both'] else None

            db.execute('''
                INSERT INTO donors (name, email, phone, area, donor_type, blood_group, blood_available, organs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, email, phone, area, donor_type, blood_group, blood_available, organs_str))
            db.commit()
            
            # Clear OTP from session
            session.pop('current_otp', None)
            
            # Redirect to Home
            return redirect(url_for('home', success=1))

    # If GET request or OTP failed, show form (with error if exists)
    return render_template('register.html', error=error_message)

# ... (Keep the rest of app.py exactly the same) ...
@app.route('/send_otp', methods=['POST'])
def send_otp():
    data = request.json
    phone = data.get('phone')
    
    if not phone:
        return jsonify({'success': False, 'message': 'Phone number required'})

    # Generate 4-digit OTP
    otp_code = str(random.randint(1000, 9999))
    
    # Store in session (Temporary server memory)
    session['current_otp'] = otp_code
    session['otp_phone'] = phone
    
    # SIMULATION: Print to console instead of sending SMS
    print(f"\n========================================")
    print(f" [SMS GATEWAY] OTP for {phone}: {otp_code}")
    print(f"========================================\n")
    
    return jsonify({'success': True, 'message': 'OTP sent (check server console)'})

@app.route('/search')
def search():
    db = get_db()
    
    # Params
    search_type = request.args.get('type', 'blood')
    seeker_name = request.args.get('seeker_name', '').strip()
    seeker_id = request.args.get('seeker_id', '').strip()
    seeker_phone = request.args.get('seeker_phone', '').strip()
    user_otp = request.args.get('otp', '').strip()
    
    area_filter = request.args.get('area', '').lower()
    bg_filter = request.args.get('bg', '')

    donors = []
    search_performed = False
    error_message = None

    # Logic: If they are trying to search (Params exist)
    if seeker_name and seeker_id and seeker_phone and user_otp:
        
        # 1. VERIFY OTP
        server_otp = session.get('current_otp')
        server_phone = session.get('otp_phone')

        if not server_otp or user_otp != server_otp:
            error_message = "Invalid or expired OTP."
        elif seeker_phone != server_phone:
            error_message = "Phone number changed after OTP generation."
        else:
            # 2. SUCCESS: Log and Search
            search_performed = True
            
            # Clear OTP to prevent replay
            session.pop('current_otp', None)

            # Log
            criteria = f"Area: {area_filter}, BG: {bg_filter}"
            db.execute('INSERT INTO search_logs (seeker_name, seeker_id, seeker_phone, search_type, criteria) VALUES (?, ?, ?, ?, ?)',
                       (seeker_name, seeker_id, seeker_phone, search_type, criteria))
            db.commit()

            # Query
            query = "SELECT * FROM donors WHERE 1=1"
            params = []

            if search_type == 'blood':
                query += " AND (donor_type = 'blood' OR donor_type = 'both')"
                if bg_filter:
                    query += " AND blood_group = ?"
                    params.append(bg_filter)
            elif search_type == 'organ':
                query += " AND (donor_type = 'organ' OR donor_type = 'both')"

            if area_filter:
                query += " AND lower(area) LIKE ?"
                params.append(f"%{area_filter}%")

            query += " ORDER BY id DESC"
            donors = db.execute(query, params).fetchall()

    return render_template('search.html', 
                           donors=donors, 
                           search_type=search_type, 
                           search_performed=search_performed,
                           error_message=error_message)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)