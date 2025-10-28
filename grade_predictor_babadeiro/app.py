from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sklearn.linear_model import LinearRegression
import numpy as np
import datetime

app = Flask(__name__)
app.secret_key = "troque_este_seguro"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    subjects = db.relationship("Subject", backref="user", lazy=True)
    entries = db.relationship("StudyEntry", backref="user", lazy=True)

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class StudyEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    date = db.Column(db.Date, default=datetime.date.today)
    hours = db.Column(db.Float, nullable=False)
    quality = db.Column(db.Float, nullable=False)  # 0.2 - 1.4
    difficulty = db.Column(db.Integer, nullable=False)  # 1 easy,2 medium,3 hard
    grade = db.Column(db.Float, nullable=True)  # 0-10 or None if not a test
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.relationship("Subject", backref="entries")

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        if not username or not password:
            flash('Preencha usuário e senha','error')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Usuário já existe','error')
            return redirect(url_for('register'))
        u = User(username=username, password=generate_password_hash(password))
        db.session.add(u); db.session.commit()
        flash('Conta criada! Faça login.','success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        u = User.query.filter_by(username=username).first()
        if u and check_password_hash(u.password, password):
            session['user_id'] = u.id
            return redirect(url_for('dashboard'))
        flash('Login inválido','error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

# APIs
@app.route('/api/subjects', methods=['GET','POST','DELETE'])
def api_subjects():
    if 'user_id' not in session:
        return jsonify({'error':'unauthorized'}), 401
    uid = session['user_id']
    if request.method == 'GET':
        subs = Subject.query.filter_by(user_id=uid).all()
        return jsonify([{'id':s.id,'name':s.name} for s in subs])
    if request.method == 'POST':
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'error':'nome vazio'}), 400
        s = Subject(name=name, user_id=uid)
        db.session.add(s); db.session.commit()
        return jsonify({'id':s.id,'name':s.name}), 201
    if request.method == 'DELETE':
        sid = request.args.get('id')
        s = Subject.query.filter_by(id=sid, user_id=uid).first()
        if not s:
            return jsonify({'error':'não encontrado'}), 404
        db.session.delete(s); db.session.commit()
        return jsonify({'ok':True})

@app.route('/api/entries', methods=['GET','POST','DELETE'])
def api_entries():
    if 'user_id' not in session:
        return jsonify({'error':'unauthorized'}), 401
    uid = session['user_id']
    if request.method == 'GET':
        subj = request.args.get('subject_id')
        q = StudyEntry.query.filter_by(user_id=uid)
        if subj:
            q = q.filter_by(subject_id=subj)
        entries = q.order_by(StudyEntry.date.desc()).all()
        out = []
        for e in entries:
            out.append({
                'id': e.id,
                'subject_id': e.subject_id,
                'subject_name': e.subject.name,
                'date': e.date.isoformat(),
                'hours': e.hours,
                'quality': e.quality,
                'difficulty': e.difficulty,
                'grade': e.grade
            })
        return jsonify(out)
    if request.method == 'POST':
        data = request.get_json() or {}
        sid = data.get('subject_id')
        subject = Subject.query.filter_by(id=sid, user_id=uid).first()
        if not subject:
            return jsonify({'error':'matéria inválida'}), 400
        try:
            hours = float(data.get('hours',0) or 0)
            quality = float(data.get('quality',1.0))
            difficulty = int(data.get('difficulty',2))
        except:
            return jsonify({'error':'dados inválidos'}), 400
        grade = data.get('grade')
        grade = None if grade in (None,'') else float(grade)
        date = data.get('date')
        if date:
            try:
                date = datetime.date.fromisoformat(date)
            except:
                date = datetime.date.today()
        else:
            date = datetime.date.today()
        e = StudyEntry(subject_id=subject.id, hours=hours, quality=quality,
                       difficulty=difficulty, grade=grade, user_id=uid, date=date)
        db.session.add(e); db.session.commit()
        return jsonify({'id': e.id})
    if request.method == 'DELETE':
        eid = request.args.get('id')
        e = StudyEntry.query.filter_by(id=eid, user_id=uid).first()
        if not e:
            return jsonify({'error':'not found'}), 404
        db.session.delete(e); db.session.commit()
        return jsonify({'ok':True})

@app.route('/api/predict', methods=['POST'])
def api_predict():
    if 'user_id' not in session:
        return jsonify({'error':'unauthorized'}), 401
    uid = session['user_id']
    data = request.get_json() or {}
    subject_id = data.get('subject_id')
    try:
        hours = float(data.get('hours',0))
        difficulty = int(data.get('difficulty',2))
        quality = float(data.get('quality',1.0))
    except:
        return jsonify({'error':'dados inválidos'}), 400
    q = StudyEntry.query.filter_by(user_id=uid)
    if subject_id:
        q = q.filter_by(subject_id=subject_id)
    hist = [e for e in q.all() if e.grade is not None]
    if len(hist) < 2:
        return jsonify({'error':'cadastre ao menos 2 registros com nota para treinar'}), 400
    X = np.array([[e.hours, e.difficulty, e.quality] for e in hist])
    y = np.array([e.grade for e in hist])
    model = LinearRegression().fit(X, y)
    pred = model.predict(np.array([[hours, difficulty, quality]]))[0]
    pred = max(0.0, min(10.0, float(pred)))
    return jsonify({'prediction': round(pred,2)})

@app.route('/api/performance', methods=['GET'])
def api_performance():
    if 'user_id' not in session:
        return jsonify({'error':'unauthorized'}), 401
    uid = session['user_id']
    # average grade per subject and grade timeline
    subs = Subject.query.filter_by(user_id=uid).all()
    avg = []
    timeline = []
    for s in subs:
        grades = [e.grade for e in s.entries if e.grade is not None and e.user_id==uid]
        if grades:
            avg.append({'subject': s.name, 'avg': sum(grades)/len(grades)})
        # timeline: date, subject, grade for entries with grade
        for e in s.entries:
            if e.grade is not None and e.user_id==uid:
                timeline.append({'date': e.date.isoformat(), 'subject': s.name, 'grade': e.grade})
    # sort timeline by date
    timeline.sort(key=lambda x: x['date'])
    return jsonify({'avg': avg, 'timeline': timeline})

@app.route('/api/status')
def api_status():
    if 'user_id' in session:
        u = User.query.get(session['user_id'])
        return jsonify({'logged':True,'username':u.username})
    return jsonify({'logged':False})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
