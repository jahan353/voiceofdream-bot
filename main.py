import os
import logging
import random
import asyncio
from datetime import datetime
from io import BytesIO
from PIL import Image
import requests
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup,
    KeyboardButton, InputMediaPhoto
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from groq import Groq
from google.generativeai import GenerativeModel, configure
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,  # تغییر از DEBUG به INFO برای کاهش لاگ
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()  # افزودن خروجی به کنسول
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Environment variables
try:
    TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
    GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
    GROQ_API_KEY = os.environ['GROQ_API_KEY']
    ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID', '')
    PORT = int(os.environ.get('PORT', 8000))
    logger.info("Environment variables loaded successfully")
except KeyError as e:
    logger.error(f"Missing environment variable: {e}")
    raise ValueError(f"Environment variable {e} is not set!")

# Configure Gemini and Groq
try:
    configure(api_key=GEMINI_API_KEY)
    gemini_model = GenerativeModel('gemini-1.5-flash')
    groq_client = Groq(api_key=GROQ_API_KEY)
    logger.info("Gemini and Groq APIs configured successfully")
except Exception as e:
    logger.error(f"Error configuring APIs: {e}")
    raise

# User data storage (in-memory; use database for production)
user_data = {}

# Tarot layouts
TAROT_LAYOUTS = {
    'رازهای نهفته': 'Celtic Cross',
    'مسیر سرنوشت': 'Three Card Spread',
    'آینه روح': 'One Card Draw',
    'چرخه تقدیر': 'Past Present Future',
    'هماهنگی ستارگان': 'Relationship Spread'
}

# Tarot card names
TAROT_CARDS = [
    'The Fool', 'The Magician', 'The High Priestess', 'The Empress', 'The Emperor',
    'The Hierophant', 'The Lovers', 'The Chariot', 'Strength', 'The Hermit',
    'Wheel of Fortune', 'Justice', 'The Hanged Man', 'Death', 'Temperance',
    'The Devil', 'The Tower', 'The Star', 'The Moon', 'The Sun', 'Judgement', 'The World',
    'Ace of Wands', 'Two of Wands', 'Three of Wands', 'Four of Wands', 'Five of Wands',
    'Six of Wands', 'Seven of Wands', 'Eight of Wands', 'Nine of Wands', 'Ten of Wands',
    'Page of Wands', 'Knight of Wands', 'Queen of Wands', 'King of Wands',
    'Ace of Cups', 'Two of Cups', 'Three of Cups', 'Four of Cups', 'Five of Cups',
    'Six of Cups', 'Seven of Cups', 'Eight of Cups', 'Nine of Cups', 'Ten of Cups',
    'Page of Cups', 'Knight of Cups', 'Queen of Cups', 'King of Cups',
    'Ace of Swords', 'Two of Swords', 'Three of Swords', 'Four of Swords', 'Five of Swords',
    'Six of Swords', 'Seven of Swords', 'Eight of Swords', 'Nine of Swords', 'Ten of Swords',
    'Page of Swords', 'Knight of Swords', 'Queen of Swords', 'King of Swords',
    'Ace of Pentacles', 'Two of Pentacles', 'Three of Pentacles', 'Four of Pentacles', 'Five of Pentacles',
    'Six of Pentacles', 'Seven of Pentacles', 'Eight of Pentacles', 'Nine of Pentacles', 'Ten of Pentacles',
    'Page of Pentacles', 'Knight of Pentacles', 'Queen of Pentacles', 'King of Pentacles'
]

# Persian months
PERSIAN_MONTHS = [
    'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
    'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'
]

# Main menu (shown initially)
MAIN_MENU = ReplyKeyboardMarkup([
    ['تعبیر خواب 🌙', 'فال قهوه ☕️'],
    ['فال تاروت 🃏', 'توضیحات 📜']
], resize_keyboard=True, one_time_keyboard=True)

# Persistent menu (shown after main menu selection)
PERSISTENT_MENU = ReplyKeyboardMarkup([
    ['خانه 🏠', 'خانه تکانی 🧹']
], resize_keyboard=True)

# Welcome message (before /start)
WELCOME_MESSAGE = "🌌 ای مسافر شب‌های پرستاره، به نجوای رویا خوش آمدی... جایی که اسرار نهفته در اعماق روحت آشکار می‌شود. با لمس گزینه آغاز، درهای راز را بگشای. ✨"

async def pre_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Handling pre_start for user {update.effective_user.id}")
    if update.message:
        await update.message.reply_text(WELCOME_MESSAGE, parse_mode='Markdown')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Starting bot for user {user_id}")
    user_data[user_id] = {'state': 'main_menu'}
    await update.message.reply_text(
        "🌟 ای جوینده‌ی حقیقت، به دنیای نجوای رویا قدم نهادی. اسرار کیهان در انتظار توست... ✨\n"
        "حال، کدامین مسیر را برمی‌گزی؟",
        reply_markup=MAIN_MENU
    )

# سایر توابع بدون تغییر (همانند کد قبلی)
# [کلیه توابع handle_message, handle_callback, start_section, ... را اینجا قرار دهید]

# فقط تابع main را تغییر دهید:
if __name__ == '__main__':
    try:
        logger.info("Starting bot application")
        application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

        application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, pre_start))
        application.add_handler(CommandHandler('start', start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(CallbackQueryHandler(handle_callback))
        application.add_handler(MessageHandler(filters.VOICE | filters.PHOTO, handle_message))

        # راه حل ساده‌تر: همیشه از polling استفاده کنید
        logger.info("Running polling (simplified for Railway)")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
            close_loop=False
        )
            
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        # در Railway باید exception را دوباره raise کنیم تا لاگ شود
        raise
