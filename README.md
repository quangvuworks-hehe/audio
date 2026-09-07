# AIdancing Audiobook Automation

Tự động chuyển toàn bộ 1 file epub/docx thành audiobook bằng giọng clone
trên audio.aidancing.net: tách văn bản thành từng đoạn 1800–2000 ký tự,
lần lượt gọi API nội bộ của site (dùng cookie phiên đăng nhập của bạn) để
tạo audio, tải về, rồi ghép/liên kết thành 1 luồng nghe liền mạch.

**Chỉ dùng cho mục đích cá nhân** (nghe sách bạn sở hữu), không dùng để
phát tán lại nội dung đã tạo. Đây là script tự động hoá dựa trên chính
tài khoản của bạn — vẫn có rủi ro cookie/tài khoản bị khoá nếu AIdancing
phát hiện traffic bất thường, vì việc này đi vòng qua giới hạn thao tác
thủ công mà bản free của họ đặt ra.

## 1. Cài đặt

```bash
pip install -r requirements.txt
```

Nếu muốn script tự ghép các đoạn thành 1 file mp3 duy nhất, cài thêm `ffmpeg`
(không bắt buộc — nếu không có, script vẫn tạo `playlist.m3u` để phát tuần tự).

- macOS: `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt install ffmpeg`
- Windows: tải từ https://ffmpeg.org rồi thêm vào PATH

## 2. Lấy Cookie

1. Mở https://audio.aidancing.net trên trình duyệt, đăng nhập/dùng bình thường 1 lần
   (upload thử 1 giọng mẫu, tạo thử 1 audio) để chắc chắn có session hợp lệ.
2. Mở DevTools (F12) → tab **Network**.
3. Tạo 1 audio bất kỳ (thủ công) để có request xuất hiện.
4. Click vào request `jobs` bất kỳ → tab **Headers** → phần **Request Headers**
   → copy toàn bộ giá trị của dòng `Cookie: ...`.
5. Dán giá trị đó vào field `"cookie"` trong `config.json`.

**Lưu ý:** Cookie sẽ hết hạn theo thời gian hoặc khi bạn đăng xuất ở nơi khác.
Nếu script báo lỗi kiểu "Failed to upload voice... cookie is valid", nghĩa là
cần lấy lại cookie mới theo đúng các bước trên.

## 3. Cấu hình

```bash
cp config.example.json config.json
```

Sửa `config.json`:

| Field | Ý nghĩa |
|---|---|
| `cookie` | Cookie lấy ở bước 2 |
| `voice_sample_path` | Đường dẫn tới file audio giọng mẫu để clone (mp3) |
| `book_path` | Đường dẫn tới file `.epub` hoặc `.docx` cần chuyển |
| `output_dir` | Thư mục lưu kết quả |
| `min_chunk_len` / `max_chunk_len` | Khoảng độ dài mỗi đoạn văn bản (mặc định 1800–2000) |
| `poll_interval_sec` | Tần suất kiểm tra trạng thái job (giây) |
| `max_wait_sec` | Thời gian chờ tối đa 1 job trước khi báo timeout |
| `delay_between_jobs_sec` | Khoảng nghỉ ngẫu nhiên giữa các lần tạo job, để tránh gửi request quá dồn dập |

## 4. Chạy

```bash
python main.py
```

Script sẽ:
1. Trích xuất toàn bộ text từ epub/docx.
2. Tách thành các đoạn theo đúng ranh giới câu, mỗi đoạn trong khoảng đã cấu hình.
3. Với từng đoạn: tạo job → upload giọng mẫu → chờ xử lý xong → tải file `.mp3` về `output_dir/part_XXXX.mp3`.
4. Sau khi xong hết: tạo `playlist.m3u` (mở bằng VLC hoặc trình phát hỗ trợ m3u để nghe liền mạch tất cả các phần theo đúng thứ tự), và nếu máy có `ffmpeg` thì tự ghép thành `full_audiobook.mp3`.

## 5. Resume khi bị gián đoạn

Tiến trình được lưu vào `output_dir/state.json`. Nếu script dừng giữa chừng
(mất mạng, cookie hết hạn, Ctrl+C...), chỉ cần chạy lại `python main.py`,
các đoạn đã tải xong sẽ tự động được bỏ qua, tiếp tục từ đoạn còn dang dở.

## Cấu trúc endpoint đã dùng (tham khảo)

```
POST /jobs                     {"text": "...", "lang": "vi"}   -> {"jobUid": "..."}
POST /jobs/{jobUid}/upload     multipart, field "file"         -> bắt đầu xử lý
GET  /jobs                     -> danh sách job kèm "status" ("PENDING"/"COMPLETED"/"FAILED") và "outputUrl"
GET  {outputUrl}                (vd /files/715912)             -> file audio kết quả
```

Nếu AIdancing thay đổi cấu trúc API trong tương lai, script sẽ báo lỗi rõ ràng
(kèm nội dung response) — bạn F12 lại và cập nhật `aidancing_client.py` tương ứng.
