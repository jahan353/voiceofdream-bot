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
    level=logging.DEBUG,  # Changed to DEBUG for more detailed logs
    filename='bot.log',
    filemode='a'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Environment variables
try:
    TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
    GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
    GROQ_API_KEY = os.environ['GROQ_API_KEY']
    ADMIN_CHAT_ID = os.environ['ADMIN_CHAT_ID']
    logger.debug("Environment variables loaded successfully")
except KeyError as e:
    logger.error(f"Missing environment variable: {e}")
    raise ValueError(f"Environment variable {e} is not set!")

# Configure Gemini and Groq
try:
    configure(api_key=GEMINI_API_KEY)
    gemini_model = GenerativeModel('gemini-1.5-flash')
    groq_client = Groq(api_key=GROQ_API_KEY)
    logger.debug("Gemini and Groq APIs configured successfully")
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
    logger.debug(f"Handling pre_start for user {update.effective_user.id}")
    if update.message:
        await update.message.reply_text(WELCOME_MESSAGE, parse_mode='Markdown')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.debug(f"Starting bot for user {user_id}")
    user_data[user_id] = {'state': 'main_menu'}
    await update.message.reply_text(
        "🌟 ای جوینده‌ی حقیقت، به دنیای نجوای رویا قدم نهادی. اسرار کیهان در انتظار توست... ✨\n"
        "حال، کدامین مسیر را برمی‌گزی؟",
        reply_markup=MAIN_MENU
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text if update.message.text else None
    logger.debug(f"Handling message from {user_id}: {text}")

    if user_id not in user_data:
        user_data[user_id] = {'state': 'main_menu'}

    state = user_data[user_id].get('state', 'main_menu')

    # Handle main menu selections
    if state == 'main_menu':
        if text == 'تعبیر خواب 🌙':
            user_data[user_id]['section'] = 'dream'
            user_data[user_id]['state'] = 'awaiting_info'
            await start_section(update, context)
        elif text == 'فال قهوه ☕️':
            user_data[user_id]['section'] = 'coffee'
            user_data[user_id]['state'] = 'awaiting_info'
            await start_section(update, context)
        elif text == 'فال تاروت 🃏':
            user_data[user_id]['section'] = 'tarot'
            user_data[user_id]['state'] = 'awaiting_info'
            await start_section(update, context)
        elif text == 'توضیحات 📜':
            user_data[user_id]['state'] = 'main_menu'
            await show_explanations(update, context)
        else:
            await update.message.reply_text(
                "🌑 مسیری ناشناخته... از منو برگزین، ای مسافر. ✨",
                reply_markup=MAIN_MENU
            )
        return

    # Handle persistent menu options
    if text == 'خانه 🏠':
        user_data[user_id]['state'] = 'main_menu'
        await update.message.reply_text(
            "🏠 به خانه بازگشتی، ای مسافر... اسرار پیشین همچنان نهفته‌اند. ✨",
            reply_markup=MAIN_MENU
        )
        return
    elif text == 'خانه تکانی 🧹':
        user_data[user_id] = {'state': 'main_menu'}
        await update.message.reply_text(
            "🧹 بادهای تغییر وزیدند و همه چیز پاک شد... از نو آغاز کن، ای جوینده. ✨",
            reply_markup=MAIN_MENU
        )
        return

    # Handle user input based on state
    if state == 'awaiting_gender':
        if text in ['مرد 👨', 'زن 👩']:
            user_data[user_id]['gender'] = text
            user_data[user_id]['state'] = 'awaiting_birth_month'
            await ask_birth_month(update, context)
        else:
            await update.message.reply_text(
                "🌑 ای مسافر، انتخابی درست بنما... مرد یا زن؟ ✨",
                reply_markup=PERSISTENT_MENU
            )
        return

    elif state == 'awaiting_birth_month':
        if text in PERSIAN_MONTHS:
            user_data[user_id]['birth_month'] = PERSIAN_MONTHS.index(text) + 1
            user_data[user_id]['state'] = 'awaiting_birth_year'
            await ask_birth_year(update, context)
        else:
            await update.message.reply_text(
                "🌑 ای جوینده، ماهی از تقویم شمسی برگزین... ✨",
                reply_markup=PERSISTENT_MENU
            )
        return

    elif state == 'awaiting_birth_year':
        try:
            year = int(text)
            current_year = datetime.now().year
            if 1900 <= year <= current_year:
                user_data[user_id]['birth_year'] = year
                user_data[user_id]['state'] = f'awaiting_{user_data[user_id]["section"]}'
                await proceed_to_section(update, context, user_data[user_id]['section'])
            else:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "🌑 ای مسافر، سالی معتبر از تقویم شمسی وارد کن... ✨",
                reply_markup=PERSISTENT_MENU
            )
        return

    elif state == 'awaiting_dream':
        if update.message.voice:
            try:
                voice_file = await update.message.voice.get_file()
                voice_bytes = await voice_file.download_as_bytearray()
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
            except Exception as e:
                logger.error(f"Error processing voice: {e}")
                await update.message.reply_text(
                    "🌑 خطایی رخ داد... خواب خود را با کلمات بازگو کن، ای مسافر. ✨",
                    reply_markup=PERSISTENT_MENU
                )
                return
        else:
            dream_text = text

        if dream_text:
            user_data[user_id]['state'] = 'awaiting_feedback'
            await interpret_dream(update, context, dream_text)
        else:
            await update.message.reply_text(
                "🌑 ای خواب‌دیده، راز خوابت را با کلمات یا صدا بازگو کن... ✨",
                reply_markup=PERSISTENT_MENU
            )
        return

    elif state == 'awaiting_coffee_photo':
        if update.message.photo:
            photo_file = await update.message.photo[-1].get_file()
            photo_bytes = await photo_file.download_as_bytearray()
            user_data[user_id]['state'] = 'awaiting_feedback'
            await interpret_coffee(update, context, photo_bytes)
        else:
            await update.message.reply_text(
                "🌑 ای جوینده، تصویری واضح از فنجان ارسال کن... ✨",
                reply_markup=PERSISTENT_MENU
            )
        return

    elif state == 'awaiting_feedback':
        feedback = text
        logger.debug(f"Feedback from {user_id}: {feedback}")
        try:
            await context.bot.send_message(ADMIN_CHAT_ID, f"Feedback from {user_id}: {feedback}")
        except Exception as e:
            logger.error(f"Error sending feedback: {e}")
        user_data[user_id]['state'] = 'main_menu'
        await update.message.reply_text(
            "🌟 سپاس از صداقتت، ای مسافر... اسرار بیشتری در انتظارند. ✨",
            reply_markup=MAIN_MENU
        )
        return

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    logger.debug(f"Handling callback from {user_id}: {data}")

    if data.startswith('gender_'):
        gender = 'مرد 👨' if data == 'gender_male' else 'زن 👩'
        user_data[user_id]['gender'] = gender
        user_data[user_id]['state'] = 'awaiting_birth_month'
        await query.answer()
        await ask_birth_month(query.message, context)

    elif data.startswith('month_'):
        month = int(data.split('_')[1])
        user_data[user_id]['birth_month'] = month
        user_data[user_id]['state'] = 'awaiting_birth_year'
        await query.answer()
        await ask_birth_year(query.message, context)

    elif data.startswith('tarot_layout_'):
        layout_key = data.split('_')[2]
        user_data[user_id]['tarot_layout'] = layout_key
        layout_real = TAROT_LAYOUTS[layout_key]
        card_counts = {
            'Celtic Cross': 10,
            'Three Card Spread': 3,
            'One Card Draw': 1,
            'Past Present Future': 3,
            'Relationship Spread': 7
        }
        num_cards = card_counts[layout_real]
        cards = random.sample(range(78), num_cards)
        orientations = [random.choice(['upright', 'reversed']) for _ in range(num_cards)]
        user_data[user_id]['tarot_cards'] = list(zip(cards, orientations))
        user_data[user_id]['state'] = 'awaiting_feedback'
        await query.answer()
        await interpret_tarot(query.message, context)

