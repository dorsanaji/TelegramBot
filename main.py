import re
import requests
from bs4 import BeautifulSoup
from telegram import Update, BotCommand, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import jdatetime
from datetime import datetime, timedelta
import asyncio
import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("peppy-aileron-427715-t9-2c2c475ed163.json", scope)
client = gspread.authorize(creds)

# Open the Google Sheets
doctors_sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1r6FYG2Otae-kQcGLEB9KHN7cU2tdLJloEKVq_la-hX0/edit?gid=0#gid=0").sheet1
patients_sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1kd7vvrlOcq1fx0Q9GAD-GHz2GmcIyWmhlFzSsoHOs-I/edit?gid=0#gid=0").sheet1
verification_sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1peuDMA_D_AQ3hM9b0B7XaumEKkZ4BW2jetjHCw4Ftyo/edit?usp=sharing").sheet1
# Define states for the dentist conversation
NAME, LAST_NAME, PROFESSION, MEDICAL_CODE = range(4)

# Define states for the patient conversation
P_NAME, P_LAST_NAME, NATIONAL_ID, DOB, CITY, PHONE = range(6)

# Constants for validation
MAX_LENGTH = 100
PERSIAN_NAME_REGEX = r'^[آ-ی\s]+$'
CITY_NAME_REGEX = r'^[آ-ی\s]{1,20}$'
MEDICAL_CODE_REGEX = r'^\d+$'
POSITIVE_INTEGER_REGEX = r'^[1-9]\d*$'
PHONE_NUMBER_REGEX = r'^\d{11}$'


def generate_unique_id(prefix):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{prefix}{timestamp}"


# Function to check if the doctor name exists in the verification sheet
def check_doctor_name(full_name):
    records = verification_sheet.get_all_records()
    for record in records:
        if record['Doctor Name'] == full_name:
            return True
    return False


# Function to check if the doctor ID matches the name in the verification sheet
def check_doctor_id(full_name, doctor_id):
    records = verification_sheet.get_all_records()
    for record in records:
        if record['Doctor Name'] == full_name and str(record['Doctor ID']) == doctor_id:
            return True
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Hello! I am your bot.')


async def register_dentist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('لطفا نام خود را وارد کنید:')
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if 1 <= len(name) <= MAX_LENGTH and re.match(PERSIAN_NAME_REGEX, name):
        context.user_data['name'] = name
        await update.message.reply_text('لطفا نام خانوادگی خود را وارد کنید:')
        return LAST_NAME
    else:
        await update.message.reply_text(f'لطفا نامی معتبر وارد کنید (فقط حروف فارسی، بدون اعداد):')
        return NAME


async def get_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    last_name = update.message.text.strip()
    if len(last_name) <= MAX_LENGTH and re.match(PERSIAN_NAME_REGEX, last_name):
        context.user_data['last_name'] = last_name
        full_name = f"{context.user_data['name']} {last_name}"

        if check_doctor_name(full_name):
            context.user_data['full_name'] = full_name
            await update.message.reply_text('لطفا تخصص خود را وارد کنید:')
            return PROFESSION
        else:
            await update.message.reply_text(
                'نام پزشک در سیستم موجود نیست. لطفا دوباره وارد کنید یا "لغو" را وارد کنید:')
            return LAST_NAME
    else:
        await update.message.reply_text(f'لطفا نام خانوادگی معتبر وارد کنید (فقط حروف فارسی، بدون اعداد):')
        return LAST_NAME


