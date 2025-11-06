import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from database import DatabaseManager

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'
db = DatabaseManager()

def check_auth():
    return session.get('authenticated', False)

def get_current_user():
    return session.get('user')

def is_administrator():
    user = get_current_user()
    return user and user.get('role') == 'administrator'

def is_hr():
    user = get_current_user()
    return user and user.get('role') in ['hr', 'administrator']

def check_test_access(test_id):
    """Проверка прав доступа к тесту"""
    if not check_auth():
        return False, 'Требуется авторизация'
    
    user = get_current_user()
    if user['role'] == 'administrator':
        return True, None
    
    test = db.get_test_by_id(test_id)
    if not test:
        return False, 'Тест не найден'
    
    if test['created_by'] != user['user_id']:
        return False, 'Доступ запрещен'
    
    return True, None

def check_candidate_access(candidate_id):
    """Проверка прав доступа к кандидату"""
    if not check_auth():
        return False, 'Требуется авторизация'
    
    candidate = db.get_candidate_by_id(candidate_id)
    if not candidate:
        return False, 'Кандидат не найден'
    
    return check_test_access(candidate['test_id'])

# === ОСНОВНЫЕ МАРШРУТЫ ===

@app.route('/')
def index():
    if not check_auth():
        return redirect(url_for('login'))
    
    user = get_current_user()
    stats = db.get_statistics(user['user_id'] if user and user['role'] != 'administrator' else None)
    tests = db.get_all_tests(user['user_id'] if user and user['role'] != 'administrator' else None)
    return render_template('index.html', stats=stats, tests=tests, user=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = db.authenticate_admin(username, password)
        if user:
            session['authenticated'] = True
            session['user'] = user
            flash('Успешный вход в систему!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверные учетные данные', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    session.pop('user', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))

@app.route('/profile')
def profile():
    if not check_auth():
        return redirect(url_for('login'))
    
    user = get_current_user()
    user_stats = db.get_admin_statistics(user['user_id'])
    return render_template('profile.html', user=user, stats=user_stats)

@app.route('/change-password', methods=['POST'])
def change_password():
    if not check_auth():
        return redirect(url_for('login'))
    
    user = get_current_user()
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']
    
    if new_password != confirm_password:
        flash('Пароли не совпадают', 'error')
        return redirect(url_for('profile'))
    
    if len(new_password) < 6:
        flash('Пароль должен содержать минимум 6 символов', 'error')
        return redirect(url_for('profile'))
    
    db.change_password(user['user_id'], new_password)
    flash('Пароль успешно изменен', 'success')
    return redirect(url_for('profile'))

# === УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ===

@app.route('/users')
def users():
    if not check_auth() or not is_administrator():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('index'))
    
    users_list = db.get_all_admin_users()
    return render_template('users.html', users=users_list)

@app.route('/users/create', methods=['GET', 'POST'])
def create_user():
    if not check_auth() or not is_administrator():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        role = request.form['role']
        
        success, message = db.create_admin_user(
            username, password, email, role, 
            get_current_user()['user_id']
        )
        
        if success:
            flash('Пользователь успешно создан', 'success')
            return redirect(url_for('users'))
        else:
            flash(message, 'error')
    
    return render_template('create_user.html')

@app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
def edit_user(user_id):
    if not check_auth() or not is_administrator():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('index'))
    
    user = db.get_admin_user_by_id(user_id)
    if not user:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('users'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        role = request.form['role']
        is_active = request.form.get('is_active') == 'on'
        
        db.update_admin_user(user_id, username, email, role, is_active)
        flash('Пользователь успешно обновлен', 'success')
        return redirect(url_for('users'))
    
    return render_template('edit_user.html', user=user)

@app.route('/users/<int:user_id>/delete', methods=['POST'])
def delete_user(user_id):
    if not check_auth() or not is_administrator():
        return jsonify({'success': False, 'message': 'Доступ запрещен'})
    
    success, message = db.delete_admin_user(user_id, get_current_user()['user_id'])
    return jsonify({'success': success, 'message': message})

# === УПРАВЛЕНИЕ ТЕСТАМИ ===

@app.route('/tests')
def tests():
    if not check_auth() or not is_hr():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('index'))
    
    user = get_current_user()
    tests_list = db.get_all_tests(user['user_id'] if user['role'] != 'administrator' else None)
    return render_template('tests.html', tests=tests_list, user=user)

@app.route('/tests/create', methods=['GET', 'POST'])
def create_test():
    if not check_auth() or not is_hr():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        test_id = db.create_test(title, description, get_current_user()['user_id'])
        flash('Тест успешно создан', 'success')
        return redirect(url_for('edit_test', test_id=test_id))
    
    return render_template('create_test.html')

