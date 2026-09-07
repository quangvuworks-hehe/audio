# -*- coding: utf-8 -*-
"""
Trích xuất văn bản từ file .epub / .docx và tách thành các đoạn
có độ dài trong khoảng [min_len, max_len] ký tự, ưu tiên cắt tại
ranh giới câu để không làm vỡ ngữ nghĩa.
"""
import re
from pathlib import Path


def extract_text_from_epub(path: str) -> str:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup

    book = epub.read_epub(path)
    texts = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), "html.parser")
            text = soup.get_text(separator="\n")
            if text.strip():
                texts.append(text)
    return "\n\n".join(texts)


def extract_text_from_docx(path: str) -> str:
    from docx import Document

    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text(book_path: str) -> str:
    ext = Path(book_path).suffix.lower()
    if ext == ".epub":
        return extract_text_from_epub(book_path)
    elif ext == ".docx":
        return extract_text_from_docx(book_path)
    else:
        raise ValueError(f"Định dạng không hỗ trợ: {ext} (chỉ hỗ trợ .epub và .docx)")


_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def split_into_chunks(text: str, min_len: int = 1800, max_len: int = 2000):
    """
    Tách văn bản thành danh sách các đoạn, mỗi đoạn <= max_len ký tự,
    cố gắng đạt >= min_len trước khi ngắt đoạn, và luôn ưu tiên
    ngắt tại cuối câu. Nếu một câu đơn lẻ dài hơn max_len, buộc phải
    cắt cứng theo ký tự để không bị kẹt vô hạn.
    """
    text = text.replace("\r\n", "\n")
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    chunks = []
    current = ""

    def flush():
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for para in paragraphs:
        sentences = _SENTENCE_END.split(para)
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue

            # Câu quá dài, phải cắt cứng
            while len(sent) > max_len:
                if current:
                    flush()
                chunks.append(sent[:max_len])
                sent = sent[max_len:]

            candidate = f"{current} {sent}".strip() if current else sent
            if len(candidate) <= max_len:
                current = candidate
            else:
                flush()
                current = sent

            if len(current) >= min_len:
                flush()

        # Có xu hướng ngắt theo đoạn văn gốc nếu đã đủ dài
        if len(current) >= min_len:
            flush()

    flush()
    return chunks
