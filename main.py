
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

# Environment variables
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='bot.log',
    filemode='a'
)
logger = logging.getLogger(__name__)

# Configure Gemini
configure(api_key=GEMINI_API_KEY)
gemini_model = GenerativeModel('gemini-1.5-flash')  # Free tier model

# Configure Groq
groq_client = Groq(api_key=GROQ_API_KEY)

# User data storage (in-memory for simplicity; use database for production)
user_data = {}

# Tarot layouts (mystical names for user, real names for AI)
TAROT_LAYOUTS = {
    'رازهای نهفته': 'Celtic Cross',  # 10 cards
    'مسیر سرنوشت': 'Three Card Spread',  # 3 cards
    'آینه灵魂': 'One Card Draw',  # 1 card
    'چرخه تقدیر': 'Past Present Future',  # 3 cards
    'هماهنگی ستارگان': 'Relationship Spread'  # 7 cards
}

# Tarot card names (00-77 as per user)
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

# Main menu
MAIN_MENU = ReplyKeyboardMarkup([
    ['تعبیر خواب 🌙', 'فال قهوه ☕️'],
    ['فال تاروت 🃏', 'توضیحات 📜'],
    ['خانه 🏠', 'خانه تکانی 🧹']
], resize_keyboard=True, one_time_keyboard=False)

# Mystical welcome message (shown before /start)
WELCOME_MESSAGE = "🌌 ای مسافر شب‌های پرستاره، به نجوای رویا خوش آمدی... جایی که اسرار نهفته در اعماق روحت آشکار می‌شود. با زدن /start، درهای راز را بگشای. ✨"

# ادامه کد شما ...
# لطفاً اینجا کل کد اصلی شما ادامه پیدا کند