@app.route('/tests/<int:test_id>/edit')
def edit_test(test_id):
    if not check_auth() or not is_hr():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('index'))
    
    test = db.get_test_by_id(test_id)
    if not test:
        flash('Тест не найден', 'error')
        return redirect(url_for('tests'))
    
    access, message = check_test_access(test_id)
    if not access:
        flash(message, 'error')
        return redirect(url_for('tests'))
    
    questions = db.get_questions_for_test(test_id)
    for question in questions:
        question['options'] = db.get_options_for_question(question['question_id'])
    
    return render_template('edit_test.html', test=test, questions=questions)

@app.route('/tests/<int:test_id>/update', methods=['POST'])
def update_test(test_id):
    if not check_auth() or not is_hr():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('index'))
    
    access, message = check_test_access(test_id)
    if not access:
        flash(message, 'error')
        return redirect(url_for('tests'))
    
    title = request.form['title']
    description = request.form['description']
    is_active = request.form.get('is_active') == 'on'
    
    db.update_test(test_id, title, description, is_active)
    flash('Тест успешно обновлен', 'success')
    return redirect(url_for('edit_test', test_id=test_id))

@app.route('/tests/<int:test_id>/delete', methods=['POST'])
def delete_test(test_id):
    if not check_auth() or not is_hr():
        return jsonify({'success': False, 'message': 'Доступ запрещен'})
    
    access, message = check_test_access(test_id)
    if not access:
        return jsonify({'success': False, 'message': message})
    
    db.delete_test(test_id)
    return jsonify({'success': True, 'message': 'Тест успешно удален'})

# === УПРАВЛЕНИЕ ВОПРОСАМИ ===

@app.route('/tests/<int:test_id>/add_question', methods=['POST'])
def add_question(test_id):
    if not check_auth() or not is_hr():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('index'))
    
    access, message = check_test_access(test_id)
    if not access:
        flash(message, 'error')
        return redirect(url_for('tests'))
    
    text = request.form['text']
    question_order = int(request.form['order'])
    
    question_id = db.create_question(test_id, text, question_order)
    
    options = request.form.getlist('options[]')
    correct_index = int(request.form['correct_index'])
    
    for i, option_text in enumerate(options):
        if option_text.strip():
            is_correct = (i == correct_index)
            db.create_option(question_id, option_text, is_correct)
    
    flash('Вопрос успешно добавлен', 'success')
    return redirect(url_for('edit_test', test_id=test_id))

@app.route('/questions/<int:question_id>/edit', methods=['GET', 'POST'])
def edit_question(question_id):
    if not check_auth() or not is_hr():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('index'))
    
    question = db.get_question_by_id(question_id)
    if not question:
        flash('Вопрос не найден', 'error')
        return redirect(url_for('tests'))
    
    access, message = check_test_access(question['test_id'])
    if not access:
        flash(message, 'error')
        return redirect(url_for('tests'))
    
    options = db.get_options_for_question(question_id)
    
    if request.method == 'POST':
        text = request.form['text']
        question_order = int(request.form['order'])
        
        db.update_question(question_id, text, question_order)
        
        for i, option in enumerate(options):
            option_text = request.form.get(f'option_{option["option_id"]}')
            is_correct = request.form.get(f'correct_{option["option_id"]}') == 'on'
            db.update_option(option['option_id'], option_text, is_correct)
        
        flash('Вопрос успешно обновлен', 'success')
        return redirect(url_for('edit_test', test_id=question['test_id']))
    
    return render_template('edit_question.html', question=question, options=options)

@app.route('/questions/<int:question_id>/delete', methods=['POST'])
def delete_question(question_id):
    if not check_auth() or not is_hr():
        return jsonify({'success': False, 'message': 'Доступ запрещен'})
    
    question = db.get_question_by_id(question_id)
    if not question:
        return jsonify({'success': False, 'message': 'Вопрос не найден'})
    
    access, message = check_test_access(question['test_id'])
    if not access:
        return jsonify({'success': False, 'message': message})
    
    db.delete_question(question_id)
    return jsonify({'success': True, 'message': 'Вопрос успешно удален'})

# === УПРАВЛЕНИЕ КАНДИДАТАМИ ===

@app.route('/candidates')
def all_candidates():
    if not check_auth() or not is_hr():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('index'))
    
    user = get_current_user()
    tests = db.get_all_tests(user['user_id'] if user['role'] != 'administrator' else None)
    
    all_candidates = []
    for test in tests:
        candidates = db.get_candidates_for_test(test['test_id'])
        for candidate in candidates:
            candidate['test_title'] = test['title']
            candidate['test_id'] = test['test_id']
            all_candidates.append(candidate)
    
    candidates_with_stats = []
    for candidate in all_candidates:
        stats = db.get_test_candidates_statistics(candidate['test_id'])
        candidate_stats = next((c for c in stats if c['candidate_id'] == candidate['candidate_id']), None)
        
        if candidate_stats:
            candidate['best_score'] = candidate_stats['best_score']
            candidate['tests_taken'] = candidate_stats['tests_taken']
        else:
            candidate['best_score'] = 0
            candidate['tests_taken'] = 0
            
        candidates_with_stats.append(candidate)
    
    return render_template('all_candidates.html', candidates=candidates_with_stats)

