from datetime import datetime
import os
from flask import Flask, abort, flash, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import date

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nutrition.db'  # Используем существующую БД
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key_here'  # Для работы сессий
db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Integer)
    height = db.Column(db.Integer)
    weight = db.Column(db.Float)
    gender = db.Column(db.String(10))
    
    # Добавляем связь с приемами пищи
    meals = db.relationship('Meal', backref='user', lazy=True)

class Meal(db.Model):
    __tablename__ = 'meals'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, default=date.today)
    meal_type = db.Column(db.String(10))  # 'breakfast', 'lunch', 'dinner'
    name = db.Column(db.String(100))
    calories = db.Column(db.Float)
    proteins = db.Column(db.Float)
    fats = db.Column(db.Float)
    carbs = db.Column(db.Float)

class DailyStat(db.Model):
    __tablename__ = 'daily_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, default=date.today)
    total_calories = db.Column(db.Float)
    total_proteins = db.Column(db.Float)
    total_fats = db.Column(db.Float)
    total_carbs = db.Column(db.Float)
    
    # Добавляем связь с пользователем
    user = db.relationship('User', backref='daily_stats')

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = User.query.filter_by(login=request.form['email']).first()
        if user and user.password == request.form['password']:
            session['user_id'] = user.id  # Сохраняем ID пользователя в сессии
            return redirect(url_for('index'))
        error = 'Неверный логин или пароль'
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    genders = ['male', 'female', 'other']  # Варианты выбора пола
    
    if request.method == 'POST':
        # Проверка обязательных полей
        if not all(field in request.form for field in ['email', 'password']):
            error = 'Заполните все обязательные поля'
        elif User.query.filter_by(login=request.form['email']).first():
            error = 'Пользователь уже существует'
        else:
            try:
                # Создание нового пользователя
                new_user = User(
                    login=request.form['email'],
                    password=(request.form['password']),
                    age=int(request.form.get('age', 0)),
                    height=int(request.form.get('height', 170)),  # Добавляем рост
                    weight=float(request.form.get('weight', 0.0)),
                    gender=request.form.get('gender', 'other')
                )
                db.session.add(new_user)
                db.session.commit()
                return redirect(url_for('login'))
            except ValueError:
                error = 'Некорректные данные возраста или веса'
            except Exception as e:
                error = f'Ошибка при регистрации: {str(e)}'
    
    return render_template('register.html', error=error, genders=genders)

@app.route('/index')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    
    # Get today's meals from database
    today = date.today()
    meals = Meal.query.filter_by(
        user_id=session['user_id'],
        date=today
    ).all()
    
    # Organize meals by type
    breakfast_items = []
    lunch_items = []
    dinner_items = []
    
    for meal in meals:
        if meal.meal_type == 'breakfast':
            breakfast_items.append({
                'id': meal.id,
                'name': meal.name,
                'calories': meal.calories,
                'proteins': meal.proteins,
                'fats': meal.fats,
                'carbs': meal.carbs
            })
        elif meal.meal_type == 'lunch':
            lunch_items.append({
                'id': meal.id,
                'name': meal.name,
                'calories': meal.calories,
                'proteins': meal.proteins,
                'fats': meal.fats,
                'carbs': meal.carbs
            })
        elif meal.meal_type == 'dinner':
            dinner_items.append({
                'id': meal.id,
                'name': meal.name,
                'calories': meal.calories,
                'proteins': meal.proteins,
                'fats': meal.fats,
                'carbs': meal.carbs
            })
    
    # Calculate totals
    breakfast_total = sum(item['calories'] for item in breakfast_items)
    lunch_total = sum(item['calories'] for item in lunch_items)
    dinner_total = sum(item['calories'] for item in dinner_items)
    daily_total = breakfast_total + lunch_total + dinner_total
    
    daily_data = {
    "date": datetime.now().strftime("%d %B %Y"),
    "time": datetime.now().strftime("%H:%M"),
    "calories": daily_total,
    "breakfast": {
        "total": breakfast_total,
        "foods": breakfast_items  # Изменили с items на foods
    },
    "lunch": {
        "total": lunch_total,
        "foods": lunch_items  # Изменили с items на foods
    },
    "dinner": {
        "total": dinner_total,
        "foods": dinner_items  # Изменили с items на foods
    }
}
    
    return render_template('index.html',
                         user=user,
                         daily_data=daily_data)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))


