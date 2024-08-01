import os
import sys
import json
import asyncio
import logging
import subprocess
import requests

def download_file(url, dest):
    """Tải tệp xuống từ URL tới đường dẫn đích."""
    try:
        response = requests.get(url)
        response.raise_for_status()  #Đảm bảo chúng tôi nhận thấy phản hồi không tốt
        with open(dest, 'wb') as f:
            f.write(response.content)
        print(f"Đã tải xuống {url} to {dest}")
    except Exception as e:
        print(f"Không thể tải xuống {url}: {e}")
        sys.exit(1)

def modify_pull_games_script(script_path):
    """Sửa đổi tập lệnh pull-games.sh cho phù hợp với mục đích của chúng tôi."""
    script_content = """#!/bin/bash

# Xác định thư mục đích và nguồn
TARGET_DIR="/app"
GAMES_DIR="$TARGET_DIR/games"
DEST_DIR="/usr/src/app/games"

# Kiểm tra xem thư mục có tồn tại không và có phải là kho lưu trữ git không
if [ -d "$TARGET_DIR" ] && [ -d "$TARGET_DIR/.git" ]; then
    echo "$TARGET_DIR pulling latest changes."
    cd $TARGET_DIR
    git pull
elif [ -d "$TARGET_DIR" ] ; then
    echo "$TARGET_DIR tồn tại nhưng không phải là kho lưu trữ git. Loại bỏ và nhân bản một lần nữa."
    rm -rf $TARGET_DIR
    git clone https://github.com/bibo318/telegram-claim-bot.git $TARGET_DIR
else
    echo "$TARGET_DIR không tồn tại. Kho nhân bản."
    git clone https://github.com/bibo318/telegram-claim-bot.git $TARGET_DIR
fi

# Đặt thư mục làm việc vào kho lưu trữ nhân bản
cd $GAMES_DIR

# Tạo thư mục đích
mkdir -p $DEST_DIR

# Sao chép đệ quy nội dung của thư mục trò chơi
cp -r $GAMES_DIR/* $DEST_DIR

echo "All files and subdirectories have been copied to $DEST_DIR"
"""
    try:
        with open(script_path, 'w') as f:
            f.write(script_content)
        print(f"Đã sửa đổi {script_path} thành công.")
    except Exception as e:
        print(f"Không thể sửa đổi {script_path}: {e}")
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
                print(f"Không thể thực thi {pull_games_dest}: {result.stderr}")
                sys.exit(1)
            else:
                print(f"Thực hiện thành công {pull_games_dest}: {result.stdout}")
        else:
            print("pull-games.sh không tồn tại, bỏ qua cập nhật.")

#Đảm bảo trò chơi/tiện ích có mặt trước khi tiến hành nhập
check_and_update_games_utils()

try:
    from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove, Update,
                          InlineKeyboardButton, InlineKeyboardMarkup)
    from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                              ContextTypes, ConversationHandler, MessageHandler, filters)
except ImportError:
    print("Mô-đun 'python-telegram-bot' chưa được cài đặt. Đang cài đặt nó bây giờ...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-telegram-bot"])
    from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove, Update,
                          InlineKeyboardButton, InlineKeyboardMarkup)
    from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                              ContextTypes, ConversationHandler, MessageHandler, filters)

try:
    from utils.pm2 import start_pm2_app, save_pm2
except ImportError:
    print("Không thể nhập tiện ích PM2 ngay cả sau khi cố gắng sao chép các tệp và thư mục cần thiết.")
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
    """Tải mã thông báo bot telegram từ tệp được chỉ định."""
    if not os.path.exists(file_path):
        logger.error(f"Tệp {file_path} không tồn tại.")
        sys.exit(1)

    with open(file_path, 'r') as file:
        config = json.load(file)
    
    token = config.get("telegramBotToken")

    if token:
        logger.info(f"Đã trích xuất mã thông báo: {token}")
        return token
    else:
        logger.error("không tìm thấy telegramBotToken trong tệp.")
        sys.exit(1)

