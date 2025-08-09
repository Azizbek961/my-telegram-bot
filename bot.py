import logging
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, \
    KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
BOT_TOKEN = "8192121642:AAFbCaYFWx99c8NFzo8wNQw-OircHuScGZ4"  # Replace with your bot token
ADMIN_CHAT_ID = 6807309073  # Replace with your admin chat ID
CARD_NUMBER = "9860 1234 5678 1234"
MIN_AGE = 18
PHONE_REGEX = r'^\+?\d{10,12}$'
NAME_REGEX = r'^[a-zA-Zа-яА-Я\s]+$'

# Global storage for courses and users (temporary, replace with database in production)
COURSES = []
USERS = []

# Conversation states
(
    FIRST_NAME, LAST_NAME, GENDER, PHONE, BIRTHDATE, COURSE_SELECTION,
    COURSE_INFO, PAYMENT_RECEIPT, ADD_COURSE_NAME, ADD_COURSE_PRICE,
    ADD_COURSE_DESCRIPTION, ADD_COURSE_DURATION, ADD_COURSE_PHOTO
) = range(13)


# Validation functions
def validate_name(name: str) -> bool:
    """Validate that the name contains only letters and spaces."""
    return bool(re.match(NAME_REGEX, name))


def validate_phone(phone: str) -> bool:
    """Validate phone number format."""
    return bool(re.match(PHONE_REGEX, phone))


def validate_price(price: str) -> bool:
    """Validate that price is a positive number."""
    try:
        return float(price) > 0
    except ValueError:
        return False


def calculate_age(birthdate: datetime) -> int:
    """Calculate age based on birthdate."""
    today = datetime.today()
    return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))


# Admin check
def is_admin(update: Update) -> bool:
    """Check if the user is an admin."""
    return update.effective_chat.id == ADMIN_CHAT_ID


