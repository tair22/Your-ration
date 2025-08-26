import os
import fatsecret
import requests
import sys
from urllib.parse import quote, urlencode
from pathlib import Path
from datetime import datetime
from datetime import date
from requests_oauthlib import OAuth1
from fatsecret import Fatsecret
from flask import Flask, abort, flash, render_template, request, redirect, url_for, session, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import decimal
import hashlib  # Для хеширования паролей

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nutrition.db'  # Используем существующую БД
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')

CONSUMER_KEY = ''
CONSUMER_SECRET = ''

if CONSUMER_KEY and CONSUMER_SECRET:
    fs = fatsecret.Fatsecret(CONSUMER_KEY, CONSUMER_SECRET)
    print("✅ FatSecret инициализирован")
else:
    print("❌ Ключи FatSecret не найдены")
    fs = None

db = SQLAlchemy(app)

# Функция для хеширования паролей (базовое хеширование)
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Integer)
    height = db.Column(db.Integer)
    weight = db.Column(db.Float)
    gender = db.Column(db.String(10))    
    meals = db.relationship('Meal', backref='user', lazy=True)

class Meal(db.Model):
    __tablename__ = 'meals'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, default=date.today)
    meal_type = db.Column(db.String(10))  # 'breakfast', 'lunch', 'dinner'
    name = db.Column(db.String(100))
    grams = db.Column(db.Float)
    calories = db.Column(db.Float)
    proteins = db.Column(db.Float)
    fats = db.Column(db.Float)
    carbs = db.Column(db.Float)

class DailyStat(db.Model):
    __tablename__ = 'daily_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, default=date.today)
    total_grams = db.Column(db.Float)
    total_calories = db.Column(db.Float)
    total_proteins = db.Column(db.Float)
    total_fats = db.Column(db.Float)
    total_carbs = db.Column(db.Float)
    
    # Добавляем связь с пользователем
    user = db.relationship('User', backref='daily_stats')

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/fatsecret')
def fatsecret_search():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('fatsecret.html')

@app.route('/search-food')
def search_food():
    try:
        if not fs:
            return jsonify({
                "error": "FatSecret не настроен",
                "message": "Проверьте API ключи"
            }), 500

        query = request.args.get('query', '')
        region = request.args.get('region', 'RU')
        language = request.args.get('language', 'ru')
        
        if not query:
            return jsonify({"error": "Введите запрос для поиска"}), 400

        print(f"🔍 Поиск: '{query}', region: {region}, language: {language}")
        
        foods = fs.foods_search(query, max_results=12, region=region, language=language)
        
        print(f"✅ Найдено продуктов: {len(foods) if foods else 0}")
        
        if foods:
            print(f"Пример данных: {foods[0] if len(foods) > 0 else 'Нет данных'}")
        
        return jsonify({
            "foods": {
                "food": foods or []
            }
        })

    except Exception as e:
        print(f"❌ Ошибка поиска: {str(e)}")
        return jsonify({
            "error": str(e),
            "message": "Ошибка при поиске продуктов"
        }), 500

@app.route('/get-food-details/<food_id>')
def get_food_details(food_id):
    try:
        if not fs:
            return jsonify({"error": "FatSecret не настроен"}), 500

        food = fs.food_get(food_id)
        
        if not food:
            return jsonify({"error": "Продукт не найден"}), 404
            
        return jsonify({"food": food})

    except Exception as e:
        print(f"❌ Ошибка получения деталей: {str(e)}")
        return jsonify({"error": str(e)}), 500

def extract_nutrition_info(serving, grams=100):
    """Извлекает информацию о питательной ценности из serving для указанного количества граммов"""
    if isinstance(serving, list):
        serving = serving[0] if serving else {}
    
    # Получаем граммы в стандартной порции
    serving_grams = float(serving.get('metric_serving_amount', serving.get('grams', 100)))
    
    # Рассчитываем коэффициент для указанного количества граммов
    ratio = grams / serving_grams
    
    return {
        'grams': grams,
        'calories': round(float(serving.get('calories', 0)) * ratio),
        'protein': round(float(serving.get('protein', 0)) * ratio, 1),
        'fat': round(float(serving.get('fat', 0)) * ratio, 1),
        'carbohydrate': round(float(serving.get('carbohydrate', 0)) * ratio, 1)
    }


