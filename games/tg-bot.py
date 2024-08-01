import os
import sys
import json
import asyncio
import logging
import subprocess
import requests

def download_file(url, dest):
    """Download a file from a URL to a destination path."""
    try:
        response = requests.get(url)
        response.raise_for_status()  #Đảm bảo chúng tôi nhận thấy phản hồi không tốt
        with open(dest, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded {url} to {dest}")
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        sys.exit(1)

def modify_pull_games_script(script_path):
    """Modify the pull-games.sh script to suit our purpose."""
    script_content = """#!/bin/bash

# Define the target and source directories
TARGET_DIR="/app"
GAMES_DIR="$TARGET_DIR/games"
DEST_DIR="/usr/src/app/games"

# Check if the directory exists and is a git repository
if [ -d "$TARGET_DIR" ] && [ -d "$TARGET_DIR/.git" ]; then
    echo "$TARGET_DIR pulling latest changes."
    cd $TARGET_DIR
    git pull
elif [ -d "$TARGET_DIR" ] ; then
    echo "$TARGET_DIR exists but is not a git repository. Removing and cloning afresh."
    rm -rf $TARGET_DIR
    git clone https://github.com/bibo318/telegram-claim-bot.git $TARGET_DIR
else
    echo "$TARGET_DIR does not exist. Cloning repository."
    git clone https://github.com/bibo318/telegram-claim-bot.git $TARGET_DIR
fi

# Set the working directory to the cloned repository
cd $GAMES_DIR

# Create the destination directory
mkdir -p $DEST_DIR

# Copy the contents of the games directory recursively
cp -r $GAMES_DIR/* $DEST_DIR

echo "All files and subdirectories have been copied to $DEST_DIR"
"""
    try:
        with open(script_path, 'w') as f:
            f.write(script_content)
        print(f"Modified {script_path} successfully.")
    except Exception as e:
        print(f"Failed to modify {script_path}: {e}")
        sys.exit(1)

def check_and_update_games_utils():
    """Kiểm tra xem trò chơi/tiện ích có tồn tại không và nếu không, hãy cập nhật bằng pull-games.sh."""
    if not os.path.exists("/usr/src/app/games/utils"):
        pull_games_dest = "/usr/src/app/pull-games.sh"

        #Kiểm tra xem pull-games.sh có tồn tại không
        if os.path.exists(pull_games_dest):
            #Sửa đổi tập lệnh pull-games.sh
            modify_pull_games_script(pull_games_dest)

            #Làm cho tập lệnh có thể thực thi được
            os.chmod(pull_games_dest, 0o755)

            #Chạy tập lệnh pull-games.sh
            result = subprocess.run([pull_games_dest], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Failed to execute {pull_games_dest}: {result.stderr}")
                sys.exit(1)
            else:
                print(f"Successfully executed {pull_games_dest}: {result.stdout}")
        else:
            print("pull-games.sh does not exist, skipping the update.")

#Đảm bảo trò chơi/tiện ích có mặt trước khi tiến hành nhập
check_and_update_games_utils()

try:
    from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove, Update,
                          InlineKeyboardButton, InlineKeyboardMarkup)
    from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                              ContextTypes, ConversationHandler, MessageHandler, filters)
except ImportError:
    print("The 'python-telegram-bot' module is not installed. Installing it now...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-telegram-bot"])
    from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove, Update,
                          InlineKeyboardButton, InlineKeyboardMarkup)
    from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                              ContextTypes, ConversationHandler, MessageHandler, filters)

try:
    from utils.pm2 import start_pm2_app, save_pm2
except ImportError:
    print("Failed to import PM2 utilities even after attempting to copy the necessary files and directories.")
    sys.exit(1)

from status import list_pm2_processes, list_all_pm2_processes, get_inactive_directories, get_logs_by_process_name, get_status_logs_by_process_name, fetch_and_process_logs

#Bật ghi nhật ký
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

#Xác định trạng thái
COMMAND_DECISION, SELECT_PROCESS, PROCESS_DECISION, PROCESS_COMMAND_DECISION = range(4)

stopped_processes = []
running_processes = []
inactive_directories = []

selected_process = None

