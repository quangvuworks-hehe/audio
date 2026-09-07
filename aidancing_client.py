# -*- coding: utf-8 -*-
"""
Client gọi các endpoint nội bộ của audio.aidancing.net, dựa trên
request thực tế lấy từ DevTools (F12) của chính tài khoản người dùng.

Luồng hoạt động:
  1. POST /jobs            {"text": "...", "lang": "vi"}  -> {"jobUid": "..."}
  2. POST /jobs/{uid}/upload   (multipart, field "file")  -> upload giọng mẫu, bắt đầu xử lý
  3. GET  /jobs             -> danh sách job, tìm theo jobUid, đọc "status" / "outputUrl"
  4. GET  {outputUrl}        -> tải file audio kết quả (vd /files/715912)
"""
import os
import time
import requests


class AIDancingError(RuntimeError):
    pass


class AIDancingClient:
    BASE_URL = "https://audio.aidancing.net"

    def __init__(self, cookie: str, lang: str = "vi"):
        self.session = requests.Session()
        self.lang = lang
        self.headers = {
            "Origin": self.BASE_URL,
            "Referer": self.BASE_URL + "/",
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/152.0.0.0 Mobile Safari/537.36"
            ),
            "Cookie": cookie,
            "Accept": "*/*",
        }

    def create_job(self, text: str) -> str:
        url = f"{self.BASE_URL}/jobs"
        headers = {**self.headers, "Content-Type": "application/json"}
        resp = self.session.post(url, headers=headers, json={"text": text, "lang": self.lang})
        if resp.status_code >= 400:
            raise AIDancingError(f"Tạo job thất bại ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        job_uid = data.get("jobUid") or data.get("uid") or data.get("id")
        if not job_uid:
            raise AIDancingError(f"Không tìm thấy jobUid trong response: {data}")
        return job_uid

    def upload_voice(self, job_uid: str, voice_path: str):
        url = f"{self.BASE_URL}/jobs/{job_uid}/upload"
        filename = os.path.basename(voice_path)
        with open(voice_path, "rb") as f:
            files = {"file": (filename, f, "audio/mpeg")}
            resp = self.session.post(url, headers=self.headers, files=files)
        if resp.status_code >= 400:
            raise AIDancingError(f"Upload giọng mẫu thất bại ({resp.status_code}): {resp.text[:300]}")
        return resp

    def get_jobs(self):
        url = f"{self.BASE_URL}/jobs"
        resp = self.session.get(url, headers=self.headers)
        if resp.status_code >= 400:
            raise AIDancingError(f"Lấy danh sách job thất bại ({resp.status_code}): {resp.text[:300]}")
        return resp.json()

    def poll_job(self, job_uid: str, interval: int = 5, max_wait: int = 300) -> str:
        waited = 0
        while waited < max_wait:
            jobs = self.get_jobs()
            job = next((j for j in jobs if j.get("jobUid") == job_uid), None)
            if job is None:
                raise AIDancingError(f"Không tìm thấy job {job_uid} trong danh sách /jobs")

            status = job.get("status")
            if status == "COMPLETED":
                output_url = job.get("outputUrl")
                if not output_url:
                    raise AIDancingError(f"Job {job_uid} COMPLETED nhưng không có outputUrl: {job}")
                return output_url
            if status == "FAILED":
                raise AIDancingError(
                    f"Job {job_uid} FAILED — có thể cookie hết hạn hoặc voice mẫu lỗi. "
                    f"Chi tiết: {job.get('title')}"
                )

            time.sleep(interval)
            waited += interval

        raise AIDancingError(f"Job {job_uid} không hoàn tất sau {max_wait}s (timeout)")

    def download_file(self, output_url: str, save_path: str):
        url = f"{self.BASE_URL}{output_url}"
        resp = self.session.get(url, headers=self.headers, stream=True)
        if resp.status_code >= 400:
            raise AIDancingError(f"Tải file thất bại ({resp.status_code}): {output_url}")
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
