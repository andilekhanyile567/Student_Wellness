from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import secrets
import os
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wellness.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'dut.wellness@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'your-app-password')
app.config['MAIL_DEFAULT_SENDER'] = ('DUT Wellness Centre', os.environ.get('MAIL_USERNAME', 'dut.wellness@gmail.com'))

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
mail = Mail(app)

# ─────────────────────────── MODELS ─────────────────────────────

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_number = db.Column(db.String(20), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='student')
    faculty = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    emergency_contact = db.Column(db.String(100))
    emergency_phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reset_token = db.Column(db.String(100))
    reset_token_expiry = db.Column(db.DateTime)

    # ── Relationships with explicit foreign_keys to resolve ambiguity ──
    checkins = db.relationship('CheckIn', backref='user', lazy=True,
                               foreign_keys='CheckIn.user_id')
    posts = db.relationship('ForumPost', backref='author', lazy=True,
                            foreign_keys='ForumPost.user_id')
    # Bookings where this user is the STUDENT
    bookings = db.relationship('Booking', backref='student', lazy=True,
                               foreign_keys='Booking.student_id')
    # Bookings where this user is the COUNSELLOR
    counsellor_bookings = db.relationship('Booking', backref='counsellor', lazy=True,
                                          foreign_keys='Booking.counsellor_id')
    # SOS alerts RAISED by this user
    sos_alerts = db.relationship('SOSAlert', backref='user', lazy=True,
                                 foreign_keys='SOSAlert.user_id')
    # SOS alerts RESPONDED to by this user
    sos_responses = db.relationship('SOSAlert', backref='responder', lazy=True,
                                    foreign_keys='SOSAlert.responded_by')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_authenticated(self): return True
    @property
    def is_anonymous(self): return False
    def get_id(self): return str(self.id)


class CheckIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mood_score = db.Column(db.Integer, nullable=False)
    stress_level = db.Column(db.Integer)
    sleep_hours = db.Column(db.Float)
    physical_activity = db.Column(db.String(50))
    notes = db.Column(db.Text)
    ai_feedback = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class ForumPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(50))
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False)
    is_pinned = db.Column(db.Boolean, default=False)
    likes = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    replies = db.relationship('ForumReply', backref='post', lazy=True)


class ForumReply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    counsellor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    session_type = db.Column(db.String(50))
    preferred_date = db.Column(db.DateTime)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SOSAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text)
    location = db.Column(db.String(200))
    status = db.Column(db.String(20), default='active')
    responded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)


class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50))
    content = db.Column(db.Text)
    url = db.Column(db.String(300))
    resource_type = db.Column(db.String(30))
    is_featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}


# ─────────────────────────── DECORATORS ──────────────────────────

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


# ─────────────────────────── HELPERS ─────────────────────────────

def send_email(to, subject, body, html=None):
    try:
        msg = Message(subject, recipients=[to])
        msg.body = body
        if html:
            msg.html = html
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


def get_ai_feedback(mood_score, stress, sleep, notes):
    tips = {
        'low_mood': ["Consider talking to a counsellor.", "Try a 10-minute walk outside.", "Reach out to a friend or peer."],
        'high_stress': ["Practice deep breathing exercises.", "Break tasks into smaller steps.", "Schedule a 15-min break every 2 hours."],
        'poor_sleep': ["Avoid screens 1 hour before bed.", "Try a consistent sleep schedule.", "Limit caffeine after 2pm."],
        'positive': ["Great job maintaining your wellness!", "Keep up the positive habits.", "Share your strategies in the peer forum!"]
    }
    feedback = []
    if mood_score <= 4:
        feedback.extend(tips['low_mood'])
    if stress and stress >= 7:
        feedback.extend(tips['high_stress'])
    if sleep and sleep < 6:
        feedback.extend(tips['poor_sleep'])
    if mood_score >= 8 and (not stress or stress <= 4):
        feedback.extend(tips['positive'])
    if not feedback:
        feedback = ["Keep monitoring your wellness daily.", "Stay connected with the DUT community.", "Remember, help is always available."]
    return " | ".join(feedback[:3])