async def start_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    section = user_data[user_id].get('section')
    logger.debug(f"Starting section {section} for user {user_id}")

    if 'gender' not in user_data[user_id] or 'birth_month' not in user_data[user_id] or 'birth_year' not in user_data[user_id]:
        user_data[user_id]['state'] = 'awaiting_gender'
        await ask_gender(update, context)
    else:
        user_data[user_id]['state'] = f'awaiting_{section}'
        await proceed_to_section(update, context, section)

async def proceed_to_section(update: Update, context: ContextTypes.DEFAULT_TYPE, section: str):
    user_id = update.effective_user.id
    logger.debug(f"Proceeding to section {section} for user {user_id}")
    if section == 'dream':
        await update.message.reply_text(
            "🌙 ای خواب‌دیده، راز خوابت را با کلمات یا صدا برایم بازگو کن... ✨",
            reply_markup=PERSISTENT_MENU
        )
        user_data[user_id]['state'] = 'awaiting_dream'

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
            reply_markup=PERSISTENT_MENU
        )
        user_data[user_id]['state'] = 'awaiting_coffee_photo'

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

async def ask_birth_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for i, month in enumerate(PERSIAN_MONTHS, 1):
        keyboard.append([InlineKeyboardButton(month, callback_data=f'month_{i}')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📅 ماهی که ستارگان بر تو تابیدند را برگزین... ✨",
        reply_markup=reply_markup
    )

async def ask_birth_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📅 سالی که به این جهان آمدی را با اعداد شمسی وارد کن... ✨",
        reply_markup=PERSISTENT_MENU
    )