@app.route('/bmi')
def bmi():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    
    # Рассчитываем ИМТ
    bmi_value = None
    bmi_category = None
    if user.height and user.weight:
        bmi_value = round(user.weight / ((user.height / 100) ** 2), 1)
        
        if bmi_value < 18.5:
            bmi_category = "Недостаточный вес"
        elif 18.5 <= bmi_value < 25:
            bmi_category = "Нормальный вес"
        elif 25 <= bmi_value < 30:
            bmi_category = "Избыточный вес"
        else:
            bmi_category = "Ожирение"
    
    return render_template('bmi.html', 
                         user=user,
                         bmi_value=bmi_value,
                         bmi_category=bmi_category)

@app.route('/add_meal', methods=['GET', 'POST'])
def add_meal():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    meal_types = ['breakfast', 'lunch', 'dinner', 'snack']  # Добавлен ужин и перекус
    
    if request.method == 'POST':
        try:
            new_meal = Meal(
                user_id=session['user_id'],
                meal_type=request.form['meal_type'],
                name=request.form['name'],
                calories=float(request.form['calories']),
                proteins=float(request.form['proteins']),
                fats=float(request.form['fats']),
                carbs=float(request.form['carbs'])
            )
            db.session.add(new_meal)
            update_daily_stats(session['user_id'])
            db.session.commit()
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            return render_template('add_meal.html', 
                                error=str(e),
                                meal_types=meal_types)
    
    return render_template('add_meal.html',
                         meal_types=meal_types)

def update_daily_stats(user_id):
    today = date.today()
    # Суммируем все приемы пищи за сегодня
    meals = Meal.query.filter_by(
        user_id=user_id,
        date=today
    ).all()
    
    # Рассчитываем итоги
    total_calories = sum(m.calories for m in meals)
    total_proteins = sum(m.proteins for m in meals)
    total_fats = sum(m.fats for m in meals)
    total_carbs = sum(m.carbs for m in meals)
    
    # Обновляем или создаем запись статистики
    stat = DailyStat.query.filter_by(
        user_id=user_id,
        date=today
    ).first()
    
    if not stat:
        stat = DailyStat(
            user_id=user_id,
            date=today
        )
        db.session.add(stat)
    
    stat.total_calories = total_calories
    stat.total_proteins = total_proteins
    stat.total_fats = total_fats
    stat.total_carbs = total_carbs

@app.route('/delete_meal/<int:id>', methods=['POST'])
def delete_meal(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    meal = Meal.query.get_or_404(id)
    if meal.user_id != session['user_id']:
        abort(403)
    
    db.session.delete(meal)
    update_daily_stats(session['user_id'])
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/stats')
def stats():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    stats = DailyStat.query.filter_by(
        user_id=session['user_id']
    ).order_by(DailyStat.date.desc()).limit(30).all()
    
    return render_template('stats.html', stats=stats)

@app.route('/save_day', methods=['POST'])
def save_day():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    update_daily_stats(session['user_id'])
    db.session.commit()
    
    # Можно добавить отправку статистики на email/телеграм
    # send_daily_report(session['user_id'])
    
    flash('Дневной рацион сохранен!', 'success')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        try:
            # Обновляем данные профиля
            user.age = int(request.form.get('age', user.age))
            user.height = int(request.form.get('height', user.height))
            user.weight = float(request.form.get('weight', user.weight))
            user.gender = request.form.get('gender', user.gender)
            
            db.session.commit()
            flash('Профиль успешно обновлен!', 'success')
            return redirect(url_for('profile'))
        except ValueError:
            flash('Ошибка в данных. Проверьте вводимые значения.', 'error')
    
    return render_template('profile.html', user=user)



if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    
    app.run(debug=True)