# ─────────────────────────── AUTH ROUTES ─────────────────────────

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(f'{current_user.role}_dashboard'))
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter(
            (User.student_number == identifier) | (User.email == identifier)
        ).first()
        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=request.form.get('remember'))
            flash(f'Welcome back, {user.full_name.split()[0]}!', 'success')
            return redirect(url_for(f'{user.role}_dashboard'))
        flash('Invalid credentials. Please try again.', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        sn = request.form.get('student_number', '').strip().upper()
        name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        pw = request.form.get('password', '')
        pw2 = request.form.get('confirm_password', '')
        faculty = request.form.get('faculty', '')
        phone = request.form.get('phone', '')
        ec = request.form.get('emergency_contact', '')
        ep = request.form.get('emergency_phone', '')
        if not all([sn, name, email, pw]):
            flash('All required fields must be filled.', 'danger')
            return render_template('register.html')
        if pw != pw2:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')
        if len(pw) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('register.html')
        if User.query.filter_by(student_number=sn).first():
            flash('Student number already registered.', 'danger')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('register.html')
        user = User(student_number=sn, full_name=name, email=email,
                    faculty=faculty, phone=phone, emergency_contact=ec, emergency_phone=ep)
        user.set_password(pw)
        db.session.add(user)
        db.session.commit()
        html = render_template('emails/welcome.html', user=user)
        send_email(email, 'Welcome to DUT Wellness Centre', f'Welcome {name}!', html)
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            reset_url = url_for('reset_password', token=token, _external=True)
            html = render_template('emails/reset_password.html', user=user, reset_url=reset_url)
            send_email(email, 'DUT Wellness - Password Reset', f'Reset link: {reset_url}', html)
        flash('If that email is registered, a reset link has been sent.', 'info')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.reset_token_expiry or user.reset_token_expiry < datetime.utcnow():
        flash('Invalid or expired reset link.', 'danger')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        pw = request.form.get('password', '')
        pw2 = request.form.get('confirm_password', '')
        if pw != pw2:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html', token=token)
        if len(pw) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('reset_password.html', token=token)
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


# ────────────────────── STUDENT DASHBOARD ────────────────────────

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role not in ['student']:
        return redirect(url_for(f'{current_user.role}_dashboard'))
    recent_checkins = CheckIn.query.filter_by(user_id=current_user.id).order_by(CheckIn.timestamp.desc()).limit(7).all()
    bookings = Booking.query.filter_by(student_id=current_user.id).order_by(Booking.created_at.desc()).limit(5).all()
    active_sos = SOSAlert.query.filter_by(user_id=current_user.id, status='active').first()
    posts = ForumPost.query.order_by(ForumPost.timestamp.desc()).limit(5).all()
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).limit(3).all()
    mood_data = [c.mood_score for c in reversed(recent_checkins)]
    mood_labels = [c.timestamp.strftime('%d %b') for c in reversed(recent_checkins)]
    return render_template('student_dashboard.html',
        checkins=recent_checkins, bookings=bookings, active_sos=active_sos,
        posts=posts, announcements=announcements,
        mood_data=mood_data, mood_labels=mood_labels)


@app.route('/checkin', methods=['GET', 'POST'])
@login_required
def checkin():
    if request.method == 'POST':
        mood = int(request.form.get('mood_score', 5))
        stress = request.form.get('stress_level')
        sleep = request.form.get('sleep_hours')
        activity = request.form.get('physical_activity', '')
        notes = request.form.get('notes', '')
        ai_fb = get_ai_feedback(mood, int(stress) if stress else None, float(sleep) if sleep else None, notes)
        c = CheckIn(user_id=current_user.id, mood_score=mood,
                    stress_level=int(stress) if stress else None,
                    sleep_hours=float(sleep) if sleep else None,
                    physical_activity=activity, notes=notes, ai_feedback=ai_fb)
        db.session.add(c)
        db.session.commit()
        if mood <= 3:
            html = render_template('emails/low_mood_alert.html', user=current_user, mood=mood)
            counsellors = User.query.filter_by(role='counsellor').all()
            for co in counsellors:
                send_email(co.email, f'Low Mood Alert - {current_user.full_name}',
                           f'Student {current_user.full_name} reported mood {mood}/10', html)
        flash(f'Check-in saved! AI Tip: {ai_fb.split("|")[0]}', 'success')
        return redirect(url_for('student_dashboard'))
    return render_template('checkin.html')


