import re
import streamlit as st
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)
from youtube_transcript_api.formatters import TextFormatter


def extract_video_id(url_or_id: str) -> str:
    """
    Nhận vào URL YouTube hoặc video_id, trả về video_id (11 ký tự).
    Ví dụ:
      - https://www.youtube.com/watch?v=NXJqHVZJ9lI
      - https://youtu.be/NXJqHVZJ9lI
      - NXJqHVZJ9lI
    """
    url_or_id = url_or_id.strip()

    # Regex bắt video id trong các dạng URL phổ biến
    m = re.search(r'(?:v=|/)([a-zA-Z0-9_-]{11})', url_or_id)
    if m:
        return m.group(1)

    # Nếu không match regex, giả sử user đưa thẳng video_id
    return url_or_id


def get_clean_transcript(url_or_id: str,
                         languages=('vi', 'en')) -> tuple[str, str]:
    """
    Lấy transcript dạng text sạch (không timestamp) cho 1 video.
    Trả về: (video_id, transcript_text)
    """
    video_id = extract_video_id(url_or_id)
    ytt_api = YouTubeTranscriptApi()

    try:
        fetched = ytt_api.fetch(video_id, languages=list(languages))

        formatter = TextFormatter()
        transcript_text = formatter.format_transcript(fetched)

        return video_id, transcript_text

    except TranscriptsDisabled:
        raise RuntimeError(
            f"🚫 Phụ đề bị tắt cho video này (video_id = {video_id})."
        )
    except NoTranscriptFound:
        raise RuntimeError(
            f"❌ Không tìm thấy transcript cho video này (video_id = {video_id})."
        )
    except VideoUnavailable:
        raise RuntimeError(
            f"📛 Video không tồn tại hoặc bị chặn (video_id = {video_id})."
        )
    except Exception as e:
        raise RuntimeError(f"⚠️ Lỗi không xác định: {e}") from e


# ======================
# PHẦN GIAO DIỆN STREAMLIT
# ======================

st.set_page_config(page_title="YouTube Transcript", page_icon="🎬", layout="wide")

st.title("🎬 YouTube Transcript (Free)")
st.write("Dán link hoặc video_id YouTube để lấy transcript dạng text.")

url = st.text_input(
    "Link hoặc video_id YouTube",
    placeholder="Ví dụ: https://www.youtube.com/watch?v=NXJqHVZJ9lI",
)

# Cho phép chọn thứ tự ngôn ngữ ưu tiên
lang_options = st.multiselect(
    "Ưu tiên ngôn ngữ phụ đề (chọn theo thứ tự):",
    ["vi", "en"],
    default=["vi", "en"],
)

get_btn = st.button("Lấy transcript")

if get_btn:
    if not url:
        st.warning("⚠️ Vui lòng nhập link hoặc video_id trước.")
    else:
        if not lang_options:
            st.warning("⚠️ Vui lòng chọn ít nhất một ngôn ngữ.")
        else:
            with st.spinner("⏳ Đang lấy transcript..."):
                try:
                    video_id, transcript_text = get_clean_transcript(
                        url,
                        languages=tuple(lang_options),
                    )

                    st.success(f"✅ Lấy transcript thành công cho video_id: {video_id}")

                    # Nút tải file .txt
                    st.download_button(
                        label="💾 Tải transcript (.txt)",
                        data=transcript_text,
                        file_name=f"transcript_{video_id}.txt",
                        mime="text/plain",
                    )

                    # Hiện transcript
                    st.text_area(
                        "Transcript (có thể copy dán qua chỗ khác)",
                        value=transcript_text,
                        height=400,
                    )

                except RuntimeError as e:
                    st.error(str(e))
