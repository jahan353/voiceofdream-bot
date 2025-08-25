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
    # Major Arcana 00-21
    'The Fool', 'The Magician', 'The High Priestess', 'The Empress', 'The Emperor',
    'The Hierophant', 'The Lovers', 'The Chariot', 'Strength', 'The Hermit',
    'Wheel of Fortune', 'Justice', 'The Hanged Man', 'Death', 'Temperance',
    'The Devil', 'The Tower', 'The Star', 'The Moon', 'The Sun', 'Judgement', 'The World',
    # Wands 22-35: Ace to King
    'Ace of Wands', 'Two of Wands', 'Three of Wands', 'Four of Wands', 'Five of Wands',
    'Six of Wands', 'Seven of Wands', 'Eight of Wands', 'Nine of Wands', 'Ten of Wands',
    'Page of Wands', 'Knight of Wands', 'Queen of Wands', 'King of Wands',
    # Cups 36-49
    'Ace of Cups', 'Two of Cups', 'Three of Cups', 'Four of Cups', 'Five of Cups',
    'Six of Cups', 'Seven of Cups', 'Eight of Cups', 'Nine of Cups', 'Ten of Cups',
    'Page of Cups', 'Knight of Cups', 'Queen of Cups', 'King of Cups',
    # Swords 50-63
    'Ace of Swords', 'Two of Swords', 'Three of Swords', 'Four of Swords', 'Five of Swords',
    'Six of Swords', 'Seven of Swords', 'Eight of Swords', 'Nine of Swords', 'Ten of Swords',
    'Page of Swords', 'Knight of Swords', 'Queen of Swords', 'King of Swords',
    # Pentacles 64-77
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