@app.route('/checkin/history')
@login_required
def checkin_history():
    checkins = CheckIn.query.filter_by(user_id=current_user.id).order_by(CheckIn.timestamp.desc()).all()
    return render_template('checkin_history.html', checkins=checkins)


# ───────────────────────── SOS ROUTES ────────────────────────────

@app.route('/sos', methods=['GET', 'POST'])
@login_required
def sos():
    if request.method == 'POST':
        message = request.form.get('message', 'EMERGENCY ASSISTANCE NEEDED')
        location = request.form.get('location', '')
        alert = SOSAlert(user_id=current_user.id, message=message, location=location)
        db.session.add(alert)
        db.session.commit()
        counsellors = User.query.filter(User.role.in_(['counsellor', 'admin'])).all()
        for co in counsellors:
            html = render_template('emails/sos_alert.html', user=current_user, alert=alert)
            send_email(co.email, f'SOS ALERT - {current_user.full_name}',
                       f'SOS from {current_user.full_name}: {message}', html)
        flash('SOS Alert sent! Help is on the way. Stay safe.', 'success')
        return redirect(url_for('student_dashboard'))
    return render_template('sos.html')


@app.route('/crisis')
def crisis():
    return render_template('crisis.html')


# ───────────────────────── FORUM ROUTES ──────────────────────────

@app.route('/forum')
@login_required
def forum():
    category = request.args.get('category', 'all')
    q = ForumPost.query
    if category != 'all':
        q = q.filter_by(category=category)
    posts = q.order_by(ForumPost.is_pinned.desc(), ForumPost.timestamp.desc()).all()
    return render_template('forum.html', posts=posts, category=category)


@app.route('/forum/new', methods=['GET', 'POST'])
@login_required
def new_post():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        category = request.form.get('category', 'general')
        anon = bool(request.form.get('anonymous'))
        if not title or not content:
            flash('Title and content are required.', 'danger')
            return render_template('new_post.html')
        p = ForumPost(user_id=current_user.id, title=title, content=content,
                      category=category, is_anonymous=anon)
        db.session.add(p)
        db.session.commit()
        flash('Post published successfully!', 'success')
        return redirect(url_for('forum'))
    return render_template('new_post.html')


