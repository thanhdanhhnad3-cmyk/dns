# Hướng dẫn triển khai lên VPS Ubuntu (tự động)

Các file trong thư mục `deploy/` giúp bạn triển khai project lên VPS Ubuntu 24.04.

- `dns.service.template`: template systemd service (thay `__REPLACE_USER__` bằng username trên VPS).
- `setup.sh`: script dùng để chạy trên VPS (chạy bằng `sudo`) — nó sẽ cài gói, clone repo, tạo virtualenv, cài dependencies và cài systemd service.

Ví dụ chạy trên VPS (qua SSH):

```bash
# Trên VPS, chạy (đổi user và repo URL):
sudo bash /path/to/setup.sh ubuntu_user https://github.com/thanhdanhhnad3-cmyk/dns.git main
```

Sau khi chạy xong, service sẽ được enable và start. Kiểm tra trạng thái:

```bash
sudo systemctl status dns --no-pager
sudo journalctl -u dns -f
```

Nếu bạn muốn chỉnh `--count` hoặc tham số khác, chỉnh phần `ExecStart` trong file `/etc/systemd/system/dns.service` hoặc chỉnh `dns.service.template` trước khi dùng `setup.sh`.
