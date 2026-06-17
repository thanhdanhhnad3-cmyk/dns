# NextDNS Auto-Register Tool

Tự động đăng ký tài khoản NextDNS và lấy API key bằng email tạm từ tinyhost.shop + Playwright.

**Made by: henxi**

---

## Yêu cầu

- Python 3.10+
- Internet (truy cập tinyhost.shop & nextdns.io)
- Windows / macOS / Linux

## Cài đặt

```bash
# 1. Clone/copy thư mục project
cd d:\adsgoogle

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Cài trình duyệt Chromium (bắt buộc)
playwright install chromium
```

## Sử dụng

```bash
# Hỏi số lượng API key cần tạo
python main.py

# Tạo trực tiếp N accounts
python main.py --count 10

# Hiển thị trình duyệt (thay vì headless)
python main.py --visible

# Kết hợp nhiều tùy chọn
python main.py -c 5 -o my_keys.txt --visible
```

## Output

Kết quả được lưu vào `api_keys.txt` (append, không ghi đè):

```
email|password|apiKey|profileId|timestamp
```

## Cấu trúc project

```
d:\adsgoogle\
├── main.py          # Entry point
├── config.py        # Cấu hình
├── logger.py        # Logging
├── tinyhost.py      # Tinyhost API client
├── nextdns.py       # NextDNS Playwright engine
├── requirements.txt # Dependencies
├── api_keys.txt     # Kết quả
├── README.md        # Hướng dẫn
└── nextdns_tool.log # Log file
```