@app.route('/forum/post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def view_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        anon = bool(request.form.get('anonymous'))
        if content:
            r = ForumReply(post_id=post_id, user_id=current_user.id, content=content, is_anonymous=anon)
            db.session.add(r)
            db.session.commit()
            flash('Reply added!', 'success')
    replies = ForumReply.query.filter_by(post_id=post_id).order_by(ForumReply.timestamp).all()
    return render_template('view_post.html', post=post, replies=replies)


@app.route('/forum/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    post.likes += 1
    db.session.commit()
    return jsonify({'likes': post.likes})


# ───────────────────────── BOOKING ROUTES ────────────────────────

@app.route('/booking', methods=['GET', 'POST'])
@login_required
def booking():
    counsellors = User.query.filter_by(role='counsellor').all()
    if request.method == 'POST':
        c_id = request.form.get('counsellor_id')
        stype = request.form.get('session_type', 'individual')
        date_str = request.form.get('preferred_date', '')
        reason = request.form.get('reason', '')
        try:
            pdate = datetime.strptime(date_str, '%Y-%m-%dT%H:%M') if date_str else None
        except ValueError:
            pdate = None
        b = Booking(student_id=current_user.id, counsellor_id=int(c_id) if c_id else None,
                    session_type=stype, preferred_date=pdate, reason=reason)
        db.session.add(b)
        db.session.commit()
        counsellor = User.query.get(int(c_id)) if c_id else None
        html = render_template('emails/booking_confirmation.html', booking=b, student=current_user, counsellor=counsellor)
        send_email(current_user.email, 'Booking Request Submitted', 'Your booking has been submitted.', html)
        if counsellor:
            send_email(counsellor.email, f'New Booking from {current_user.full_name}', 'A student has requested a session.', html)
        flash('Booking request submitted! You will receive a confirmation email.', 'success')
        return redirect(url_for('student_dashboard'))
    return render_template('booking.html', counsellors=counsellors)


# ───────────────────────── RESOURCES ─────────────────────────────

@app.route('/resources')
def resources():
    category = request.args.get('category', 'all')
    q = Resource.query
    if category != 'all':
        q = q.filter_by(category=category)
    resources_list = q.order_by(Resource.is_featured.desc(), Resource.created_at.desc()).all()
    return render_template('resources.html', resources=resources_list, category=category)


# ────────────────── COUNSELLOR DASHBOARD ─────────────────────────

@app.route('/counsellor/dashboard')
@login_required
@counsellor_required
def counsellor_dashboard():
    students = User.query.filter_by(role='student').all()
    pending_bookings = Booking.query.filter_by(counsellor_id=current_user.id, status='pending').all()
    active_sos = SOSAlert.query.filter_by(status='active').all()
    recent_checkins = CheckIn.query.order_by(CheckIn.timestamp.desc()).limit(20).all()
    low_mood = CheckIn.query.filter(CheckIn.mood_score <= 4).order_by(CheckIn.timestamp.desc()).limit(10).all()
    return render_template('counsellor_dashboard.html',
        students=students, pending_bookings=pending_bookings,
        active_sos=active_sos, recent_checkins=recent_checkins, low_mood=low_mood)


@app.route('/counsellor/booking/<int:booking_id>/update', methods=['POST'])
@login_required
@counsellor_required
def update_booking(booking_id):
    b = Booking.query.get_or_404(booking_id)
    status = request.form.get('status')
    notes = request.form.get('notes', '')
    b.status = status
    b.notes = notes
    db.session.commit()
    student = User.query.get(b.student_id)
    html = render_template('emails/booking_update.html', booking=b, student=student)
    send_email(student.email, f'Booking {status.title()} - DUT Wellness', f'Your booking has been {status}.', html)
    flash(f'Booking {status}.', 'success')
    return redirect(url_for('counsellor_dashboard'))


@app.route('/counsellor/sos/<int:sos_id>/respond', methods=['POST'])
@login_required
@counsellor_required
def respond_sos(sos_id):
    alert = SOSAlert.query.get_or_404(sos_id)
    alert.status = 'responded'
    alert.responded_by = current_user.id
    db.session.commit()
    user = User.query.get(alert.user_id)
    html = render_template('emails/sos_response.html', user=user, counsellor=current_user)
    send_email(user.email, 'SOS Response - Help is Coming', f'{current_user.full_name} is responding to your SOS.', html)
    flash(f'Responded to SOS alert for {user.full_name}.', 'success')
    return redirect(url_for('counsellor_dashboard'))


@app.route('/counsellor/student/<int:student_id>')
@login_required
@counsellor_required
def view_student(student_id):
    student = User.query.get_or_404(student_id)
    checkins = CheckIn.query.filter_by(user_id=student_id).order_by(CheckIn.timestamp.desc()).all()
    bookings = Booking.query.filter_by(student_id=student_id).all()
    mood_data = [c.mood_score for c in reversed(checkins[:14])]
    mood_labels = [c.timestamp.strftime('%d %b') for c in reversed(checkins[:14])]
    return render_template('view_student.html', student=student, checkins=checkins,
                           bookings=bookings, mood_data=mood_data, mood_labels=mood_labels)


# ───────────────────────── ADMIN DASHBOARD ───────────────────────

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    total_students = User.query.filter_by(role='student').count()
    total_counsellors = User.query.filter_by(role='counsellor').count()
    total_checkins = CheckIn.query.count()
    active_sos = SOSAlert.query.filter_by(status='active').count()
    pending_bookings = Booking.query.filter_by(status='pending').count()
    users = User.query.order_by(User.created_at.desc()).all()
    sos_alerts = SOSAlert.query.order_by(SOSAlert.created_at.desc()).limit(10).all()
    bookings = Booking.query.order_by(Booking.created_at.desc()).limit(10).all()
    resources = Resource.query.all()
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template('admin_dashboard.html',
        total_students=total_students, total_counsellors=total_counsellors,
        total_checkins=total_checkins, active_sos=active_sos,
        pending_bookings=pending_bookings, users=users, sos_alerts=sos_alerts,
        bookings=bookings, resources=resources, announcements=announcements)


@app.route('/admin/user/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    flash(f'User {"activated" if user.is_active else "deactivated"}.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/user/<int:user_id>/role', methods=['POST'])
@login_required
@admin_required
def change_role(user_id):
    user = User.query.get_or_404(user_id)
    role = request.form.get('role')
    if role in ['student', 'counsellor', 'admin']:
        user.role = role
        db.session.commit()
        flash(f'Role updated to {role}.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/resource/add', methods=['POST'])
@login_required
@admin_required
def add_resource():
    r = Resource(
        title=request.form.get('title'),
        category=request.form.get('category'),
        content=request.form.get('content'),
        url=request.form.get('url'),
        resource_type=request.form.get('resource_type', 'article'),
        is_featured=bool(request.form.get('is_featured'))
    )
    db.session.add(r)
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
    a = Announcement(title=request.form.get('title'),
                     content=request.form.get('content'),
                     author_id=current_user.id)
    db.session.add(a)
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
    q = User.query.filter_by(is_active=True)
    if target != 'all':
        q = q.filter_by(role=target)
    users_list = q.all()
    sent = sum(1 for u in users_list if send_email(u.email, subject, content))
    flash(f'Broadcast sent to {sent} users.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/sos/<int:sos_id>/resolve', methods=['POST'])
@login_required
@admin_required
def resolve_sos(sos_id):
    alert = SOSAlert.query.get_or_404(sos_id)
    alert.status = 'resolved'
    alert.resolved_at = datetime.utcnow()
    db.session.commit()
    flash('SOS resolved.', 'success')
    return redirect(url_for('admin_dashboard'))


# ───────────────────────── PROFILE ───────────────────────────────

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
        flash('Profile updated successfully.', 'success')
    return render_template('profile.html')


# ─────────────────────── API ENDPOINTS ───────────────────────────

@app.route('/api/mood-data')
@login_required
def mood_data_api():
    days = int(request.args.get('days', 30))
    since = datetime.utcnow() - timedelta(days=days)
    checkins = CheckIn.query.filter(
        CheckIn.user_id == current_user.id,
        CheckIn.timestamp >= since
    ).order_by(CheckIn.timestamp).all()
    return jsonify({
        'labels': [c.timestamp.strftime('%d %b') for c in checkins],
        'mood': [c.mood_score for c in checkins],
        'stress': [c.stress_level for c in checkins],
        'sleep': [c.sleep_hours for c in checkins]
    })


@app.route('/api/sos-count')
@login_required
def sos_count():
    count = SOSAlert.query.filter_by(status='active').count()
    return jsonify({'count': count})


# ──────────────────────── SEED DATA ──────────────────────────────

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
                   phone='071-000-0001', emergency_contact='Mrs Mthembu',
                   emergency_phone='071-000-0002')
    student.set_password('Student@123')
    db.session.add(student)

    for r in [
        Resource(title='DUT Crisis Hotline', category='crisis',
                 content='24/7 emergency mental health support',
                 url='tel:0800-567-567', resource_type='hotline', is_featured=True),
        Resource(title='SADAG Mental Health Line', category='crisis',
                 content='SA Depression and Anxiety Group helpline',
                 url='tel:0800-456-789', resource_type='hotline', is_featured=True),
        Resource(title='Managing Academic Stress', category='academic',
                 content='Tips for balancing studies and mental wellness.',
                 url='#', resource_type='article', is_featured=True),
        Resource(title='Mindfulness Meditation Guide', category='wellness',
                 content='A beginner guide to daily mindfulness practice.',
                 url='#', resource_type='article'),
        Resource(title='Lifeline South Africa', category='crisis',
                 content='Emotional support and suicide prevention',
                 url='tel:0861-322-322', resource_type='hotline'),
        Resource(title='Campus Health Centre', category='health',
                 content='DUT campus clinic services', url='#', resource_type='article'),
    ]:
        db.session.add(r)

    db.session.add(Announcement(
        title='Welcome to DUT Wellness Centre',
        content='We are here for your mental health and wellness journey. '
                'Use the check-in feature daily and book sessions with our counsellors.',
        author_id=1
    ))
    db.session.commit()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_database()
    app.run(debug=True, port=5000)