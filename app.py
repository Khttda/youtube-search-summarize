import streamlit as st
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound
import google.generativeai as genai

# --- Chức năng (Functions) ---

def search_youtube(api_key, query, max_results=5):
    """Tìm kiếm video trên YouTube."""
    try:
        # Xây dựng service YouTube
        youtube = build('youtube', 'v3', developerKey=api_key)
        
        # Tạo yêu cầu tìm kiếm
        request = youtube.search().list(
            part='snippet',
            q=query,
            type='video',
            maxResults=max_results
        )
        # Thực thi
        response = request.execute()
        
        # Xử lý kết quả
        videos = []
        for item in response['items']:
            video_id = item['id']['videoId']
            title = item['snippet']['title']
            channel = item['snippet']['channelTitle']
            videos.append({'id': video_id, 'title': title, 'channel': channel})
        return videos
    except Exception as e:
        st.error(f"Lỗi khi tìm kiếm YouTube: {e}")
        st.error("Gợi ý: API Key của YouTube đã chính xác chưa? Bạn đã bật 'YouTube Data API v3' trong Google Cloud Console chưa?")
        return None

def get_transcript(video_id):
    """Lấy transcript (phụ đề) của video."""
    try:
        # Thử lấy transcript tiếng Việt hoặc tiếng Anh
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['vi', 'en'])
        
        # Ghép các đoạn text lại
        transcript = " ".join([item['text'] for item in transcript_list])
        return transcript
    except NoTranscriptFound:
        st.warning(f"Video (ID: {video_id}) không có phụ đề (transcript). Không thể tóm tắt.")
        return None
    except Exception as e:
        st.error(f"Lỗi khi lấy transcript: {e}")
        return None

def summarize_text(api_key, text_to_summarize):
    """Tóm tắt văn bản bằng Gemini."""
    try:
        # Cấu hình Gemini API Key
        genai.configure(api_key=api_key)
        
        # Chọn model (flash nhanh và miễn phí)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Tạo prompt tóm tắt
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
# Đây là mô hình BYOK (Bring Your Own Key)
st.sidebar.header("🔑 API Keys (Bắt buộc)")
st.sidebar.markdown("""
Bạn cần cung cấp 2 API Key của riêng bạn để ứng dụng hoạt động.
""")

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
        
    # Kiểm tra Key trước khi tìm
    if not youtube_api_key:
        st.error("Vui lòng nhập YouTube API Key ở thanh bên.")
    elif not search_query:
        st.error("Vui lòng nhập từ khóa tìm kiếm.")
    else:
        # Gọi hàm tìm kiếm
        with st.spinner("Đang tìm video, vui lòng đợi..."):
            videos = search_youtube(youtube_api_key, search_query)
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
    
    # Hiển thị 5 nút. Khi nhấn 1 nút, nó sẽ xử lý tóm tắt
    for i, video in enumerate(videos):
        st.markdown(f"**{video['title']}** (Kênh: *{video['channel']}*)")
        
        # Khi nhấn nút này, ta sẽ lưu video_id vào session_state để xử lý
        if st.button(f"Tóm tắt Video này", key=f"btn_{video['id']}"):
            st.session_state['video_to_summarize'] = video
            # Xóa các tóm tắt cũ
            if 'summary' in st.session_state:
                del st.session_state['summary']

# 3. Xử lý và Hiển thị Tóm tắt
if 'video_to_summarize' in st.session_state:
    
    # Kiểm tra Gemini Key
    if not gemini_api_key:
        st.error("Vui lòng nhập Gemini API Key ở thanh bên để tóm tắt.")
    else:
        video = st.session_state['video_to_summarize']
        video_id = video['id']
        
        st.markdown("---")
        st.header(f"Bước 3: Bản Tóm Tắt (Video: {video['title']})")
        
        # Lấy transcript
        with st.spinner("Đang lấy transcript (phụ đề) của video..."):
            transcript = get_transcript(video_id)
        
        if transcript:
            st.success("Đã lấy được transcript!")
            
            # Tóm tắt
            with st.spinner("AI (Gemini) đang tóm tắt nội dung... (việc này có thể mất chút thời"
                           " gian)"):
                summary = summarize_text(gemini_api_key, transcript)
                if summary:
                    st.session_state['summary'] = summary
                    # Xóa video đã chọn để tránh tóm tắt lại khi trang refresh
                    del st.session_state['video_to_summarize']
        else:
            # Lỗi (không có transcript) đã được xử lý bên trong hàm get_transcript
            pass

# Hiển thị tóm tắt (nếu đã tóm tắt xong)
if 'summary' in st.session_state:
    st.markdown("---")
    st.subheader("✅ Kết Quả Tóm Tắt")
    st.markdown(st.session_state['summary'])