# DUT Wellness Centre – Setup Guide
=============================================

## 1. Install Dependencies
```
pip install Flask Flask-SQLAlchemy Flask-Login Flask-Mail Werkzeug
```

## 2. Configure Email (Optional)
Edit `app.py` and update these lines with your Gmail credentials:
```python
app.config['MAIL_USERNAME'] = 'your-gmail@gmail.com'
app.config['MAIL_PASSWORD'] = 'your-app-password'  # Gmail App Password
```
To get a Gmail App Password:
- Go to Google Account → Security → 2-Step Verification → App passwords

## 3. Run the Application
```
python app.py
```
Access at: http://localhost:5000

## 4. Default Login Accounts
| Role       | Student #  | Password        | Email                   |
|------------|------------|-----------------|-------------------------|
| Admin      | ADMIN001   | Admin@123       | admin@dut.ac.za         |
| Counsellor | COUN001    | Counsellor@123  | counsellor@dut.ac.za    |
| Student    | 21200001   | Student@123     | student@dut.ac.za       |

## 5. Features
- ✅ Login / Register / Forgot Password / Reset Password
- ✅ Student Dashboard with mood chart
- ✅ Daily check-ins with AI feedback
- ✅ Check-in history and progress tracking
- ✅ SOS emergency alerts (emails all counsellors)
- ✅ Crisis support page (public, no login required)
- ✅ Peer forum with anonymous posting
- ✅ Book counselling sessions (individual/group/online)
- ✅ Wellness resources page
- ✅ Counsellor dashboard (manage bookings, SOS, student profiles)
- ✅ Admin dashboard (user management, resources, announcements, broadcast email)
- ✅ Auto-changing campus images on login page
- ✅ Automatic emails: welcome, password reset, SOS alert, low mood, booking updates
- ✅ Role-based access control (student / counsellor / admin)
- ✅ Emergency contact storage
- ✅ Profile management

## 6. Project Structure
```
dut_wellness/
├── app.py                    # Main Flask application
├── requirements.txt
├── static/
│   ├── css/main.css          # Full stylesheet
│   └── js/main.js            # Client-side JS
└── templates/
    ├── base.html             # Base layout with sidebar
    ├── login.html            # Login with sliding campus images
    ├── register.html
    ├── forgot_password.html
    ├── reset_password.html
    ├── student_dashboard.html
    ├── checkin.html
    ├── checkin_history.html
    ├── sos.html
    ├── crisis.html           # Public crisis page
    ├── forum.html
    ├── new_post.html
    ├── view_post.html
    ├── booking.html
    ├── resources.html
    ├── profile.html
    ├── counsellor_dashboard.html
    ├── view_student.html
    ├── admin_dashboard.html
    └── emails/
        ├── welcome.html
        ├── reset_password.html
        ├── sos_alert.html
        ├── low_mood_alert.html
        ├── booking_confirmation.html
        ├── booking_update.html
        └── sos_response.html
```
