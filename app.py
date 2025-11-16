import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound
import google.generativeai as genai

# --- Cấu hình chung ---
MAX_TRANSCRIPT_CHARS = 12000  # cắt bớt transcript nếu quá dài


# --- Chức năng (Functions) ---

@st.cache_resource(show_spinner=False)
def get_youtube_service(api_key: str):
    """Tạo YouTube service và cache theo API key."""
    return build('youtube', 'v3', developerKey=api_key)


def _search_youtube(api_key, query, max_results=5):
    """Tìm kiếm video trên YouTube (hàm nội bộ, không cache)."""
    try:
        youtube = get_youtube_service(api_key)

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
            videos.append({'id': video_id, 'title': title, 'channel': channel})
        return videos

    except HttpError as e:
        if e.resp.status == 429:
            st.error("LỖI 429: Máy chủ đang bị YouTube giới hạn tạm thời "
                     "(quá nhiều request từ IP Streamlit Cloud). "
                     "Hãy thử lại sau vài phút, hoặc dùng API Key khác / deploy ở nơi khác.")
        else:
            st.error(f"Lỗi khi gọi YouTube API: {e}")
        return None
    except Exception as e:
        st.error(f"Lỗi khi tìm kiếm YouTube: {e}")
        st.error("Gợi ý: API Key của YouTube đã chính xác chưa? "
                 "Bạn đã bật 'YouTube Data API v3' trong Google Cloud Console chưa?")
        return None


@st.cache_data(show_spinner=False, ttl=60 * 60)
def search_youtube(api_key, query, max_results=3):
    """Tìm kiếm video và cache kết quả 1 tiếng theo (api_key, query, max_results)."""
    return _search_youtube(api_key, query, max_results)


def _get_transcript(video_id: str):
    """Lấy transcript (phụ đề) của video (hàm nội bộ, không cache)."""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(
            video_id,
            languages=['vi', 'en']
        )
        transcript = " ".join([item['text'] for item in transcript_list])
        return transcript
    except NoTranscriptFound:
        st.warning(f"Video (ID: {video_id}) không có phụ đề (transcript). Không thể tóm tắt.")
        return None
    except Exception as e:
        # Ở đây thư viện transcript không dùng HttpError, nên chỉ báo chung
        st.error(f"Lỗi khi lấy transcript: {e}")
        return None


@st.cache_data(show_spinner=False, ttl=24 * 60 * 60)
def get_transcript(video_id: str):
    """Lấy transcript và cache theo video_id trong 1 ngày."""
    return _get_transcript(video_id)


def summarize_text(api_key, text_to_summarize):
    """Tóm tắt văn bản bằng Gemini."""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        # Cắt transcript nếu quá dài
        if len(text_to_summarize) > MAX_TRANSCRIPT_CHARS:
            text_to_summarize = text_to_summarize[:MAX_TRANSCRIPT_CHARS]

        prompt = f"""Hãy tóm tắt văn bản sau đây (transcript của một video) một cách súc tích.
        Tập trung vào các ý chính, các bước hướng dẫn, hoặc các kết luận quan trọng.
        Trình bày dưới dạng các gạch đầu dòng.

        Văn bản:
        {text_to_summarize}
        """

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Lỗi khi tóm tắt (Gemini): {e}")
        st.error("Gợi ý: API Key của Gemini đã chính xác chưa?")
        return None


# --- Giao diện (UI) ---

st.set_page_config(layout="wide", page_title="Trình Tóm Tắt YouTube")
st.title("🚀 Trình Tóm Tắt Video YouTube")

st.markdown("""
Chào mừng! Ứng dụng này giúp bạn:
1.  Tìm kiếm video trên YouTube.
2.  Chọn 1 video từ kết quả.
3.  Đọc transcript (phụ đề) và tóm tắt nội dung chính bằng AI (Gemini).
""")

# --- Sidebar (Thanh bên) để nhập Keys ---
st.sidebar.header("🔑 API Keys (Bắt buộc)")
st.sidebar.markdown("Bạn cần cung cấp 2 API Key của riêng bạn để ứng dụng hoạt động.")

youtube_api_key = st.sidebar.text_input("1. YouTube Data API Key", type="password")
st.sidebar.markdown("[Cách lấy YouTube Key (từ Google Cloud)](https://developers.google.com/youtube/v3/getting-started)")

gemini_api_key = st.sidebar.text_input("2. Gemini API Key", type="password")
st.sidebar.markdown("[Cách lấy Gemini Key (từ Google AI Studio)](https://aistudio.google.com/app/apikey)")

st.sidebar.info("Đừng lo, Key của bạn chỉ được dùng trong phiên truy cập này và không được lưu lại.")

# --- Nội dung chính (Main Content) ---

# 1. Khu vực Tìm kiếm
st.header("Bước 1: Tìm kiếm Video")
search_query = st.text_input("Nhập từ khóa tìm kiếm (ví dụ: 'Streamlit tutorial'):", key="search_query")

if st.button("Tìm kiếm", key="search_button"):
    # Xóa kết quả tóm tắt cũ (nếu có)
    if 'summary' in st.session_state:
        del st.session_state['summary']

    if not youtube_api_key:
        st.error("Vui lòng nhập YouTube API Key ở thanh bên.")
    elif not search_query:
        st.error("Vui lòng nhập từ khóa tìm kiếm.")
    else:
        with st.spinner("Đang tìm video, vui lòng đợi..."):
            videos = search_youtube(youtube_api_key, search_query, max_results=3)
            if videos:
                st.session_state['search_results'] = videos
                st.success(f"Đã tìm thấy {len(videos)} video!")
            else:
                st.error("Không tìm thấy video nào hoặc có lỗi xảy ra khi tìm kiếm.")

# 2. Hiển thị Kết quả tìm kiếm
if 'search_results' in st.session_state:
    st.markdown("---")
    st.header("Bước 2: Chọn Video để Tóm tắt")

    videos = st.session_state['search_results']

    for i, video in enumerate(videos):
        st.markdown(f"**{video['title']}** (Kênh: *{video['channel']}*)")
        if st.button(f"Tóm tắt Video này", key=f"btn_{video['id']}"):
            st.session_state['video_to_summarize'] = video
            if 'summary' in st.session_state:
                del st.session_state['summary']

# 3. Xử lý và Hiển thị Tóm tắt
if 'video_to_summarize' in st.session_state:
    if not gemini_api_key:
        st.error("Vui lòng nhập Gemini API Key ở thanh bên để tóm tắt.")
    else:
        video = st.session_state['video_to_summarize']
        video_id = video['id']

        st.markdown("---")
        st.header(f"Bước 3: Bản Tóm Tắt (Video: {video['title']})")

        with st.spinner("Đang lấy transcript (phụ đề) của video..."):
            transcript = get_transcript(video_id)

        if transcript:
            st.success("Đã lấy được transcript!")
            with st.spinner("AI (Gemini) đang tóm tắt nội dung..."):
                summary = summarize_text(gemini_api_key, transcript)
                if summary:
                    st.session_state['summary'] = summary
                    del st.session_state['video_to_summarize']

# Hiển thị tóm tắt (nếu đã tóm tắt xong)
if 'summary' in st.session_state:
    st.markdown("---")
    st.subheader("✅ Kết Quả Tóm Tắt")
    st.markdown(st.session_state['summary'])
