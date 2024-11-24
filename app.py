from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta
import calendar

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'workout.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy()
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    workouts = db.relationship('Workout', backref='user', lazy=True, cascade='all, delete-orphan')

class WorkoutSet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    set_number = db.Column(db.Integer, nullable=False)
    reps = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    workout_id = db.Column(db.Integer, db.ForeignKey('workout.id'), nullable=False)

    def to_dict(self):
        return {
            'set_number': self.set_number,
            'reps': self.reps,
            'weight': self.weight
        }

class Workout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exercise_name = db.Column(db.String(100), nullable=False)
    muscle_group = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sets = db.relationship('WorkoutSet', backref='workout', lazy=True, cascade='all, delete-orphan')
    week_number = db.Column(db.Integer, nullable=False)
    day_number = db.Column(db.Integer, nullable=False)
    workout_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text)

    def to_dict(self):
        return {
            'id': self.id,
            'exercise_name': self.exercise_name,
            'muscle_group': self.muscle_group,
            'sets': [s.to_dict() for s in self.sets],
            'week_number': self.week_number,
            'day_number': self.day_number,
            'workout_date': self.workout_date.strftime('%Y-%m-%d'),
            'notes': self.notes
        }

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        new_user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    workouts = Workout.query.filter_by(user_id=current_user.id).all()
    workouts_list = [workout.to_dict() for workout in workouts]

    # Get workout dates for the last year
    today = datetime.now().date()
    year_ago = today - timedelta(days=365)
    workout_dates = (Workout.query
                    .filter(Workout.user_id == current_user.id)
                    .filter(Workout.workout_date >= year_ago)
                    .with_entities(Workout.workout_date)
                    .distinct()
                    .all())
    
    # Create attendance data for the heatmap
    attendance_data = {}
    for date in (year_ago + timedelta(days=x) for x in range(366)):
        date_str = date.strftime('%Y-%m-%d')
        attendance_data[date_str] = 0

    for workout_date in workout_dates:
        date_str = workout_date[0].strftime('%Y-%m-%d')
        attendance_data[date_str] = 1

    return render_template('dashboard.html', 
                         workouts=workouts_list,
                         attendance_data=attendance_data,
                         start_date=year_ago.strftime('%Y-%m-%d'),
                         today=today.strftime('%Y-%m-%d'))

@app.route('/add_workout', methods=['GET', 'POST'])
@login_required
def add_workout():
    if request.method == 'POST':
        # Create the workout first
        workout = Workout(
            exercise_name=request.form['exercise_name'],
            muscle_group=request.form['muscle_group'],
            user_id=current_user.id,
            week_number=int(request.form['week_number']),
            day_number=int(request.form['day_number']),
            workout_date=datetime.strptime(request.form['workout_date'], '%Y-%m-%d').date(),
            notes=request.form['notes']
        )
        db.session.add(workout)
        db.session.flush()  # This assigns an ID to the workout
        
        # Now add the sets
        num_sets = int(request.form['num_sets'])
        for i in range(num_sets):
            set_number = i + 1
            workout_set = WorkoutSet(
                set_number=set_number,
                reps=int(request.form[f'reps_{set_number}']),
                weight=float(request.form[f'weight_{set_number}']),
                workout_id=workout.id
            )
            db.session.add(workout_set)
        
        db.session.commit()
        return redirect(url_for('dashboard'))
    
    return render_template('add_workout.html')

if __name__ == '__main__':
    with app.app_context():
        # Drop all tables and recreate them
        db.drop_all()
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
