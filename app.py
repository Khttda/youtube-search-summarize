import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google import genai

# ================== FUNCTIONS ==================


@st.cache_data(show_spinner=False, ttl=60 * 60)
def search_youtube(api_key: str, query: str, max_results: int = 3):
    """
    Tìm kiếm video trên YouTube bằng YouTube Data API v3.
    Kết quả được cache 1 tiếng để giảm số lần gọi API.
    """
    try:
        youtube = build("youtube", "v3", developerKey=api_key)

        request = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            maxResults=max_results,
        )
        response = request.execute()

        videos = []
        for item in response.get("items", []):
            video_id = item["id"]["videoId"]
            title = item["snippet"]["title"]
            channel = item["snippet"]["channelTitle"]
            videos.append(
                {
                    "id": video_id,
                    "title": title,
                    "channel": channel,
                }
            )
        return videos

    except HttpError as e:
        if e.resp.status == 403:
            st.error(
                "Lỗi 403 từ YouTube Data API (có thể do hết quota hoặc cấu hình API Key).\n"
                "Vào Google Cloud Console kiểm tra lại hạn mức và xem đã bật "
                "'YouTube Data API v3' chưa."
            )
        else:
            st.error(f"Lỗi khi gọi YouTube Data API: {e}")
        return None
    except Exception as e:
        st.error(f"Lỗi khi tìm kiếm YouTube: {e}")
        st.error(
            "Gợi ý: kiểm tra lại YouTube API Key, Project, và việc bật "
            "'YouTube Data API v3' trong Google Cloud."
        )
        return None


def summarize_youtube_video(gemini_api_key: str, youtube_url: str):
    """
    Gọi Gemini để tóm tắt trực tiếp video YouTube qua URL.
    Không cần tự lấy transcript, không dùng youtube-transcript-api.
    """
    try:
        client = genai.Client(api_key=gemini_api_key)

        # Theo ví dụ chính thức: truyền file_data.file_uri là YouTube URL :contentReference[oaicite:1]{index=1}
        response = client.models.generate_content(
            model="gemini-2.0-flash",  # có thể đổi sang model khác nếu bạn muốn
            contents=[
                {
                    "parts": [
                        {
                            "text": (
                                "Hãy tóm tắt video này bằng TIẾNG VIỆT, "
                                "trình bày dạng các gạch đầu dòng, "
                                "tập trung vào kiến thức/ý chính và các bước hành động (nếu có)."
                            )
                        },
                        {
                            "file_data": {
                                "file_uri": youtube_url
                            }
                        },
                    ]
                }
            ],
        )

        # SDK sẽ tự ghép các phần text của response lại
        return getattr(response, "text", None)

    except Exception as e:
        st.error(f"Lỗi khi tóm tắt video với Gemini: {e}")
        st.error(
            "Kiểm tra lại Gemini API Key (từ Google AI Studio) "
            "và đảm bảo key còn hạn mức sử dụng, "
            "model tên 'gemini-2.0-flash' khả dụng."
        )
        return None


# ================== UI (GIAO DIỆN) ==================

st.set_page_config(layout="wide", page_title="Trình Tóm Tắt Video YouTube")
st.title("🚀 Trình Tóm Tắt Video YouTube")

st.markdown(
    """
Ứng dụng này giúp bạn:

1. 🔍 Tìm kiếm video trên YouTube bằng từ khóa.  
2. 🎯 Chọn 1 video từ kết quả.  
3. 🧠 Để Gemini tự đọc video YouTube và tóm tắt nội dung chính bằng tiếng Việt.

YouTube API Key chỉ dùng cho **tìm kiếm video**.  
Gemini API Key dùng để **tóm tắt nội dung video**.
"""
)

# ----- SIDEBAR: API KEYS -----

st.sidebar.header("🔑 API Keys")
st.sidebar.markdown("Bạn nên cung cấp cả 2 API Key để dùng đủ tính năng.")

youtube_api_key = st.sidebar.text_input(
    "1. YouTube Data API Key (dùng để TÌM KIẾM)",
    type="password",
)
st.sidebar.markdown(
    "[Cách lấy YouTube Key (Google Cloud)](https://developers.google.com/youtube/v3/getting-started)"
)

gemini_api_key = st.sidebar.text_input(
    "2. Gemini API Key (dùng để TÓM TẮT)",
    type="password",
)
st.sidebar.markdown(
    "[Cách lấy Gemini Key (Google AI Studio)](https://aistudio.google.com/app/apikey)"
)

st.sidebar.info(
    "Key chỉ được dùng trong phiên làm việc hiện tại và **không được lưu lại**."
)

# ----- MAIN LAYOUT -----

# 1. Khu vực Tìm kiếm
st.header("Bước 1: Tìm kiếm Video trên YouTube")

col1, col2 = st.columns([3, 1])

with col1:
    search_query = st.text_input(
        "Nhập từ khóa (ví dụ: 'chu kỳ kinh tế', 'Streamlit tutorial')",
        key="search_query",
    )

with col2:
    max_results = st.number_input(
        "Số video tối đa",
        min_value=1,
        max_value=10,
        value=3,
        step=1,
        key="max_results",
    )

if st.button("🔍 Tìm kiếm", key="search_button"):
    # Xoá summary cũ nếu có
    st.session_state.pop("summary", None)

    if not youtube_api_key:
        st.error("Vui lòng nhập YouTube Data API Key ở thanh bên (mục 1).")
    elif not search_query:
        st.error("Vui lòng nhập từ khóa tìm kiếm.")
    else:
        with st.spinner("Đang tìm video trên YouTube..."):
            videos = search_youtube(
                youtube_api_key, search_query, max_results=int(max_results)
            )

        if videos:
            st.session_state["search_results"] = videos
            st.success(f"Đã tìm thấy {len(videos)} video.")
        else:
            st.session_state.pop("search_results", None)

# 2. Hiển thị kết quả và cho chọn video
if "search_results" in st.session_state:
    st.markdown("---")
    st.header("Bước 2: Chọn Video để Tóm tắt")

    videos = st.session_state["search_results"]

    for video in videos:
        st.markdown(
            f"**{video['title']}**  \n"
            f"(Kênh: *{video['channel']}*)"
        )
        if st.button("📝 Tóm tắt video này", key=f"btn_{video['id']}"):
            st.session_state["video_to_summarize"] = video
            st.session_state.pop("summary", None)

# 3. Tóm tắt video đã chọn
if "video_to_summarize" in st.session_state:
    if not gemini_api_key:
        st.error("Vui lòng nhập Gemini API Key ở thanh bên (mục 2) để tóm tắt.")
    else:
        video = st.session_state["video_to_summarize"]
        video_id = video["id"]
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"

        st.markdown("---")
        st.header(f"Bước 3: Tóm Tắt Video\n\n📺 {video['title']}")
        st.markdown(f"🔗 Link: {youtube_url}")

        with st.spinner("Gemini đang phân tích video và tóm tắt nội dung..."):
            summary = summarize_youtube_video(gemini_api_key, youtube_url)

        if summary:
            st.session_state["summary"] = summary
            # Không tự xoá video_to_summarize, để user có thể tóm tắt lại nếu muốn

# 4. Hiển thị kết quả tóm tắt
if "summary" in st.session_state:
    st.markdown("---")
    st.subheader("✅ Kết Quả Tóm Tắt")
    st.markdown(st.session_state["summary"])