def run() -> None:
    """Chạy bot."""
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
    """Bắt đầu cuộc trò chuyện và hỏi người dùng về loại lệnh ưa thích của họ."""
    await update.message.reply_text(
        '<b>Telegram Claim Bot!\n'
        'Làm thế nào để tôi giúp bạn?</b>',
        parse_mode='HTML',
        reply_markup=ReplyKeyboardRemove(),
    )

    #Xác định các nút nội tuyến để chọn màu ô tô
    keyboard = [
        [InlineKeyboardButton('TẤT CẢ CÁC TRẠNG THÁI', callback_data='status')],
        [InlineKeyboardButton('QUY TRÌNH CHỌN', callback_data='process')],
        [InlineKeyboardButton('Giúp đỡ', callback_data='help')],
        [InlineKeyboardButton('Thoát', callback_data='exit')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('<b>Xin vui lòng chọn:</b>', parse_mode='HTML', reply_markup=reply_markup)

    return COMMAND_DECISION

async def command_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Yêu cầu người dùng điền số dặm hoặc bỏ qua."""
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
    """Gửi tin nhắn với sự trợ giúp của bot."""
    return await send_message(update, context, "Các lệnh có sẵn:\n/start -Khởi động bot\n/status -Kiểm tra trạng thái của tất cả các tiến trình\n/help -Hiển thị thông báo trợ giúp này\n/exit -Thoát bot")

async def exit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exit the bot."""
    return await send_message(update, context, "Tạm biệt!")

#khu vực Quy trình duy nhất

async def select_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    global stopped_processes, running_processes, inactive_directories

    await get_processes()

    """Chọn một tiến trình để chạy."""
    query = update.callback_query

    keyboard = []

    print("Quá trình đã dừng: " + ', '.join(stopped_processes))
    print("Tiến trình đang chạy: " + ', '.join(running_processes))
    print("Thư mục không hoạt động: " + ', '.join(inactive_directories))

    for process in stopped_processes:
        keyboard.append([InlineKeyboardButton(process + u" 🔴", callback_data=process)])

    for process in running_processes:
        keyboard.append([InlineKeyboardButton(process + u" 🟢", callback_data=process)])

    for directory in inactive_directories:
        keyboard.append([InlineKeyboardButton(directory + u" ⚫", callback_data=directory)])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text('<b>Chọn một sự lựa chọn:</b>', parse_mode='HTML', reply_markup=reply_markup)

    return PROCESS_DECISION

async def process_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    global selected_process

    """Yêu cầu người dùng điền số dặm hoặc bỏ qua."""
    query = update.callback_query
    await query.answer()
    selected_process = query.data

    #Xác định các nút nội tuyến để chọn màu ô tô
    keyboard = [
        [InlineKeyboardButton('Trạng thái', callback_data='status')],
        [InlineKeyboardButton('LOGS', callback_data='logs')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text('<b>Xin vui lòng chọn:</b>', parse_mode='HTML', reply_markup=reply_markup)

    return PROCESS_COMMAND_DECISION

async def process_command_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Yêu cầu người dùng điền số dặm hoặc bỏ qua."""
    query = update.callback_query
    await query.answer()
    decision = query.data

    if decision == 'status':
        return await status_process(update, context)
    elif decision == 'logs':
        return await logs_process(update, context)
    else:
        await query.edit_message_text(f"Lệnh không hợp lệ: {decision}")
        return ConversationHandler.END

async def status_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gửi tin nhắn với trạng thái của bot."""

    logs = get_status_logs_by_process_name(selected_process)
    await send_message(update, context, (f"{logs}." if logs != "" else f"Không tìm thấy quá trình {selected_process}."))
    return ConversationHandler.END

async def logs_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gửi tin nhắn với trạng thái của bot."""

    logs = get_logs_by_process_name(selected_process)
    await send_message(update, context, (f"{logs}." if logs != "" else f"Không tìm thấy quá trình {selected_process}."))
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
    """Gửi tin nhắn với trạng thái của bot."""

    try:
        name, balance, next_claim_at, log_status = fetch_and_process_logs(process.strip())
        return f"{name}:\n\t BALANCE: {balance}\n\tYÊU CẦU TIẾP THEO TẠI: {next_claim_at}\n\TRẠNG THÁI LOGS: {log_status}"
    except Exception as e:
        print(f"Lỗi: {e}")
        return f"{process}: LỖI lấy thông tin."

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
        logger.warning('Skip_mileage được gọi mà không có thông báo hoặc bối cảnh callback_query.')

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
                print(f"Không thể thực thi {pull_games_dest}: {result.stderr}")
                sys.exit(1)
            else:
                print(f"Thực hiện thành công {pull_games_dest}: {result.stdout}")
        else:
            print("pull-games.sh không tồn tại, bỏ qua cập nhật.")

    list_pm2_processes = set(list_all_pm2_processes())

    if "Telegram-Bot" not in list_pm2_processes:
        script = "games/tg-bot.py"

        pm2_session = "Telegram-Bot"
        print(f"Bạn có thể thêm phiên mới/cập nhật vào sử dụng PM: pm2 start {script} --interpreter venv/bin/python3 --name {pm2_session} -- {pm2_session}", 1)
        user_choice = input("Nhập 'e' để thoát, 'a' hoặc <enter> để tự động thêm vào PM2: ").lower()

        if user_choice == "e":
            print("Đang thoát tập lệnh. Bạn có thể tiếp tục quá trình này sau.", 1)
            sys.exit()
        elif user_choice == "a" or not user_choice:
            start_pm2_app(script, pm2_session, pm2_session)
            user_choice = input("Chúng tôi có nên lưu quy trình PM2 của bạn không? (Y/n): ").lower()
            if user_choice == "y" or not user_choice:
                save_pm2()
            print(f"Bây giờ bạn có thể xem nhật ký phiên vào PM2 bằng: nhật ký pm2 {pm2_session}", 2)
            sys.exit()

    run()

async def run_command(command: str) -> str:
    """Thực thi lệnh shell và trả về đầu ra của nó."""
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