async def pre_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(WELCOME_MESSAGE, parse_mode='Markdown')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data:
        user_data[user_id] = {}
    await update.message.reply_text(
        "🌟 ای جوینده‌ی حقیقت، به دنیای نجوای رویا قدم نهادی. اسرار کیهان در انتظار توست... ✨\n"
        "حال، کدامین مسیر را برمی‌گزی؟",
        reply_markup=MAIN_MENU
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text if update.message.text else None

    if user_id not in user_data:
        user_data[user_id] = {}

    if 'awaiting' in user_data[user_id]:
        awaiting = user_data[user_id]['awaiting']

        if awaiting == 'gender':
            if text in ['مرد 👨', 'زن 👩']:
                user_data[user_id]['gender'] = text
                await ask_birth_month(update, context)
            else:
                await update.message.reply_text("🌑 ای مسافر، انتخابی درست بنما... مرد یا زن؟ ✨")
            return

        elif awaiting == 'birth_month':
            if text in PERSIAN_MONTHS:
                user_data[user_id]['birth_month'] = PERSIAN_MONTHS.index(text) + 1
                await ask_birth_year(update, context)
            else:
                await update.message.reply_text("🌑 ای جوینده، ماهی از تقویم شمسی برگزین... ✨")
            return

        elif awaiting == 'birth_year':
            try:
                year = int(text)
                current_year = datetime.now().year
                if 1900 <= year <= current_year:
                    user_data[user_id]['birth_year'] = year
                    del user_data[user_id]['awaiting']
                    await proceed_to_section(update, context, user_data[user_id]['section'])
                else:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("🌑 ای مسافر، سالی معتبر از تقویم شمسی وارد کن... ✨")
            return

        elif awaiting == 'dream':
            if update.message.voice:
                # Download voice
                voice_file = await update.message.voice.get_file()
                voice_bytes = await voice_file.download_as_bytearray()
                # STT with Groq Whisper
                with open('temp.ogg', 'wb') as f:
                    f.write(voice_bytes)
                with open('temp.ogg', 'rb') as audio:
                    transcription = groq_client.audio.transcriptions.create(
                        file=audio,
                        model='whisper-large-v3',
                        language='fa'
                    )
                dream_text = transcription.text
                os.remove('temp.ogg')
            else:
                dream_text = text

            await interpret_dream(update, context, dream_text)
            del user_data[user_id]['awaiting']
            return

        elif awaiting == 'coffee_photo':
            if update.message.photo:
                photo_file = await update.message.photo[-1].get_file()
                photo_bytes = await photo_file.download_as_bytearray()
                await interpret_coffee(update, context, photo_bytes)
            else:
                await update.message.reply_text("🌑 ای جوینده، تصویری واضح از فنجان ارسال کن... ✨")
            return

    elif text == 'خانه 🏠':
        await update.message.reply_text(
            "🏠 به خانه بازگشتی، ای مسافر... اسرار پیشین همچنان نهفته‌اند. ✨",
            reply_markup=MAIN_MENU
        )

    elif text == 'خانه تکانی 🧹':
        if user_id in user_data:
            del user_data[user_id]
        await update.message.reply_text(
            "🧹 بادهای تغییر وزیدند و همه چیز پاک شد... از نو آغاز کن، ای جوینده. ✨",
            reply_markup=MAIN_MENU
        )

    elif text == 'تعبیر خواب 🌙':
        await start_section(update, context, 'dream')

    elif text == 'فال قهوه ☕️':
        await start_section(update, context, 'coffee')

    elif text == 'فال تاروت 🃏':
        await start_section(update, context, 'tarot')

    elif text == 'توضیحات 📜':
        await show_explanations(update, context)

    else:
        await update.message.reply_text("🌑 مسیری ناشناخته... از منو برگزین، ای مسافر. ✨")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if data.startswith('gender_'):
        gender = 'مرد 👨' if data == 'gender_male' else 'زن 👩'
        user_data[user_id]['gender'] = gender
        await query.answer()
        await ask_birth_month(query.message, context)

    elif data.startswith('month_'):
        month = int(data.split('_')[1])
        user_data[user_id]['birth_month'] = month
        await query.answer()
        await ask_birth_year(query.message, context)

    elif data.startswith('tarot_layout_'):
        layout_key = data.split('_')[2]
        user_data[user_id]['tarot_layout'] = layout_key
        layout_real = TAROT_LAYOUTS[layout_key]
        # Number of cards based on layout
        card_counts = {
            'Celtic Cross': 10,
            'Three Card Spread': 3,
            'One Card Draw': 1,
            'Past Present Future': 3,
            'Relationship Spread': 7
        }
        num_cards = card_counts[layout_real]
        # Draw random cards
        cards = random.sample(range(78), num_cards)
        orientations = [random.choice(['upright', 'reversed']) for _ in range(num_cards)]
        user_data[user_id]['tarot_cards'] = list(zip(cards, orientations))
        await query.answer()
        await interpret_tarot(query.message, context)

async def start_section(update: Update, context: ContextTypes.DEFAULT_TYPE, section: str):
    user_id = update.effective_user.id
    user_data[user_id]['section'] = section

    if 'gender' not in user_data[user_id] or 'birth_month' not in user_data[user_id] or 'birth_year' not in user_data[user_id]:
        await ask_gender(update, context)
    else:
        await proceed_to_section(update, context, section)

async def proceed_to_section(update: Update, context: ContextTypes.DEFAULT_TYPE, section: str):
    user_id = update.effective_user.id
    if section == 'dream':
        await update.message.reply_text(
            "🌙 ای خواب‌دیده، راز خوابت را با کلمات یا صدا برایم بازگو کن... ✨",
            reply_markup=MAIN_MENU
        )
        user_data[user_id]['awaiting'] = 'dream'

    elif section == 'coffee':
        await update.message.reply_text(
            "☕️ *آداب خواندن نقش تقدیر* ☕️\n\n"
            "ای جوینده‌ی راز، برای آنکه نقاب از چهره‌ی سرنوشت برگیری، این آداب را به جای آور:\n\n"
            "۱. قهوه‌ات را با طمأنینه و حضور قلب بنوش، و بگذار اندکی از آن در ژرفای فنجان باقی بماند.\n"
            "۲. نعلبکی را چون آسمانی بر فنجان زمینی‌ات قرار ده.\n"
            "۳. فنجان را به آرامی نزدیک قلب خود آور، آن را با نیتی خالص و در سکوت، به سمت بیرون بچرخان و برگردان.\n"
            "۴. اکنون صبر کن... بگذار تا جوهر تقدیر بر دیواره‌ی فنجان خشک شود و اشکال پدیدار گردند.\n"
            "۵. سرانجام، تصویری **واضح، روشن و کاملاً از بالا** از تمام نمای داخل فنجان برایم ارسال کن.\n\n"
            "من در انتظارم تا اسرار نهفته در آن را برایت بازگو کنم. ✨",
            parse_mode='Markdown',
            reply_markup=MAIN_MENU
        )
        user_data[user_id]['awaiting'] = 'coffee_photo'

    elif section == 'tarot':
        keyboard = []
        for key in TAROT_LAYOUTS:
            keyboard.append([InlineKeyboardButton(key, callback_data=f'tarot_layout_{key}')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🃏 ای جوینده‌ی کارت‌های تقدیر، چیدمانی را برگزین... ✨",
            reply_markup=reply_markup
        )

async def ask_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton('مرد 👨', callback_data='gender_male')],
        [InlineKeyboardButton('زن 👩', callback_data='gender_female')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🌟 ای مسافر، جنسیت روحت را آشکار کن... ✨",
        reply_markup=reply_markup
    )
    user_data[update.effective_user.id]['awaiting'] = 'gender'

async def ask_birth_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for i, month in enumerate(PERSIAN_MONTHS, 1):
        keyboard.append([InlineKeyboardButton(month, callback_data=f'month_{i}')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📅 ماهی که ستارگان بر تو تابیدند را برگزین... ✨",
        reply_markup=reply_markup
    )
    user_data[update.effective_user.id]['awaiting'] = 'birth_month'

async def ask_birth_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📅 سالی که به این جهان آمدی را با اعداد شمسی وارد کن... ✨",
        reply_markup=MAIN_MENU
    )
    user_data[update.effective_user.id]['awaiting'] = 'birth_year'

async def interpret_dream(update: Update, context: ContextTypes.DEFAULT_TYPE, dream_text: str):
    user_id = update.effective_user.id
    gender = user_data[user_id]['gender']
    birth_month = user_data[user_id]['birth_month']
    birth_year = user_data[user_id]['birth_year']

    await update.message.reply_text("🌌 اسرار در حال آشکار شدن‌اند... لحظه‌ای صبر کن، ای جوینده. ✨")
    await asyncio.sleep(5)

    prompt = f"به عنوان استاد تعبیر خواب، با استفاده از اطلاعات شخصی: جنسیت {gender}، ماه تولد {birth_month}، سال تولد {birth_year}، خواب زیر را به صورت متنی کامل، عرفانی، اغواگرایانه و رازآلود تعبیر کن و با ایموجی و نتیجه‌گیری پاسخ ده:\n{dream_text}"

    response = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama3-8b-8192"  # Free tier model
    )
    interpretation = response.choices[0].message.content

    await update.message.reply_text(interpretation, parse_mode='Markdown')
    await ask_feedback(update, context)

