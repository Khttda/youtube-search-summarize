import streamlit as st
import re
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)
from youtube_transcript_api.formatters import TextFormatter

# ==========================================
# 1. CÁC HÀM XỬ LÝ (Logic cũ của bạn)
# ==========================================

def extract_video_id(url_or_id: str) -> str:
    """
    Nhận vào URL YouTube hoặc video_id, trả về video_id (11 ký tự).
    """
    url_or_id = url_or_id.strip()
    # Regex bắt video id trong các dạng URL phổ biến
    m = re.search(r'(?:v=|/)([a-zA-Z0-9_-]{11})', url_or_id)
    if m:
        return m.group(1)
    return url_or_id


def get_clean_transcript(url_or_id: str, languages=('vi', 'en')) -> tuple[str, str]:
    """
    Lấy transcript dạng text sạch (không timestamp).
    """
    video_id = extract_video_id(url_or_id)
    ytt_api = YouTubeTranscriptApi()

    try:
        # Thử lấy transcript theo thứ tự ngôn ngữ ưu tiên
        fetched = ytt_api.fetch(video_id, languages=list(languages))
        
        # Format sang text thuần
        formatter = TextFormatter()
        transcript_text = formatter.format_transcript(fetched)

        return video_id, transcript_text

    except TranscriptsDisabled:
        raise RuntimeError(f"🚫 Phụ đề bị tắt cho video này ({video_id}).")
    except NoTranscriptFound:
        raise RuntimeError(f"❌ Không tìm thấy transcript ({video_id}).")
    except VideoUnavailable:
        raise RuntimeError(f"📛 Video không tồn tại hoặc bị chặn ({video_id}).")
    except Exception as e:
        raise RuntimeError(f"⚠️ Lỗi không xác định: {e}") from e

# ==========================================
# 2. GIAO DIỆN STREAMLIT
# ==========================================

st.set_page_config(page_title="YouTube Transcript", page_icon="📝")

st.title("📝 Lấy Transcript YouTube")
st.write("Nhập link YouTube để lấy nội dung văn bản (phụ đề).")

# Input nhận link
url_input = st.text_input("Link YouTube hoặc Video ID:", placeholder="Ví dụ: https://www.youtube.com/watch?v=...")

# Nút bấm thực thi
if st.button("🚀 Lấy Transcript"):
    if not url_input:
        st.warning("Vui lòng nhập đường link trước!")
    else:
        try:
            with st.spinner("Đang tải dữ liệu..."):
                # Gọi hàm xử lý trực tiếp tại đây (không cần Colab)
                video_id, text_content = get_clean_transcript(url_input)
            
            # Hiển thị kết quả
            st.success(f"Thành công! Video ID: {video_id}")
            
            # Vùng chứa nội dung text (cho phép copy)
            st.text_area("Nội dung:", value=text_content, height=300)
            
            # Nút tải về máy
            file_name = f"transcript_{video_id}.txt"
            st.download_button(
                label="💾 Tải xuống file .txt",
                data=text_content,
                file_name=file_name,
                mime="text/plain"
            )
            
        except RuntimeError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Lỗi lạ: {e}")
