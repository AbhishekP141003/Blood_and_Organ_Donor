import sqlite3
import random
import csv
import io
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, g, redirect, url_for, session, jsonify, make_response
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'campus_secret_key_123_change_in_production'
DB_NAME = "campus_donor.db"

# ===== DATABASE HELPER FUNCTIONS =====
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
        
        # Donors Table - Blood Donors Only
        db.execute('''
            CREATE TABLE IF NOT EXISTS donors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT NOT NULL UNIQUE,
                area TEXT,
                blood_group TEXT NOT NULL,
                blood_available TEXT DEFAULT 'yes',
                is_available TEXT DEFAULT 'yes',
                last_login DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Search Logs
        db.execute('''
            CREATE TABLE IF NOT EXISTS search_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seeker_name TEXT,
                seeker_id TEXT,
                seeker_phone TEXT,
                criteria TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Admins Table
        db.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create default admin if not exists
        admin_exists = db.execute("SELECT * FROM admins WHERE username = 'admin'").fetchone()
        if not admin_exists:
            hashed_pw = generate_password_hash('admin123')
            db.execute("INSERT INTO admins (username, password_hash) VALUES (?, ?)", ('admin', hashed_pw))
        
        db.commit()

# ===== AUTHENTICATION DECORATORS =====
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def donor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'donor_id' not in session:
            return redirect(url_for('donor_login'))
        return f(*args, **kwargs)
    return decorated_function

# ===== PUBLIC ROUTES =====
@app.route('/')
def home():
    db = get_db()
    
    # Count Blood Donors
    res_blood = db.execute("SELECT COUNT(*) FROM donors").fetchone()
    blood_count = res_blood[0] if res_blood else 0
    
    return render_template('index.html', blood_count=blood_count)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error_message = None
    
    if request.method == 'POST':
        # Verify OTP
        user_otp = request.form.get('otp')
        phone = request.form.get('phone')
        
        server_otp = session.get('current_otp')
        server_phone = session.get('otp_phone')
        
        if not server_otp or not user_otp:
            error_message = "OTP verification is required."
        elif user_otp != server_otp:
            error_message = "Invalid OTP code."
        elif phone != server_phone:
            error_message = "Phone number changed after OTP was sent."
        else:
            # Save to Database
            db = get_db()
            name = request.form.get('name')
            email = request.form.get('email')
            area = request.form.get('area')
            blood_group = request.form.get('blood_group')
            blood_available = request.form.get('blood_available', 'yes')
            
            try:
                db.execute('''
                    INSERT INTO donors (name, email, phone, area, blood_group, blood_available)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (name, email, phone, area, blood_group, blood_available))
                db.commit()
                
                # Clear OTP
                session.pop('current_otp', None)
                session.pop('otp_phone', None)
                
                return redirect(url_for('home', success=1))
            except sqlite3.IntegrityError:
                error_message = "This phone number is already registered."
    
    return render_template('register.html', error=error_message)

@app.route('/send_otp', methods=['POST'])
def send_otp():
    data = request.json
    phone = data.get('phone')
    
    if not phone:
        return jsonify({'success': False, 'message': 'Phone number required'})
    
    # Generate 4-digit OTP
    otp_code = str(random.randint(1000, 9999))
    
    # Store in session
    session['current_otp'] = otp_code
    session['otp_phone'] = phone
    
    # SIMULATION: Print to console
    print(f"\n========================================")
    print(f" [SMS GATEWAY] OTP for {phone}: {otp_code}")
    print(f"========================================\n")
    
    return jsonify({'success': True, 'message': 'OTP sent (check server console)'})

@app.route('/search')
def search():
    db = get_db()
    
    seeker_name = request.args.get('seeker_name', '').strip()
    seeker_id = request.args.get('seeker_id', '').strip()
    seeker_phone = request.args.get('seeker_phone', '').strip()
    user_otp = request.args.get('otp', '').strip()
    
    area_filter = request.args.get('area', '').lower()
    bg_filter = request.args.get('bg', '')
    
    donors = []
    search_performed = False
    error_message = None
    
    if seeker_name and seeker_id and seeker_phone and user_otp:
        server_otp = session.get('current_otp')
        server_phone = session.get('otp_phone')
        
        if not server_otp or user_otp != server_otp:
            error_message = "Invalid or expired OTP."
        elif seeker_phone != server_phone:
            error_message = "Phone number changed after OTP generation."
        else:
            search_performed = True
            session.pop('current_otp', None)
            
            # Log search
            criteria = f"Area: {area_filter}, BG: {bg_filter}"
            db.execute('INSERT INTO search_logs (seeker_name, seeker_id, seeker_phone, criteria) VALUES (?, ?, ?, ?)',
                       (seeker_name, seeker_id, seeker_phone, criteria))
            db.commit()
            
            # Query donors
            query = "SELECT * FROM donors WHERE is_available = 'yes' AND 1=1"
            params = []
            
            if bg_filter:
                query += " AND blood_group = ?"
                params.append(bg_filter)
            
            if area_filter:
                query += " AND lower(area) LIKE ?"
                params.append(f"%{area_filter}%")
            
            query += " ORDER BY id DESC"
            donors = db.execute(query, params).fetchall()
    
    return render_template('search.html', 
                           donors=donors, 
                           search_performed=search_performed,
                           error_message=error_message)

# ===== ADMIN ROUTES =====
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if 'admin_id' in session:
        return redirect(url_for('admin_dashboard'))
    
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        db = get_db()
        admin = db.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
        
        if admin and check_password_hash(admin['password_hash'], password):
            session['admin_id'] = admin['id']
            session['admin_username'] = admin['username']
            return redirect(url_for('admin_dashboard'))
        else:
            error = "Invalid username or password"
    
    return render_template('admin_login.html', error=error)

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    db = get_db()
    
    # Statistics
    total_donors = db.execute("SELECT COUNT(*) FROM donors").fetchone()[0]
    total_searches = db.execute("SELECT COUNT(*) FROM search_logs").fetchone()[0]
    
    # All donors
    all_donors = db.execute("SELECT * FROM donors ORDER BY created_at DESC").fetchall()
    
    # Blood group distribution
    blood_distribution = db.execute("""
        SELECT blood_group, COUNT(*) as count 
        FROM donors 
        GROUP BY blood_group
        ORDER BY count DESC
    """).fetchall()
    
    return render_template('admin_dashboard.html',
                           total_donors=total_donors,
                           total_searches=total_searches,
                           all_donors=all_donors,
                           blood_distribution=blood_distribution)

@app.route('/admin/donors/delete/<int:donor_id>', methods=['POST'])
@admin_required
def admin_delete_donor(donor_id):
    db = get_db()
    db.execute("DELETE FROM donors WHERE id = ?", (donor_id,))
    db.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/export_csv')
@admin_required
def admin_export_csv():
    db = get_db()
    donors = db.execute("SELECT * FROM donors ORDER BY created_at DESC").fetchall()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['ID', 'Name', 'Email', 'Phone', 'Area', 'Blood Group', 'Available', 'Created At'])
    
    # Data
    for donor in donors:
        writer.writerow([
            donor['id'], donor['name'], donor['email'], donor['phone'],
            donor['area'], donor['blood_group'],
            donor['is_available'], donor['created_at']
        ])
    
    # Create response
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=blood_donors_{datetime.now().strftime('%Y%m%d')}.csv"
    response.headers["Content-type"] = "text/csv"
    
    return response

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    return redirect(url_for('home'))

# ===== DONOR ROUTES =====
@app.route('/donor/login', methods=['GET', 'POST'])
def donor_login():
    if 'donor_id' in session:
        return redirect(url_for('donor_profile'))
    
    error = None
    if request.method == 'POST':
        phone = request.form.get('phone')
        otp = request.form.get('otp')
        
        server_otp = session.get('current_otp')
        server_phone = session.get('otp_phone')
        
        if not server_otp or otp != server_otp:
            error = "Invalid OTP"
        elif phone != server_phone:
            error = "Phone number mismatch"
        else:
            db = get_db()
            donor = db.execute("SELECT * FROM donors WHERE phone = ?", (phone,)).fetchone()
            
            if donor:
                session['donor_id'] = donor['id']
                session['donor_name'] = donor['name']
                session.pop('current_otp', None)
                session.pop('otp_phone', None)
                
                # Update last login
                db.execute("UPDATE donors SET last_login = ? WHERE id = ?", 
                          (datetime.now(), donor['id']))
                db.commit()
                
                return redirect(url_for('donor_profile'))
            else:
                error = "No donor found with this phone number"
    
    return render_template('donor_login.html', error=error)

@app.route('/donor/profile')
@donor_required
def donor_profile():
    db = get_db()
    donor = db.execute("SELECT * FROM donors WHERE id = ?", (session['donor_id'],)).fetchone()
    return render_template('donor_profile.html', donor=donor)

@app.route('/donor/edit', methods=['GET', 'POST'])
@donor_required
def donor_edit():
    db = get_db()
    donor = db.execute("SELECT * FROM donors WHERE id = ?", (session['donor_id'],)).fetchone()
    
    error = None
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        area = request.form.get('area')
        blood_group = request.form.get('blood_group')
        blood_available = request.form.get('blood_available', 'yes')
        
        db.execute('''
            UPDATE donors 
            SET name = ?, email = ?, area = ?, blood_group = ?, blood_available = ?
            WHERE id = ?
        ''', (name, email, area, blood_group, blood_available, session['donor_id']))
        db.commit()
        
        return redirect(url_for('donor_profile'))
    
    return render_template('donor_edit.html', donor=donor, error=error)

@app.route('/donor/toggle_availability', methods=['POST'])
@donor_required
def donor_toggle_availability():
    db = get_db()
    donor = db.execute("SELECT is_available FROM donors WHERE id = ?", (session['donor_id'],)).fetchone()
    
    new_status = 'no' if donor['is_available'] == 'yes' else 'yes'
    db.execute("UPDATE donors SET is_available = ? WHERE id = ?", (new_status, session['donor_id']))
    db.commit()
    
    return jsonify({'success': True, 'new_status': new_status})

@app.route('/donor/logout')
def donor_logout():
    session.pop('donor_id', None)
    session.pop('donor_name', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)