async def interpret_coffee(update: Update, context: ContextTypes.DEFAULT_TYPE, photo_bytes: bytes):
    user_id = update.effective_user.id
    gender = user_data[user_id]['gender']
    birth_month = user_data[user_id]['birth_month']
    birth_year = user_data[user_id]['birth_year']

    await update.message.reply_text("☕️ نقش‌ها در حال پدیدار شدن‌اند... لحظه‌ای صبر کن، ای جوینده. ✨")
    await asyncio.sleep(5)

    # Prepare image for Gemini
    img = {'mime_type': 'image/jpeg', 'data': photo_bytes}

    prompt = f"اگر این تصویر یک فنجان قهوه معتبر برای فال قهوه است، به عنوان استاد فال قهوه، با استفاده از اطلاعات شخصی: جنسیت {gender}، ماه تولد {birth_month}، سال تولد {birth_year}، فنجان را تحلیل کن و نتیجه را به صورت متنی اغواگرایانه، عرفانی و رازآلود، با ایموجی و نتیجه‌گیری بده. اگر نامعتبر است، بگو 'نامعتبر'."

    response = gemini_model.generate_content([prompt, img])
    text = response.text

    if 'نامعتبر' in text:
        await update.message.reply_text("🌑 این نقش، اسرار قهوه را در خود ندارد... تصویری دیگر ارسال کن، ای مسافر. ✨")
        return

    await update.message.reply_text(text, parse_mode='Markdown')
    del user_data[user_id]['awaiting']
    await ask_feedback(update, context)