@app.route('/add-from-fatsecret', methods=['POST'])
def add_from_fatsecret():
    try:
        if 'user_id' not in session:
            return jsonify({"error": "Требуется авторизация"}), 401

        data = request.json
        food_id = data.get('food_id')
        meal_type = data.get('meal_type', 'lunch')
        user_grams = data.get('grams', 100)  # Получаем граммы от пользователя
        nutrition_data = data.get('nutrition_data')  # Получаем рассчитанные данные

        if not food_id:
            return jsonify({"error": "Не указан ID продукта"}), 400

        # Получаем детали продукта
        food = fs.food_get(food_id)
        if not food:
            return jsonify({"error": "Продукт не найден"}), 404

        # Обрабатываем информацию о порциях
        servings = food.get('servings', {})
        serving_data = servings.get('serving', [])
        
        if not serving_data:
            return jsonify({"error": "Нет информации о порциях"}), 400

        # Берем первую порцию для расчета
        serving = serving_data[0] if isinstance(serving_data, list) else serving_data
        
        # Если есть предварительно рассчитанные данные, используем их
        if nutrition_data:
            calories = nutrition_data['calories']
            protein = nutrition_data['protein']
            fat = nutrition_data['fat']
            carbs = nutrition_data['carbs']
            grams = nutrition_data['grams']
        else:
            # Иначе рассчитываем вручную на основе стандартной порции
            serving_grams = float(serving.get('metric_serving_amount', serving.get('grams', 100)))
            ratio = user_grams / serving_grams
            
            calories = round(float(serving.get('calories', 0)) * ratio)
            protein = round(float(serving.get('protein', 0)) * ratio, 1)
            fat = round(float(serving.get('fat', 0)) * ratio, 1)
            carbs = round(float(serving.get('carbohydrate', 0)) * ratio, 1)
            grams = user_grams

        # Создаем запись в базе
        new_meal = Meal(
            user_id=session['user_id'],
            meal_type=meal_type,
            name=food.get('food_name', 'Неизвестный продукт'),
            grams=grams,
            calories=calories,
            proteins=protein,
            fats=fat,
            carbs=carbs
        )
        
        db.session.add(new_meal)
        db.session.commit()
        
        # Обновляем статистику
        update_daily_stats(session['user_id'])
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Продукт добавлен в дневник",
            "food": food.get('food_name', 'Неизвестный продукт'),
            "grams": grams
        })

    except Exception as e:
        db.session.rollback()
        print(f"❌ Ошибка добавления: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/debug/fatsecret')
def debug_fatsecret():
    """Проверка работы FatSecret"""
    try:
        if not fs:
            return jsonify({"error": "FatSecret не инициализирован"}), 500
        
        # Тестовый поиск
        test_foods = fs.foods_search('apple', max_results=3)
        
        return jsonify({
            "initialized": fs is not None,
            "test_search": test_foods,
            "consumer_key_set": bool(CONSUMER_KEY),
            "consumer_secret_set": bool(CONSUMER_SECRET)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = User.query.filter_by(login=request.form['email']).first()
        if user and user.password == hash_password(request.form['password']):
            session['user_id'] = user.id  # Сохраняем ID пользователя в сессии
            return redirect(url_for('index'))
        error = 'Неверный логин или пароль'
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    genders = ['Мужской', 'Женский']  # Варианты выбора пола
    
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
                    password=hash_password(request.form['password']),
                    age=int(request.form.get('age', 0)) if request.form.get('age') else None,
                    height=int(request.form.get('height', 170)) if request.form.get('height') else None,
                    weight=float(request.form.get('weight', 0.0)) if request.form.get('weight') else None,
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
    snack_items = []  # Добавляем список для перекусов
    
    for meal in meals:
        if meal.meal_type == 'breakfast':
            breakfast_items.append({
                'id': meal.id,
                'name': meal.name,
                'grams': meal.grams,
                'calories': meal.calories,
                'proteins': meal.proteins,
                'fats': meal.fats,
                'carbs': meal.carbs
            })
        elif meal.meal_type == 'lunch':
            lunch_items.append({
                'id': meal.id,
                'name': meal.name,
                'grams': meal.grams,
                'calories': meal.calories,
                'proteins': meal.proteins,
                'fats': meal.fats,
                'carbs': meal.carbs
            })
        elif meal.meal_type == 'dinner':
            dinner_items.append({
                'id': meal.id,
                'name': meal.name,
                'grams': meal.grams,
                'calories': meal.calories,
                'proteins': meal.proteins,
                'fats': meal.fats,
                'carbs': meal.carbs
            })
        elif meal.meal_type == 'snack':  # Добавляем обработку перекусов
            snack_items.append({
                'id': meal.id,
                'name': meal.name,
                'grams': meal.grams,
                'calories': meal.calories,
                'proteins': meal.proteins,
                'fats': meal.fats,
                'carbs': meal.carbs
            })
    
    # Calculate totals
    breakfast_total = sum(item['calories'] for item in breakfast_items)
    lunch_total = sum(item['calories'] for item in lunch_items)
    dinner_total = sum(item['calories'] for item in dinner_items)
    snack_total = sum(item['calories'] for item in snack_items)  # Добавляем перекусы
    daily_total = breakfast_total + lunch_total + dinner_total + snack_total
    
    daily_data = {
        "date": datetime.now().strftime("%d %B %Y"),
        "time": datetime.now().strftime("%H:%M"),
        "calories": daily_total,
        "breakfast": {
            "total": breakfast_total,
            "foods": breakfast_items
        },
        "lunch": {
            "total": lunch_total,
            "foods": lunch_items
        },
        "dinner": {
            "total": dinner_total,
            "foods": dinner_items
        },
        "snack": {  # Добавляем данные перекуса
            "total": snack_total,
            "foods": snack_items
        }
    }
    
    return render_template('index.html',
                         user=user,
                         daily_data=daily_data)

@app.route('/dci')
def dci():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Получаем данные пользователя из базы данных
    user = User.query.get(session['user_id'])
    return render_template('dci.html', user=user)

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
    
    meal_types = ['breakfast', 'lunch', 'dinner', 'snack']
    
    if request.method == 'POST':
        try:
            new_meal = Meal(
                user_id=session['user_id'],
                meal_type=request.form['meal_type'],
                name=request.form['name'],
                grams=float(request.form['grams']),
                calories=float(request.form['calories']),
                proteins=float(request.form['proteins']),
                fats=float(request.form['fats']),
                carbs=float(request.form['carbs'])
            )
            db.session.add(new_meal)
            db.session.commit()  # Сначала коммитим meal
            
            # Теперь обновляем статистику
            update_daily_stats(session['user_id'])
            db.session.commit()  # Коммитим статистику
            
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            return render_template('add_meal.html', 
                                error=str(e),
                                meal_types=meal_types)
    
    meal_type = request.args.get('meal_type', '')
    return render_template('add_meal.html',
                         meal_types=meal_types,
                         default_meal_type=meal_type)

@app.route('/edit_meal/<int:id>', methods=['GET', 'POST'])
def edit_meal(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    meal = Meal.query.get_or_404(id)
    if meal.user_id != session['user_id']:
        abort(403)
    
    meal_types = ['breakfast', 'lunch', 'dinner', 'snack'] 
    
    if request.method == 'POST':
        try:
            meal.meal_type = request.form['meal_type']
            meal.name = request.form['name']
            meal.grams = float(request.form['grams'])
            meal.calories = float(request.form['calories'])
            meal.proteins = float(request.form['proteins'])
            meal.fats = float(request.form['fats'])
            meal.carbs = float(request.form['carbs'])
            
            db.session.commit()
            update_daily_stats(session['user_id'])
            db.session.commit()
            
            flash('Блюдо успешно обновлено!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            return render_template('edit_meal.html', 
                                meal=meal,
                                meal_types=meal_types,
                                error=str(e))
    
    return render_template('edit_meal.html',
                         meal=meal,
                         meal_types=meal_types)

def update_daily_stats(user_id):
    today = date.today()
    
    # Проверяем, существует ли запись за сегодня
    stat = DailyStat.query.filter_by(
        user_id=user_id,
        date=today
    ).first()
    
    # Суммируем все приемы пищи за сегодня
    meals = Meal.query.filter_by(
        user_id=user_id,
        date=today
    ).all()
    
    # Рассчитываем итоги
    total_grams = sum(m.grams for m in meals)
    total_calories = sum(m.calories for m in meals)
    total_proteins = sum(m.proteins for m in meals)
    total_fats = sum(m.fats for m in meals)
    total_carbs = sum(m.carbs for m in meals)
    
    if not stat:
        # Создаем новую запись
        stat = DailyStat(
            user_id=user_id,
            date=today,
            total_grams=total_grams,
            total_calories=total_calories,
            total_proteins=total_proteins,
            total_fats=total_fats,
            total_carbs=total_carbs
        )
        db.session.add(stat)
    else:
        # Обновляем существующую запись
        stat.total_grams = total_grams
        stat.total_calories = total_calories
        stat.total_proteins = total_proteins
        stat.total_fats = total_fats
        stat.total_carbs = total_carbs

@app.route('/debug/stats')
def debug_stats():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    today = date.today()
    
    # Получаем все meals за сегодня
    meals = Meal.query.filter_by(
        user_id=session['user_id'],
        date=today
    ).all()
    
    # Получаем статистику за сегодня
    stat = DailyStat.query.filter_by(
        user_id=session['user_id'],
        date=today
    ).first()
    
    return jsonify({
        'meals_today': len(meals),
        'meals_details': [{'name': m.name, 'calories': m.calories} for m in meals],
        'stat_exists': stat is not None,
        'stat_details': {
            'grams': stat.total_grams if stat else 0,
            'calories': stat.total_calories if stat else 0,
            'proteins': stat.total_proteins if stat else 0,
            'fats': stat.total_fats if stat else 0,
            'carbs': stat.total_carbs if stat else 0
        } if stat else None
    })

@app.route('/delete_meal/<int:id>', methods=['POST'])
def delete_meal(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    meal = Meal.query.get_or_404(id)
    if meal.user_id != session['user_id']:
        abort(403)
    
    db.session.delete(meal)
    db.session.commit()  # Сначала удаляем meal
    
    # Теперь обновляем статистику
    update_daily_stats(session['user_id'])
    db.session.commit()  # Коммитим статистику
    
    return redirect(url_for('index'))

@app.route('/stats')
def stats():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Получаем статистику и сортируем по дате (новые сверху)
    stats = DailyStat.query.filter_by(
        user_id=session['user_id']
    ).order_by(DailyStat.date.desc()).limit(30).all()
    
    # Дебаг вывод
    print(f"📊 Найдено записей статистики: {len(stats)}")
    for stat in stats:
        print(f"📅 {stat.date}: {stat.total_calories} ккал")
    
    return render_template('stats.html', stats=stats)

@app.route('/save_day', methods=['POST'])
def save_day():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    update_daily_stats(session['user_id'])
    db.session.commit()
    
    flash('Дневный рацион сохранен!', 'success')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        
        if form_type == 'profile':
            # Обновление данных профиля
            try:
                user.age = int(request.form.get('age', user.age)) if request.form.get('age') else user.age
                user.height = int(request.form.get('height', user.height)) if request.form.get('height') else user.height
                user.weight = float(request.form.get('weight', user.weight)) if request.form.get('weight') else user.weight
                user.gender = request.form.get('gender', user.gender)
                
                db.session.commit()
                flash('Профиль успешно обновлен!', 'success')
                return redirect(url_for('profile'))
            except ValueError:
                flash('Ошибка в данных. Проверьте вводимые значения.', 'error')
        
        elif form_type == 'password_change':
            # Смена пароля
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            # Проверяем текущий пароль
            if user.password != hash_password(current_password):
                flash('Текущий пароль неверен', 'error')
            elif not new_password:
                flash('Введите новый пароль', 'error')
            elif len(new_password) < 6:
                flash('Пароль должен содержать не менее 6 символов', 'error')
            elif new_password != confirm_password:
                flash('Новый пароль и подтверждение не совпадают', 'error')
            else:
                # Обновляем пароль
                user.password = hash_password(new_password)
                db.session.commit()
                flash('Пароль успешно изменен!', 'success')
                return redirect(url_for('profile'))
    
    return render_template('profile.html', user=user)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    app.run(debug=True)