@app.route('/tests/<int:test_id>/candidates')
def test_candidates(test_id):
    if not check_auth() or not is_hr():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('index'))
    
    access, message = check_test_access(test_id)
    if not access:
        flash(message, 'error')
        return redirect(url_for('tests'))
    
    test = db.get_test_by_id(test_id)
    candidates = db.get_candidates_for_test(test_id)
    candidates_stats = db.get_test_candidates_statistics(test_id)
    
    return render_template('candidates.html', test=test, candidates=candidates, candidates_stats=candidates_stats)

@app.route('/candidates/<int:candidate_id>/codes')
def candidate_codes(candidate_id):
    if not check_auth() or not is_hr():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('index'))
    
    access, message = check_candidate_access(candidate_id)
    if not access:
        flash(message, 'error')
        return redirect(url_for('tests'))
    
    candidate = db.get_candidate_by_id(candidate_id)
    test = db.get_test_by_id(candidate['test_id'])
    codes = db.get_codes_for_candidate(candidate_id)
    candidate_results = db.get_candidate_results(candidate_id)
    
    return render_template('candidate_codes.html', candidate=candidate, test=test, codes=codes, candidate_results=candidate_results)

@app.route('/candidates/<int:candidate_id>/generate-codes', methods=['POST'])
def generate_candidate_codes(candidate_id):
    if not check_auth() or not is_hr():
        return jsonify({'success': False, 'message': 'Доступ запрещен'})
    
    access, message = check_candidate_access(candidate_id)
    if not access:
        return jsonify({'success': False, 'message': message})
    
    count = int(request.form['count'])
    codes = db.generate_codes_for_candidate(candidate_id, count, get_current_user()['user_id'])
    return jsonify({'success': True, 'codes': codes, 'count': len(codes)})

# === API МАРШРУТЫ ===

@app.route('/api/tests')
def api_tests():
    """API для получения списка тестов"""
    if not check_auth() or not is_hr():
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    user = get_current_user()
    tests = db.get_all_tests(user['user_id'] if user['role'] != 'administrator' else None)
    return jsonify(tests)

@app.route('/api/candidates', methods=['POST'])
def api_create_candidate():
    """API для создания кандидата"""
    if not check_auth() or not is_hr():
        return jsonify({'success': False, 'message': 'Доступ запрещен'})
    
    full_name = request.form['full_name']
    position = request.form.get('position', '')
    department = request.form.get('department', '')
    test_id = request.form['test_id']
    
    access, message = check_test_access(test_id)
    if not access:
        return jsonify({'success': False, 'message': message})
    
    candidate_id = db.create_candidate(test_id, full_name, position, department, get_current_user()['user_id'])
    return jsonify({'success': True, 'candidate_id': candidate_id})

@app.route('/api/candidates/<int:candidate_id>', methods=['PUT'])
def api_update_candidate(candidate_id):
    """API для обновления кандидата"""
    if not check_auth() or not is_hr():
        return jsonify({'success': False, 'message': 'Доступ запрещен'})
    
    access, message = check_candidate_access(candidate_id)
    if not access:
        return jsonify({'success': False, 'message': message})
    
    full_name = request.form['full_name']
    position = request.form.get('position', '')
    department = request.form.get('department', '')
    
    db.update_candidate(candidate_id, full_name, position, department)
    return jsonify({'success': True})

@app.route('/api/candidates/<int:candidate_id>', methods=['DELETE'])
def api_delete_candidate(candidate_id):
    """API для удаления кандидата"""
    if not check_auth() or not is_hr():
        return jsonify({'success': False, 'message': 'Доступ запрещен'})
    
    access, message = check_candidate_access(candidate_id)
    if not access:
        return jsonify({'success': False, 'message': message})
    
    db.delete_candidate(candidate_id)
    return jsonify({'success': True})

# === СТАТИСТИКА ===

@app.route('/statistics')
def statistics():
    if not check_auth():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('login'))
    
    user = get_current_user()
    stats = db.get_statistics(user['user_id'] if user['role'] != 'administrator' else None)
    return render_template('statistics.html', stats=stats, user=user)

@app.route('/clear-data', methods=['POST'])
def clear_data():
    if not check_auth() or not is_administrator():
        return jsonify({'success': False, 'message': 'Доступ запрещен'})
    
    try:
        db.clear_user_data()
        return jsonify({'success': True, 'message': 'Данные пользователей успешно очищены'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)