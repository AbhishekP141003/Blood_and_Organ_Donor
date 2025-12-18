# CampusBloodDonor - Blood Donation Platform

A professional blood donation platform connecting donors within campus communities.

## Features

- 🩸 **Donor Registration** - Easy registration with email OTP verification
- 🔍 **Smart Search** - Find blood donors by blood group and location
- 📧 **Email Notifications** - Automated OTP system via Gmail
- 👤 **Donor Profiles** - Manage availability and personal information
- 📊 **Admin Dashboard** - Track donors, searches, and analytics
- 🌙 **Dark Mode** - Eye-friendly theme toggle
- 📱 **Responsive Design** - Works on all devices

## Live Demo

🌐 **[CampusBloodDonor](https://campusblooddonor.onrender.com)** (Update with your Render URL)

## Local Development

### Prerequisites
- Python 3.8+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/AbhishekP141003/Blood_and_Organ_Donor.git
cd "Royal Squad"

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

Visit `http://127.0.0.1:5000` in your browser.

## Configuration

### Email OTP Setup
Update the following in `app.py`:
```python
EMAIL_ADDRESS = 'your-email@gmail.com'
EMAIL_PASSWORD = 'your-app-password'
```

Generate a Gmail App Password at: https://myaccount.google.com/apppasswords

### Admin Credentials
Default admin is configured in `app.py` (lines 143-147). Change the email and password for production.

## Deployment

### Render (Recommended)

#### Step 1: Create PostgreSQL Database
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New +" → "PostgreSQL"
3. Name: `campusblooddonor-db` (or your choice)
4. Select Free tier
5. Click "Create Database"
6. Copy the **Internal Database URL** (starts with `postgres://`)

#### Step 2: Deploy Web Service
1. In Render, click "New +" → "Web Service"
2. Connect your GitHub repository: `AbhishekP141003/Blood_and_Organ_Donor`
3. Settings will be auto-detected from `render.yaml`
4. Add Environment Variable:
   - **Key**: `DATABASE_URL`
   - **Value**: Paste the PostgreSQL Internal URL from Step 1
5. (Optional) Add `SENDGRID_API_KEY` and `FROM_EMAIL` for email functionality
6. Click "Create Web Service"

Your app will deploy automatically! Data will now persist across deployments.

## Tech Stack

- **Backend**: Flask 3.0.0
- **Database**: PostgreSQL (production) / SQLite (local dev)
- **Email**: SendGrid API
- **Frontend**: HTML5, CSS3, JavaScript
- **Fonts**: Google Fonts (Inter, Poppins)
- **Hosting**: Render.com

## Project Structure

```
Royal Squad/
├── app.py              # Main Flask application
├── templates/          # HTML templates
├── static/            # Static assets (images, CSS, JS)
├── campus_donor.db    # SQLite database
└── requirements.txt   # Python dependencies
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the MIT License.

## Contact

- **Email**: abhip141003@gmail.com
- **GitHub**: [@AbhishekP141003](https://github.com/AbhishekP141003)

---

Made with ❤️ for saving lives