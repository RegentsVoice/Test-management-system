import sqlite3
import os
import logging
from datetime import datetime

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
            CREATE TABLE IF NOT EXISTS personal_codes (
                code_id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER,
                code TEXT UNIQUE NOT NULL,
                is_used BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES tests(test_id)
            )
        """)
        
        conn_tests.commit()
        conn_tests.close()
        
        # Инициализация базы пользователей
        conn_users = sqlite3.connect(self.users_db)
        cursor_users = conn_users.cursor()
        
        cursor_users.execute("""
            CREATE TABLE IF NOT EXISTS users (
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
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        cursor_users.execute("""
            CREATE TABLE IF NOT EXISTS testing_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                test_id INTEGER,
                code TEXT,
                current_question INTEGER DEFAULT 0,
                answers JSON TEXT,
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        conn_users.commit()
        conn_users.close()
    
    # === МЕТОДЫ ДЛЯ ТЕСТОВ ===
    
    def get_all_tests(self):
        """Получить все тесты для админки"""
        conn = sqlite3.connect(self.tests_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tests ORDER BY created_at DESC")
        tests = cursor.fetchall()
        conn.close()
        return tests
    
    def get_test_by_id(self, test_id):
        """Получить тест по ID"""
        conn = sqlite3.connect(self.tests_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tests WHERE test_id = ?", (test_id,))
        test = cursor.fetchone()
        conn.close()
        return test
    
    def create_test(self, title, description):
        """Создать новый тест"""
        conn = sqlite3.connect(self.tests_db)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO tests (title, description) VALUES (?, ?)",
            (title, description)
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
            (title, description, is_active, test_id)
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
        questions = cursor.fetchall()
        conn.close()
        return questions
    
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
    
    # === МЕТОДЫ ДЛЯ КОДОВ ===
    
    def generate_codes(self, test_id, count):
        """Сгенерировать коды для теста"""
        import random
        import string
        
        conn = sqlite3.connect(self.tests_db)
        cursor = conn.cursor()
        
        codes = []
        for _ in range(count):
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            cursor.execute(
                "INSERT INTO personal_codes (test_id, code) VALUES (?, ?)",
                (test_id, code)
            )
            codes.append(code)
        
        conn.commit()
        conn.close()
        return codes
    
    def get_codes_for_test(self, test_id):
        """Получить все коды для теста"""
        conn = sqlite3.connect(self.tests_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT pc.*, u.username, u.user_id, r.finished_at
            FROM personal_codes pc
            LEFT JOIN results r ON pc.code = r.code
            LEFT JOIN users u ON r.user_id = u.user_id
            WHERE pc.test_id = ?
            ORDER BY pc.created_at DESC
        """, (test_id,))
        codes = cursor.fetchall()
        conn.close()
        return codes
    
    # === МЕТОДЫ ДЛЯ БОТА ===
    
    def get_test_by_code(self, code):
        """Получить тест по коду"""
        conn = sqlite3.connect(self.tests_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT t.test_id, t.title, t.description, pc.code
            FROM personal_codes pc
            JOIN tests t ON pc.test_id = t.test_id
            WHERE pc.code = ? AND pc.is_used = 0 AND t.is_active = 1
        """, (code,))
        
        result = cursor.fetchone()
        conn.close()
        return result
    
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
        
        rows = cursor.fetchall()
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
    
    # === МЕТОДЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ===
    
    def get_or_create_user(self, user_id, username, first_name):
        """Получить или создать пользователя"""
        conn = sqlite3.connect(self.users_db)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        user = cursor.fetchone()
        
        if not user:
            cursor.execute(
                "INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
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
            UPDATE users 
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
            "SELECT consent_accepted FROM users WHERE user_id = ?", (user_id,)
        )
        result = cursor.fetchone()
        conn.close()
        
        return result and result[0] == 1
    
    def mark_code_used(self, code, user_id, test_id):
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
        
        # Получаем текущие ответы
        cursor.execute(
            "SELECT answers FROM testing_sessions WHERE session_id = ?", 
            (session_id,)
        )
        result = cursor.fetchone()
        
        answers = {}
        if result and result[0]:
            import json
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
        
        # Получаем данные сессии
        cursor.execute("""
            SELECT user_id, test_id, code FROM testing_sessions 
            WHERE session_id = ?
        """, (session_id,))
        session = cursor.fetchone()
        
        if session:
            user_id, test_id, code = session
            
            # Сохраняем результат
            cursor.execute("""
                INSERT INTO results (user_id, test_id, code, score, total_questions)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, test_id, code, score, total_questions))
            
            # Удаляем сессию
            cursor.execute(
                "DELETE FROM testing_sessions WHERE session_id = ?", 
                (session_id,)
            )
        
        conn.commit()
        conn.close()
    
    # === МЕТОДЫ ДЛЯ СТАТИСТИКИ ===
    
    def get_statistics(self):
        """Получить статистику для админки"""
        conn_users = sqlite3.connect(self.users_db)
        cursor_users = conn_users.cursor()
        
        # Общая статистика
        cursor_users.execute("SELECT COUNT(*) FROM users")
        total_users = cursor_users.fetchone()[0]
        
        cursor_users.execute("SELECT COUNT(*) FROM results")
        total_tests_taken = cursor_users.fetchone()[0]
        
        cursor_users.execute("SELECT AVG(score * 100.0 / total_questions) FROM results")
        avg_score = cursor_users.fetchone()[0] or 0
        
        # Статистика по тестам
        conn_tests = sqlite3.connect(self.tests_db)
        cursor_tests = conn_tests.cursor()
        
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
    
    # === МЕТОДЫ ДЛЯ ОЧИСТКИ ===
    
    def clear_user_data(self):
        """Очистить все пользовательские данные"""
        conn_users = sqlite3.connect(self.users_db)
        cursor_users = conn_users.cursor()
        
        # Очищаем все таблицы пользовательских данных
        cursor_users.execute("DELETE FROM results")
        cursor_users.execute("DELETE FROM testing_sessions")
        cursor_users.execute("DELETE FROM users")
        
        # Сбрасываем автоинкремент
        cursor_users.execute("DELETE FROM sqlite_sequence WHERE name IN ('results', 'testing_sessions', 'users')")
        
        conn_users.commit()
        conn_users.close()
        
        # Сбрасываем коды в tests.db
        conn_tests = sqlite3.connect(self.tests_db)
        cursor_tests = conn_tests.cursor()
        
        cursor_tests.execute("UPDATE personal_codes SET is_used = 0")
        conn_tests.commit()
        conn_tests.close()
        
        return True