#!/bin/bash

# Cập nhật danh sách gói
sudo apt update

# Cài đặt các phụ thuộc cơ bản
sudo apt install -y snapd curl wget python3 python3-pip libzbar0 unzip python3-venv gdebi-core || true
sudo systemctl daemon-reload

# Tạo môi trường ảo và cài đặt phụ thuộc
python3 -m venv venv
source venv/bin/activate
pip install wheel selenium Pillow pyzbar qrcode-terminal python-telegram-bot requests mitmproxy
deactivate

# Cài đặt Node.js và npm
curl -fsSL https://deb.nodesource.com/setup_current.x | sudo -E bash -
sudo apt-get install -y nodejs || true

# Cài đặt pm2 
sudo npm install pm2@latest -g

install_chromium_arm64() {
    sudo apt-get clean
    sudo apt-get autoclean
    sudo rm -rf /var/lib/apt/lists/
    sudo apt update
    sudo apt-get install xdg-utils libasound2-dev -y
    # Tìm nạp và cài đặt crom-codec-ffmpeg-extra
    wget http://launchpadlibrarian.net/660838579/chromium-codecs-ffmpeg-extra_112.0.5615.49-0ubuntu0.18.04.1_arm64.deb
    sudo gdebi -n chromium-codecs-ffmpeg-extra_112.0.5615.49-0ubuntu0.18.04.1_arm64.deb

    # Tìm nạp và cài đặt trình duyệt crom
    wget http://launchpadlibrarian.net/660838574/chromium-browser_112.0.5615.49-0ubuntu0.18.04.1_arm64.deb
    sudo gdebi -n chromium-browser_112.0.5615.49-0ubuntu0.18.04.1_arm64.deb

    # Tìm nạp và cài đặt crom-chromedriver
    wget http://launchpadlibrarian.net/660838578/chromium-chromedriver_112.0.5615.49-0ubuntu0.18.04.1_arm64.deb
    sudo gdebi -n chromium-chromedriver_112.0.5615.49-0ubuntu0.18.04.1_arm64.deb
}

install_chromium_x86_64() {
    sudo apt install -y chromium-browser chromium-chromedriver
}

install_google_chrome() {
    wget -O /tmp/chrome.deb https://mirror.cs.uchicago.edu/google-chrome/pool/main/g/google-chrome-stable/google-chrome-stable_126.0.6478.114-1_amd64.deb
    sudo dpkg -i /tmp/chrome.deb
    sudo apt-get install -f -y  # Khắc phục mọi vấn đề phụ thuộc
    rm /tmp/chrome.deb
}

install_chromedriver() {
    sudo apt install -y unzip || true  # Đảm bảo giải nén được cài đặt
    wget https://storage.googleapis.com/chrome-for-testing-public/126.0.6478.63/linux64/chromedriver-linux64.zip
    unzip chromedriver-linux64.zip
    rm chromedriver-linux64.zip
    sudo mv chromedriver-linux64/chromedriver /usr/local/bin/
    sudo chmod +x /usr/local/bin/chromedriver
}

prompt_swap_browser() {
    local current_browser=$1
    local new_browser=$2
    local install_function=$3

    read -p "Bạn có muốn đổi từ $current_browser sang $new_browser không? (có/không): " response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        echo "Chuyển từ $current_browser sang $new_browser..."
        sudo apt-get remove -y chromium-browser google-chrome-stable
        $install_function
    else
        echo "Duy trì $current_browser..."
    fi
}

ARCH=$(uname -m)

