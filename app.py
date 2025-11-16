import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound
import google.generativeai as genai

# Giới hạn độ dài transcript gửi cho Gemini (tránh quá dài)
MAX_TRANSCRIPT_CHARS = 12000


# ================== FUNCTIONS ==================

@st.cache_data(show_spinner=False, ttl=60 * 60)
def search_youtube(api_key, query, max_results=3):
    """
    Tìm kiếm video trên YouTube, được cache 1 tiếng theo (api_key, query, max_results).
    """
    try:
        youtube = build('youtube', 'v3', developerKey=api_key)

        request = youtube.search().list(
            part='snippet',
            q=query,
            type='video',
            maxResults=max_results
        )
        response = request.execute()

        videos = []
        for item in response.get('items', []):
            video_id = item['id']['videoId']
            title = item['snippet']['title']
            channel = item['snippet']['channelTitle']
            videos.append(
                {
                    "id": video_id,
                    "title": title,
                    "channel": channel,
                }
            )
        return videos

    except HttpError as e:
        # Bắt riêng lỗi quota / rate limit từ YouTube Data API
        if e.resp.status == 429:
            st.error(
                "LỖI 429 khi gọi YouTube Data API: IP của server (Streamlit Cloud) "
                "đang bị giới hạn tạm thời. Hãy thử lại sau vài phút, hoặc "
                "dùng API Key khác / deploy app ở nơi khác."
            )
        else:
            st.error(f"Lỗi khi gọi YouTube Data API: {e}")
        return None
    except Exception as e:
        st.error(f"Lỗi khi tìm kiếm YouTube: {e}")
        st.error(
            "Gợi ý: API Key YouTube đã đúng chưa? "
            "Bạn đã bật 'YouTube Data API v3' trong Google Cloud Console chưa?"
        )
        return None


@st.cache_data(show_spinner=False, ttl=24 * 60 * 60)
def get_transcript(video_id: str):
    """
    Lấy transcript của video, cache 1 ngày theo video_id.
    Vì youtube-transcript-api không dùng API key, rất dễ bị YouTube chặn (429) trên server free.
    """
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(
            video_id,
            languages=["vi", "en"]
        )
        transcript = " ".join([item["text"] for item in transcript_list])
        return transcript

    except NoTranscriptFound:
        st.warning(
            f"Video (ID: {video_id}) không có phụ đề (transcript) "
            "=> Không thể tóm tắt."
        )
        return None
    except Exception as e:
        msg = str(e)
        # Nhận diện lỗi 429 / Too Many Requests từ YouTube
        if "Too Many Requests" in msg or "429" in msg:
            st.error(
                "YouTube đang trả về lỗi 429 (Too Many Requests) khi lấy transcript.\n\n"
                "- Điều này thường xảy ra với các server free như Streamlit Cloud "
                "khi có quá nhiều request từ cùng một IP, hoặc IP bị YouTube đánh dấu là 'lạ'.\n"
                "- Code của bạn không sai, đây là giới hạn từ phía YouTube.\n\n"
                "Cách khắc phục:\n"
                "1. Thử lại sau vài phút.\n"
                "2. Chạy app trên máy local để dùng IP của bạn.\n"
                "3. Deploy lên VPS riêng / dịch vụ khác để có IP riêng."
            )
        else:
            st.error(f"Lỗi khi lấy transcript: {e}")
        return None


def summarize_text(api_key: str, text_to_summarize: str):
    """
    Tóm tắt transcript bằng Gemini.
    """
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        # Cắt bớt transcript nếu quá dài
        if len(text_to_summarize) > MAX_TRANSCRIPT_CHARS:
            text_to_summarize = text_to_summarize[:MAX_TRANSCRIPT_CHARS]

        prompt = f"""
        Hãy tóm tắt văn bản sau đây (transcript của một video YouTube) một cách súc tích.
        - Tập trung vào các ý chính, các khái niệm quan trọng, các bước / quy trình (nếu có).
        - Trình bày kết quả dưới dạng các gạch đầu dòng rõ ràng.
        - Nếu video mang tính hướng dẫn, hãy liệt kê các bước theo thứ tự.

        Văn bản:
        {text_to_summarize}
        """

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        st.error(f"Lỗi khi tóm tắt bằng Gemini: {e}")
        st.error("Gợi ý: Gemini API Key đã nhập đúng chưa?")
        return None


