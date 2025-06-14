import streamlit as st
from google.cloud import vision
from google.oauth2 import service_account
from PIL import Image
import io
import requests
import xml.etree.ElementTree as ET
import openai  # 향후 확장 가능

st.title("💊 약사봇: 사진 한 장으로 약 정보 확인")

# 1. 이미지 업로드
uploaded_file = st.file_uploader("약 포장지나 설명서 사진을 올려주세요", type=["png", "jpg", "jpeg"])
if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="업로드된 이미지", use_column_width=True)

    # 2. Google Vision API 인증 및 텍스트 추출
    google_creds = dict(st.secrets["google_cloud"])
    google_creds["private_key"] = google_creds["private_key"].replace("\\\\n", "\n")  # 줄바꿈 복원
    credentials = service_account.Credentials.from_service_account_info(google_creds)
    client = vision.ImageAnnotatorClient(credentials=credentials)

    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    vision_image = vision.Image(content=buffered.getvalue())
    response = client.text_detection(image=vision_image)
    texts = response.text_annotations

    if texts:
        raw_text = texts[0].description
        st.subheader("📄 인식된 텍스트:")
        st.text(raw_text)

        # 3. 약 이름 추출 (단순화된 첫 줄)
        keyword = raw_text.split("\n")[0]
        st.info(f"🔍 약 이름 추정: {keyword}")

        # 4. 'e약은요' API 호출
        api_key = st.secrets["drug_api"]["service_key"]
        url = "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"
        params = {
            "serviceKey": api_key,
            "itemName": keyword,
            "type": "xml",
            "numOfRows": "1"
        }

        response = requests.get(url, params=params)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            item = root.find(".//item")
            if item is not None:
                entpName = item.findtext("entpName")
                efcyQesitm = item.findtext("efcyQesitm")
                useMethodQesitm = item.findtext("useMethodQesitm")
                atpnQesitm = item.findtext("atpnQesitm")

                st.markdown(f"**제약사:** {entpName}")
                st.markdown(f"**효능/효과:** {efcyQesitm}")
                st.markdown(f"**복용 방법:** {useMethodQesitm}")
                st.markdown(f"**주의 사항:** {atpnQesitm}")
            else:
                st.warning("해당 이름으로 등록된 의약품 정보를 찾을 수 없습니다.")
        else:
            st.error("의약품 정보를 불러오지 못했습니다. API 호출 오류.")
    else:
        st.warning("❌ 텍스트를 인식하지 못했습니다.")