def load_telegram_token(file_path: str) -> str:
    """Load the telegram bot token from the specified file."""
    if not os.path.exists(file_path):
        logger.error(f"File {file_path} does not exist.")
        sys.exit(1)

    with open(file_path, 'r') as file:
        config = json.load(file)
    
    token = config.get("telegramBotToken")

    if token:
        logger.info(f"Token extracted: {token}")
        return token
    else:
        logger.error("telegramBotToken not found in the file.")
        sys.exit(1)

def run() -> None:
    """Run the bot."""
    token = load_telegram_token('variables.txt')
    if not token:
        sys.exit(1)

    application = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            COMMAND_DECISION: [CallbackQueryHandler(command_decision)],
            SELECT_PROCESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_process)],
            PROCESS_DECISION: [CallbackQueryHandler(process_decision)],
            PROCESS_COMMAND_DECISION: [CallbackQueryHandler(process_command_decision)]
        },
        fallbacks=[CommandHandler('exit', exit)],
    )

    application.add_handler(conv_handler)

    #Xử lý trường hợp người dùng gửi /start nhưng họ không tham gia cuộc trò chuyện
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler("status", status_all))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("exit", exit))

    application.run_polling()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks the user about their preferred command type."""
    await update.message.reply_text(
        '<b>Telegram Claim Bot!\n'
        'How can I help you?</b>',
        parse_mode='HTML',
        reply_markup=ReplyKeyboardRemove(),
    )

    #Xác định các nút nội tuyến để chọn màu ô tô
    keyboard = [
        [InlineKeyboardButton('ALL STATUS', callback_data='status')],
        [InlineKeyboardButton('SELECT PROCESS', callback_data='process')],
        [InlineKeyboardButton('Help', callback_data='help')],
        [InlineKeyboardButton('Exit', callback_data='exit')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('<b>Please choose:</b>', parse_mode='HTML', reply_markup=reply_markup)

    return COMMAND_DECISION

async def command_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user to fill in the mileage or skip."""
    query = update.callback_query
    await query.answer()
    decision = query.data

    if decision == 'process':
        return await select_process(update, context)
    elif decision == 'status':
        return await status_all(update, context)
    elif decision == 'help':
        return await help(update, context)
    elif decision == 'exit':
        return await exit(update, context)
    else:
        await query.edit_message_text(f"Invalid command: {decision}")
        return ConversationHandler.END

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send a message with the help of the bot."""
    return await send_message(update, context, "Available commands:\n/start - Start the bot\n/status - Check the status of all processes\n/help - Show this help message\n/exit - Exit the bot")

async def exit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exit the bot."""
    return await send_message(update, context, "Goodbye!")

#khu vực Quy trình duy nhất

async def select_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    global stopped_processes, running_processes, inactive_directories

    await get_processes()

    """Select a process to run."""
    query = update.callback_query

    keyboard = []

    print("Stopped Processes: " + ', '.join(stopped_processes))
    print("Running Processes: " + ', '.join(running_processes))
    print("Inactive Directories: " + ', '.join(inactive_directories))

    for process in stopped_processes:
        keyboard.append([InlineKeyboardButton(process + u" 🔴", callback_data=process)])

    for process in running_processes:
        keyboard.append([InlineKeyboardButton(process + u" 🟢", callback_data=process)])

    for directory in inactive_directories:
        keyboard.append([InlineKeyboardButton(directory + u" ⚫", callback_data=directory)])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text('<b>Choose an option:</b>', parse_mode='HTML', reply_markup=reply_markup)

    return PROCESS_DECISION

