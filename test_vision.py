import streamlit as st
from google.cloud import vision
from google.oauth2 import service_account
from PIL import Image
import io
import requests
import xml.etree.ElementTree as ET
from openai import OpenAI

# ✅ API 키 설정
google_creds = dict(st.secrets["google_cloud"])
google_creds["private_key"] = google_creds["private_key"].replace("\\\\n", "\n")
credentials = service_account.Credentials.from_service_account_info(google_creds)
vision_client = vision.ImageAnnotatorClient(credentials=credentials)

openai_client = OpenAI(api_key=st.secrets["openai"]["api_key"])
drug_api_key = st.secrets["drug_api"]["service_key"]

# ✅ Streamlit 제목
st.title("💊 약사봇 - 사진 기반 복약 위험 분석기")

uploaded_files = st.file_uploader(
    "📷 복용 중인 약 사진 여러 장을 업로드하세요", 
    type=["png", "jpg", "jpeg"], 
    accept_multiple_files=True
)

drug_infos = []
extracted_ingredients = []  # 성분 추출 리스트

if uploaded_files:
    for uploaded_file in uploaded_files:
        st.image(uploaded_file, caption=uploaded_file.name, use_column_width=True)

        # ✅ Google Vision API로 텍스트 추출
        image = Image.open(uploaded_file)
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        vision_image = vision.Image(content=buffered.getvalue())
        response = vision_client.text_detection(image=vision_image)
        texts = response.text_annotations

        if not texts:
            st.warning(f"❌ 텍스트 인식 실패: {uploaded_file.name}")
            continue

        extracted_text = texts[0].description.strip()
        keyword = extracted_text.split("\n")[0]  # 첫 줄 → 약 이름 추정
        st.markdown(f"🔍 **인식된 약 이름(추정):** `{keyword}`")

        # ✅ 식약처 API 조회
        url = "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"
        params = {
            "serviceKey": drug_api_key,
            "itemName": keyword,
            "type": "xml",
            "numOfRows": "1"
        }

        res = requests.get(url, params=params)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            item = root.find(".//item")
            if item is not None:
                entpName = item.findtext("entpName")
                efcy = item.findtext("efcyQesitm")
                useMethod = item.findtext("useMethodQesitm")
                atpn = item.findtext("atpnQesitm")
                ingr = item.findtext("mainIngr") or ""

                drug_infos.append({
                    "name": keyword,
                    "entp": entpName,
                    "effect": efcy,
                    "usage": useMethod,
                    "warning": atpn,
                    "ingredient": ingr
                })

                extracted_ingredients.append(ingr)
                st.success(f"✅ `{keyword}` 정보 수집 완료")
                st.markdown(f"**효능:** {efcy}")
                st.markdown(f"**복용법:** {useMethod}")
                st.markdown(f"**주의사항:** {atpn}")
            else:
                st.warning(f"📭 `{keyword}` 관련 의약품 정보 없음 → 텍스트 내용 기반 GPT 분석 예정")
                extracted_ingredients.append(keyword)
        else:
            st.error("🚫 식약처 API 호출 실패")

# ✅ GPT 분석
if len(extracted_ingredients) >= 2:
    st.subheader("🤖 GPT 분석: 복합 복용 주의사항")

    ingredient_list = "\n".join([f"- {i}" for i in extracted_ingredients])
    prompt = f"""
한 사용자가 다음 성분 또는 약 이름들이 포함된 약을 함께 복용 중입니다.
이 약들 간의 상호작용, 부작용 가능성, 주의사항 등을 복약 전문가의 시각에서 간단히 안내해주세요.

성분 또는 약 목록:
{ingredient_list}
"""

    with st.spinner("GPT가 분석 중입니다..."):
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "너는 약학 지식을 갖춘 복약 도우미야."},
                {"role": "user", "content": prompt}
            ]
        )
        result = response.choices[0].message.content.strip()
        st.markdown("🧠 **GPT 분석 결과:**")
        st.info(result)
