import re
import requests
from bs4 import BeautifulSoup
from telegram import Update, BotCommand, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import jdatetime
from datetime import datetime, timedelta
import asyncio


# Define states for the dentist conversation
NAME, LAST_NAME, PROFESSION, MEDICAL_CODE = range(4)

# Define states for the patient conversation
P_NAME, P_LAST_NAME, NATIONAL_ID, DOB, CITY, PHONE = range(6)

# Constants for validation
MAX_LENGTH = 100
PERSIAN_NAME_REGEX = r'^[آ-ی\s]+$'
MEDICAL_CODE_REGEX = r'^\d+$'  # Only numbers
POSITIVE_INTEGER_REGEX = r'^[1-9]\d*$'  # Positive integers
PHONE_NUMBER_REGEX = r'^\d{11}$'

# URL صفحه وب
url = "https://membersearch.irimc.org/list/council/%d8%aa%d9%87%d8%b1%d8%a7%d9%86/%d8%aa%d9%87%d8%b1%d8%a7%d9%86/%d8%af%da%a9%d8%aa%d8%b1%d8%a7%db%8c%20%d8%ad%d8%b1%d9%81%d9%87%e2%80%8c%d8%a7%db%8c%20%d8%af%d9%86%d8%af%d8%a7%d9%86%d9%be%d8%b2%d8%b4%da%a9%db%8c/"


def get_doctor_data_from_website(url):
    response = requests.get(url)
    response.encoding = 'utf-8'
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find('tbody').find_all('tr')
        doctors = {}
        for row in rows:
            cols = row.find_all('td')
            if len(cols) > 1:
                name_parts = cols[1].text.split()
                name = " ".join(name_parts[1:]).strip()  # حذف کلمه "دکتر"
                medical_id = cols[2].text.strip()  # شماره نظام پزشکی
                doctors[name] = medical_id
        cleaned_doctors = {name: id for name, id in doctors.items() if
                           len(name) > 0 and not any(char.isdigit() for char in name.split()[0])}
        return cleaned_doctors
    else:
        return None


def search_doctor(doctor_name, doctors):
    return doctor_name in doctors


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
        await update.message.reply_text('لطفا تخصص خود را وارد کنید:')
        return PROFESSION
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

        # Collect all the data
        name = context.user_data['name']
        last_name = context.user_data['last_name']
        full_name = f"{name} {last_name}"
        profession = context.user_data['profession']
        medical_code = context.user_data['medical_code']

        # Verify the doctor from the website
        doctors_dict = get_doctor_data_from_website(url)
        if doctors_dict:
            if search_doctor(full_name, doctors_dict):
                medical_id = doctors_dict[full_name]
                await update.message.reply_text(
                    f"دکتر {full_name} با کد نظام پزشکی {medical_id} با موفقیت ثبت شد.",
                    reply_markup=ReplyKeyboardRemove())
            else:
                await update.message.reply_text("اطلاعات پزشک نامعتبر است.")
        else:
            await update.message.reply_text("Error: Unable to access the doctor data.")

        return ConversationHandler.END
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
        # Convert Shamsi date to Gregorian date
        shamsi_year, shamsi_month, shamsi_day = map(int, dob_input.split('-'))
        dob = jdatetime.date(shamsi_year, shamsi_month, shamsi_day).togregorian()

        # Calculate age
        today = datetime.now()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

        # Check if age is between 3 and 18
        if 3 <= age <= 18:
            context.user_data['dob'] = dob_input  # Store the Shamsi date
            context.user_data['age'] = age  # Store the calculated age
            await update.message.reply_text('لطفا نام شهر خود را وارد کنید:')
            return CITY
        else:
            await update.message.reply_text('لطفا تاریخ تولدی بین سنین ۳ تا ۱۸ سال وارد کنید:')
            return DOB

    except ValueError:
        # Handle wrong format or conversion error
        await update.message.reply_text('تاریخ تولد باید به صورت YYYY-MM-DD باشد و معتبر. لطفا دوباره وارد کنید:')
        return DOB

async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['city'] = update.message.text
    await update.message.reply_text('لطفا شماره تلفن خود را وارد کنید (باید ۱۱ رقم باشد):')
    return PHONE

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

        # Save the data or process it as needed
        # For demonstration, we'll just print it
        patient_info = f"Name: {p_name}\nLast Name: {p_last_name}\nNational ID: {national_id}\nDate of Birth: {dob} (Age: {age} years)\nCity: {city}\nPhone Number: {phone_number}"
        print(patient_info)  # You can replace this with a call to save data to a database or file

        await update.message.reply_text('ثبت نام بیمار با موفقیت انجام شد!', reply_markup=ReplyKeyboardRemove())
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