# Start handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Checks if user is registered, shows previous courses or starts registration."""
    user_id = update.effective_chat.id
    user = next((u for u in USERS if u['chat_id'] == user_id), None)

    if user:
        # User is already registered
        previous_courses = user.get('courses', [])
        if previous_courses:
            courses_text = "\n".join(
                [f"- {course['name']} (Narxi: {course['price']:,}, Davomiyligi: {course['duration']})" for course in
                 previous_courses])
            message = f"Siz oldin ro‘yxatdan o‘tgansiz!\nOldingi kurslaringiz:\n{courses_text}"
        else:
            message = "Siz oldin ro‘yxatdan o‘tgansiz, lekin hali kurs tanlamagansiz."

        if COURSES:
            keyboard = [[course['name'] for course in COURSES]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text(
                f"{message}\n\nQuyidagi kurslardan birini tanlang:",
                reply_markup=reply_markup
            )
            return COURSE_SELECTION
        else:
            await update.message.reply_text(
                f"{message}\n\nHozirda mavjud kurslar yo‘q. Keyinroq qaytib keling!",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
    else:
        # New user registration
        keyboard = [[InlineKeyboardButton("Ro‘yxatdan o‘tish", callback_data='register')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Arab tili o‘quv markazi botiga xush kelibsiz! Ro‘yxatdan o‘tish uchun tugmani bosing:",
            reply_markup=reply_markup
        )
        return FIRST_NAME


# Register button handler
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the register button click."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Iltimos, ismingizni kiriting:")
    return FIRST_NAME


# First name handler
async def first_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the first name and asks for the last name."""
    name = update.message.text.strip()
    if not validate_name(name):
        await update.message.reply_text("Iltimos, faqat harflardan iborat ismingizni kiriting:")
        return FIRST_NAME
    context.user_data['first_name'] = name
    await update.message.reply_text("Rahmat! Iltimos, familiyangizni kiriting:")
    return LAST_NAME


# Last name handler
async def last_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the last name and asks for gender."""
    last_name = update.message.text.strip()
    if not validate_name(last_name):
        await update.message.reply_text("Iltimos, faqat harflardan iborat familiyangizni kiriting:")
        return LAST_NAME
    context.user_data['last_name'] = last_name

    keyboard = [
        [InlineKeyboardButton("Ayol", callback_data='female')],
        [InlineKeyboardButton("Erkak", callback_data='male')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Iltimos, jinsingizni tanlang:", reply_markup=reply_markup)
    return GENDER


# Gender handler
async def gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the gender and asks for the phone number."""
    query = update.callback_query
    await query.answer()
    context.user_data['gender'] = query.data  # 'female' or 'male'
    gender_text = "Ayol" if query.data == 'female' else "Erkak"
    await query.message.reply_text(
        f"Jins: {gender_text}\nIltimos, telefon raqamingizni yuboring (+998901234567 formatida yoki quyidagi tugmani bosing):",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("Telefon raqamni yuborish", request_contact=True)]],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return PHONE


# Phone handler
async def phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the phone number and asks for the birthdate."""
    phone = None
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text.strip()

    if not validate_phone(phone):
        await update.message.reply_text(
            "Iltimos, to‘g‘ri telefon raqamini kiriting (masalan, +998901234567):",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Telefon raqamni yuborish", request_contact=True)]],
                one_time_keyboard=True,
                resize_keyboard=True
            )
        )
        return PHONE

    context.user_data['phone'] = phone
    await update.message.reply_text("Deyarli tayyor! Iltimos, tug‘ilgan kuningizni kiriting (KK/MM/YYYY):",
                                    reply_markup=ReplyKeyboardRemove())
    return BIRTHDATE


# Birthdate handler
async def birthdate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Parses birthdate, calculates age, stores user data, and shows available courses."""
    try:
        birthdate_str = update.message.text.strip()
        birthdate = datetime.strptime(birthdate_str, "%d/%m/%Y")
        today = datetime.today()

        if birthdate > today:
            await update.message.reply_text(
                "Tug‘ilgan kun kelajakda bo‘lishi mumkin emas. Iltimos, to‘g‘ri sanani kiriting (KK/MM/YYYY):")
            return BIRTHDATE

        age = calculate_age(birthdate)
        context.user_data['birthdate'] = birthdate

        if age < MIN_AGE:
            await update.message.reply_text(
                f"Kursga yozilish uchun {MIN_AGE} yoshdan katta bo‘lishingiz kerak. Iltimos, {MIN_AGE} yoshga to‘lganda qaytib keling.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        else:
            # Store user data
            user_data = {
                'chat_id': update.effective_chat.id,
                'first_name': context.user_data['first_name'],
                'last_name': context.user_data['last_name'],
                'gender': context.user_data['gender'],
                'phone': context.user_data['phone'],
                'birthdate': context.user_data['birthdate'],
                'courses': []
            }
            if not any(u['chat_id'] == user_data['chat_id'] for u in USERS):
                USERS.append(user_data)

            if not COURSES:
                await update.message.reply_text(
                    "Hozirda mavjud kurslar yo‘q. Keyinroq qaytib keling!",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END

            keyboard = [[course['name'] for course in COURSES]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text(
                "Siz kursga yozilish huquqiga egasiz! Quyidagi kurslardan birini tanlang:",
                reply_markup=reply_markup
            )
            return COURSE_SELECTION
    except ValueError:
        await update.message.reply_text("Tug‘ilgan kun formati noto‘g‘ri. Iltimos, KK/MM/YYYY formatida kiriting:")
        return BIRTHDATE


# Course selection handler
async def course_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles course selection and shows course details."""
    selected_course = update.message.text
    course = next((c for c in COURSES if c['name'] == selected_course), None)

    if not course:
        await update.message.reply_text("Iltimos, ro‘yxatdan kurs tanlang.")
        return COURSE_SELECTION

    context.user_data['selected_course'] = course
    keyboard = [[InlineKeyboardButton("Yozilish", callback_data='enroll')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = f"Kurs: {course['name']}\nNarxi: {course['price']:,}\nDavomiyligi: {course['duration']}\nTavsif: {course['description']}"
    if course.get('photo'):
        await update.message.reply_photo(photo=course['photo'], caption=message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup)

    return COURSE_INFO


# Course info handler
async def course_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles enrollment confirmation and requests payment receipt."""
    query = update.callback_query
    await query.answer()

    course = context.user_data['selected_course']
    await query.message.reply_text(
        f"Iltimos, to‘lovni quyidagi karta raqamiga amalga oshiring: {CARD_NUMBER}\nTo‘lov chekining rasmini yuboring:",
        reply_markup=ReplyKeyboardRemove()
    )
    return PAYMENT_RECEIPT


# Payment receipt handler
async def payment_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles payment receipt, stores course in user data, and sends user data to admin."""
    if not update.message.photo:
        await update.message.reply_text("Iltimos, to‘lov chekining rasmini yuboring:")
        return PAYMENT_RECEIPT

    receipt_photo = update.message.photo[-1].file_id
    user_data = context.user_data
    course = user_data['selected_course']
    gender_text = "Ayol" if user_data['gender'] == 'female' else "Erkak"

    # Add course to user's course list
    user = next((u for u in USERS if u['chat_id'] == update.effective_chat.id), None)
    if user and course not in user['courses']:
        user['courses'].append(course)

    # Send user data and receipt to admin
    admin_message = (
        f"Yangi ro‘yxatdan o‘tish:\n"
        f"Ism: {user_data['first_name']}\n"
        f"Familiya: {user_data['last_name']}\n"
        f"Jins: {gender_text}\n"
        f"Telefon: {user_data['phone']}\n"
        f"Tug‘ilgan kun: {user_data['birthdate'].strftime('%d/%m/%Y')}\n"
        f"Kurs: {course['name']}\n"
        f"Narxi: {course['price']:,}\n"
        f"Davomiyligi: {course['duration']}\n"
        f"To‘lov cheki:"
    )
    await context.bot.send_photo(
        chat_id=ADMIN_CHAT_ID,
        photo=receipt_photo,
        caption=admin_message
    )

    # Notify user
    await update.message.reply_text(
        "To‘lov cheki qabul qilindi! Adminlar tasdiqlashini kuting.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


# Admin: Add course handler
async def add_course(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the course addition process for admin."""
    if not is_admin(update):
        await update.message.reply_text("Bu buyruq faqat admin uchun!")
        return ConversationHandler.END

    await update.message.reply_text("Yangi kurs nomini kiriting:")
    return ADD_COURSE_NAME


async def add_course_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores course name and asks for price."""
    context.user_data['new_course'] = {'name': update.message.text.strip()}
    await update.message.reply_text("Kurs narxini kiriting (masalan, 500000):")
    return ADD_COURSE_PRICE


async def add_course_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores course price and asks for description."""
    price = update.message.text.strip()
    if not validate_price(price):
        await update.message.reply_text("Iltimos, to‘g‘ri narx kiriting (musbat raqam):")
        return ADD_COURSE_PRICE
    context.user_data['new_course']['price'] = float(price)
    await update.message.reply_text("Kurs tavsifini kiriting:")
    return ADD_COURSE_DESCRIPTION


async def add_course_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores course description and asks for duration."""
    context.user_data['new_course']['description'] = update.message.text.strip()
    await update.message.reply_text("Kurs davomiyligini kiriting (masalan, '3 oy' yoki '6 hafta'):")
    return ADD_COURSE_DURATION


async def add_course_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores course duration and asks for photo."""
    context.user_data['new_course']['duration'] = update.message.text.strip()
    await update.message.reply_text("Iltimos, kurs uchun rasm yuboring (yoki 'o‘tkazib yuborish' deb yozing):")
    return ADD_COURSE_PHOTO


async def add_course_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores course photo and saves the course."""
    if update.message.text and update.message.text.lower() == "o‘tkazib yuborish":
        context.user_data['new_course']['photo'] = None
    elif update.message.photo:
        context.user_data['new_course']['photo'] = update.message.photo[-1].file_id
    else:
        await update.message.reply_text("Iltimos, rasm yuboring yoki 'o‘tkazib yuborish' deb yozing:")
        return ADD_COURSE_PHOTO

    COURSES.append(context.user_data['new_course'])
    await update.message.reply_text("Kurs muvaffaqiyatli qo‘shildi!", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# Admin: View courses handler
async def view_courses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows all available courses to admin."""
    if not is_admin(update):
        await update.message.reply_text("Bu buyruq faqat admin uchun!")
        return

    if not COURSES:
        await update.message.reply_text("Hozirda mavjud kurslar yo‘q.")
        return

    for course in COURSES:
        message = f"Kurs: {course['name']}\nNarxi: {course['price']:,}\nDavomiyligi: {course['duration']}\nTavsif: {course['description']}"
        if course.get('photo'):
            await update.message.reply_photo(photo=course['photo'], caption=message)
        else:
            await update.message.reply_text(message)


# Admin: View users handler
async def view_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows all registered users to admin."""
    if not is_admin(update):
        await update.message.reply_text("Bu buyruq faqat admin uchun!")
        return

    if not USERS:
        await update.message.reply_text("Hozirda ro‘yxatdan o‘tgan foydalanuvchilar yo‘q.")
        return

    for user in USERS:
        gender_text = "Ayol" if user['gender'] == 'female' else "Erkak"
        courses_text = "\n".join(
            [f"- {course['name']} (Narxi: {course['price']:,}, Davomiyligi: {course['duration']})" for course in
             user['courses']]) if user['courses'] else "Hali kurs tanlanmagan"
        message = (
            f"Foydalanuvchi:\n"
            f"Ism: {user['first_name']}\n"
            f"Familiya: {user['last_name']}\n"
            f"Jins: {gender_text}\n"
            f"Telefon: {user['phone']}\n"
            f"Tug‘ilgan kun: {user['birthdate'].strftime('%d/%m/%Y')}\n"
            f"Kurslar:\n{courses_text}"
        )
        await update.message.reply_text(message)


# Cancel handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the conversation."""
    await update.message.reply_text("Jarayon bekor qilindi. Qaytadan boshlash uchun /start ni bosing.",
                                    reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error {context.error}")


# Main function
def main() -> None:
    """Run the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('add_course', add_course),
            CommandHandler('view_courses', view_courses),
            CommandHandler('view_users', view_users)
        ],
        states={
            FIRST_NAME: [
                CallbackQueryHandler(register, pattern='^register$'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, first_name)
            ],
            LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, last_name)],
            GENDER: [CallbackQueryHandler(gender, pattern='^(female|male)$')],
            PHONE: [
                MessageHandler(filters.CONTACT, phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, phone)
            ],
            BIRTHDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, birthdate)],
            COURSE_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, course_selection)],
            COURSE_INFO: [CallbackQueryHandler(course_info, pattern='^enroll$')],
            PAYMENT_RECEIPT: [MessageHandler(filters.PHOTO, payment_receipt)],
            ADD_COURSE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_course_name)],
            ADD_COURSE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_course_price)],
            ADD_COURSE_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_course_description)],
            ADD_COURSE_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_course_duration)],
            ADD_COURSE_PHOTO: [
                MessageHandler(filters.PHOTO, add_course_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_course_photo)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()