if [[ "$ARCH" == "x86_64" ]]; then
    # Các biến để kiểm tra trạng thái cài đặt
    GOOGLE_CHROME_INSTALLED=false
    CHROMIUM_INSTALLED=false

    # Kiểm tra xem Google Chrome đã được cài đặt chưa
    if google-chrome --version &>/dev/null; then
        GOOGLE_CHROME_INSTALLED=true
        CHROME_VERSION=$(google-chrome --version | grep -oP '(?<=Google Chrome\s)[\d.]+')
        echo "Google Chrome đã được cài đặt. Phiên bản: $CHROME_VERSION"
    fi

    # Kiểm tra xem Chrome đã được cài đặt chưa
    if chromium-browser --version &>/dev/null; then
        CHROMIUM_INSTALLED=true
        CHROME_VERSION=$(chromium-browser --version | grep -oP '(?<=Chromium\s)[\d.]+')
        echo "Chrome đã được cài đặt. Phiên bản: $CHROME_VERSION"
    fi

    # Nhắc trao đổi trình duyệt nếu cả hai đều được cài đặt
    if $GOOGLE_CHROME_INSTALLED && $CHROMIUM_INSTALLED; then
        prompt_swap_browser "Google Chrome" "Chromium" install_chromium_x86_64
    elif $GOOGLE_CHROME_INSTALLED; then
        prompt_swap_browser "Google Chrome" "Chromium" install_chromium_x86_64
    elif $CHROMIUM_INSTALLED; then
        prompt_swap_browser "Chromium" "Google Chrome" install_google_chrome
    else
        echo "Cả Google Chrome và Chrome đều không được cài đặt. Cài đặt Crom..."
        install_chromium_x86_64
    fi

    # Kiểm tra xem Chromedriver đã được cài đặt chưa
    if chromedriver --version &>/dev/null; then
        CHROMEDRIVER_VERSION=$(chromedriver --version | grep -oP '(?<=ChromeDriver\s)[\d.]+')
        echo "Chromedriver đã được cài đặt. Phiên bản: $CHROMEDRIVER_VERSION"
    else
        echo "Chromedriver chưa được cài đặt. Đang cài đặt ngay bây giờ..."
        install_chromedriver
    fi
elif [[ "$ARCH" == "aarch64" ]]; then
    # Kiểm tra xem Chrome đã được cài đặt chưa
    if chromium-browser --version &>/dev/null; then
        CHROME_VERSION=$(chromium-browser --version | grep -oP '(?<=Chromium\s)[\d.]+')
        echo "Chrome đã được cài đặt. Phiên bản: $CHROME_VERSION"
    else
        echo "Chrome chưa được cài đặt. Đang cài đặt ngay bây giờ..."
        install_chromium_arm64
    fi

    # Kiểm tra xem Chromedriver đã được cài đặt chưa
    if chromedriver --version &>/dev/null; then
        CHROMEDRIVER_VERSION=$(chromedriver --version | grep -oP '(?<=ChromeDriver\s)[\d.]+')
        echo "Chromedriver đã được cài đặt. Phiên bản: $CHROMEDRIVER_VERSION"
    else
        echo "Chromedriver chưa được cài đặt. Đang cài đặt ngay bây giờ..."
        install_chromium_arm64
    fi
else
    echo "Kiến trúc không được hỗ trợ: $ARCH"
    exit 1
fi

# Tìm nạp và hiển thị các phiên bản đã cài đặt
if google-chrome --version &>/dev/null; then
    CHROME_VERSION=$(google-chrome --version | grep -oP '(?<=Google Chrome\s)[\d.]+')
elif chromium-browser --version &>/dev/null; then
    CHROME_VERSION=$(chromium-browser --version | grep -oP '(?<=Chromium\s)[\d.]+')
fi

CHROMEDRIVER_VERSION=$(chromedriver --version | grep -oP '(?<=ChromeDriver\s)[\d.]+')

echo ""
echo "Phiên bản đã cài đặt:"
echo "Phiên bản PM2: $(pm2 --version)"
echo "Phiên bản Python: $(python3 --version 2>/dev/null || echo 'Python 3 not found')"
echo "Phiên bản Node.js: $(node --version 2>/dev/null || echo 'Node.js not found')"
echo "phiên bản npm: $(npm --version 2>/dev/null || echo 'npm not found')"
echo "Phiên bản Chrome/Chrome: $CHROME_VERSION"
echo "Phiên bản Chromedriver: $CHROMEDRIVER_VERSION"
echo "Architecture: $ARCH"
echo "Ghi chú: Người dùng x86_64 có thể chạy lại tập lệnh này để chuyển đổi giữa các trình duyệt Google Chrome/Chromium."
