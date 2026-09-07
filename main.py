# -*- coding: utf-8 -*-
"""
Script chính: đọc epub/docx -> tách đoạn <=2000 ký tự -> lần lượt gọi
AIdancing để clone giọng đọc -> tải về -> ghép/playlist liền mạch.

Chạy:  python main.py
Cấu hình: config.json (copy từ config.example.json rồi điền cookie, path...)
"""
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

from aidancing_client import AIDancingClient, AIDancingError
from text_utils import extract_text, split_into_chunks

CONFIG_PATH = "config.json"


def load_config(path=CONFIG_PATH):
    if not os.path.exists(path):
        print(f"Không tìm thấy {path}. Hãy copy config.example.json thành config.json rồi điền thông tin.")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state(state_path):
    if os.path.exists(state_path):
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"completed": {}}


def save_state(state_path, state):
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def build_playlist(output_dir, part_files):
    playlist_path = os.path.join(output_dir, "playlist.m3u")
    with open(playlist_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for p in part_files:
            f.write(os.path.basename(p) + "\n")
    return playlist_path


def try_merge_with_ffmpeg(output_dir, part_files):
    has_ffmpeg = subprocess.run(["which", "ffmpeg"], capture_output=True).returncode == 0
    if not has_ffmpeg:
        print("Không tìm thấy ffmpeg trên máy -> bỏ qua bước ghép file, dùng playlist.m3u để nghe tuần tự.")
        return None

    concat_list_path = os.path.join(output_dir, "concat_list.txt")
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for p in part_files:
            f.write(f"file '{os.path.basename(p)}'\n")

    merged_path = os.path.join(output_dir, "full_audiobook.mp3")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat_list.txt", "-c", "copy", "full_audiobook.mp3"]
    result = subprocess.run(cmd, cwd=output_dir, capture_output=True)
    if result.returncode == 0:
        return merged_path
    print("Ghép file bằng ffmpeg thất bại, dùng playlist.m3u thay thế. Lỗi:")
    print(result.stderr.decode(errors="ignore")[-800:])
    return None


def main():
    config = load_config()

    cookie = config["cookie"]
    voice_path = config["voice_sample_path"]
    book_path = config["book_path"]
    output_dir = config.get("output_dir", "audio_output")
    lang = config.get("lang", "vi")
    min_len = config.get("min_chunk_len", 1800)
    max_len = config.get("max_chunk_len", 2000)
    poll_interval = config.get("poll_interval_sec", 5)
    max_wait = config.get("max_wait_sec", 300)
    delay_lo, delay_hi = config.get("delay_between_jobs_sec", [3, 8])

    if not os.path.exists(voice_path):
        print(f"Không tìm thấy file giọng mẫu: {voice_path}")
        sys.exit(1)
    if not os.path.exists(book_path):
        print(f"Không tìm thấy file sách: {book_path}")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    state_path = os.path.join(output_dir, "state.json")
    state = load_state(state_path)

    print("Đang trích xuất văn bản từ sách...")
    text = extract_text(book_path)
    chunks = split_into_chunks(text, min_len, max_len)
    print(f"Đã tách thành {len(chunks)} đoạn (mỗi đoạn {min_len}-{max_len} ký tự).")

    client = AIDancingClient(cookie, lang=lang)

    part_files = []
    for i, chunk in enumerate(chunks):
        key = str(i)
        save_path = os.path.join(output_dir, f"part_{i:04d}.mp3")

        if key in state["completed"] and os.path.exists(save_path):
            print(f"[{i + 1}/{len(chunks)}] Đã có sẵn, bỏ qua.")
            part_files.append(save_path)
            continue

        print(f"[{i + 1}/{len(chunks)}] Đang tạo job ({len(chunk)} ký tự)...")
        try:
            job_uid = client.create_job(chunk)
            print(f"[{i + 1}/{len(chunks)}] jobUid={job_uid}, đang upload giọng mẫu...")
            client.upload_voice(job_uid, voice_path)
            print(f"[{i + 1}/{len(chunks)}] Đang chờ AIdancing xử lý...")
            output_url = client.poll_job(job_uid, interval=poll_interval, max_wait=max_wait)
            client.download_file(output_url, save_path)
        except AIDancingError as e:
            print(f"LỖI ở đoạn {i + 1}: {e}")
            print("Đã lưu tiến trình. Sửa lỗi (vd lấy cookie mới) rồi chạy lại `python main.py`,")
            print("script sẽ tự bỏ qua các đoạn đã xong và tiếp tục từ đoạn bị lỗi.")
            save_state(state_path, state)
            sys.exit(1)

        state["completed"][key] = save_path
        save_state(state_path, state)
        part_files.append(save_path)
        print(f"[{i + 1}/{len(chunks)}] Xong: {save_path}")

        if i < len(chunks) - 1:
            delay = random.uniform(delay_lo, delay_hi)
            time.sleep(delay)

    playlist_path = build_playlist(output_dir, part_files)
    print(f"\nĐã tạo playlist: {playlist_path} (mở bằng VLC hoặc trình phát hỗ trợ m3u để nghe liền mạch)")

    merged_path = try_merge_with_ffmpeg(output_dir, part_files)
    if merged_path:
        print(f"Đã ghép toàn bộ thành 1 file duy nhất: {merged_path}")

    print("\nHoàn tất!")


if __name__ == "__main__":
    main()