# ================== UI (GIAO DIỆN) ==================

st.set_page_config(layout="wide", page_title="Trình Tóm Tắt Video YouTube")
st.title("🚀 Trình Tóm Tắt Video YouTube")

st.markdown(
    """
Chào mừng! Ứng dụng này giúp bạn:

1. 🔍 Tìm kiếm video trên YouTube.  
2. 🎯 Chọn 1 video từ kết quả.  
3. 🧠 Đọc transcript (phụ đề) và tóm tắt nội dung chính bằng AI (Gemini).
"""
)

# ----- SIDEBAR -----
st.sidebar.header("🔑 API Keys (Bắt buộc)")
st.sidebar.markdown("Bạn cần cung cấp 2 API Key của riêng bạn để ứng dụng hoạt động.")

youtube_api_key = st.sidebar.text_input(
    "1. YouTube Data API Key",
    type="password"
)
st.sidebar.markdown(
    "[Cách lấy YouTube Key (từ Google Cloud)](https://developers.google.com/youtube/v3/getting-started)"
)

gemini_api_key = st.sidebar.text_input(
    "2. Gemini API Key",
    type="password"
)
st.sidebar.markdown(
    "[Cách lấy Gemini Key (từ Google AI Studio)](https://aistudio.google.com/app/apikey)"
)

st.sidebar.info(
    "Đừng lo, Key của bạn chỉ được dùng trong phiên truy cập này "
    "và **không được lưu lại**."
)

# ----- MAIN CONTENT -----

# 1. Tìm kiếm video
st.header("Bước 1: Tìm kiếm Video")
search_query = st.text_input(
    "Nhập từ khóa tìm kiếm (ví dụ: 'Streamlit tutorial'):",
    key="search_query"
)

if st.button("Tìm kiếm", key="search_button"):
    # Xoá tóm tắt cũ (nếu có)
    if "summary" in st.session_state:
        del st.session_state["summary"]

    if not youtube_api_key:
        st.error("Vui lòng nhập YouTube API Key ở thanh bên.")
    elif not search_query:
        st.error("Vui lòng nhập từ khóa tìm kiếm.")
    else:
        with st.spinner("Đang tìm video trên YouTube..."):
            videos = search_youtube(youtube_api_key, search_query, max_results=3)

        if videos:
            st.session_state["search_results"] = videos
            st.success(f"Đã tìm thấy {len(videos)} video.")
        else:
            # Nếu search_youtube trả về None thì lỗi đã được báo ở trong hàm
            if "search_results" in st.session_state:
                del st.session_state["search_results"]

# 2. Hiển thị kết quả tìm kiếm
if "search_results" in st.session_state:
    st.markdown("---")
    st.header("Bước 2: Chọn Video để Tóm tắt")

    videos = st.session_state["search_results"]

    for video in videos:
        st.markdown(f"**{video['title']}**  \n(Kênh: *{video['channel']}*)")
        if st.button(f"📝 Tóm tắt video này", key=f"btn_{video['id']}"):
            st.session_state["video_to_summarize"] = video
            if "summary" in st.session_state:
                del st.session_state["summary"]

# 3. Tóm tắt video đã chọn
if "video_to_summarize" in st.session_state:
    if not gemini_api_key:
        st.error("Vui lòng nhập Gemini API Key ở thanh bên để tóm tắt.")
    else:
        video = st.session_state["video_to_summarize"]
        video_id = video["id"]

        st.markdown("---")
        st.header(f"Bước 3: Bản Tóm Tắt (Video: {video['title']})")

        with st.spinner("Đang lấy transcript (phụ đề) từ YouTube..."):
            transcript = get_transcript(video_id)

        if transcript:
            st.success("Đã lấy được transcript!")
            with st.spinner("AI (Gemini) đang tóm tắt nội dung..."):
                summary = summarize_text(gemini_api_key, transcript)
                if summary:
                    st.session_state["summary"] = summary
                    # Xoá video đã chọn để tránh tóm tắt lại khi refresh
                    del st.session_state["video_to_summarize"]

# 4. Hiển thị kết quả tóm tắt
if "summary" in st.session_state:
    st.markdown("---")
    st.subheader("✅ Kết Quả Tóm Tắt")
    st.markdown(st.session_state["summary"])