async def interpret_dream(update: Update, context: ContextTypes.DEFAULT_TYPE, dream_text: str):
    user_id = update.effective_user.id
    gender = user_data[user_id]['gender']
    birth_month = user_data[user_id]['birth_month']
    birth_year = user_data[user_id]['birth_year']
    logger.debug(f"Interpreting dream for user {user_id}: {dream_text}")

    await update.message.reply_text(
        "🌌 اسرار در حال آشکار شدن‌اند... لحظه‌ای صبر کن، ای جوینده. ✨"
    )
    await asyncio.sleep(5)

    prompt = f"به عنوان استاد تعبیر خواب، با استفاده از اطلاعات شخصی: جنسیت {gender}، ماه تولد {birth_month}، سال تولد {birth_year}، خواب زیر را به صورت متنی کامل، عرفانی، اغواگرایانه و رازآلود تعبیر کن و با ایموجی و نتیجه‌گیری پاسخ ده:\n{dream_text}"

    try:
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192"
        )
        interpretation = response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error in dream interpretation: {e}")
        interpretation = "🌑 خطایی در گشودن رازهای خواب رخ داد... دوباره تلاش کن، ای مسافر. ✨"

    await update.message.reply_text(interpretation, parse_mode='Markdown', reply_markup=PERSISTENT_MENU)
    await ask_feedback(update, context)

async def interpret_coffee(update: Update, context: ContextTypes.DEFAULT_TYPE, photo_bytes: bytes):
    user_id = update.effective_user.id
    gender = user_data[user_id]['gender']
    birth_month = user_data[user_id]['birth_month']
    birth_year = user_data[user_id]['birth_year']
    logger.debug(f"Interpreting coffee for user {user_id}")

    await update.message.reply_text(
        "☕️ نقش‌ها در حال پدیدار شدن‌اند... لحظه‌ای صبر کن، ای جوینده. ✨"
    )
    await asyncio.sleep(5)

    img = {'mime_type': 'image/jpeg', 'data': photo_bytes}
    prompt = f"اگر این تصویر یک فنجان قهوه معتبر برای فال قهوه است، به عنوان استاد فال قهوه، با استفاده از اطلاعات شخصی: جنسیت {gender}، ماه تولد {birth_month}، سال تولد {birth_year}، فنجان را تحلیل کن و نتیجه را به صورت متنی اغواگرایانه، عرفانی و رازآلود، با ایموجی و نتیجه‌گیری بده. اگر نامعتبر است، بگو 'نامعتبر'."

    try:
        response = gemini_model.generate_content([prompt, img])
        text = response.text
    except Exception as e:
        logger.error(f"Error in coffee reading: {e}")
        text = "نامعتبر"

    if 'نامعتبر' in text:
        await update.message.reply_text(
            "🌑 این نقش، اسرار قهوه را در خود ندارد... تصویری دیگر ارسال کن، ای مسافر. ✨",
            reply_markup=PERSISTENT_MENU
        )
        return

    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=PERSISTENT_MENU)
    await ask_feedback(update, context)