async def interpret_tarot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    layout_key = user_data[user_id]['tarot_layout']
    layout_real = TAROT_LAYOUTS[layout_key]
    cards = user_data[user_id]['tarot_cards']
    gender = user_data[user_id]['gender']
    birth_month = user_data[user_id]['birth_month']
    birth_year = user_data[user_id]['birth_year']

    await update.message.reply_text("🃏 کارت‌ها در حال چرخش‌اند... لحظه‌ای صبر کن، ای جوینده. ✨")
    await asyncio.sleep(5)

    card_names = [f"{TAROT_CARDS[idx]} ({orient})" for idx, orient in cards]
    prompt = f"به عنوان استاد فال تاروت، با استفاده از اطلاعات شخصی: جنسیت {gender}، ماه تولد {birth_month}، سال تولد {birth_year}، تفسیر چیدمان {layout_real} با کارت‌های {', '.join(card_names)} را به صورت متنی اغواگرایانه، عرفانی و رازآلود، با ایموجی و نتیجه‌گیری بده."

    response = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama3-8b-8192"
    )
    interpretation = response.choices[0].message.content

    # Send card images
    media = []
    for idx, (card_idx, orient) in enumerate(cards):
        img_path = f'images/{card_idx:02d}.jpg'
        with open(img_path, 'rb') as img_file:
            img = Image.open(img_file)
            if orient == 'reversed':
                img = img.rotate(180)
            bio = BytesIO()
            img.save(bio, 'JPEG')
            bio.seek(0)
            media.append(InputMediaPhoto(media=bio, caption=TAROT_CARDS[card_idx]))

    await update.message.reply_media_group(media)
    await update.message.reply_text(interpretation, parse_mode='Markdown')
    await ask_feedback(update, context)

async def show_explanations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📜 ای مسافر، این نکات را به خاطر بسپار:\n\n"
        "- خانه 🏠: بازگشت به آغاز بدون پاک کردن اسرار.\n"
        "- خانه تکانی 🧹: پاک کردن همه چیز و شروع تازه.\n"
        "- حریم خصوصی: اسرار تو نزد من امانت است، تنها برای آشکارسازی استفاده می‌شود.\n"
        "- امنیت: هیچ اطلاعی به بیرون نمی‌رود، در دنیای رازها می‌ماند. ✨"
    )
    await update.message.reply_text(text, reply_markup=MAIN_MENU)

async def ask_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup([
        ['عالی 🌟', 'خوب 👍'],
        ['متوسط 🤔', 'ضعیف 👎']
    ], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "🌌 ای جوینده، از این رازگشایی چه احساسی داری؟ ✨",
        reply_markup=keyboard
    )
    user_data[update.effective_user.id]['awaiting'] = 'feedback'

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if 'awaiting' in user_data[user_id] and user_data[user_id]['awaiting'] == 'feedback':
        feedback = update.message.text
        logger.info(f"Feedback from {user_id}: {feedback}")
        await context.bot.send_message(ADMIN_CHAT_ID, f"Feedback from {user_id}: {feedback}")
        await update.message.reply_text("🌟 سپاس از صداقتت، ای مسافر... اسرار بیشتری در انتظارند. ✨", reply_markup=MAIN_MENU)
        del user_data[user_id]['awaiting']

if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Pre-start handler for messages before /start
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, pre_start))

    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback))  # For feedback

    # For voice and photo
    application.add_handler(MessageHandler(filters.VOICE | filters.PHOTO, handle_message))

    application.run_polling()
