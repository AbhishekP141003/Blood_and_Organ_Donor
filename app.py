import sqlite3
import random
import csv
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, g, redirect, url_for, session, jsonify, make_response
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'campus_secret_key_123_change_in_production'
DB_NAME = "campus_donor.db"

# ===== EMAIL CONFIGURATION =====
# Configure these with your email credentials
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_ADDRESS = 'abhip141003@gmail.com'
EMAIL_PASSWORD = 'nfldldhiikvbjmgi'     # Gmail App Password configured

# IMPORTANT: To get your Gmail App Password:
# 1. Go to: https://myaccount.google.com/security
# 2. Enable "2-Step Verification" (if not already enabled)
# 3. Go to: https://myaccount.google.com/apppasswords
# 4. Select "Mail" and "Other (Custom name)"
# 5. Name it "CampusBloodDonor" and Generate
# 6. Copy the 16-character password (looks like: xxxx xxxx xxxx xxxx)
# 7. Paste it above replacing 'your-app-password' (remove spaces)

def send_otp_email(recipient_email, otp_code, recipient_name=""):
    """Send OTP via email"""
    # Check if email is configured
    if EMAIL_ADDRESS == 'your-email@gmail.com' or EMAIL_PASSWORD == 'your-app-password':
        print(f"\n⚠️  EMAIL NOT CONFIGURED!")
        print(f"========================================")
        print(f" [CONSOLE MODE] OTP for {recipient_email}: {otp_code}")
        print(f"========================================\n")
        print("To enable email sending, configure EMAIL_ADDRESS and EMAIL_PASSWORD in app.py")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Your CampusBloodDonor OTP: {otp_code}'
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = recipient_email
        
        # HTML email body
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; background: #f8f9fa; border-radius: 10px;">
                    <h2 style="color: #ef4444;">🩸 CampusBloodDonor</h2>
                    <p>Hello {recipient_name or 'there'},</p>
                    <p>Your One-Time Password (OTP) for verification is:</p>
                    <div style="background: white; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0;">
                        <h1 style="color: #ef4444; font-size: 32px; margin: 0; letter-spacing: 5px;">{otp_code}</h1>
                    </div>
                    <p><strong>This OTP is valid for 10 minutes.</strong></p>
                    <p>If you didn't request this OTP, please ignore this email.</p>
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p style="font-size: 12px; color: #666;">
                        CampusBloodDonor - Connecting blood donors within your campus community
                    </p>
                </div>
            </body>
        </html>
        """
        
        # Attach HTML body
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send email
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ OTP sent successfully to {recipient_email}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending email: {str(e)}")
        # Fallback: print to console
        print(f"\n========================================")
        print(f" [EMAIL FAILED - CONSOLE FALLBACK] OTP: {otp_code}")
        print(f" For: {recipient_email}")
        print(f"========================================\n")
        return False

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
        
        # Donors Table - Blood Donors Only (Email now required)
        db.execute('''
            CREATE TABLE IF NOT EXISTS donors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
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
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create default admin if not exists
        admin_exists = db.execute("SELECT * FROM admins WHERE email = 'abhip141003@gmail.com'").fetchone()
        if not admin_exists:
            hashed_pw = generate_password_hash('Abhi@Engineering')
            db.execute("INSERT INTO admins (email, password_hash) VALUES (?, ?)", 
                      ('abhip141003@gmail.com', hashed_pw))
        
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
        email = request.form.get('email')
        
        server_otp = session.get('current_otp')
        server_email = session.get('otp_email')
        
        if not server_otp or not user_otp:
            error_message = "OTP verification is required."
        elif user_otp != server_otp:
            error_message = "Invalid OTP code."
        elif email != server_email:
            error_message = "Email changed after OTP was sent."
        else:
            # Save to Database
            db = get_db()
            name = request.form.get('name')
            phone = request.form.get('phone')
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
                session.pop('otp_email', None)
                
                return redirect(url_for('home', success=1))
            except sqlite3.IntegrityError:
                error_message = "This phone number is already registered."
    
    return render_template('register.html', error=error_message)

@app.route('/send_otp', methods=['POST'])
def send_otp():
    data = request.json
    email = data.get('email')
    name = data.get('name', '')
    
    if not email:
        return jsonify({'success': False, 'message': 'Email address required'})
    
    # Validate email format
    if '@' not in email or '.' not in email:
        return jsonify({'success': False, 'message': 'Invalid email format'})
    
    # Generate 4-digit OTP
    otp_code = str(random.randint(1000, 9999))
    
    # Store in session
    session['current_otp'] = otp_code
    session['otp_email'] = email
    
    # Send OTP via email
    email_sent = send_otp_email(email, otp_code, name)
    
    if email_sent:
        return jsonify({'success': True, 'message': f'OTP sent to {email}'})
    else:
        return jsonify({'success': True, 'message': 'OTP sent (check console if email failed)'})

@app.route('/search')
def search():
    db = get_db()
    
    seeker_name = request.args.get('seeker_name', '').strip()
    seeker_id = request.args.get('seeker_id', '').strip()
    seeker_email = request.args.get('seeker_email', '').strip()
    user_otp = request.args.get('otp', '').strip()
    
    area_filter = request.args.get('area', '').lower()
    bg_filter = request.args.get('bg', '')
    
    donors = []
    search_performed = False
    error_message = None
    
    if seeker_name and seeker_id and seeker_email and user_otp:
        server_otp = session.get('current_otp')
        server_email = session.get('otp_email')
        
        if not server_otp or user_otp != server_otp:
            error_message = "Invalid or expired OTP."
        elif seeker_email != server_email:
            error_message = "Email changed after OTP was sent."
        else:
            search_performed = True
            session.pop('current_otp', None)
            session.pop('otp_email', None)
            
            # Log search
            criteria = f"Area: {area_filter}, BG: {bg_filter}"
            db.execute('INSERT INTO search_logs (seeker_name, seeker_id, seeker_phone, criteria) VALUES (?, ?, ?, ?)',
                       (seeker_name, seeker_id, seeker_email, criteria))
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
        email = request.form.get('email')
        password = request.form.get('password')
        
        db = get_db()
        admin = db.execute("SELECT * FROM admins WHERE email = ?", (email,)).fetchone()
        
        if admin and check_password_hash(admin['password_hash'], password):
            session['admin_id'] = admin['id']
            session['admin_email'] = admin['email']
            return redirect(url_for('admin_dashboard'))
        else:
            error = "Invalid email or password"
    
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
                           blood_distribution=blood_distribution,
                           admin_email=session.get('admin_email'))

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
    session.pop('admin_email', None)
    return redirect(url_for('home'))

# ===== DONOR ROUTES =====
@app.route('/donor/login', methods=['GET', 'POST'])
def donor_login():
    if 'donor_id' in session:
        return redirect(url_for('donor_profile'))
    
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        otp = request.form.get('otp')
        
        server_otp = session.get('current_otp')
        server_email = session.get('otp_email')
        
        if not server_otp or otp != server_otp:
            error = "Invalid OTP"
        elif email != server_email:
            error = "Email mismatch"
        else:
            db = get_db()
            donor = db.execute("SELECT * FROM donors WHERE email = ?", (email,)).fetchone()
            
            if donor:
                session['donor_id'] = donor['id']
                session['donor_name'] = donor['name']
                session.pop('current_otp', None)
                session.pop('otp_email', None)
                
                # Update last login
                db.execute("UPDATE donors SET last_login = ? WHERE id = ?", 
                          (datetime.now(), donor['id']))
                db.commit()
                
                return redirect(url_for('donor_profile'))
            else:
                error = "No donor found with this email address"
    
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