import sqlite3
import os
import logging
import json
from datetime import datetime
import hashlib
import secrets
import random
import string

class DatabaseManager:
    def __init__(self):
        self.data_dir = "data"
        self.tests_db = os.path.join(self.data_dir, "tests.db")
        self.users_db = os.path.join(self.data_dir, "users.db")
        self._init_databases()
    
    def _init_databases(self):
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Инициализация базы тестов
        conn_tests = sqlite3.connect(self.tests_db)
        cursor_tests = conn_tests.cursor()
        
        cursor_tests.execute("""
            CREATE TABLE IF NOT EXISTS tests (
                test_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_by INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor_tests.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER,
                text TEXT NOT NULL,
                question_order INTEGER,
                FOREIGN KEY (test_id) REFERENCES tests(test_id) ON DELETE CASCADE
            )
        """)
        
        cursor_tests.execute("""
            CREATE TABLE IF NOT EXISTS options (
                option_id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER,
                text TEXT NOT NULL,
                is_correct BOOLEAN DEFAULT 0,
                FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE
            )
        """)
        
        cursor_tests.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER,
                full_name TEXT NOT NULL,
                position TEXT,
                department TEXT,
                created_by INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES tests(test_id)
            )
        """)
        
        cursor_tests.execute("""
            CREATE TABLE IF NOT EXISTS personal_codes (
                code_id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER,
                candidate_id INTEGER,
                code TEXT UNIQUE NOT NULL,
                is_used BOOLEAN DEFAULT 0,
                created_by INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES tests(test_id),
                FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id)
            )
        """)
        
        # Создаем администратора по умолчанию если нет пользователей
        conn_users = sqlite3.connect(self.users_db)
        cursor_users = conn_users.cursor()
        
        cursor_users.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                role TEXT DEFAULT 'admin',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                created_by INTEGER
            )
        """)
        
        cursor_users.execute("""
            CREATE TABLE IF NOT EXISTS telegram_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                consent_accepted BOOLEAN DEFAULT 0,
                consent_accepted_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor_users.execute("""
            CREATE TABLE IF NOT EXISTS results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                test_id INTEGER,
                code TEXT,
                score INTEGER,
                total_questions INTEGER,
                finished_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES telegram_users(user_id)
            )
        """)
        
        cursor_users.execute("""
            CREATE TABLE IF NOT EXISTS testing_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                test_id INTEGER,
                code TEXT,
                current_question INTEGER DEFAULT 0,
                answers TEXT,
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES telegram_users(user_id)
            )
        """)
        
        # Создаем администратора по умолчанию
        cursor_users.execute("SELECT COUNT(*) FROM admin_users WHERE username = 'admin'")
        if cursor_users.fetchone()[0] == 0:
            default_password = "admin123"
            password_hash = self._hash_password(default_password)
            try:
                cursor_users.execute(
                    "INSERT INTO admin_users (username, password_hash, email, role) VALUES (?, ?, ?, ?)",
                    ("admin", password_hash, "admin@example.com", "administrator")
                )
                print("Создан администратор по умолчанию: admin / admin123 (роль: Администратор)")
            except sqlite3.IntegrityError as e:
                print(f"Ошибка при создании администратора: {e}")
        
        conn_tests.commit()
        conn_tests.close()
        conn_users.commit()
        conn_users.close()
    
    def _hash_password(self, password):
        """Хеширование пароля"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    # === МЕТОДЫ ДЛЯ АУТЕНТИФИКАЦИИ АДМИНОВ ===
    
    def authenticate_admin(self, username, password):
        """Аутентификация администратора"""
        conn = sqlite3.connect(self.users_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM admin_users WHERE username = ? AND is_active = 1",
            (username,)
        )
        user = cursor.fetchone()
        conn.close()
        
        if user:
            user_dict = dict(user)
            password_hash = self._hash_password(password)
            if user_dict['password_hash'] == password_hash:
                return user_dict
        
        return None
    
    def create_admin_user(self, username, password, email, role="hr", current_user_id=None):
        """Создать нового администратора"""
        conn = sqlite3.connect(self.users_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM admin_users WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            return False, "Пользователь с таким именем уже существует"
        
        password_hash = self._hash_password(password)
        cursor.execute(
            "INSERT INTO admin_users (username, password_hash, email, role, created_by) VALUES (?, ?, ?, ?, ?)",
            (username, password_hash, email, role, current_user_id)
        )
        conn.commit()
        conn.close()
        return True, "Пользователь успешно создан"
    
    def get_all_admin_users(self):
        """Получить всех администраторов"""
        conn = sqlite3.connect(self.users_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT a1.*, a2.username as created_by_username 
            FROM admin_users a1 
            LEFT JOIN admin_users a2 ON a1.created_by = a2.user_id 
            ORDER BY a1.created_at DESC
        """)
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return users
    
    def get_admin_user_by_id(self, user_id):
        """Получить администратора по ID"""
        conn = sqlite3.connect(self.users_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM admin_users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    
    def update_admin_user(self, user_id, username, email, role, is_active):
        """Обновить администратора"""
        conn = sqlite3.connect(self.users_db)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE admin_users SET username = ?, email = ?, role = ?, is_active = ? WHERE user_id = ?",
            (username, email, role, 1 if is_active else 0, user_id)
        )
        conn.commit()
        conn.close()
        return True
    
    def delete_admin_user(self, user_id, current_user_id):
        """Удалить администратора"""
        if user_id == current_user_id:
            return False, "Нельзя удалить самого себя"
        
        conn = sqlite3.connect(self.users_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM admin_users WHERE created_by = ?", (user_id,))
        if cursor.fetchone()[0] > 0:
            conn.close()
            return False, "Нельзя удалить пользователя, который создал других пользователей"
        
        cursor.execute("DELETE FROM admin_users WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True, "Пользователь успешно удален"
    
    def change_password(self, user_id, new_password):
        """Изменить пароль текущего пользователя"""
        conn = sqlite3.connect(self.users_db)
        cursor = conn.cursor()
        
        password_hash = self._hash_password(new_password)
        cursor.execute(
            "UPDATE admin_users SET password_hash = ? WHERE user_id = ?",
            (password_hash, user_id)
        )
        conn.commit()
        conn.close()
        return True
    
    def change_user_password(self, admin_user_id, target_user_id, new_password):
        """Смена пароля другого пользователя (только для администраторов)"""
        conn = sqlite3.connect(self.users_db)
        cursor = conn.cursor()
        
        # Проверяем, что текущий пользователь - администратор
        cursor.execute("SELECT role FROM admin_users WHERE user_id = ?", (admin_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user or current_user[0] != 'administrator':
            conn.close()
            return False, "Только администраторы могут менять пароли других пользователей"
        
        # Проверяем, что целевой пользователь существует
        cursor.execute("SELECT username FROM admin_users WHERE user_id = ?", (target_user_id,))
        target_user = cursor.fetchone()
        
        if not target_user:
            conn.close()
            return False, "Пользователь не найден"
        
        # Меняем пароль
        password_hash = self._hash_password(new_password)
        cursor.execute(
            "UPDATE admin_users SET password_hash = ? WHERE user_id = ?",
            (password_hash, target_user_id)
        )
        
        conn.commit()
        conn.close()
        return True, f"Пароль для пользователя {target_user[0]} успешно изменен"
    
    # === МЕТОДЫ ДЛЯ ТЕСТОВ ===
    
    def get_all_tests(self, user_id=None):
        """Получить все тесты"""
        conn = sqlite3.connect(self.tests_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute("SELECT * FROM tests WHERE created_by = ? ORDER BY created_at DESC", (user_id,))
        else:
            cursor.execute("SELECT * FROM tests ORDER BY created_at DESC")
        
        tests = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return tests
    
    def get_test_by_id(self, test_id):
        """Получить тест по ID"""
        conn = sqlite3.connect(self.tests_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tests WHERE test_id = ?", (test_id,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    
    def create_test(self, title, description, created_by):
        """Создать новый тест"""
        conn = sqlite3.connect(self.tests_db)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO tests (title, description, created_by) VALUES (?, ?, ?)",
            (title, description, created_by)
        )
        test_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return test_id
    
    def update_test(self, test_id, title, description, is_active):
        """Обновить тест"""
        conn = sqlite3.connect(self.tests_db)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE tests SET title = ?, description = ?, is_active = ? WHERE test_id = ?",
            (title, description, 1 if is_active else 0, test_id)
        )
        conn.commit()
        conn.close()
    
    def delete_test(self, test_id):
        """Удалить тест"""
        conn = sqlite3.connect(self.tests_db)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM tests WHERE test_id = ?", (test_id,))
        conn.commit()
        conn.close()
        return True
    
    # === МЕТОДЫ ДЛЯ ВОПРОСОВ ===
    
    def get_questions_for_test(self, test_id):
        """Получить все вопросы для теста"""
        conn = sqlite3.connect(self.tests_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM questions 
            WHERE test_id = ? 
            ORDER BY question_order
        """, (test_id,))
        questions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return questions
    
    def get_question_by_id(self, question_id):
        """Получить вопрос по ID"""
        conn = sqlite3.connect(self.tests_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM questions WHERE question_id = ?", (question_id,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    
    def create_question(self, test_id, text, question_order):
        """Создать вопрос"""
        conn = sqlite3.connect(self.tests_db)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO questions (test_id, text, question_order) VALUES (?, ?, ?)",
            (test_id, text, question_order)
        )
        question_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return question_id
    
    def update_question(self, question_id, text, question_order):
        """Обновить вопрос"""
        conn = sqlite3.connect(self.tests_db)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE questions SET text = ?, question_order = ? WHERE question_id = ?",
            (text, question_order, question_id)
        )
        conn.commit()
        conn.close()
        return True
    
    def delete_question(self, question_id):
        """Удалить вопрос"""
        conn = sqlite3.connect(self.tests_db)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM questions WHERE question_id = ?", (question_id,))
        conn.commit()
        conn.close()
        return True
    
    def get_options_for_question(self, question_id):
        """Получить варианты ответов для вопроса"""
        conn = sqlite3.connect(self.tests_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM options WHERE question_id = ? ORDER BY option_id", (question_id,))
        options = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return options
    
    def create_option(self, question_id, text, is_correct):
        """Создать вариант ответа"""
        conn = sqlite3.connect(self.tests_db)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO options (question_id, text, is_correct) VALUES (?, ?, ?)",
            (question_id, text, is_correct)
        )
        conn.commit()
        conn.close()
    
    def update_option(self, option_id, text, is_correct):
        """Обновить вариант ответа"""
        conn = sqlite3.connect(self.tests_db)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE options SET text = ?, is_correct = ? WHERE option_id = ?",
            (text, is_correct, option_id)
        )
        conn.commit()
        conn.close()
        return True
    
    def delete_option(self, option_id):
        """Удалить вариант ответа"""
        conn = sqlite3.connect(self.tests_db)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM options WHERE option_id = ?", (option_id,))
        conn.commit()
        conn.close()
        return True
    
    # === МЕТОДЫ ДЛЯ КАНДИДАТОВ ===
    
    def create_candidate(self, test_id, full_name, position, department, created_by):
        """Создать кандидата"""
        conn = sqlite3.connect(self.tests_db)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO candidates (test_id, full_name, position, department, created_by) VALUES (?, ?, ?, ?, ?)",
            (test_id, full_name, position, department, created_by)
        )
        candidate_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return candidate_id
    
    def get_candidates_for_test(self, test_id):
        """Получить всех кандидатов для теста"""
        conn = sqlite3.connect(self.tests_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT c.*
            FROM candidates c
            WHERE c.test_id = ?
            ORDER BY c.created_at DESC
        """, (test_id,))
        
        candidates = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return candidates
    
    def get_candidate_by_id(self, candidate_id):
        """Получить кандидата по ID"""
        conn = sqlite3.connect(self.tests_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM candidates WHERE candidate_id = ?", (candidate_id,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    
    def update_candidate(self, candidate_id, full_name, position, department):
        """Обновить кандидата"""
        conn = sqlite3.connect(self.tests_db)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE candidates SET full_name = ?, position = ?, department = ? WHERE candidate_id = ?",
            (full_name, position, department, candidate_id)
        )
        conn.commit()
        conn.close()
        return True
    
    def delete_candidate(self, candidate_id):
        """Удалить кандидата"""
        conn = sqlite3.connect(self.tests_db)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM candidates WHERE candidate_id = ?", (candidate_id,))
        conn.commit()
        conn.close()
        return True
    
    # === МЕТОДЫ ДЛЯ КОДОВ ===
    
    def generate_codes_for_candidate(self, candidate_id, count, created_by):
        """Сгенерировать коды для конкретного кандидата"""
        conn = sqlite3.connect(self.tests_db)
        cursor = conn.cursor()
        
        # Получаем информацию о кандидате и тесте
        cursor.execute("SELECT test_id FROM candidates WHERE candidate_id = ?", (candidate_id,))
        candidate = cursor.fetchone()
        if not candidate:
            conn.close()
            return []
        
        test_id = candidate[0]
        
        codes = []
        for _ in range(count):
            # Генерируем код формата: ABC12345
            code = ''.join(random.choices(string.ascii_uppercase, k=3)) + \
                   ''.join(random.choices(string.digits, k=5))
            try:
                cursor.execute(
                    "INSERT INTO personal_codes (test_id, candidate_id, code, created_by) VALUES (?, ?, ?, ?)",
                    (test_id, candidate_id, code, created_by)
                )
                codes.append(code)
            except sqlite3.IntegrityError:
                continue
        
        conn.commit()
        conn.close()
        return codes
    
    def get_codes_for_candidate(self, candidate_id):
        """Получить все коды для кандидата"""
        conn = sqlite3.connect(self.tests_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT pc.* 
            FROM personal_codes pc
            WHERE pc.candidate_id = ?
            ORDER BY pc.created_at DESC
        """, (candidate_id,))
        
        codes = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return codes
    
    def get_codes_for_test(self, test_id):
        """Получить все коды для теста с информацией о кандидатах"""
        conn = sqlite3.connect(self.tests_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT pc.*, c.full_name, c.position, c.department
            FROM personal_codes pc
            LEFT JOIN candidates c ON pc.candidate_id = c.candidate_id
            WHERE pc.test_id = ?
            ORDER BY c.full_name, pc.created_at DESC
        """, (test_id,))
        
        codes = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return codes
    
    # === МЕТОДЫ ДЛЯ СТАТИСТИКИ КАНДИДАТОВ ===
    
    def get_candidate_results(self, candidate_id):
        """Получить результаты кандидата"""
        conn_tests = sqlite3.connect(self.tests_db)
        cursor_tests = conn_tests.cursor()
        
        # Получаем информацию о кандидате
        cursor_tests.execute("""
            SELECT c.*, t.title as test_title
            FROM candidates c
            JOIN tests t ON c.test_id = t.test_id
            WHERE c.candidate_id = ?
        """, (candidate_id,))
        
        candidate_info = cursor_tests.fetchone()
        conn_tests.close()
        
        if not candidate_info:
            return None
        
        # Получаем результаты из users.db
        conn_users = sqlite3.connect(self.users_db)
        cursor_users = conn_users.cursor()
        
        # Получаем коды кандидата
        conn_tests = sqlite3.connect(self.tests_db)
        cursor_tests = conn_tests.cursor()
        cursor_tests.execute("SELECT code FROM personal_codes WHERE candidate_id = ?", (candidate_id,))
        candidate_codes = [row[0] for row in cursor_tests.fetchall()]
        conn_tests.close()
        
        if not candidate_codes:
            return {
                'candidate_info': candidate_info,
                'results': []
            }
        
        # Получаем результаты по кодам кандидата
        placeholders = ','.join('?' for _ in candidate_codes)
        cursor_users.execute(f"""
            SELECT r.*, u.username, u.first_name
            FROM results r
            JOIN telegram_users u ON r.user_id = u.user_id
            WHERE r.code IN ({placeholders})
            ORDER BY r.finished_at DESC
        """, candidate_codes)
        
        results = cursor_users.fetchall()
        conn_users.close()
        
        return {
            'candidate_info': candidate_info,
            'results': results
        }
    
    def get_test_candidates_statistics(self, test_id):
        """Получить статистику по кандидатам теста"""
        conn_tests = sqlite3.connect(self.tests_db)
        cursor_tests = conn_tests.cursor()
        
        # Получаем базовую информацию о кандидатах
        cursor_tests.execute("""
            SELECT c.candidate_id, c.full_name, c.position, c.department
            FROM candidates c
            WHERE c.test_id = ?
            ORDER BY c.full_name
        """, (test_id,))
        
        candidates_basic = cursor_tests.fetchall()
        
        # Получаем статистику по кодам для каждого кандидата
        enhanced_stats = []
        for candidate in candidates_basic:
            candidate_id = candidate[0]
            
            # Получаем количество кодов
            cursor_tests.execute("""
                SELECT COUNT(*), SUM(CASE WHEN is_used = 1 THEN 1 ELSE 0 END)
                FROM personal_codes 
                WHERE candidate_id = ?
            """, (candidate_id,))
            
            codes_result = cursor_tests.fetchone()
            total_codes = codes_result[0] if codes_result else 0
            used_codes = codes_result[1] if codes_result and codes_result[1] else 0
            
            # Получаем результаты тестирования из users.db
            conn_users = sqlite3.connect(self.users_db)
            cursor_users = conn_users.cursor()
            
            # Получаем коды кандидата
            cursor_tests.execute("SELECT code FROM personal_codes WHERE candidate_id = ?", (candidate_id,))
            candidate_codes = [row[0] for row in cursor_tests.fetchall()]
            
            best_score = 0
            tests_taken = 0
            
            if candidate_codes:
                placeholders = ','.join('?' for _ in candidate_codes)
                cursor_users.execute(f"""
                    SELECT MAX(score * 100.0 / total_questions), COUNT(*)
                    FROM results 
                    WHERE code IN ({placeholders})
                """, candidate_codes)
                
                result = cursor_users.fetchone()
                best_score = result[0] if result and result[0] else 0
                tests_taken = result[1] if result else 0
            
            conn_users.close()
            
            enhanced_stats.append({
                'candidate_id': candidate[0],
                'full_name': candidate[1],
                'position': candidate[2],
                'department': candidate[3],
                'total_codes': total_codes,
                'used_codes': used_codes,
                'best_score': round(best_score, 2),
                'tests_taken': tests_taken
            })
        
        conn_tests.close()
        return enhanced_stats
    
    # === МЕТОДЫ ДЛЯ БОТА ===
    
    def get_test_by_code(self, code):
        """Получить тест по коду"""
        conn = sqlite3.connect(self.tests_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT t.test_id, t.title, t.description, pc.code, c.full_name, c.candidate_id
            FROM personal_codes pc
            JOIN tests t ON pc.test_id = t.test_id
            LEFT JOIN candidates c ON pc.candidate_id = c.candidate_id
            WHERE pc.code = ? AND pc.is_used = 0 AND t.is_active = 1
        """, (code,))
        
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    
    def get_questions_with_options(self, test_id):
        """Получить вопросы с вариантами ответов"""
        conn = sqlite3.connect(self.tests_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT q.question_id, q.text, q.question_order,
                   o.option_id, o.text as option_text, o.is_correct
            FROM questions q
            LEFT JOIN options o ON q.question_id = o.question_id
            WHERE q.test_id = ?
            ORDER BY q.question_order, o.option_id
        """, (test_id,))
        
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        # Группируем варианты по вопросам
        questions = {}
        for row in rows:
            q_id = row['question_id']
            if q_id not in questions:
                questions[q_id] = {
                    'question_id': q_id,
                    'text': row['text'],
                    'question_order': row['question_order'],
                    'options': []
                }
            if row['option_id']:
                questions[q_id]['options'].append({
                    'option_id': row['option_id'],
                    'text': row['option_text'],
                    'is_correct': row['is_correct']
                })
        
        return list(questions.values())
    
    # === МЕТОДЫ ДЛЯ ТЕЛЕГРАМ ПОЛЬЗОВАТЕЛЕЙ ===
    
    def get_or_create_telegram_user(self, user_id, username, first_name):
        """Получить или создать телеграм пользователя"""
        conn = sqlite3.connect(self.users_db)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM telegram_users WHERE user_id = ?", (user_id,)
        )
        user = cursor.fetchone()
        
        if not user:
            cursor.execute(
                "INSERT INTO telegram_users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username, first_name)
            )
            conn.commit()
        
        conn.close()
        return True
    
    def accept_consent(self, user_id):
        """Принять соглашение"""
        conn = sqlite3.connect(self.users_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE telegram_users 
            SET consent_accepted = 1, consent_accepted_at = ?
            WHERE user_id = ?
        """, (datetime.now(), user_id))
        
        conn.commit()
        conn.close()
    
    def has_accepted_consent(self, user_id):
        """Проверить, принял ли пользователь соглашение"""
        conn = sqlite3.connect(self.users_db)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT consent_accepted FROM telegram_users WHERE user_id = ?", (user_id,)
        )
        result = cursor.fetchone()
        conn.close()
        
        return result and result[0] == 1
    
    def mark_code_used(self, code, user_id, test_id, candidate_id=None):
        """Пометить код как использованный и начать сессию"""
        # Помечаем код как использованный в tests.db
        conn_tests = sqlite3.connect(self.tests_db)
        cursor_tests = conn_tests.cursor()
        cursor_tests.execute(
            "UPDATE personal_codes SET is_used = 1 WHERE code = ?", 
            (code,)
        )
        conn_tests.commit()
        conn_tests.close()
        
        # Создаем сессию в users.db
        conn_users = sqlite3.connect(self.users_db)
        cursor_users = conn_users.cursor()
        
        cursor_users.execute("""
            INSERT INTO testing_sessions (user_id, test_id, code, started_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, test_id, code, datetime.now()))
        
        session_id = cursor_users.lastrowid
        conn_users.commit()
        conn_users.close()
        
        return session_id
    
    def save_answer(self, session_id, question_id, answer_index):
        """Сохранить ответ пользователя"""
        conn = sqlite3.connect(self.users_db)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT answers FROM testing_sessions WHERE session_id = ?", 
            (session_id,)
        )
        result = cursor.fetchone()
        
        answers = {}
        if result and result[0]:
            answers = json.loads(result[0])
        
        answers[str(question_id)] = answer_index
        
        cursor.execute("""
            UPDATE testing_sessions 
            SET answers = ?, last_activity = ?, current_question = ?
            WHERE session_id = ?
        """, (json.dumps(answers), datetime.now(), question_id, session_id))
        
        conn.commit()
        conn.close()
    
    def save_result(self, session_id, score, total_questions):
        """Сохранить результат теста"""
        conn = sqlite3.connect(self.users_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT user_id, test_id, code FROM testing_sessions 
            WHERE session_id = ?
        """, (session_id,))
        session = cursor.fetchone()
        
        if session:
            user_id, test_id, code = session
            
            cursor.execute("""
                INSERT INTO results (user_id, test_id, code, score, total_questions)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, test_id, code, score, total_questions))
            
            cursor.execute(
                "DELETE FROM testing_sessions WHERE session_id = ?", 
                (session_id,)
            )
        
        conn.commit()
        conn.close()
    
    # === МЕТОДЫ ДЛЯ СТАТИСТИКИ ===
    
    def get_statistics(self, user_id=None):
        """Получить статистику для админки"""
        conn_users = sqlite3.connect(self.users_db)
        cursor_users = conn_users.cursor()
        
        cursor_users.execute("SELECT COUNT(*) FROM telegram_users")
        total_users = cursor_users.fetchone()[0]
        
        cursor_users.execute("SELECT COUNT(*) FROM results")
        total_tests_taken = cursor_users.fetchone()[0]
        
        cursor_users.execute("SELECT AVG(score * 100.0 / total_questions) FROM results")
        avg_score = cursor_users.fetchone()[0] or 0
        
        conn_tests = sqlite3.connect(self.tests_db)
        cursor_tests = conn_tests.cursor()
        
        if user_id:
            cursor_tests.execute("""
                SELECT t.test_id, t.title, 
                       COUNT(pc.code) as total_codes,
                       SUM(CASE WHEN pc.is_used = 1 THEN 1 ELSE 0 END) as used_codes
                FROM tests t
                LEFT JOIN personal_codes pc ON t.test_id = pc.test_id
                WHERE t.created_by = ?
                GROUP BY t.test_id, t.title
            """, (user_id,))
        else:
            cursor_tests.execute("""
                SELECT t.test_id, t.title, 
                       COUNT(pc.code) as total_codes,
                       SUM(CASE WHEN pc.is_used = 1 THEN 1 ELSE 0 END) as used_codes
                FROM tests t
                LEFT JOIN personal_codes pc ON t.test_id = pc.test_id
                GROUP BY t.test_id, t.title
            """)
        
        tests_stats = cursor_tests.fetchall()
        
        conn_users.close()
        conn_tests.close()
        
        return {
            'total_users': total_users,
            'total_tests_taken': total_tests_taken,
            'avg_score': round(avg_score, 2),
            'tests_stats': tests_stats
        }
    
    def get_admin_statistics(self, admin_user_id):
        """Получить статистику для администратора"""
        conn_users = sqlite3.connect(self.users_db)
        cursor_users = conn_users.cursor()
        
        cursor_users.execute("SELECT COUNT(*) FROM telegram_users")
        total_users = cursor_users.fetchone()[0]
        
        cursor_users.execute("SELECT COUNT(*) FROM results")
        total_tests_taken = cursor_users.fetchone()[0]
        
        cursor_users.execute("SELECT AVG(score * 100.0 / total_questions) FROM results")
        avg_score = cursor_users.fetchone()[0] or 0
        
        conn_users.close()
        
        conn_tests = sqlite3.connect(self.tests_db)
        cursor_tests = conn_tests.cursor()
        
        cursor_tests.execute("""
            SELECT t.test_id, t.title, 
                   COUNT(pc.code) as total_codes,
                   SUM(CASE WHEN pc.is_used = 1 THEN 1 ELSE 0 END) as used_codes
            FROM tests t
            LEFT JOIN personal_codes pc ON t.test_id = pc.test_id
            WHERE t.created_by = ?
            GROUP BY t.test_id, t.title
        """, (admin_user_id,))
        
        tests_stats = cursor_tests.fetchall()
        
        total_tests = len(tests_stats)
        active_tests = 0
        total_codes = 0
        
        for test in tests_stats:
            total_codes += test[2]
            if test[2] > 0:
                active_tests += 1
        
        conn_tests.close()
        
        return {
            'total_users': total_users,
            'total_tests_taken': total_tests_taken,
            'avg_score': round(avg_score, 2),
            'total_tests': total_tests,
            'active_tests': active_tests,
            'total_codes': total_codes
        }
    
    # === МЕТОДЫ ДЛЯ ОЧИСТКИ ===
    
    def clear_user_data(self):
        """Очистить все пользовательские данные"""
        conn_users = sqlite3.connect(self.users_db)
        cursor_users = conn_users.cursor()
        
        cursor_users.execute("DELETE FROM results")
        cursor_users.execute("DELETE FROM testing_sessions")
        cursor_users.execute("DELETE FROM telegram_users")
        
        cursor_users.execute("DELETE FROM sqlite_sequence WHERE name IN ('results', 'testing_sessions', 'telegram_users')")
        
        conn_users.commit()
        conn_users.close()
        
        conn_tests = sqlite3.connect(self.tests_db)
        cursor_tests = conn_tests.cursor()
        
        cursor_tests.execute("UPDATE personal_codes SET is_used = 0")
        conn_tests.commit()
        conn_tests.close()
        
        return True