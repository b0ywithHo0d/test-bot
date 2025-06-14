# streamlit_ocr_app.py
import streamlit as st
from google.cloud import vision
from google.oauth2 import service_account
from PIL import Image
import io

st.title("🧾 이미지에서 텍스트 추출 (Google Vision API)")

# 이미지 업로드
uploaded_file = st.file_uploader("이미지를 업로드하세요", type=["png", "jpg", "jpeg"])
if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="업로드된 이미지", use_column_width=True)

    # Google Cloud Vision API 인증 (secrets 사용)
    google_creds = dict(st.secrets["google_cloud"])
    google_creds["private_key"] = google_creds["private_key"].replace("\\\\n", "\n")
    credentials = service_account.Credentials.from_service_account_info(google_creds)
    client = vision.ImageAnnotatorClient(credentials=credentials)

    # 이미지 읽기
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    content = buffered.getvalue()
    vision_image = vision.Image(content=content)

    # 텍스트 감지 요청
    response = client.text_detection(image=vision_image)
    texts = response.text_annotations

    if texts:
        st.subheader("✅ 인식된 텍스트:")
        st.text(texts[0].description)
    else:
        st.warning("❌ 텍스트를 인식하지 못했습니다.")