async def interpret_tarot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    layout_key = user_data[user_id]['tarot_layout']
    layout_real = TAROT_LAYOUTS[layout_key]
    cards = user_data[user_id]['tarot_cards']
    gender = user_data[user_id]['gender']
    birth_month = user_data[user_id]['birth_month']
    birth_year = user_data[user_id]['birth_year']
    logger.debug(f"Interpreting tarot for user {user_id}, layout: {layout_key}")

    await update.message.reply_text(
        "🃏 کارت‌ها در حال چرخش‌اند... لحظه‌ای صبر کن، ای جوینده. ✨"
    )
    await asyncio.sleep(5)

    card_names = [f"{TAROT_CARDS[idx]} ({orient})" for idx, orient in cards]
    prompt = f"به عنوان استاد فال تاروت، با استفاده از اطلاعات شخصی: جنسیت {gender}، ماه تولد {birth_month}، سال تولد {birth_year}، تفسیر چیدمان {layout_real} با کارت‌های {', '.join(card_names)} را به صورت متنی اغواگرایانه، عرفانی و رازآلود، با ایموجی و نتیجه‌گیری بده."

    try:
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192"
        )
        interpretation = response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error in tarot reading: {e}")
        interpretation = "🌑 خطایی در گشودن رازهای تاروت رخ داد... دوباره تلاش کن، ای مسافر. ✨"

    media = []
    for idx, (card_idx, orient) in enumerate(cards):
        img_path = f'images/{card_idx:02d}.jpg'
        try:
            with open(img_path, 'rb') as img_file:
                img = Image.open(img_file)
                if orient == 'reversed':
                    img = img.rotate(180)
                bio = BytesIO()
                img.save(bio, 'JPEG')
                bio.seek(0)
                media.append(InputMediaPhoto(media=bio, caption=TAROT_CARDS[card_idx]))
        except Exception as e:
            logger.error(f"Error loading tarot image {img_path}: {e}")
            await update.message.reply_text(
                "🌑 خطایی در نمایش کارت‌ها رخ داد... دوباره تلاش کن، ای مسافر. ✨",
                reply_markup=PERSISTENT_MENU
            )
            return

    await update.message.reply_media_group(media)
    await update.message.reply_text(interpretation, parse_mode='Markdown', reply_markup=PERSISTENT_MENU)
    await ask_feedback(update, context)

async def show_explanations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug("Showing explanations")
    text = (
        "📜 ای جوینده‌ی راز، به نجوای رویا خوش آمدی، جایی که اسرار روح تو در هم‌نوایی با کیهان گشوده می‌شود... ✨\n\n"
        "🌟 *درباره نجوای رویا*: این ربات، چون چراغی در شب‌های بی‌کران، راهنمای توست در مسیر کشف حقیقت. از خواب‌هایت که چون رازهایی در مه نهفته‌اند، تا نقش‌های مرموز قهوه و کارت‌های باستانی تاروت، نجوای رویا تو را به سوی شناخت ژرف‌تر خویشتن رهنمون می‌شود.\n\n"
        "🔒 *حریم خصوصی*: ای مسافر، آسوده باش که اسرار تو در این دالان‌های کیهانی محفوظ است. اطلاعاتی که با ما به اشتراک می‌گذاری، از جنسیت و تاریخ تولد گرفته تا خواب‌ها و تصاویر فنجان، تنها برای گشودن رازهای تو به کار می‌رود و چون گنجی گران‌بها در پناه ما می‌ماند.\n\n"
        "🏠 *خانه*: این گزینه تو را به آغاز سفر بازمی‌گرداند، جایی که می‌توانی مسیری تازه برگزینی، در حالی که اسرار پیشینت همچنان در خاطر ما نهفته است.\n\n"
        "🧹 *خانه تکانی*: چون بادی نیرومند، این گزینه همه اسرار و اطلاعات پیشین تو را پاک می‌کند تا سفری تازه از ابتدا آغاز کنی.\n\n"
        "ای مسافر، اکنون کدامین مسیر را برمی‌گزی؟ ✨"
    )
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=MAIN_MENU)

async def ask_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.debug(f"Asking feedback from user {user_id}")
    keyboard = ReplyKeyboardMarkup([
        ['عالی 🌟', 'خوب 👍'],
        ['متوسط 🤔', 'ضعیف 👎']
    ], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "🌌 ای جوینده، از این رازگشایی چه احساسی داری؟ ✨",
        reply_markup=keyboard
    )
    user_data[user_id]['state'] = 'awaiting_feedback'

if __name__ == '__main__':
    try:
        logger.info("Starting bot application")
        application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

        application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, pre_start))
        application.add_handler(CommandHandler('start', start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(CallbackQueryHandler(handle_callback))
        application.add_handler(MessageHandler(filters.VOICE | filters.PHOTO, handle_message))

        logger.info("Running polling")
        application.run_polling()
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise
