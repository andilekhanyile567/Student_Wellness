from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime as dt, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import secrets
import threading
import time as time_module
from functools import wraps
import string
import os
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wellness.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email settings (Gmail SMTP)
MAIL_SERVER   = 'smtp.gmail.com'
MAIL_PORT     = 587
MAIL_USERNAME = 'nkosikhonashabane16@gmail.com'
MAIL_PASSWORD = 'sdcixbzaflyigdwy'
MAIL_FROM     = f'DUT Wellness Centre <{MAIL_USERNAME}>'

db            = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# =============================================================================
#  MODELS
# =============================================================================

class User(db.Model):
    id                 = db.Column(db.Integer,     primary_key=True)
    student_number     = db.Column(db.String(20),  unique=True, nullable=False)
    full_name          = db.Column(db.String(100), nullable=False)
    email              = db.Column(db.String(120), unique=True, nullable=False)
    password_hash      = db.Column(db.String(256), nullable=False)
    role               = db.Column(db.String(20),  default='student')
    faculty            = db.Column(db.String(100))
    phone              = db.Column(db.String(20))
    emergency_contact  = db.Column(db.String(100))
    emergency_phone    = db.Column(db.String(20))
    is_active          = db.Column(db.Boolean,     default=True)
    created_at         = db.Column(db.DateTime,    default=dt.utcnow)
    last_login         = db.Column(db.DateTime,    default=dt.utcnow, nullable=True)
    reset_token        = db.Column(db.String(100), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)

    checkins            = db.relationship('CheckIn',   backref='user',       lazy=True, foreign_keys='CheckIn.user_id')
    posts               = db.relationship('ForumPost', backref='author',     lazy=True, foreign_keys='ForumPost.user_id')
    bookings            = db.relationship('Booking',   backref='student',    lazy=True, foreign_keys='Booking.student_id')
    counsellor_bookings = db.relationship('Booking',   backref='counsellor', lazy=True, foreign_keys='Booking.counsellor_id')
    sos_alerts          = db.relationship('SOSAlert',  backref='user',       lazy=True, foreign_keys='SOSAlert.user_id')
    sos_responses       = db.relationship('SOSAlert',  backref='responder',  lazy=True, foreign_keys='SOSAlert.responded_by')
    scheduled_meetings  = db.relationship('ScheduledMeeting', backref='counsellor', lazy=True, foreign_keys='ScheduledMeeting.counsellor_id')
    student_meetings    = db.relationship('ScheduledMeeting', backref='student', lazy=True, foreign_keys='ScheduledMeeting.student_id')
    
    # Health tracking relationships
    medications         = db.relationship('Medication', backref='user', lazy=True, cascade='all, delete-orphan')
    hydration_logs      = db.relationship('HydrationLog', backref='user', lazy=True, cascade='all, delete-orphan')
    pain_logs           = db.relationship('PainLog', backref='user', lazy=True, cascade='all, delete-orphan')
    substance_logs      = db.relationship('SubstanceLog', backref='user', lazy=True, cascade='all, delete-orphan')
    cycle_logs          = db.relationship('CycleLog', backref='user', lazy=True, cascade='all, delete-orphan')
    sleep_logs          = db.relationship('SleepLog', backref='user', lazy=True, cascade='all, delete-orphan')
    nutrition_logs      = db.relationship('NutritionLog', backref='user', lazy=True, cascade='all, delete-orphan')
    exercise_logs       = db.relationship('ExerciseLog', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, pw):   self.password_hash = generate_password_hash(pw)
    def check_password(self, pw): return check_password_hash(self.password_hash, pw)

    @property
    def is_authenticated(self): return True
    @property
    def is_anonymous(self):     return False
    def get_id(self):           return str(self.id)


class CheckIn(db.Model):
    id                = db.Column(db.Integer, primary_key=True)
    user_id           = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mood_score        = db.Column(db.Integer, nullable=False)
    stress_level      = db.Column(db.Integer)
    sleep_hours       = db.Column(db.Float)
    physical_activity = db.Column(db.String(50))
    notes             = db.Column(db.Text)
    ai_feedback       = db.Column(db.Text)
    timestamp         = db.Column(db.DateTime, default=dt.utcnow)


# =============================================================================
#  HEALTH TRACKING MODELS
# =============================================================================

class Medication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    dosage = db.Column(db.String(100))
    frequency = db.Column(db.String(100))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=dt.utcnow)
    doses_taken = db.relationship('MedicationDose', backref='medication', lazy=True, cascade='all, delete-orphan')


class MedicationDose(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    medication_id = db.Column(db.Integer, db.ForeignKey('medication.id'), nullable=False)
    taken_at = db.Column(db.DateTime, default=dt.utcnow)


class HydrationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount_ml = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=dt.utcnow)


class PainLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pain_level = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(100))
    duration_minutes = db.Column(db.Integer)
    notes = db.Column(db.Text)
    recorded_datetime = db.Column(db.DateTime, default=dt.utcnow)
    created_at = db.Column(db.DateTime, default=dt.utcnow)


class SubstanceLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    substance_type = db.Column(db.String(20), nullable=False)
    caffeine_mg = db.Column(db.Integer)
    alcohol_units = db.Column(db.Float)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=dt.utcnow)


class CycleLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    cycle_day = db.Column(db.Integer)
    flow_level = db.Column(db.String(20))
    symptoms = db.Column(db.Text)
    mood = db.Column(db.String(50))
    notes = db.Column(db.Text)
    logged_at = db.Column(db.DateTime, default=dt.utcnow)


class SleepLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bedtime = db.Column(db.Time)
    wake_time = db.Column(db.Time)
    duration_hours = db.Column(db.Float)
    quality = db.Column(db.Integer)
    notes = db.Column(db.Text)
    date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=dt.utcnow)


class NutritionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    meal_type = db.Column(db.String(50))
    food_items = db.Column(db.Text)
    calories = db.Column(db.Integer)
    protein_g = db.Column(db.Float)
    carbs_g = db.Column(db.Float)
    fat_g = db.Column(db.Float)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=dt.utcnow)


class ExerciseLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    exercise_type = db.Column(db.String(100))
    duration_minutes = db.Column(db.Integer)
    intensity = db.Column(db.String(20))
    calories_burned = db.Column(db.Integer)
    notes = db.Column(db.Text)
    date = db.Column(db.Date, nullable=False)
    logged_at = db.Column(db.DateTime, default=dt.utcnow)
    created_at = db.Column(db.DateTime, default=dt.utcnow)


