import os
import logging
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from database import DatabaseManager

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TestBot:
    def __init__(self, token):
        self.token = token
        self.db = DatabaseManager()
        self.application = Application.builder().token(token).build()
        
        # Регистрация обработчиков
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.handle_button))
        
        # Хранилище сессий
        self.user_sessions = {}
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        self.db.get_or_create_user(user.id, user.username, user.first_name)
        
        if not self.db.has_accepted_consent(user.id):
            # Показываем соглашение
            keyboard = [[InlineKeyboardButton("✅ Принять", callback_data="accept_consent")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            welcome_text = """
👋 Добро пожаловать в бот для тестирования знаний!

Этот бот предназначен для проверки ваших знаний в различных областях. 

Для начала работы необходимо принять условия Политики конфиденциальности и обработки персональных данных.

После принятия вы сможете проходить тесты, используя персональные коды.
            """
            
            # Сохраняем ID стартового сообщения для будущей очистки
            context.user_data['start_message_id'] = update.message.message_id
            
            await update.message.reply_text(welcome_text, reply_markup=reply_markup)
        else:
            # Пользователь уже принял соглашение
            await update.message.reply_text(
                "Введите персональный код для начала теста:"
            )
    
    async def handle_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if query.data == "accept_consent":
            # Пользователь принимает соглашение
            self.db.accept_consent(user_id)
            
            # Удаляем кнопку и обновляем сообщение
            await query.edit_message_text(
                "✅ Вы приняли условия Политики конфиденциальности.\n\n"
                "Введите персональный код для начала теста:"
            )
        
        elif query.data.startswith("answer_"):
            # Обработка ответа на вопрос
            await self.handle_answer(query, context)
    
    async def handle_answer(self, query, context):
        data_parts = query.data.split("_")
        session_id = int(data_parts[1])
        question_id = int(data_parts[2])
        answer_index = int(data_parts[3])
        
        # Сохраняем ответ
        self.db.save_answer(session_id, question_id, answer_index)
        
        # Удаляем клавиатуру с предыдущего сообщения
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception as e:
            logger.warning(f"Could not remove keyboard: {e}")
        
        # Получаем следующий вопрос
        await self.show_next_question(query, context, session_id, question_id)
    
    async def show_next_question(self, query, context, session_id, current_question_id):
        # Получаем информацию о сессии
        user_id = query.from_user.id
        
        if user_id not in self.user_sessions:
            await query.message.reply_text("❌ Сессия теста прервана. Начните заново.")
            return
        
        session_data = self.user_sessions[user_id]
        questions = session_data['questions']
        current_index = session_data['current_question_index']
        
        # Переходим к следующему вопросу
        current_index += 1
        self.user_sessions[user_id]['current_question_index'] = current_index
        
        if current_index < len(questions):
            # Показываем следующий вопрос
            question = questions[current_index]
            keyboard = [
                [InlineKeyboardButton(option['text'], callback_data=f"answer_{session_id}_{question['question_id']}_{idx}")]
                for idx, option in enumerate(question['options'])
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                f"Вопрос {current_index + 1} из {len(questions)}:\n\n{question['text']}",
                reply_markup=reply_markup
            )
        else:
            # Тест завершен
            await self.finish_test(query, context, session_id, session_data)
    
    async def finish_test(self, query, context, session_id, session_data):
        # Вычисляем результат
        score = 0
        total_questions = len(session_data['questions'])
        
        # Здесь должна быть логика проверки правильности ответов
        # Для примера - случайный результат
        import random
        score = random.randint(0, total_questions)
        
        # Сохраняем результат
        self.db.save_result(session_id, score, total_questions)
        
        # Очищаем сессию пользователя
        user_id = query.from_user.id
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        
        # Показываем результат
        result_text = (
            f"🎉 Тест завершен!\n\n"
            f"Ваш результат: {score} из {total_questions} правильных ответов\n"
            f"Успех: {score/total_questions*100:.1f}%"
        )
        
        await query.message.reply_text(result_text)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        text = update.message.text.strip()
        
        if not self.db.has_accepted_consent(user.id):
            await update.message.reply_text("Пожалуйста, сначала примите условия использования через команду /start")
            return
        
        # Проверяем код
        test_info = self.db.get_test_by_code(text)
        if test_info:
            # Начинаем тест
            session_id = self.db.mark_code_used(text, user.id, test_info['test_id'])
            
            # Получаем вопросы теста
            questions = self.db.get_questions_with_options(test_info['test_id'])
            
            if questions:
                # Сохраняем сессию пользователя
                self.user_sessions[user.id] = {
                    'session_id': session_id,
                    'test_id': test_info['test_id'],
                    'questions': questions,
                    'current_question_index': -1,
                    'start_message_id': update.message.message_id
                }
                
                # Показываем первый вопрос
                first_question = questions[0]
                self.user_sessions[user.id]['current_question_index'] = 0
                
                keyboard = [
                    [InlineKeyboardButton(option['text'], callback_data=f"answer_{session_id}_{first_question['question_id']}_{idx}")]
                    for idx, option in enumerate(first_question['options'])
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"Начинаем тест: {test_info['title']}\n\n"
                    f"Вопрос 1 из {len(questions)}:\n{first_question['text']}",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text("❌ В этом тесте нет вопросов.")
        else:
            await update.message.reply_text("❌ Код не найден или уже использован. Проверьте правильность ввода.")
    
    def run(self):
        self.application.run_polling()

if __name__ == "__main__":
    # Получите токен у @BotFather в Telegram
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Замените на ваш токен
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Пожалуйста, установите ваш Telegram Bot Token в переменной BOT_TOKEN")
        print("Получите токен у @BotFather в Telegram")
    else:
        bot = TestBot(BOT_TOKEN)
        print("Бот запущен...")
        bot.run()