async def process_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    global selected_process

    """Asks the user to fill in the mileage or skip."""
    query = update.callback_query
    await query.answer()
    selected_process = query.data

    #Xác định các nút nội tuyến để chọn màu ô tô
    keyboard = [
        [InlineKeyboardButton('STATUS', callback_data='status')],
        [InlineKeyboardButton('LOGS', callback_data='logs')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text('<b>Please choose:</b>', parse_mode='HTML', reply_markup=reply_markup)

    return PROCESS_COMMAND_DECISION

async def process_command_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user to fill in the mileage or skip."""
    query = update.callback_query
    await query.answer()
    decision = query.data

    if decision == 'status':
        return await status_process(update, context)
    elif decision == 'logs':
        return await logs_process(update, context)
    else:
        await query.edit_message_text(f"Invalid command: {decision}")
        return ConversationHandler.END

async def status_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send a message with the status of the bot."""

    logs = get_status_logs_by_process_name(selected_process)
    await send_message(update, context, (f"{logs}." if logs != "" else f"The process {selected_process} was not found."))
    return ConversationHandler.END

async def logs_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send a message with the status of the bot."""

    logs = get_logs_by_process_name(selected_process)
    await send_message(update, context, (f"{logs}." if logs != "" else f"The process {selected_process} was not found."))
    return ConversationHandler.END

def find_index(lst, value):
    for i, v in enumerate(lst):
        if v == value:
            return i
    return -1

#vùng cuối cùng
#khu vực Tất cả các quy trình

async def status_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    global stopped_processes, running_processes, inactive_directories, stopped_process_list, running_process_list

    await get_processes()

    for process in stopped_processes:
        await send_message(update, context, show_logs(process.strip()))

    for process in running_processes:
        await send_message(update, context, show_logs(process.strip()))

    for directory in inactive_directories:
        await send_message(update, context, show_logs(directory.strip()))

    return ConversationHandler.END

def show_logs(process) -> str:
    """Send a message with the status of the bot."""

    try:
        name, balance, next_claim_at, log_status = fetch_and_process_logs(process.strip())
        return f"{name}:\n\t BALANCE: {balance}\n\tNEXT CLAIM AT: {next_claim_at}\n\tLOG STATUS: {log_status}"
    except Exception as e:
        print(f"Error: {e}")
        return f"{process}: ERROR getting information."

#vùng cuối cùng
#khu vực sử dụng

async def send_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> int:
    """Send a message with the help of the bot."""

    #Xác định cách chính xác để gửi phản hồi dựa trên loại cập nhật
    if update.callback_query:
        #Nếu được gọi từ truy vấn gọi lại, hãy sử dụng thông báo của callback_query
        chat_id = update.callback_query.message.chat_id
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML')
        #Theo tùy chọn, bạn có thể muốn xác nhận truy vấn gọi lại
        await update.callback_query.answer()
    elif update.message:
        #Nếu được gọi từ tin nhắn trực tiếp
        await update.message.reply_text(text)
    else:
        #Xử lý các trường hợp khác hoặc ghi lại lỗi/cảnh báo
        logger.warning('skip_mileage was called without a message or callback_query context.')

async def get_processes():
    global stopped_processes, running_processes, inactive_directories

    stopped_processes = list_pm2_processes("stopped")
    running_processes = list_pm2_processes("online")
    inactive_directories = get_inactive_directories()

#Cuối vùng

def main() -> None:
    token = load_telegram_token('variables.txt')
    if not token:
        sys.exit(1)

    if not os.path.exists("/usr/src/app/games/utils"):
        pull_games_dest = "/usr/src/app/pull-games.sh"

        #Kiểm tra xem pull-games.sh có tồn tại không
        if os.path.exists(pull_games_dest):
            #Sửa đổi tập lệnh pull-games.sh
            modify_pull_games_script(pull_games_dest)

            #Làm cho tập lệnh có thể thực thi được
            os.chmod(pull_games_dest, 0o755)

            #Chạy tập lệnh pull-games.sh
            result = subprocess.run([pull_games_dest], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Failed to execute {pull_games_dest}: {result.stderr}")
                sys.exit(1)
            else:
                print(f"Successfully executed {pull_games_dest}: {result.stdout}")
        else:
            print("pull-games.sh does not exist, skipping the update.")

    list_pm2_processes = set(list_all_pm2_processes())

    if "Telegram-Bot" not in list_pm2_processes:
        script = "games/tg-bot.py"

        pm2_session = "Telegram-Bot"
        print(f"You could add the new/updated session to PM use: pm2 start {script} --interpreter venv/bin/python3 --name {pm2_session} -- {pm2_session}", 1)
        user_choice = input("Enter 'e' to exit, 'a' or <enter> to automatically add to PM2: ").lower()

        if user_choice == "e":
            print("Exiting script. You can resume the process later.", 1)
            sys.exit()
        elif user_choice == "a" or not user_choice:
            start_pm2_app(script, pm2_session, pm2_session)
            user_choice = input("Should we save your PM2 processes? (Y/n): ").lower()
            if user_choice == "y" or not user_choice:
                save_pm2()
            print(f"You can now watch the session log into PM2 with: pm2 logs {pm2_session}", 2)
            sys.exit()

    run()

async def run_command(command: str) -> str:
    """Execute a shell command and return its output."""
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if stderr:
        print(f"Error: {stderr.decode()}")
    return stdout.decode()

if __name__ == '__main__':
    main()