class ForumPost(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category     = db.Column(db.String(50))
    title        = db.Column(db.String(200), nullable=False)
    content      = db.Column(db.Text,        nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False)
    is_pinned    = db.Column(db.Boolean, default=False)
    likes        = db.Column(db.Integer, default=0)
    timestamp    = db.Column(db.DateTime, default=dt.utcnow)
    replies      = db.relationship('ForumReply', backref='post', lazy=True, cascade='all, delete-orphan')


class ForumReply(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    post_id      = db.Column(db.Integer, db.ForeignKey('forum_post.id', ondelete='CASCADE'), nullable=False)
    user_id      = db.Column(db.Integer, db.ForeignKey('user.id'),       nullable=False)
    content      = db.Column(db.Text, nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False)
    timestamp    = db.Column(db.DateTime, default=dt.utcnow)
    user         = db.relationship('User', foreign_keys=[user_id], lazy=True)


class Booking(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    student_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    counsellor_id  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    session_type   = db.Column(db.String(50))
    preferred_date = db.Column(db.DateTime)
    reason         = db.Column(db.Text)
    status         = db.Column(db.String(20), default='pending')
    notes          = db.Column(db.Text)
    created_at     = db.Column(db.DateTime,   default=dt.utcnow)


class ScheduledMeeting(db.Model):
    """Model for scheduled video/audio meetings between counsellors and students"""
    id             = db.Column(db.Integer, primary_key=True)
    counsellor_id  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title          = db.Column(db.String(200), nullable=False)
    meeting_date   = db.Column(db.DateTime, nullable=False)
    duration       = db.Column(db.Integer, default=45)  # minutes
    meeting_type   = db.Column(db.String(20), default='video')  # video, audio, in-person
    agenda         = db.Column(db.Text)
    status         = db.Column(db.String(20), default='scheduled')  # scheduled, completed, cancelled
    reminder_sent  = db.Column(db.Boolean, default=False)
    meeting_link   = db.Column(db.String(500))
    created_at     = db.Column(db.DateTime, default=dt.utcnow)


class SOSAlert(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message      = db.Column(db.Text)
    location     = db.Column(db.Text)  # Store as JSON string
    status       = db.Column(db.String(20),  default='active')
    responded_by = db.Column(db.Integer,     db.ForeignKey('user.id'), nullable=True)
    created_at   = db.Column(db.DateTime,    default=dt.utcnow)
    resolved_at  = db.Column(db.DateTime)


class Resource(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    title         = db.Column(db.String(200), nullable=False)
    category      = db.Column(db.String(50))
    content       = db.Column(db.Text)
    url           = db.Column(db.String(300))
    resource_type = db.Column(db.String(30))
    is_featured   = db.Column(db.Boolean, default=False)
    created_at    = db.Column(db.DateTime, default=dt.utcnow)


class Announcement(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.String(200))
    content    = db.Column(db.Text)
    author_id  = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=dt.utcnow)


class Event(db.Model):
    id                = db.Column(db.Integer, primary_key=True)
    title             = db.Column(db.String(200), nullable=False)
    description       = db.Column(db.Text)
    location          = db.Column(db.String(200))
    event_type        = db.Column(db.String(50))
    start_time        = db.Column(db.DateTime, nullable=False)
    end_time          = db.Column(db.DateTime)
    max_attendees     = db.Column(db.Integer, default=50)
    target_audience   = db.Column(db.String(20), default='all')
    is_active         = db.Column(db.Boolean,  default=True)
    reminder_sent_24h = db.Column(db.Boolean,  default=False)
    reminder_sent_1h  = db.Column(db.Boolean,  default=False)
    created_by        = db.Column(db.Integer,  db.ForeignKey('user.id'))
    created_at        = db.Column(db.DateTime, default=dt.utcnow)


class StudentReward(db.Model):
    id                = db.Column(db.Integer, primary_key=True)
    user_id           = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    total_points      = db.Column(db.Integer, default=0)
    current_streak    = db.Column(db.Integer, default=0)
    longest_streak    = db.Column(db.Integer, default=0)
    total_checkins    = db.Column(db.Integer, default=0)
    last_checkin_date = db.Column(db.Date)
    tier              = db.Column(db.String(20), default='Bronze')
    updated_at        = db.Column(db.DateTime,   default=dt.utcnow)

    user = db.relationship('User', foreign_keys=[user_id], lazy=True,
                           backref=db.backref('reward', uselist=False))

    @property
    def tier_info(self):
        p = self.total_points
        if p >= 700: return ('🌟', 'Thriver',  '#7c3aed', None)
        if p >= 300: return ('🌸', 'Bloomer',  '#ec4899', 700)
        if p >= 100: return ('🌿', 'Grower',   '#10b981', 300)
        return            ('🌱', 'Seedling', '#f59e0b', 100)

    @property
    def progress_pct(self):
        p = self.total_points
        steps = [0, 100, 300, 700]
        for i, t in enumerate(steps):
            if p < t:
                prev = steps[i - 1] if i else 0
                return int((p - prev) / (t - prev) * 100)
        return 100

    def recalc_tier(self):
        p = self.total_points
        if   p >= 700: self.tier = 'Platinum'
        elif p >= 300: self.tier = 'Gold'
        elif p >= 100: self.tier = 'Silver'
        else:          self.tier = 'Bronze'


class RewardLog(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    points     = db.Column(db.Integer, nullable=False)
    reason     = db.Column(db.String(200), nullable=False)
    badge      = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=dt.utcnow)
    user       = db.relationship('User', foreign_keys=[user_id], lazy=True)


# =============================================================================
#  DATABASE MIGRATION HELPER
# =============================================================================

def migrate_database():
    """Add missing columns to existing tables if needed."""
    with app.app_context():
        inspector = db.inspect(db.engine)
        
        if 'user' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('user')]
            
            if 'last_login' not in columns:
                print("Adding missing 'last_login' column to user table...")
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE user ADD COLUMN last_login DATETIME'))
                    conn.commit()
                print("Column added successfully!")
            
            if 'reset_token' not in columns:
                print("Adding missing 'reset_token' column to user table...")
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE user ADD COLUMN reset_token VARCHAR(100)'))
                    conn.commit()
                print("Column added successfully!")
            
            if 'reset_token_expiry' not in columns:
                print("Adding missing 'reset_token_expiry' column to user table...")
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE user ADD COLUMN reset_token_expiry DATETIME'))
                    conn.commit()
                print("Column added successfully!")


# =============================================================================
#  FLASK SETUP
# =============================================================================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.context_processor
def inject_globals():
    reward = None
    if current_user.is_authenticated and current_user.role == 'student':
        reward = StudentReward.query.filter_by(user_id=current_user.id).first()
    return {'now': dt.utcnow(), 'student_reward': reward}


# =============================================================================
#  ACCESS DECORATORS
# =============================================================================

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def counsellor_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['counsellor', 'admin']:
            flash('Counsellor access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# =============================================================================
#  HELPER FUNCTIONS
# =============================================================================

def generate_temp_password(length=10):
    """Generate a random temporary password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%&"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_meeting_link():
    """Generate a unique meeting link for video calls."""
    meeting_id = secrets.token_urlsafe(12)
    return f"https://dut-wellness.zoom.us/j/{meeting_id}"


# =============================================================================
#  EMAIL HELPER
# =============================================================================

def send_email(to, subject, body, html=None):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = MAIL_FROM
        msg['To']      = to
        msg.attach(MIMEText(body, 'plain'))
        if html:
            msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as s:
            s.ehlo()
            s.starttls()
            s.login(MAIL_USERNAME, MAIL_PASSWORD)
            s.sendmail(MAIL_USERNAME, to, msg.as_string())
        return True
    except Exception as e:
        print(f'[Email error] {e}')
        return False


# =============================================================================
#  EMAIL BUILDERS — BOOKINGS
# =============================================================================

def email_booking_new(booking, student, counsellor):
    ds = booking.preferred_date.strftime('%A, %d %B %Y at %I:%M %p') if booking.preferred_date else 'TBC'

    c_html = f"""<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">
      <div style="background:linear-gradient(135deg,#003087,#1d4ed8);padding:24px;border-radius:12px 12px 0 0;color:#fff;text-align:center;">
        <h2 style="margin:0;font-size:1.3rem;">New Session Request</h2>
        <p style="margin:6px 0 0;opacity:.8;font-size:.85rem;">A student has requested a session with you</p>
      </div>
      <div style="background:#fff;border:1px solid #e2e8f0;padding:24px;border-radius:0 0 12px 12px;">
        <table style="width:100%;border-collapse:collapse;font-size:.88rem;">
                <tr><td style="padding:8px 0;color:#64748b;width:140px;"><b>Student</b></td><td>{student.full_name} ({student.student_number})</td></tr>
                <tr><td style="padding:8px 0;color:#64748b;"><b>Session Type</b></td><td>{booking.session_type.title()}</td></tr>
                <tr><td style="padding:8px 0;color:#64748b;"><b>Preferred Date</b></td><td>{ds}</td></tr>
                <tr><td style="padding:8px 0;color:#64748b;"><b>Reason</b></td><td>{booking.reason or 'Not specified'}</td></tr>
                <tr><td style="padding:8px 0;color:#64748b;"><b>Phone</b></td><td>{student.phone or 'Not provided'}</td></tr>
              </table>
        <div style="margin-top:16px;padding:12px;background:#eff6ff;border-radius:8px;border-left:4px solid #003087;font-size:.82rem;color:#1e40af;">Log in to the DUT Wellness portal to confirm or decline this request.</div>
        <p style="margin-top:14px;font-size:.75rem;color:#94a3b8;text-align:center;">DUT Wellness Centre · Automated notification</p>
      </div></div>"""

    s_html = f"""<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">
      <div style="background:linear-gradient(135deg,#003087,#1d4ed8);padding:24px;border-radius:12px 12px 0 0;color:#fff;text-align:center;">
        <h2 style="margin:0;font-size:1.3rem;">Booking Request Received</h2>
        <p style="margin:6px 0 0;opacity:.8;font-size:.85rem;">Your request has been submitted</p>
      </div>
      <div style="background:#fff;border:1px solid #e2e8f0;padding:24px;border-radius:0 0 12px 12px;">
        <p>Hi <b>{student.full_name.split()[0]}</b>, your request has been sent to <b>{counsellor.full_name}</b>. You will hear back within 24 hours.</p>
        <table style="width:100%;border-collapse:collapse;font-size:.88rem;margin-top:14px;">
                <tr><td style="padding:8px 0;color:#64748b;width:140px;"><b>Counsellor</b></td><td>{counsellor.full_name}</td></tr>
                <tr><td style="padding:8px 0;color:#64748b;"><b>Session Type</b></td><td>{booking.session_type.title()}</td></tr>
                <tr><td style="padding:8px 0;color:#64748b;"><b>Requested Date</b></td><td>{ds}</td></tr>
                <tr><td style="padding:8px 0;color:#64748b;"><b>Status</b></td><td><span style="background:#fef9c3;color:#854d0e;padding:2px 10px;border-radius:99px;font-size:.75rem;font-weight:700;">PENDING</span></td></tr>
              </table>
        <div style="margin-top:16px;padding:12px;background:#f0fdf4;border-radius:8px;border-left:4px solid #10b981;font-size:.82rem;color:#065f46;">Need immediate support? Call <b>0800-567-567</b> (24/7 crisis line).</div>
        <p style="margin-top:14px;font-size:.75rem;color:#94a3b8;text-align:center;">DUT Wellness Centre · Automated notification</p>
      </div></div>"""

    send_email(counsellor.email, f'New Session Request from {student.full_name}',
               f'New booking from {student.full_name} for a {booking.session_type} session.', c_html)
    send_email(student.email, 'Your Booking Request Has Been Submitted – DUT Wellness',
               f'Your session request has been submitted. {counsellor.full_name} will confirm soon.', s_html)


def email_booking_update(booking, student, status, counsellor_name='Your counsellor'):
    confirmed = status == 'confirmed'
    ds = booking.preferred_date.strftime('%A, %d %B %Y at %I:%M %p') if booking.preferred_date else 'TBC'
    col = '#059669' if confirmed else '#dc2626'
    bg = '#ecfdf5' if confirmed else '#fef2f2'
    lbl = 'CONFIRMED' if confirmed else 'DECLINED'
    icon = '🎉' if confirmed else '❌'
    body = (f'Great news! Your session with <b>{counsellor_name}</b> is confirmed for <b>{ds}</b>. Please arrive 5 minutes early.'
            if confirmed else
            f'Your session request was declined by <b>{counsellor_name}</b>. Please rebook or call 031-373-2000.')
    tip = 'Bring any notes or topics you want to discuss.' if confirmed else 'You can rebook anytime on the portal.'
    notes_row = f'<tr><td style="padding:8px 0;color:#64748b;width:140px;"><b>Notes</b></td><td>{booking.notes}</td></tr>' if booking.notes else ''

    html = f"""<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">
      <div style="background:linear-gradient(135deg,{col},{col}cc);padding:24px;border-radius:12px 12px 0 0;color:#fff;text-align:center;">
        <div style="font-size:2.5rem;margin-bottom:8px;">{icon}</div>
        <h2 style="margin:0;font-size:1.3rem;">Session {'Confirmed!' if confirmed else 'Declined'}</h2>
      </div>
      <div style="background:#fff;border:1px solid #e2e8f0;padding:24px;border-radius:0 0 12px 12px;">
        <p>Hi <b>{student.full_name.split()[0]}</b>,</p>
        <p style="color:#64748b;font-size:.88rem;line-height:1.6;">{body}</p>
        <table style="width:100%;border-collapse:collapse;font-size:.88rem;margin-top:14px;">
                <tr><td style="padding:8px 0;color:#64748b;width:140px;"><b>Counsellor</b></td><td>{counsellor_name}</td></tr>
                <tr><td style="padding:8px 0;color:#64748b;"><b>Session Type</b></td><td>{booking.session_type.title()}</td></tr>
                <tr><td style="padding:8px 0;color:#64748b;"><b>Date</b></td><td>{ds}</td></tr>
                <tr><td style="padding:8px 0;color:#64748b;"><b>Status</b></td><td><span style="background:{bg};color:{col};padding:2px 10px;border-radius:99px;font-size:.75rem;font-weight:700;">{lbl}</span></td></tr>
                {notes_row}
              </table>
        <div style="margin-top:16px;padding:12px;background:{bg};border-radius:8px;border-left:4px solid {col};font-size:.82rem;color:{col};">{tip}</div>
        <p style="margin-top:14px;font-size:.75rem;color:#94a3b8;text-align:center;">DUT Wellness Centre · Automated notification</p>
      </div></div>"""

    send_email(student.email, f'Your Session Has Been {status.title()} – DUT Wellness',
               f'Your session has been {status}.', html)


# =============================================================================
#  SOS EMAIL WITH LOCATION
# =============================================================================

def send_sos_email(alert, counsellor, student):
    """Send SOS alert email with location map"""
    location_data = None
    if alert.location:
        try:
            location_data = json.loads(alert.location)
        except:
            location_data = None
    
    location_html = ''
    
    if location_data and location_data.get('lat') and location_data.get('lng'):
        lat = location_data.get('lat')
        lng = location_data.get('lng')
        address = location_data.get('address', 'Address not available')
        accuracy = location_data.get('accuracy', 'Unknown')
        
        google_maps_link = f"https://www.google.com/maps?q={lat},{lng}"
        map_url = f"https://staticmap.openstreetmap.de/staticmap.php?center={lat},{lng}&zoom=15&size=600x300&maptype=mapnik&markers={lat},{lng},red-pushpin"
        
        location_html = f"""
        <div style="background:#fef2f2; padding: 1rem; border-radius: 8px; margin: 1rem 0; border-left: 4px solid #dc2626;">
            <h4 style="margin: 0 0 0.5rem 0;"><i class="fas fa-location-dot"></i> Student Location</h4>
            <p><strong>Address:</strong> {address}</p>
            <p><strong>Coordinates:</strong> {lat}, {lng}</p>
            <p><strong>Accuracy:</strong> ±{accuracy} meters</p>
            <p><strong>Time:</strong> {location_data.get('timestamp', 'Unknown')}</p>
            <div style="margin-top: 0.5rem;">
                <a href="{google_maps_link}" target="_blank" style="display: inline-block; background: #dc2626; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; margin-right: 8px;">
                    Open in Google Maps
                </a>
                <a href="https://waze.com/ul?ll={lat},{lng}&navigate=yes" target="_blank" style="display: inline-block; background: #3b82f6; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none;">
                    Navigate with Waze
                </a>
            </div>
            <div style="margin-top: 1rem;">
                <img src="{map_url}" style="width: 100%; max-width: 600px; border-radius: 8px; border: 1px solid #e5e7eb;" alt="Location Map">
            </div>
        </div>
        """
    
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #dc2626, #ef4444); padding: 24px; border-radius: 12px 12px 0 0; color: white; text-align: center;">
            <div style="font-size: 48px; margin-bottom: 8px;">🚨</div>
            <h2 style="margin: 0; font-size: 24px;">SOS ALERT - URGENT</h2>
            <p style="margin: 8px 0 0; opacity: 0.9;">Student requires immediate assistance</p>
        </div>
        
        <div style="background: white; border: 1px solid #e5e7eb; padding: 24px; border-radius: 0 0 12px 12px;">
            <div style="background: #fef2f2; padding: 16px; border-radius: 8px; margin-bottom: 20px;">
                <h3 style="margin: 0 0 8px 0; color: #dc2626;">Student Information</h3>
                <p><strong>Name:</strong> {student.full_name}</p>
                <p><strong>Student Number:</strong> {student.student_number}</p>
                <p><strong>Phone:</strong> {student.phone or 'Not provided'}</p>
                <p><strong>Emergency Contact:</strong> {student.emergency_contact or 'Not set'} ({student.emergency_phone or 'N/A'})</p>
            </div>
            
            <div style="background: #fef9c3; padding: 16px; border-radius: 8px; margin-bottom: 20px;">
                <h3 style="margin: 0 0 8px 0; color: #92400e;">Message</h3>
                <p style="margin: 0;">{alert.message}</p>
            </div>
            
            {location_html}
            
            <div style="margin-top: 20px; text-align: center;">
                <a href="{url_for('view_student', student_id=student.id, _external=True)}" style="display: inline-block; background: #dc2626; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; margin-right: 10px;">
                    View Student Profile
                </a>
                <a href="{url_for('respond_sos', sos_id=alert.id, _external=True)}" style="display: inline-block; background: #10b981; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none;">
                    Mark as Responded
                </a>
            </div>
            
            <p style="margin-top: 20px; font-size: 12px; color: #9ca3af; text-align: center;">
                This is an automated emergency alert from DUT Wellness Centre.<br>
                Please respond immediately.
            </p>
        </div>
    </div>
    """
    
    send_email(counsellor.email, f'🚨 URGENT: SOS Alert from {student.full_name}', 
               f'SOS Alert from {student.full_name}. Please check the portal immediately.', html)


# =============================================================================
#  MEETING REMINDER EMAIL
# =============================================================================

def send_meeting_reminder_email(meeting, student, counsellor):
    meeting_time = meeting.meeting_date.strftime('%A, %d %B %Y at %I:%M %p')
    
    html = f"""<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">
      <div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:24px;border-radius:12px 12px 0 0;color:#fff;text-align:center;">
        <div style="font-size:2rem;margin-bottom:8px;">📅</div>
        <h2 style="margin:0;font-size:1.3rem;">Meeting Reminder</h2>
        <p style="margin:6px 0 0;opacity:.8;font-size:.85rem;">Your session starts in 45 minutes</p>
      </div>
      <div style="background:#fff;border:1px solid #e2e8f0;padding:24px;border-radius:0 0 12px 12px;">
        <p>Hi <b>{student.full_name.split()[0]}</b>,</p>
        <p style="color:#64748b;font-size:.88rem;line-height:1.6;">This is a reminder that your meeting <b>"{meeting.title}"</b> with Counsellor <b>{counsellor.full_name}</b> starts in 45 minutes.</p>
        
        <table style="width:100%;border-collapse:collapse;font-size:.88rem;margin:1rem 0;">
           ...
         </table>
        
        {f'<div style="margin:1rem 0;padding:12px;background:#eef2ff;border-radius:8px;text-align:center;"><a href="{meeting.meeting_link}" style="display:inline-block;padding:12px 24px;background:#6366f1;color:white;text-decoration:none;border-radius:8px;font-weight:600;">Join Meeting →</a></div>' if meeting.meeting_link else ''}
        
        <p style="margin-top:14px;font-size:.75rem;color:#94a3b8;text-align:center;">DUT Wellness Centre · Automated notification</p>
      </div></div>"""
    
    send_email(student.email, f'Reminder: {meeting.title} – DUT Wellness',
               f'Your meeting "{meeting.title}" with {counsellor.full_name} starts in 45 minutes.', html)


# =============================================================================
#  EMAIL BUILDERS — EVENTS
# =============================================================================

def _event_html(event, window_label=None, cancelled=False):
    icons = {'workshop': '🛠️', 'webinar': '💻', 'group': '👥', 'seminar': '🎓'}
    icon = icons.get(event.event_type or '', '📅')
    start = event.start_time.strftime('%A, %d %B %Y at %I:%M %p')
    end = event.end_time.strftime('%I:%M %p') if event.end_time else 'TBC'
    if cancelled:
        hbg = 'linear-gradient(135deg,#dc2626,#b91c1c)'; htxt = 'Event Cancelled'
    elif window_label:
        hbg = 'linear-gradient(135deg,#7c3aed,#4f46e5)'; htxt = f'Event Reminder — {window_label} away'
    else:
        hbg = 'linear-gradient(135deg,#0891b2,#0e7490)'; htxt = 'New Wellness Event'

    return f"""<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">
      <div style="background:{hbg};padding:26px 24px;border-radius:12px 12px 0 0;color:#fff;text-align:center;">
        <div style="font-size:2.6rem;margin-bottom:8px;">{icon}</div>
        <h2 style="margin:0;font-size:1.3rem;">{htxt}</h2>
      </div>
      <div style="background:#fff;border:1px solid #e2e8f0;padding:24px;border-radius:0 0 12px 12px;">
        <h3 style="margin:0 0 4px;">{event.title}</h3>
        <p style="color:#64748b;font-size:.84rem;margin:0 0 16px;">{event.description or ''}</p>
        <table style="width:100%;border-collapse:collapse;font-size:.87rem;">
                ...
         </table>
        <div style="margin-top:16px;padding:12px;background:#fff5f5;border-radius:8px;border-left:4px solid #dc2626;font-size:.8rem;color:#991b1b;">Need urgent help? Call <b>0800-567-567</b> (24/7).</div>
        <p style="margin-top:14px;font-size:.75rem;color:#94a3b8;text-align:center;">DUT Wellness Centre · Automated notification</p>
      </div></div>"""


def _event_recipients(event):
    a = event.target_audience or 'all'
    roles = ['student'] if a == 'students' else (['counsellor'] if a == 'counsellors' else ['student', 'counsellor', 'admin'])
    return User.query.filter(User.role.in_(roles), User.is_active == True).all()


def email_event_created(event):
    html = _event_html(event)
    plain = f'New event: "{event.title}" on {event.start_time.strftime("%d %b %Y at %I:%M %p")}. Location: {event.location or "TBA"}.'
    sent = sum(1 for u in _event_recipients(event) if send_email(u.email, f'New Event: "{event.title}" – DUT Wellness', plain, html))
    print(f'[Event created] "{event.title}" → {sent} emails sent')
    return sent


def email_event_reminder(event, window_label):
    html = _event_html(event, window_label=window_label)
    plain = f'Reminder: "{event.title}" starts in {window_label}. Location: {event.location or "TBA"}.'
    sent = sum(1 for u in _event_recipients(event) if send_email(u.email, f'Reminder: "{event.title}" in {window_label} – DUT Wellness', plain, html))
    print(f'[Event reminder {window_label}] "{event.title}" → {sent} sent')
    return sent


def email_event_cancelled(event):
    html = _event_html(event, cancelled=True)
    start = event.start_time.strftime('%d %b %Y at %I:%M %p')
    plain = f'The event "{event.title}" on {start} has been cancelled.'
    return sum(1 for u in _event_recipients(event) if send_email(u.email, f'Event Cancelled: "{event.title}" – DUT Wellness', plain, html))


def email_inactivity_reminder(student):
    fn = student.full_name.split()[0]
    html = f"""<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">
      <div style="background:linear-gradient(135deg,#0f172a,#312e81);padding:24px;border-radius:12px 12px 0 0;color:#fff;text-align:center;">
        <div style="font-size:2.5rem;margin-bottom:8px;">💙</div>
        <h2 style="margin:0;font-size:1.3rem;">We Miss You, {fn}!</h2>
        <p style="margin:6px 0 0;opacity:.75;font-size:.85rem;">Your wellness matters to us</p>
      </div>
      <div style="background:#fff;border:1px solid #e2e8f0;padding:24px;border-radius:0 0 12px 12px;">
        <p>Hi <b>{fn}</b>, we noticed you haven't logged in for 2 days. Even a 2-minute check-in earns you <b>reward points</b> and helps track your wellbeing.</p>
        <div style="text-align:center;margin:20px 0;">
          <a href="http://localhost:5000/checkin" style="display:inline-block;padding:12px 28px;background:linear-gradient(135deg,#003087,#1d4ed8);color:#fff;border-radius:10px;text-decoration:none;font-weight:700;font-size:.88rem;">Log Today's Check-in (+10 pts) →</a>
        </div>
        <div style="padding:12px;background:#fff5f5;border-radius:8px;border-left:4px solid #dc2626;font-size:.8rem;color:#991b1b;">Struggling? Call <b>0800-567-567</b> (24/7).</div>
        <p style="margin-top:14px;font-size:.75rem;color:#94a3b8;text-align:center;">DUT Wellness Centre · Your wellness matters 💙</p>
      </div></div>"""
    send_email(student.email, f'We miss you, {fn} 💙 — DUT Wellness',
               f'Hi {fn}, you have not logged in for 2 days. Check in to earn reward points!', html)


# =============================================================================
#  REWARDS ENGINE
# =============================================================================

POINTS_CHECKIN   = 10
POINTS_STREAK_3  =  5
POINTS_STREAK_7  = 15
POINTS_STREAK_30 = 25


def award_checkin_points(user):
    today = dt.utcnow().date()
    reward = StudentReward.query.filter_by(user_id=user.id).first()
    if not reward:
        reward = StudentReward(user_id=user.id)
        db.session.add(reward)

    logs = []
    earned = 0

    reward.total_checkins += 1
    earned += POINTS_CHECKIN
    logs.append(RewardLog(user_id=user.id, points=POINTS_CHECKIN, reason='Daily check-in', badge='✅'))

    if reward.last_checkin_date is None:
        reward.current_streak = 1
    elif reward.last_checkin_date == today:
        pass
    elif reward.last_checkin_date == today - timedelta(days=1):
        reward.current_streak += 1
    else:
        reward.current_streak = 1

    if reward.current_streak > reward.longest_streak:
        reward.longest_streak = reward.current_streak

    reward.last_checkin_date = today

    if reward.current_streak == 3:
        earned += POINTS_STREAK_3
        logs.append(RewardLog(user_id=user.id, points=POINTS_STREAK_3, reason='3-day streak bonus', badge='🔥'))
    elif reward.current_streak == 7:
        earned += POINTS_STREAK_7
        logs.append(RewardLog(user_id=user.id, points=POINTS_STREAK_7, reason='7-day streak — one full week!', badge='🏆'))
    elif reward.current_streak == 30:
        earned += POINTS_STREAK_30
        logs.append(RewardLog(user_id=user.id, points=POINTS_STREAK_30, reason='30-day streak — incredible!', badge='💎'))

    reward.total_points += earned
    reward.recalc_tier()
    reward.updated_at = dt.utcnow()

    for log in logs:
        db.session.add(log)

    db.session.commit()
    return earned, reward, logs


# =============================================================================
#  AI FEEDBACK
# =============================================================================

def get_ai_feedback(mood, stress, sleep, notes):
    tips = {
        'low_mood':    ['Consider talking to a counsellor.', 'Try a 10-minute walk outside.', 'Reach out to a friend or peer.'],
        'high_stress': ['Practice deep breathing.', 'Break tasks into smaller steps.', 'Take a 15-min break every 2 hours.'],
        'poor_sleep':  ['Avoid screens 1 h before bed.', 'Keep a consistent sleep schedule.', 'Limit caffeine after 2 pm.'],
        'positive':    ['Great job maintaining your wellness!', 'Keep up those positive habits!', 'Share your tips in the peer forum!'],
    }
    fb = []
    if mood <= 4:                                    fb.extend(tips['low_mood'])
    if stress and stress >= 7:                       fb.extend(tips['high_stress'])
    if sleep and sleep < 6:                          fb.extend(tips['poor_sleep'])
    if mood >= 8 and (not stress or stress <= 4):   fb.extend(tips['positive'])
    if not fb:
        fb = ['Keep monitoring your wellness daily.', 'Stay connected with the DUT community.', 'Help is always available.']
    return ' | '.join(fb[:3])


# =============================================================================
#  BACKGROUND SCHEDULER
# =============================================================================

def run_background_scheduler():
    INACTIVITY_INTERVAL = 43200
    LOOP_SLEEP = 1800
    last_inactivity = 0

    while True:
        time_module.sleep(LOOP_SLEEP)
        now = time_module.time()
        try:
            with app.app_context():
                dt_now = dt.utcnow()

                if now - last_inactivity >= INACTIVITY_INTERVAL:
                    cutoff = dt_now - timedelta(days=2)
                    for s in User.query.filter(User.role == 'student', User.is_active == True, User.last_login < cutoff).all():
                        email_inactivity_reminder(s)
                        print(f'[Inactivity] sent to {s.full_name}')
                    last_inactivity = now

                reminder_time = dt_now + timedelta(minutes=45)
                meetings = ScheduledMeeting.query.filter(
                    ScheduledMeeting.status == 'scheduled',
                    ScheduledMeeting.reminder_sent == False,
                    ScheduledMeeting.meeting_date <= reminder_time,
                    ScheduledMeeting.meeting_date >= dt_now
                ).all()
                
                for meeting in meetings:
                    student = User.query.get(meeting.student_id)
                    counsellor = User.query.get(meeting.counsellor_id)
                    if student and counsellor:
                        send_meeting_reminder_email(meeting, student, counsellor)
                        meeting.reminder_sent = True
                        db.session.commit()
                        print(f'[Meeting Reminder] Sent for meeting {meeting.id} to {student.email}')

                for ev in Event.query.filter(Event.is_active == True, Event.reminder_sent_24h == False,
                                             Event.start_time >= dt_now + timedelta(hours=22),
                                             Event.start_time <= dt_now + timedelta(hours=26)).all():
                    email_event_reminder(ev, '24 hours')
                    ev.reminder_sent_24h = True
                    db.session.commit()

                for ev in Event.query.filter(Event.is_active == True, Event.reminder_sent_1h == False,
                                             Event.start_time >= dt_now + timedelta(minutes=45),
                                             Event.start_time <= dt_now + timedelta(hours=2)).all():
                    email_event_reminder(ev, '1 hour')
                    ev.reminder_sent_1h = True
                    db.session.commit()

        except Exception as e:
            print(f'[Scheduler error] {e}')


# =============================================================================
#  AUTH ROUTES
# =============================================================================

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(f'{current_user.role}_dashboard'))
    if request.method == 'POST':
        ident = request.form.get('identifier', '').strip()
        pw = request.form.get('password', '')
        user = User.query.filter((User.student_number == ident) | (User.email == ident)).first()
        if user and user.check_password(pw) and user.is_active:
            user.last_login = dt.utcnow()
            db.session.commit()
            login_user(user, remember=request.form.get('remember'))
            flash(f'Welcome back, {user.full_name.split()[0]}!', 'success')
            return redirect(url_for(f'{user.role}_dashboard'))
        flash('Invalid credentials. Please try again.', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        sn = request.form.get('student_number', '').strip().upper()
        nm = request.form.get('full_name', '').strip()
        em = request.form.get('email', '').strip().lower()
        pw = request.form.get('password', '')
        pw2 = request.form.get('confirm_password', '')
        if not all([sn, nm, em, pw]):
            flash('All required fields must be filled.', 'danger'); return render_template('register.html')
        if pw != pw2:
            flash('Passwords do not match.', 'danger'); return render_template('register.html')
        if len(pw) < 8:
            flash('Password must be at least 8 characters.', 'danger'); return render_template('register.html')
        if User.query.filter_by(student_number=sn).first():
            flash('Student number already registered.', 'danger'); return render_template('register.html')
        if User.query.filter_by(email=em).first():
            flash('Email already registered.', 'danger'); return render_template('register.html')
        u = User(student_number=sn, full_name=nm, email=em,
                 faculty=request.form.get('faculty', ''), phone=request.form.get('phone', ''),
                 emergency_contact=request.form.get('emergency_contact', ''),
                 emergency_phone=request.form.get('emergency_phone', ''))
        u.set_password(pw)
        db.session.add(u)
        db.session.commit()
        try:
            send_email(em, 'Welcome to DUT Wellness Centre', f'Welcome {nm}! Your account is ready.')
        except Exception:
            pass
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        em = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=em).first()
        
        if user:
            if request.form.get('method') == 'link':
                tok = secrets.token_urlsafe(32)
                user.reset_token = tok
                user.reset_token_expiry = dt.utcnow() + timedelta(hours=1)
                db.session.commit()
                reset_url = url_for('reset_password', token=tok, _external=True)
                html = f"""
                <div style="font-family: Arial, sans-serif; max-width: 560px; margin: 0 auto;">
                    <div style="background: linear-gradient(135deg, #003087, #1d4ed8); padding: 24px; border-radius: 12px 12px 0 0; color: #fff; text-align: center;">
                        <h2 style="margin: 0;">Password Reset Link</h2>
                    </div>
                    <div style="background: #fff; border: 1px solid #e2e8f0; padding: 24px; border-radius: 0 0 12px 12px;">
                        <p>Hello {user.full_name.split()[0]},</p>
                        <p>Click the button below to reset your password. This link will expire in 1 hour.</p>
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{reset_url}" style="display: inline-block; padding: 12px 30px; background: #003087; color: #fff; text-decoration: none; border-radius: 8px;">Reset Password</a>
                        </div>
                        <p>If you didn't request this, please ignore this email.</p>
                    </div>
                </div>
                """
                send_email(em, 'DUT Wellness – Password Reset', f'Reset link: {reset_url}', html)
            else:
                temp_password = generate_temp_password()
                user.set_password(temp_password)
                user.reset_token = None
                user.reset_token_expiry = None
                db.session.commit()
                html = f"""
                <div style="font-family: Arial, sans-serif; max-width: 560px; margin: 0 auto;">
                    <div style="background: linear-gradient(135deg, #003087, #1d4ed8); padding: 24px; border-radius: 12px 12px 0 0; color: #fff; text-align: center;">
                        <h2 style="margin: 0;">Temporary Password</h2>
                    </div>
                    <div style="background: #fff; border: 1px solid #e2e8f0; padding: 24px; border-radius: 0 0 12px 12px;">
                        <p>Hello {user.full_name.split()[0]},</p>
                        <p>Your password has been reset. Here's your temporary password:</p>
                        <div style="background: #f3f4f6; padding: 15px; border-radius: 8px; text-align: center; margin: 20px 0;">
                            <code style="font-size: 20px; font-weight: bold; letter-spacing: 1px;">{temp_password}</code>
                        </div>
                        <p><strong>Important:</strong> Please log in with this password and change it immediately in your profile settings.</p>
                        <div style="text-align: center; margin: 20px 0;">
                            <a href="{url_for('login', _external=True)}" style="display: inline-block; padding: 12px 30px; background: #003087; color: #fff; text-decoration: none; border-radius: 8px;">Log In Now</a>
                        </div>
                        <p style="color: #dc2626; font-size: 0.85rem;">⚠️ For security reasons, please change this password as soon as you log in.</p>
                    </div>
                </div>
                """
                send_email(em, 'DUT Wellness – Temporary Password', 
                          f'Your temporary password is: {temp_password}\n\nPlease log in and change it immediately.', html)
        
        flash('If that email is registered, password reset instructions have been sent.', 'info')
        return redirect(url_for('login'))
    
    return render_template('forgot_password.html')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.reset_token_expiry or user.reset_token_expiry < dt.utcnow():
        flash('Invalid or expired reset link.', 'danger')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        pw = request.form.get('password', '')
        pw2 = request.form.get('confirm_password', '')
        if pw != pw2:
            flash('Passwords do not match.', 'danger'); return render_template('reset_password.html', token=token)
        if len(pw) < 8:
            flash('Password must be at least 8 characters.', 'danger'); return render_template('reset_password.html', token=token)
        user.set_password(pw)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        flash('Password reset successfully. Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('reset_password.html', token=token)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# =============================================================================
#  STUDENT DASHBOARD
# =============================================================================

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        return redirect(url_for(f'{current_user.role}_dashboard'))
    recent = CheckIn.query.filter_by(user_id=current_user.id).order_by(CheckIn.timestamp.desc()).limit(7).all()
    
    today = dt.utcnow().date()
    hydration_today = db.session.query(db.func.sum(HydrationLog.amount_ml)).filter(
        HydrationLog.user_id == current_user.id, HydrationLog.date == today
    ).scalar() or 0
    
    caffeine_today = db.session.query(db.func.sum(SubstanceLog.caffeine_mg)).filter(
        SubstanceLog.user_id == current_user.id, SubstanceLog.date == today, SubstanceLog.substance_type == 'caffeine'
    ).scalar() or 0
    
    alcohol_today = db.session.query(db.func.sum(SubstanceLog.alcohol_units)).filter(
        SubstanceLog.user_id == current_user.id, SubstanceLog.date == today, SubstanceLog.substance_type == 'alcohol'
    ).scalar() or 0
    
    calories_today = db.session.query(db.func.sum(NutritionLog.calories)).filter(
        NutritionLog.user_id == current_user.id, NutritionLog.date == today
    ).scalar() or 0
    
    exercise_count = ExerciseLog.query.filter_by(user_id=current_user.id, date=today).count()
    pain_count = PainLog.query.filter(db.func.date(PainLog.recorded_datetime) == today, PainLog.user_id == current_user.id).count()
    medications_count = Medication.query.filter_by(user_id=current_user.id).count()
    
    return render_template('student_dashboard.html',
        checkins=recent,
        bookings=Booking.query.filter_by(student_id=current_user.id).order_by(Booking.created_at.desc()).limit(5).all(),
        active_sos=SOSAlert.query.filter_by(user_id=current_user.id, status='active').first(),
        posts=ForumPost.query.order_by(ForumPost.timestamp.desc()).limit(5).all(),
        announcements=Announcement.query.order_by(Announcement.created_at.desc()).limit(3).all(),
        upcoming_events=Event.query.filter(Event.is_active == True, Event.start_time >= dt.utcnow()).order_by(Event.start_time).limit(5).all(),
        mood_data=[c.mood_score for c in reversed(recent)],
        mood_labels=[c.timestamp.strftime('%d %b') for c in reversed(recent)],
        hydration_today=hydration_today,
        caffeine_today=caffeine_today,
        alcohol_today=alcohol_today,
        calories_today=calories_today,
        exercise_count=exercise_count,
        pain_count=pain_count,
        medications_count=medications_count)


# =============================================================================
#  VIDEO SESSIONS ROUTE
# =============================================================================

@app.route('/counsellor/video-sessions')
@login_required
@counsellor_required
def video_sessions():
    students = User.query.filter_by(role='student', is_active=True).all()
    return render_template('video_sessions.html', students=students)


# =============================================================================
#  API ENDPOINTS FOR VIDEO SESSIONS
# =============================================================================

@app.route('/api/counsellor/bookings')
@login_required
@counsellor_required
def get_counsellor_bookings():
    bookings = Booking.query.filter_by(
        counsellor_id=current_user.id,
        status='confirmed'
    ).order_by(Booking.preferred_date).all()
    
    return jsonify([{
        'id': b.id,
        'student_name': b.student.full_name,
        'student_number': b.student.student_number,
        'preferred_date': b.preferred_date.isoformat() if b.preferred_date else None,
        'session_type': b.session_type,
        'status': b.status,
        'reason': b.reason
    } for b in bookings])


@app.route('/api/schedule-meeting', methods=['POST'])
@login_required
@counsellor_required
def schedule_meeting():
    data = request.json
    
    student = User.query.get(data.get('studentId'))
    if not student:
        return jsonify({'error': 'Student not found'}), 404
    
    meeting = ScheduledMeeting(
        counsellor_id=current_user.id,
        student_id=data.get('studentId'),
        title=data.get('title'),
        meeting_date=dt.fromisoformat(data.get('dateTime')),
        duration=data.get('duration', 45),
        meeting_type=data.get('type', 'video'),
        agenda=data.get('agenda', ''),
        meeting_link=generate_meeting_link() if data.get('type') == 'video' else None
    )
    
    db.session.add(meeting)
    db.session.commit()
    
    meeting_time = meeting.meeting_date.strftime('%A, %d %B %Y at %I:%M %p')
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">
        <div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:24px;border-radius:12px 12px 0 0;color:#fff;text-align:center;">
            <h2 style="margin:0;">Meeting Scheduled</h2>
        </div>
        <div style="background:#fff;border:1px solid #e2e8f0;padding:24px;border-radius:0 0 12px 12px;">
            <p>Hi <b>{student.full_name.split()[0]}</b>,</p>
            <p>A meeting has been scheduled with Counsellor <b>{current_user.full_name}</b>.</p>
            <table style="width:100%;margin:1rem 0;">
                <tr><td><b>Title:</b></td><td>{meeting.title}</td></tr>
                <tr><td><b>Date & Time:</b></td><td>{meeting_time}</td></tr>
                <tr><td><b>Duration:</b></td><td>{meeting.duration} minutes</td></tr>
                <tr><td><b>Type:</b></td><td>{meeting.meeting_type.title()}</td></tr>
                {f'<tr><td><b>Agenda:</b></td><td>{meeting.agenda}</td></tr>' if meeting.agenda else ''}
            </table>
            {f'<div style="margin:1rem 0;padding:12px;background:#eef2ff;border-radius:8px;text-align:center;"><a href="{meeting.meeting_link}" style="display:inline-block;padding:12px 24px;background:#6366f1;color:white;text-decoration:none;border-radius:8px;">Join Meeting →</a></div>' if meeting.meeting_link else ''}
            <p style="font-size:0.75rem;color:#6b7280;">You will receive a reminder 45 minutes before the meeting.</p>
        </div>
    </div>
    """
    
    send_email(student.email, f'Meeting Scheduled: {meeting.title} – DUT Wellness',
               f'Your meeting "{meeting.title}" has been scheduled for {meeting_time}', html)
    
    return jsonify({'success': True, 'meeting_id': meeting.id, 'message': 'Meeting scheduled'})


@app.route('/api/send-meeting-reminder', methods=['POST'])
@login_required
@counsellor_required
def send_meeting_reminder():
    data = request.json
    meeting = ScheduledMeeting.query.get(data.get('meetingId'))
    
    if not meeting:
        return jsonify({'error': 'Meeting not found'}), 404
    
    student = User.query.get(meeting.student_id)
    if student:
        send_meeting_reminder_email(meeting, student, current_user)
        meeting.reminder_sent = True
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'error': 'Student not found'}), 404


@app.route('/api/counsellor/meetings')
@login_required
@counsellor_required
def get_counsellor_meetings():
    meetings = ScheduledMeeting.query.filter_by(
        counsellor_id=current_user.id
    ).order_by(ScheduledMeeting.meeting_date).all()
    
    return jsonify([{
        'id': m.id,
        'title': m.title,
        'student_name': m.student.full_name,
        'student_id': m.student.id,
        'meeting_date': m.meeting_date.isoformat(),
        'duration': m.duration,
        'type': m.meeting_type,
        'agenda': m.agenda,
        'status': m.status,
        'meeting_link': m.meeting_link
    } for m in meetings])


# =============================================================================
#  HEALTH TRACKING ROUTES
# =============================================================================

@app.route('/health/medications')
@login_required
def medications():
    meds = Medication.query.filter_by(user_id=current_user.id).order_by(Medication.created_at.desc()).all()
    return render_template('medications.html', medications=meds)


@app.route('/api/medications', methods=['GET'])
@login_required
def get_medications():
    meds = Medication.query.filter_by(user_id=current_user.id).all()
    return jsonify([{
        'id': m.id,
        'name': m.name,
        'dosage': m.dosage,
        'frequency': m.frequency,
        'start_date': m.start_date.isoformat() if m.start_date else None,
        'end_date': m.end_date.isoformat() if m.end_date else None,
        'notes': m.notes,
        'doses_taken': [{'id': d.id, 'taken_at': d.taken_at.isoformat()} for d in m.doses_taken]
    } for m in meds])


@app.route('/api/medications', methods=['POST'])
@login_required
def add_medication():
    data = request.json
    med = Medication(
        user_id=current_user.id,
        name=data.get('name'),
        dosage=data.get('dosage'),
        frequency=data.get('frequency'),
        start_date=dt.strptime(data.get('start_date'), '%Y-%m-%d').date() if data.get('start_date') else None,
        end_date=dt.strptime(data.get('end_date'), '%Y-%m-%d').date() if data.get('end_date') else None,
        notes=data.get('notes')
    )
    db.session.add(med)
    db.session.commit()
    return jsonify({'id': med.id, 'message': 'Medication added successfully'}), 201


@app.route('/api/medications/<int:med_id>/dose', methods=['POST'])
@login_required
def log_medication_dose(med_id):
    med = Medication.query.get_or_404(med_id)
    if med.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    dose = MedicationDose(medication_id=med_id)
    db.session.add(dose)
    db.session.commit()
    
    reward = StudentReward.query.filter_by(user_id=current_user.id).first()
    if reward:
        reward.total_points += 2
        reward.recalc_tier()
        db.session.add(RewardLog(user_id=current_user.id, points=2, reason='Medication dose taken', badge='💊'))
        db.session.commit()
    
    return jsonify({'success': True, 'dose_id': dose.id})


@app.route('/api/medications/<int:med_id>', methods=['DELETE'])
@login_required
def delete_medication(med_id):
    med = Medication.query.get_or_404(med_id)
    if med.user_id != current_user.id and current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    db.session.delete(med)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/health/hydration')
@login_required
def hydration():
    return render_template('hydration.html')


@app.route('/api/hydration', methods=['GET'])
@login_required
def get_hydration():
    today = dt.utcnow().date()
    logs = HydrationLog.query.filter_by(user_id=current_user.id, date=today).order_by(HydrationLog.time).all()
    total = sum(log.amount_ml for log in logs)
    return jsonify({
        'logs': [{'id': l.id, 'amount_ml': l.amount_ml, 'time': l.time.strftime('%H:%M'), 'notes': l.notes} for l in logs],
        'total_ml': total
    })


@app.route('/api/hydration', methods=['POST'])
@login_required
def log_hydration():
    data = request.json
    now = dt.utcnow()
    log = HydrationLog(
        user_id=current_user.id,
        amount_ml=data.get('amount_ml'),
        date=now.date(),
        time=now.time(),
        notes=data.get('notes', '')
    )
    db.session.add(log)
    db.session.commit()
    
    reward = StudentReward.query.filter_by(user_id=current_user.id).first()
    if reward:
        reward.total_points += 1
        reward.recalc_tier()
        db.session.add(RewardLog(user_id=current_user.id, points=1, reason='Hydration logged', badge='💧'))
        db.session.commit()
    
    return jsonify({'id': log.id, 'message': 'Hydration logged successfully'}), 201


@app.route('/health/pain')
@login_required
def pain_logs():
    logs = PainLog.query.filter_by(user_id=current_user.id).order_by(PainLog.recorded_datetime.desc()).all()
    return render_template('pain_logs.html', logs=logs)


@app.route('/api/pain', methods=['GET'])
@login_required
def get_pain():
    logs = PainLog.query.filter_by(user_id=current_user.id).order_by(PainLog.recorded_datetime.desc()).all()
    return jsonify([{
        'id': l.id,
        'pain_level': l.pain_level,
        'location': l.location,
        'duration_minutes': l.duration_minutes,
        'notes': l.notes,
        'datetime': l.recorded_datetime.isoformat()
    } for l in logs])


@app.route('/api/pain', methods=['POST'])
@login_required
def log_pain():
    data = request.json
    log = PainLog(
        user_id=current_user.id,
        pain_level=data.get('pain_level'),
        location=data.get('location'),
        duration_minutes=data.get('duration_minutes'),
        notes=data.get('notes'),
        recorded_datetime=dt.utcnow()
    )
    db.session.add(log)
    db.session.commit()
    
    reward = StudentReward.query.filter_by(user_id=current_user.id).first()
    if reward:
        reward.total_points += 1
        reward.recalc_tier()
        db.session.add(RewardLog(user_id=current_user.id, points=1, reason='Pain logged', badge='📝'))
        db.session.commit()
    
    if data.get('pain_level', 0) >= 8:
        for counsellor in User.query.filter_by(role='counsellor').all():
            send_email(counsellor.email, f'High Pain Alert - {current_user.full_name}',
                      f'{current_user.full_name} reported pain level {data.get("pain_level")}/10')
    
    return jsonify({'id': log.id, 'message': 'Pain logged successfully'}), 201


@app.route('/api/pain/<int:pain_id>', methods=['DELETE'])
@login_required
def delete_pain(pain_id):
    log = PainLog.query.get_or_404(pain_id)
    if log.user_id != current_user.id and current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    db.session.delete(log)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/health/substances')
@login_required
def substances():
    return render_template('substances.html')


@app.route('/api/substances', methods=['GET'])
@login_required
def get_substances():
    today = dt.utcnow().date()
    logs = SubstanceLog.query.filter_by(user_id=current_user.id, date=today).order_by(SubstanceLog.time).all()
    total_caffeine = sum(l.caffeine_mg or 0 for l in logs if l.substance_type == 'caffeine')
    total_alcohol = sum(l.alcohol_units or 0 for l in logs if l.substance_type == 'alcohol')
    return jsonify({
        'logs': [{
            'id': l.id,
            'substance_type': l.substance_type,
            'caffeine_mg': l.caffeine_mg,
            'alcohol_units': l.alcohol_units,
            'time': l.time.strftime('%H:%M'),
            'notes': l.notes
        } for l in logs],
        'total_caffeine_mg': total_caffeine,
        'total_alcohol_units': total_alcohol
    })


@app.route('/api/substances', methods=['POST'])
@login_required
def log_substance():
    data = request.json
    now = dt.utcnow()
    log = SubstanceLog(
        user_id=current_user.id,
        substance_type=data.get('substance_type'),
        caffeine_mg=data.get('caffeine_mg'),
        alcohol_units=data.get('alcohol_units'),
        date=now.date(),
        time=now.time(),
        notes=data.get('notes', '')
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({'id': log.id, 'message': 'Substance logged successfully'}), 201


@app.route('/health/cycle')
@login_required
def cycle():
    logs = CycleLog.query.filter_by(user_id=current_user.id).order_by(CycleLog.logged_at.desc()).all()
    return render_template('cycle.html', logs=logs)


@app.route('/api/cycle', methods=['GET'])
@login_required
def get_cycle():
    logs = CycleLog.query.filter_by(user_id=current_user.id).order_by(CycleLog.logged_at.desc()).all()
    return jsonify([{
        'id': l.id,
        'cycle_day': l.cycle_day,
        'flow_level': l.flow_level,
        'symptoms': l.symptoms,
        'mood': l.mood,
        'notes': l.notes,
        'logged_at': l.logged_at.isoformat()
    } for l in logs])


@app.route('/api/cycle', methods=['POST'])
@login_required
def log_cycle():
    data = request.json
    log = CycleLog(
        user_id=current_user.id,
        cycle_day=data.get('cycle_day'),
        flow_level=data.get('flow_level'),
        symptoms=data.get('symptoms'),
        mood=data.get('mood'),
        notes=data.get('notes'),
        logged_at=dt.utcnow()
    )
    db.session.add(log)
    db.session.commit()
    
    reward = StudentReward.query.filter_by(user_id=current_user.id).first()
    if reward:
        reward.total_points += 2
        reward.recalc_tier()
        db.session.add(RewardLog(user_id=current_user.id, points=2, reason='Cycle tracked', badge='🌸'))
        db.session.commit()
    
    return jsonify({'id': log.id, 'message': 'Cycle logged successfully'}), 201


@app.route('/health/sleep')
@login_required
def sleep_logs():
    logs = SleepLog.query.filter_by(user_id=current_user.id).order_by(SleepLog.date.desc()).all()
    return render_template('sleep_logs.html', logs=logs)


@app.route('/api/sleep', methods=['GET'])
@login_required
def get_sleep():
    logs = SleepLog.query.filter_by(user_id=current_user.id).order_by(SleepLog.date.desc()).all()
    return jsonify([{
        'id': l.id,
        'bedtime': l.bedtime.strftime('%H:%M') if l.bedtime else None,
        'wake_time': l.wake_time.strftime('%H:%M') if l.wake_time else None,
        'duration_hours': l.duration_hours,
        'quality': l.quality,
        'notes': l.notes,
        'date': l.date.isoformat()
    } for l in logs])


@app.route('/api/sleep', methods=['POST'])
@login_required
def log_sleep():
    data = request.json
    bedtime = dt.strptime(data.get('bedtime'), '%H:%M').time() if data.get('bedtime') else None
    wake_time = dt.strptime(data.get('wake_time'), '%H:%M').time() if data.get('wake_time') else None
    
    duration_hours = None
    if bedtime and wake_time:
        bed_dt = dt.combine(dt.utcnow().date(), bedtime)
        wake_dt = dt.combine(dt.utcnow().date(), wake_time)
        if wake_dt < bed_dt:
            wake_dt += timedelta(days=1)
        duration_hours = round((wake_dt - bed_dt).seconds / 3600, 1)
    
    log = SleepLog(
        user_id=current_user.id,
        bedtime=bedtime,
        wake_time=wake_time,
        duration_hours=duration_hours,
        quality=data.get('quality'),
        notes=data.get('notes'),
        date=dt.utcnow().date()
    )
    db.session.add(log)
    db.session.commit()
    
    reward = StudentReward.query.filter_by(user_id=current_user.id).first()
    if reward:
        reward.total_points += 2
        reward.recalc_tier()
        db.session.add(RewardLog(user_id=current_user.id, points=2, reason='Sleep logged', badge='😴'))
        db.session.commit()
    
    return jsonify({'id': log.id, 'message': 'Sleep logged successfully'}), 201


@app.route('/health/nutrition')
@login_required
def nutrition():
    return render_template('nutrition.html')


@app.route('/api/nutrition', methods=['GET'])
@login_required
def get_nutrition():
    today = dt.utcnow().date()
    logs = NutritionLog.query.filter_by(user_id=current_user.id, date=today).order_by(NutritionLog.time).all()
    totals = {'calories': 0, 'protein_g': 0, 'carbs_g': 0, 'fat_g': 0}
    for log in logs:
        totals['calories'] += log.calories or 0
        totals['protein_g'] += log.protein_g or 0
        totals['carbs_g'] += log.carbs_g or 0
        totals['fat_g'] += log.fat_g or 0
    
    return jsonify({
        'logs': [{
            'id': l.id,
            'meal_type': l.meal_type,
            'food_items': l.food_items,
            'calories': l.calories,
            'protein_g': l.protein_g,
            'carbs_g': l.carbs_g,
            'fat_g': l.fat_g,
            'time': l.time.strftime('%H:%M'),
            'notes': l.notes
        } for l in logs],
        'totals': totals
    })


@app.route('/api/nutrition', methods=['POST'])
@login_required
def log_nutrition():
    data = request.json
    now = dt.utcnow()
    log = NutritionLog(
        user_id=current_user.id,
        meal_type=data.get('meal_type'),
        food_items=data.get('food_items'),
        calories=data.get('calories'),
        protein_g=data.get('protein_g'),
        carbs_g=data.get('carbs_g'),
        fat_g=data.get('fat_g'),
        date=now.date(),
        time=now.time(),
        notes=data.get('notes', '')
    )
    db.session.add(log)
    db.session.commit()
    
    reward = StudentReward.query.filter_by(user_id=current_user.id).first()
    if reward:
        reward.total_points += 2
        reward.recalc_tier()
        db.session.add(RewardLog(user_id=current_user.id, points=2, reason='Nutrition logged', badge='🥗'))
        db.session.commit()
    
    return jsonify({'id': log.id, 'message': 'Nutrition logged successfully'}), 201


@app.route('/health/exercise')
@login_required
def exercise():
    logs = ExerciseLog.query.filter_by(user_id=current_user.id).order_by(ExerciseLog.date.desc()).all()
    return render_template('exercise.html', logs=logs)


@app.route('/api/exercise', methods=['GET'])
@login_required
def get_exercise():
    logs = ExerciseLog.query.filter_by(user_id=current_user.id).order_by(ExerciseLog.date.desc()).all()
    return jsonify([{
        'id': l.id,
        'exercise_type': l.exercise_type,
        'duration_minutes': l.duration_minutes,
        'intensity': l.intensity,
        'calories_burned': l.calories_burned,
        'notes': l.notes,
        'date': l.date.isoformat()
    } for l in logs])


@app.route('/api/exercise', methods=['POST'])
@login_required
def log_exercise():
    data = request.json
    log = ExerciseLog(
        user_id=current_user.id,
        exercise_type=data.get('exercise_type'),
        duration_minutes=data.get('duration_minutes'),
        intensity=data.get('intensity'),
        calories_burned=data.get('calories_burned'),
        notes=data.get('notes'),
        date=dt.utcnow().date(),
        logged_at=dt.utcnow()
    )
    db.session.add(log)
    db.session.commit()
    
    points = data.get('duration_minutes', 0) // 10
    if points > 0:
        reward = StudentReward.query.filter_by(user_id=current_user.id).first()
        if reward:
            reward.total_points += points
            reward.recalc_tier()
            db.session.add(RewardLog(user_id=current_user.id, points=points, reason=f'Exercise logged: {data.get("duration_minutes")} mins', badge='🏃'))
            db.session.commit()
    
    return jsonify({'id': log.id, 'message': 'Exercise logged successfully'}), 201


# =============================================================================
#  DASHBOARD API
# =============================================================================

@app.route('/api/dashboard', methods=['GET'])
@login_required
def dashboard_api():
    today = dt.utcnow().date()
    
    hydration_today = db.session.query(db.func.sum(HydrationLog.amount_ml)).filter(
        HydrationLog.user_id == current_user.id, HydrationLog.date == today
    ).scalar() or 0
    
    caffeine_today = db.session.query(db.func.sum(SubstanceLog.caffeine_mg)).filter(
        SubstanceLog.user_id == current_user.id, SubstanceLog.date == today, SubstanceLog.substance_type == 'caffeine'
    ).scalar() or 0
    
    alcohol_today = db.session.query(db.func.sum(SubstanceLog.alcohol_units)).filter(
        SubstanceLog.user_id == current_user.id, SubstanceLog.date == today, SubstanceLog.substance_type == 'alcohol'
    ).scalar() or 0
    
    calories_today = db.session.query(db.func.sum(NutritionLog.calories)).filter(
        NutritionLog.user_id == current_user.id, NutritionLog.date == today
    ).scalar() or 0
    
    exercise_count = ExerciseLog.query.filter_by(user_id=current_user.id, date=today).count()
    last_sleep = SleepLog.query.filter_by(user_id=current_user.id).order_by(SleepLog.date.desc()).first()
    pain_today = PainLog.query.filter(db.func.date(PainLog.recorded_datetime) == today, PainLog.user_id == current_user.id).count()
    medications_count = Medication.query.filter_by(user_id=current_user.id).count()
    
    return jsonify({
        'hydration_ml': hydration_today,
        'caffeine_mg': caffeine_today,
        'alcohol_units': alcohol_today,
        'calories': calories_today,
        'exercise_count': exercise_count,
        'sleep': {
            'date': last_sleep.date.isoformat() if last_sleep else None,
            'duration_hours': last_sleep.duration_hours if last_sleep else None,
            'quality': last_sleep.quality if last_sleep else None
        } if last_sleep else None,
        'pain_entries': pain_today,
        'medications_total': medications_count
    })


# =============================================================================
#  CHECKIN ROUTES
# =============================================================================

@app.route('/checkin', methods=['GET', 'POST'])
@login_required
def checkin():
    if request.method == 'POST':
        mood = int(request.form.get('mood_score', 5))
        stress = request.form.get('stress_level')
        sleep = request.form.get('sleep_hours')
        activity = request.form.get('physical_activity', '')
        notes = request.form.get('notes', '')
        ai_fb = get_ai_feedback(mood,
                                int(stress) if stress else None,
                                float(sleep) if sleep else None, notes)

        db.session.add(CheckIn(user_id=current_user.id, mood_score=mood,
                                stress_level=int(stress) if stress else None,
                                sleep_hours=float(sleep) if sleep else None,
                                physical_activity=activity, notes=notes, ai_feedback=ai_fb))
        db.session.commit()

        pts, rec, _ = award_checkin_points(current_user)
        emoji, label, _, _ = rec.tier_info
        streak_msg = f' 🔥 {rec.current_streak}-day streak!' if rec.current_streak >= 3 else ''

        if mood <= 3:
            try:
                for co in User.query.filter_by(role='counsellor').all():
                    send_email(co.email, f'Low Mood Alert – {current_user.full_name}',
                               f'{current_user.full_name} reported mood {mood}/10. Please follow up.')
            except Exception:
                pass

        flash(f'Check-in saved! +{pts} pts {emoji} ({rec.total_points} total · {label}){streak_msg} | {ai_fb.split("|")[0].strip()}', 'success')
        return redirect(url_for('student_dashboard'))
    return render_template('checkin.html')


@app.route('/checkin/history')
@login_required
def checkin_history():
    return render_template('checkin_history.html',
        checkins=CheckIn.query.filter_by(user_id=current_user.id).order_by(CheckIn.timestamp.desc()).all())


# =============================================================================
#  REWARDS ROUTES
# =============================================================================

@app.route('/rewards')
@login_required
def rewards():
    reward = StudentReward.query.filter_by(user_id=current_user.id).first()
    if not reward:
        reward = StudentReward(user_id=current_user.id)
        db.session.add(reward)
        db.session.commit()

    logs = (RewardLog.query.filter_by(user_id=current_user.id)
            .order_by(RewardLog.created_at.desc()).limit(30).all())

    leaderboard = (StudentReward.query
                   .join(User, StudentReward.user_id == User.id)
                   .filter(User.role == 'student', User.is_active == True)
                   .order_by(StudentReward.total_points.desc())
                   .limit(10).all())

    user_rank = next((i + 1 for i, r in enumerate(leaderboard) if r.user_id == current_user.id), None)
    if user_rank is None:
        above = (StudentReward.query.join(User, StudentReward.user_id == User.id)
                 .filter(User.role == 'student', StudentReward.total_points > reward.total_points).count())
        user_rank = above + 1

    return render_template('rewards.html', reward=reward, logs=logs,
                           leaderboard=leaderboard, user_rank=user_rank)


@app.route('/api/rewards/summary')
@login_required
def rewards_api():
    r = StudentReward.query.filter_by(user_id=current_user.id).first()
    if not r:
        return jsonify({'points': 0, 'streak': 0, 'tier': 'Bronze', 'checkins': 0})
    emoji, label, colour, _ = r.tier_info
    return jsonify({'points': r.total_points, 'streak': r.current_streak,
                    'longest_streak': r.longest_streak, 'tier': r.tier,
                    'tier_label': label, 'tier_emoji': emoji, 'tier_colour': colour,
                    'checkins': r.total_checkins, 'progress_pct': r.progress_pct})


@app.route('/admin/rewards')
@login_required
@admin_required
def admin_rewards():
    lb = (StudentReward.query.join(User, StudentReward.user_id == User.id)
          .filter(User.role == 'student').order_by(StudentReward.total_points.desc()).all())
    return render_template('admin_rewards.html', leaderboard=lb)


# =============================================================================
#  FORUM ROUTES
# =============================================================================

@app.route('/forum')
@login_required
def forum():
    cat = request.args.get('category', 'all')
    query = ForumPost.query if cat == 'all' else ForumPost.query.filter_by(category=cat)
    return render_template('forum.html',
        posts=query.order_by(ForumPost.is_pinned.desc(), ForumPost.timestamp.desc()).all(),
        category=cat)


@app.route('/forum/new', methods=['GET', 'POST'])
@login_required
def new_post():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        if not title or not content:
            flash('Title and content are required.', 'danger')
            return render_template('new_post.html')
        db.session.add(ForumPost(user_id=current_user.id, title=title, content=content,
                                  category=request.form.get('category', 'general'),
                                  is_anonymous=bool(request.form.get('anonymous'))))
        db.session.commit()
        flash('Post published!', 'success')
        return redirect(url_for('forum'))
    return render_template('new_post.html')


@app.route('/forum/post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def view_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if content:
            db.session.add(ForumReply(post_id=post_id, user_id=current_user.id,
                                       content=content, is_anonymous=bool(request.form.get('anonymous'))))
            db.session.commit()
            
            if post.user_id != current_user.id:
                author = User.query.get(post.user_id)
                if author and author.email:
                    send_email(
                        author.email,
                        f'New reply to your post: "{post.title[:50]}"',
                        f'{current_user.full_name} replied to your post: "{content[:100]}..."'
                    )
            
            flash('Reply added!', 'success')
        else:
            flash('Reply content cannot be empty.', 'danger')
    return render_template('view_post.html', post=post,
        replies=ForumReply.query.filter_by(post_id=post_id).order_by(ForumReply.timestamp).all())


@app.route('/forum/post/<int:post_id>/reply', methods=['POST'])
@login_required
def add_reply(post_id):
    post = ForumPost.query.get_or_404(post_id)
    content = request.form.get('content', '').strip()
    
    if not content:
        flash('Reply content cannot be empty.', 'danger')
        return redirect(url_for('view_post', post_id=post_id))
    
    reply = ForumReply(
        post_id=post_id,
        user_id=current_user.id,
        content=content,
        is_anonymous=bool(request.form.get('anonymous'))
    )
    
    db.session.add(reply)
    db.session.commit()
    
    if post.user_id != current_user.id:
        author = User.query.get(post.user_id)
        if author and author.email:
            html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 560px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #003087, #1d4ed8); padding: 20px; border-radius: 12px 12px 0 0; color: #fff;">
                    <h3>New Reply to Your Post</h3>
                </div>
                <div style="background: #fff; border: 1px solid #e2e8f0; padding: 20px; border-radius: 0 0 12px 12px;">
                    <p><strong>{'Anonymous' if reply.is_anonymous else current_user.full_name}</strong> replied to your post <strong>"{post.title}"</strong></p>
                    <div style="background: #f3f4f6; padding: 15px; border-radius: 8px; margin: 15px 0;">
                        {content}
                    </div>
                    <a href="{url_for('view_post', post_id=post.id, _external=True)}" style="display: inline-block; padding: 10px 20px; background: #003087; color: #fff; text-decoration: none; border-radius: 6px;">View Reply</a>
                </div>
            </div>
            """
            send_email(author.email, f'New reply to "{post.title[:50]}"', content, html)
    
    flash('Reply added successfully!', 'success')
    return redirect(url_for('view_post', post_id=post_id))


@app.route('/forum/post/<int:post_id>/comment/<int:reply_id>/delete', methods=['POST'])
@login_required
def delete_reply(post_id, reply_id):
    reply = ForumReply.query.get_or_404(reply_id)
    
    if reply.user_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to delete this reply.', 'danger')
        return redirect(url_for('view_post', post_id=post_id))
    
    db.session.delete(reply)
    db.session.commit()
    flash('Reply deleted successfully.', 'success')
    return redirect(url_for('view_post', post_id=post_id))


@app.route('/forum/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    
    if post.user_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to edit this post.', 'danger')
        return redirect(url_for('forum'))
    
    if request.method == 'POST':
        post.title = request.form.get('title', '').strip()
        post.content = request.form.get('content', '').strip()
        post.category = request.form.get('category', 'general')
        post.is_anonymous = bool(request.form.get('anonymous'))
        
        db.session.commit()
        flash('Post updated successfully!', 'success')
        return redirect(url_for('view_post', post_id=post_id))
    
    return render_template('edit_post.html', post=post)


@app.route('/forum/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    
    if post.user_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to delete this post.', 'danger')
        return redirect(url_for('forum'))
    
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted successfully.', 'success')
    return redirect(url_for('forum'))


@app.route('/forum/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    post.likes += 1
    db.session.commit()
    return jsonify({'likes': post.likes})


# =============================================================================
#  BOOKING ROUTES
# =============================================================================

@app.route('/booking', methods=['GET', 'POST'])
@login_required
def booking():
    counsellors = User.query.filter_by(role='counsellor').all()
    if request.method == 'POST':
        c_id = request.form.get('counsellor_id')
        ds = request.form.get('preferred_date', '')
        try:
            pdate = dt.strptime(ds, '%Y-%m-%dT%H:%M') if ds else None
        except ValueError:
            pdate = None
        b = Booking(student_id=current_user.id,
                    counsellor_id=int(c_id) if c_id else None,
                    session_type=request.form.get('session_type', 'individual'),
                    preferred_date=pdate,
                    reason=request.form.get('reason', ''))
        db.session.add(b)
        db.session.commit()
        if c_id:
            try:
                email_booking_new(b, current_user, User.query.get(int(c_id)))
            except Exception as e:
                print(f'[Booking email error] {e}')
        flash('Booking submitted! Confirmation email sent.', 'success')
        return redirect(url_for('student_dashboard'))
    return render_template('booking.html', counsellors=counsellors)


# =============================================================================
#  UPDATED SOS ROUTES WITH LOCATION
# =============================================================================

@app.route('/api/sos', methods=['POST'])
@login_required
def api_sos():
    """API endpoint for sending SOS alerts with location"""
    data = request.json
    
    # Store location as JSON string if provided
    location_json = None
    if data.get('location'):
        location_json = json.dumps(data.get('location'))
    
    alert = SOSAlert(
        user_id=current_user.id,
        message=data.get('message', 'EMERGENCY ASSISTANCE NEEDED'),
        location=location_json,
        status='active'
    )
    db.session.add(alert)
    db.session.commit()
    
    # Send email alerts to counsellors with location map
    for counsellor in User.query.filter(User.role.in_(['counsellor', 'admin'])).all():
        send_sos_email(alert, counsellor, current_user)
    
    # Also send SMS if phone number available (placeholder for SMS integration)
    if current_user.phone:
        send_sms_alert(current_user.phone, data.get('location'))
    
    return jsonify({'success': True, 'alert_id': alert.id}), 201


def send_sms_alert(phone_number, location_data):
    """Send SMS alert (placeholder - integrate with actual SMS service)"""
    print(f'[SMS] Would send SMS to {phone_number} with location: {location_data}')
    # Integrate with Twilio, Africa's Talking, etc. here


@app.route('/sos', methods=['GET', 'POST'])
@login_required
def sos():
    if request.method == 'POST':
        alert = SOSAlert(user_id=current_user.id,
                         message=request.form.get('message', 'EMERGENCY ASSISTANCE NEEDED'),
                         location=None)  # Location will be sent via API
        db.session.add(alert)
        db.session.commit()
        
        # Send email alerts
        for co in User.query.filter(User.role.in_(['counsellor', 'admin'])).all():
            send_sos_email(alert, co, current_user)
        
        flash('SOS Alert sent! Help is on the way. Stay safe.', 'success')
        return redirect(url_for('student_dashboard'))
    return render_template('sos.html')


@app.route('/crisis')
def crisis():
    return render_template('crisis.html')


# =============================================================================
#  RESOURCES / EVENTS
# =============================================================================

@app.route('/resources')
def resources():
    cat = request.args.get('category', 'all')
    q = Resource.query if cat == 'all' else Resource.query.filter_by(category=cat)
    return render_template('resources.html',
        resources=q.order_by(Resource.is_featured.desc(), Resource.created_at.desc()).all(),
        category=cat)


@app.route('/events')
@login_required
def events():
    return render_template('events.html',
        upcoming=Event.query.filter(Event.is_active == True, Event.start_time >= dt.utcnow()).order_by(Event.start_time).all(),
        past=Event.query.filter(Event.is_active == True, Event.start_time < dt.utcnow()).order_by(Event.start_time.desc()).limit(10).all())


# =============================================================================
#  COUNSELLOR ROUTES
# =============================================================================

@app.route('/counsellor/dashboard')
@login_required
@counsellor_required
def counsellor_dashboard():
    return render_template('counsellor_dashboard.html',
        students=User.query.filter_by(role='student').all(),
        pending_bookings=Booking.query.filter_by(counsellor_id=current_user.id, status='pending').all(),
        active_sos=SOSAlert.query.filter_by(status='active').all(),
        recent_checkins=CheckIn.query.order_by(CheckIn.timestamp.desc()).limit(20).all(),
        low_mood=CheckIn.query.filter(CheckIn.mood_score <= 4).order_by(CheckIn.timestamp.desc()).limit(10).all(),
        upcoming_events=Event.query.filter(Event.is_active == True, Event.start_time >= dt.utcnow()).order_by(Event.start_time).limit(5).all())


@app.route('/counsellor/booking/<int:booking_id>/update', methods=['POST'])
@login_required
@counsellor_required
def update_booking(booking_id):
    b = Booking.query.get_or_404(booking_id)
    b.status = request.form.get('status')
    b.notes = request.form.get('notes', '')
    db.session.commit()
    try:
        email_booking_update(b, User.query.get(b.student_id), b.status, current_user.full_name)
    except Exception as e:
        print(f'[Booking update email error] {e}')
    flash(f'Booking {b.status}. Student notified by email.', 'success')
    return redirect(url_for('counsellor_dashboard'))


@app.route('/counsellor/sos/<int:sos_id>/respond', methods=['POST'])
@login_required
@counsellor_required
def respond_sos(sos_id):
    alert = SOSAlert.query.get_or_404(sos_id)
    alert.status = 'responded'
    alert.responded_by = current_user.id
    alert.resolved_at = dt.utcnow()
    db.session.commit()
    
    user = User.query.get(alert.user_id)
    send_email(user.email, 'SOS Response – Help is Coming',
               f'{current_user.full_name} has received your SOS and is responding.')
    flash(f'Responded to SOS for {user.full_name}.', 'success')
    return redirect(url_for('counsellor_dashboard'))


@app.route('/counsellor/student/<int:student_id>')
@login_required
@counsellor_required
def view_student(student_id):
    student = User.query.get_or_404(student_id)
    checkins = CheckIn.query.filter_by(user_id=student_id).order_by(CheckIn.timestamp.desc()).all()
    sos_alerts = SOSAlert.query.filter_by(user_id=student_id).order_by(SOSAlert.created_at.desc()).all()
    
    return render_template('view_student.html',
        student=student,
        checkins=checkins,
        sos_alerts=sos_alerts,
        bookings=Booking.query.filter_by(student_id=student_id).all(),
        reward=StudentReward.query.filter_by(user_id=student_id).first(),
        mood_data=[c.mood_score for c in reversed(checkins[:14])],
        mood_labels=[c.timestamp.strftime('%d %b') for c in reversed(checkins[:14])])


# =============================================================================
#  ADMIN ROUTES
# =============================================================================

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html',
        total_students=User.query.filter_by(role='student').count(),
        total_counsellors=User.query.filter_by(role='counsellor').count(),
        total_checkins=CheckIn.query.count(),
        active_sos=SOSAlert.query.filter_by(status='active').count(),
        pending_bookings=Booking.query.filter_by(status='pending').count(),
        users=User.query.order_by(User.created_at.desc()).all(),
        sos_alerts=SOSAlert.query.order_by(SOSAlert.created_at.desc()).limit(10).all(),
        bookings=Booking.query.order_by(Booking.created_at.desc()).limit(10).all(),
        resources=Resource.query.all(),
        announcements=Announcement.query.order_by(Announcement.created_at.desc()).all(),
        events=Event.query.order_by(Event.start_time.desc()).all())


@app.route('/admin/user/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    u = User.query.get_or_404(user_id)
    u.is_active = not u.is_active
    db.session.commit()
    flash(f'User {"activated" if u.is_active else "deactivated"}.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/user/<int:user_id>/role', methods=['POST'])
@login_required
@admin_required
def change_role(user_id):
    u = User.query.get_or_404(user_id)
    role = request.form.get('role')
    if role in ['student', 'counsellor', 'admin']:
        u.role = role
        db.session.commit()
        flash(f'Role updated to {role}.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/resource/add', methods=['POST'])
@login_required
@admin_required
def add_resource():
    db.session.add(Resource(
        title=request.form.get('title'), category=request.form.get('category'),
        content=request.form.get('content'), url=request.form.get('url'),
        resource_type=request.form.get('resource_type', 'article'),
        is_featured=bool(request.form.get('is_featured'))))
    db.session.commit()
    flash('Resource added.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/resource/<int:rid>/delete', methods=['POST'])
@login_required
@admin_required
def delete_resource(rid):
    r = Resource.query.get_or_404(rid)
    db.session.delete(r)
    db.session.commit()
    flash('Resource deleted.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/announcement/add', methods=['POST'])
@login_required
@admin_required
def add_announcement():
    db.session.add(Announcement(title=request.form.get('title'),
                                 content=request.form.get('content'),
                                 author_id=current_user.id))
    db.session.commit()
    flash('Announcement posted.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/broadcast', methods=['POST'])
@login_required
@admin_required
def broadcast_email():
    subject = request.form.get('subject')
    content = request.form.get('content')
    target = request.form.get('target', 'all')
    q = User.query.filter_by(is_active=True) if target == 'all' else User.query.filter_by(is_active=True, role=target)
    sent = sum(1 for u in q.all() if send_email(u.email, subject, content))
    flash(f'Broadcast sent to {sent} users.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/sos/<int:sos_id>/resolve', methods=['POST'])
@login_required
@admin_required
def resolve_sos(sos_id):
    a = SOSAlert.query.get_or_404(sos_id)
    a.status = 'resolved'
    a.resolved_at = dt.utcnow()
    db.session.commit()
    flash('SOS resolved.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/event/add', methods=['POST'])
@login_required
@admin_required
def add_event():
    start_s = request.form.get('start_time', '')
    try:
        start_dt = dt.strptime(start_s, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('Invalid start time.', 'danger')
        return redirect(url_for('admin_dashboard'))
    end_dt = None
    end_s = request.form.get('end_time', '')
    if end_s:
        try:
            end_dt = dt.strptime(end_s, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass
    ev = Event(title=request.form.get('title', '').strip(),
               description=request.form.get('description', '').strip(),
               location=request.form.get('location', '').strip(),
               event_type=request.form.get('event_type', 'workshop'),
               target_audience=request.form.get('target_audience', 'all'),
               max_attendees=int(request.form.get('max_attendees', 50)),
               start_time=start_dt, end_time=end_dt, created_by=current_user.id)
    db.session.add(ev)
    db.session.commit()
    try:
        sent = email_event_created(ev)
        flash(f'Event created and announced to {sent} users!', 'success')
    except Exception as e:
        print(f'[Event email error] {e}')
        flash('Event created. Announcement email failed.', 'warning')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/event/<int:event_id>/cancel', methods=['POST'])
@login_required
@admin_required
def cancel_event(event_id):
    ev = Event.query.get_or_404(event_id)
    ev.is_active = False
    db.session.commit()
    sent = email_event_cancelled(ev)
    flash(f'Event cancelled. {sent} users notified.', 'success')
    return redirect(url_for('admin_dashboard'))


# =============================================================================
#  PROFILE
# =============================================================================

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name', current_user.full_name)
        current_user.phone = request.form.get('phone', current_user.phone)
        current_user.faculty = request.form.get('faculty', current_user.faculty)
        current_user.emergency_contact = request.form.get('emergency_contact', current_user.emergency_contact)
        current_user.emergency_phone = request.form.get('emergency_phone', current_user.emergency_phone)
        new_pw = request.form.get('new_password', '')
        if new_pw:
            if not current_user.check_password(request.form.get('current_password', '')):
                flash('Current password is incorrect.', 'danger')
                return render_template('profile.html')
            if len(new_pw) < 8:
                flash('New password must be at least 8 characters.', 'danger')
                return render_template('profile.html')
            current_user.set_password(new_pw)
        db.session.commit()
        flash('Profile updated.', 'success')
    return render_template('profile.html')


# =============================================================================
#  API ENDPOINTS
# =============================================================================

@app.route('/api/mood-data')
@login_required
def mood_data_api():
    days = int(request.args.get('days', 30))
    since = dt.utcnow() - timedelta(days=days)
    data = CheckIn.query.filter(CheckIn.user_id == current_user.id,
                                  CheckIn.timestamp >= since).order_by(CheckIn.timestamp).all()
    return jsonify({'labels': [c.timestamp.strftime('%d %b') for c in data],
                    'mood': [c.mood_score for c in data],
                    'stress': [c.stress_level for c in data],
                    'sleep': [c.sleep_hours for c in data]})


@app.route('/api/sos-count')
@login_required
def sos_count():
    return jsonify({'count': SOSAlert.query.filter_by(status='active').count()})


@app.route('/api/events/upcoming')
@login_required
def events_api():
    evs = Event.query.filter(Event.is_active == True, Event.start_time >= dt.utcnow()).order_by(Event.start_time).limit(10).all()
    return jsonify([{'id': e.id, 'title': e.title, 'start_time': e.start_time.isoformat(),
                     'location': e.location, 'event_type': e.event_type} for e in evs])


# =============================================================================
#  SEED DATA
# =============================================================================

def seed_database():
    if User.query.first():
        return

    admin = User(student_number='ADMIN001', full_name='System Administrator',
                 email='admin@dut.ac.za', role='admin', faculty='Administration')
    admin.set_password('Admin@123')
    db.session.add(admin)

    counsellor = User(student_number='COUN001', full_name='Dr. Sarah Nkosi',
                      email='counsellor@dut.ac.za', role='counsellor',
                      faculty='Wellness Centre', phone='031-373-2000')
    counsellor.set_password('Counsellor@123')
    db.session.add(counsellor)

    student = User(student_number='21200001', full_name='Thabo Mthembu',
                   email='student@dut.ac.za', role='student', faculty='Engineering',
                   phone='071-000-0001', emergency_contact='Mrs Mthembu', emergency_phone='071-000-0002')
    student.set_password('Student@123')
    db.session.add(student)

    for r in [
        Resource(title='DUT Crisis Hotline', category='crisis', content='24/7 emergency mental health support', url='tel:0800-567-567', resource_type='hotline', is_featured=True),
        Resource(title='SADAG Mental Health Line', category='crisis', content='SA Depression and Anxiety Group helpline', url='tel:0800-456-789', resource_type='hotline', is_featured=True),
        Resource(title='Managing Academic Stress', category='academic', content='Tips for balancing studies and mental wellness.', url='#', resource_type='article', is_featured=True),
        Resource(title='Mindfulness Meditation Guide', category='wellness', content='A beginner guide to daily mindfulness practice.', url='#', resource_type='article'),
        Resource(title='Lifeline South Africa', category='crisis', content='Emotional support and suicide prevention', url='tel:0861-322-322', resource_type='hotline'),
        Resource(title='Campus Health Centre', category='health', content='DUT campus clinic services', url='#', resource_type='article'),
    ]:
        db.session.add(r)

    db.session.add(Announcement(
        title='Welcome to DUT Wellness Centre',
        content='We are here for your mental health journey. Check in daily and book sessions with our counsellors.',
        author_id=1))

    db.session.add(Event(
        title='Stress Management Workshop',
        description='Practical techniques for managing exam stress and academic pressure.',
        location='DUT Steve Biko Campus — Room B204',
        event_type='workshop',
        start_time=dt.utcnow() + timedelta(days=3),
        end_time=dt.utcnow() + timedelta(days=3, hours=2),
        max_attendees=30, target_audience='all', created_by=1))

    db.session.flush()

    demo = User.query.filter_by(student_number='21200001').first()
    if demo:
        db.session.add(StudentReward(user_id=demo.id, total_points=45, current_streak=3,
                                      longest_streak=3, total_checkins=4, tier='Bronze'))
        for pts, reason, badge in [(10, 'Daily check-in', '✅'), (10, 'Daily check-in', '✅'),
                                    (10, 'Daily check-in', '✅'), (10, 'Daily check-in', '✅'),
                                    (5, '3-day streak bonus', '🔥')]:
            db.session.add(RewardLog(user_id=demo.id, points=pts, reason=reason, badge=badge))

    db.session.commit()


# =============================================================================
#  STARTUP
# =============================================================================
with app.app_context():
    db.create_all()
    seed_database()
    
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        migrate_database()
        seed_database()

    scheduler = threading.Thread(target=run_background_scheduler, daemon=True)
    scheduler.start()
    print('[Scheduler] Background thread started — checks every 30 minutes')
    print('  → Inactivity reminders : every 12 hours')
    print('  → Meeting reminders     : 45 minutes before each meeting')
    print('  → Event reminders      : 24 h and 1 h before each event')

    app.run(debug=True, port=5000)