async def get_profession(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['profession'] = update.message.text
    await update.message.reply_text('لطفا کد نظام پزشکی خود را وارد کنید:')
    return MEDICAL_CODE


async def get_medical_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    medical_code = update.message.text
    if re.match(MEDICAL_CODE_REGEX, medical_code):
        context.user_data['medical_code'] = medical_code

        # Check if the entered ID matches the name in the verification sheet
        full_name = context.user_data['full_name']
        if check_doctor_id(full_name, medical_code):
            # Collect all the data
            name = context.user_data['name']
            last_name = context.user_data['last_name']
            profession = context.user_data['profession']
            medical_code = context.user_data['medical_code']

            # Generate a unique ID for the doctor
            unique_id = generate_unique_id("D")
            context.user_data['unique_id'] = unique_id

            # Save to Google Sheets
            doctors_sheet.append_row([unique_id, full_name, profession, medical_code])

            await update.message.reply_text(
                f"دکتر {full_name} با کد نظام پزشکی {medical_code} و شناسه یکتا {unique_id} با موفقیت ثبت شد.",
                reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                'کد نظام پزشکی با نام مطابقت ندارد. لطفا دوباره وارد کنید یا "لغو" را وارد کنید:')
            return MEDICAL_CODE
    else:
        await update.message.reply_text('کد نظام پزشکی فقط باید شامل اعداد باشد. لطفا دوباره وارد کنید:')
        return MEDICAL_CODE


async def register_patient(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('لطفا نام خود را وارد کنید:')
    return P_NAME


async def get_p_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if 1 <= len(name) <= MAX_LENGTH and re.match(PERSIAN_NAME_REGEX, name):
        context.user_data['p_name'] = name
        await update.message.reply_text('لطفا نام خانوادگی خود را وارد کنید (می‌توانید - وارد کنید):')
        return P_LAST_NAME
    else:
        await update.message.reply_text(f'لطفا نامی معتبر وارد کنید (فقط حروف فارسی، بدون اعداد):')
        return P_NAME


async def get_p_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    last_name = update.message.text.strip()
    if len(last_name) <= MAX_LENGTH and re.match(PERSIAN_NAME_REGEX, last_name):
        context.user_data['p_last_name'] = last_name
        await update.message.reply_text('لطفا کد ملی خود را وارد کنید:')
        return NATIONAL_ID
    else:
        await update.message.reply_text(f'لطفا نام خانوادگی معتبر وارد کنید (فقط حروف فارسی، بدون اعداد):')
        return P_LAST_NAME


async def get_national_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    national_id = update.message.text
    if re.match(POSITIVE_INTEGER_REGEX, national_id):
        context.user_data['national_id'] = national_id
        await update.message.reply_text('لطفا تاریخ تولد خود را وارد کنید (به صورت YYYY-MM-DD):')
        return DOB
    else:
        await update.message.reply_text('کد ملی باید یک عدد صحیح مثبت باشد. لطفا دوباره وارد کنید:')
        return NATIONAL_ID

async def get_dob(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    dob_input = update.message.text
    try:
        shamsi_year, shamsi_month, shamsi_day = map(int, dob_input.split('-'))
        dob = jdatetime.date(shamsi_year, shamsi_month, shamsi_day).togregorian()

        # Calculate age
        today = datetime.now()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

        # Check if age is between 3 and 18
        if 3 <= age <= 18:
            context.user_data['dob'] = dob_input
            context.user_data['age'] = age
            await update.message.reply_text('لطفا نام شهر خود را وارد کنید:')
            return CITY
        else:
            await update.message.reply_text('لطفا تاریخ تولدی بین سنین ۳ تا ۱۸ سال وارد کنید:')
            return DOB

    except ValueError:
        await update.message.reply_text('تاریخ تولد باید به صورت YYYY-MM-DD باشد و معتبر. لطفا دوباره وارد کنید:')
        return DOB


async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    city = update.message.text.strip()
    if re.match(CITY_NAME_REGEX, city):
        context.user_data['city'] = city
        await update.message.reply_text('لطفا شماره تلفن خود را وارد کنید (باید ۱۱ رقم باشد):')
        return PHONE
    else:
        await update.message.reply_text('نام شهر باید حداکثر ۲۰ حرف و فقط شامل حروف فارسی باشد. لطفا دوباره وارد کنید:')
        return CITY


async def get_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone_number = update.message.text
    if re.match(PHONE_NUMBER_REGEX, phone_number):
        context.user_data['phone_number'] = phone_number

        # Collect all the data
        p_name = context.user_data['p_name']
        p_last_name = context.user_data['p_last_name']
        national_id = context.user_data['national_id']
        dob = context.user_data['dob']
        city = context.user_data['city']
        phone_number = context.user_data['phone_number']
        age = context.user_data['age']

        # Generate a unique ID for the patient
        unique_id = generate_unique_id("P")
        context.user_data['unique_id'] = unique_id

        # Save to Google Sheets
        patients_sheet.append_row([unique_id, p_name, p_last_name, national_id, dob, age, city, phone_number])

        await update.message.reply_text(f'ثبت نام بیمار با شناسه یکتا {unique_id} با موفقیت انجام شد!',
                                        reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    else:
        await update.message.reply_text('شماره تلفن باید دقیقا ۱۱ رقم باشد. لطفا دوباره وارد کنید:')
        return PHONE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('ثبت نام لغو شد.', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def set_commands(application):
    # Set commands for the bot
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("sabtpzshk", "ثبت پزشک"),
        BotCommand("sabtbimar", "ثبت بیمار")
    ]
    await application.bot.set_my_commands(commands)


async def main():
    # Replace 'YOUR_TOKEN' with the token you got from BotFather
    application = Application.builder().token("6730988266:AAFQiuJ279DQ1rXIW8u8kkSIPbm_9gLyinw").build()

    # Set the commands before running polling
    await set_commands(application)

    # Conversation handler for dentist registration
    conv_handler_dentist = ConversationHandler(
        entry_points=[CommandHandler('sabtpzshk', register_dentist)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_last_name)],
            PROFESSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_profession)],
            MEDICAL_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_medical_code)],
        },
        fallbacks=[MessageHandler(filters.TEXT & filters.Regex('^لغو$'), cancel)],
    )

    # Conversation handler for patient registration
    conv_handler_patient = ConversationHandler(
        entry_points=[CommandHandler('sabtbimar', register_patient)],
        states={
            P_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_p_name)],
            P_LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_p_last_name)],
            NATIONAL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_national_id)],
            DOB: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_dob)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone_number)],
        },
        fallbacks=[MessageHandler(filters.TEXT & filters.Regex('^لغو$'), cancel)],
    )

    application.add_handler(conv_handler_dentist)
    application.add_handler(conv_handler_patient)
    application.add_handler(CommandHandler("start", start))

    print("Bot is running... Press Ctrl-C to stop.")

    # Run the bot until you press Ctrl-C
    await application.initialize()
    try:
        await application.start()
        await application.updater.start_polling()
        await asyncio.Event().wait()  # Keep running until interrupted
    finally:
        await application.stop()
        await application.shutdown()


if __name__ == '__main__':
    try:
        # Check if there's an existing event loop and use it
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a task to run the main function
            loop.create_task(main())
        else:
            loop.run_until_complete(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped")
