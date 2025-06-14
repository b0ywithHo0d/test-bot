import streamlit as st
from google.cloud import vision
from google.oauth2 import service_account
from PIL import Image
import io
import requests
import openai

# --- Streamlit 기본 설정 ---
st.set_page_config(page_title="약사봇", layout="wide")
st.title("💊 약사봇: 약 성분 분석 및 복용 주의 안내")

# --- 구글 Vision API 인증 ---
google_creds = dict(st.secrets["google_cloud"])
google_creds["private_key"] = google_creds["private_key"].replace("\\n", "\n")
credentials = service_account.Credentials.from_service_account_info(google_creds)
vision_client = vision.ImageAnnotatorClient(credentials=credentials)

# --- OpenAI API 키 설정 ---
openai.api_key = st.secrets["openai_api_key"]
openai_client = openai

# --- 의약품 API 설정 ---
DRUG_API_KEY = st.secrets["drug_api_key"]
DRUG_API_URL = "https://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"

# --- 약 사진 업로드 ---
uploaded_files = st.file_uploader("약 사진을 하나 이상 업로드하세요", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

# --- 정보 저장 리스트 ---
ingredient_infos = []  # (약 이름, 성분)

if uploaded_files:
    for idx, uploaded_file in enumerate(uploaded_files):
        st.markdown(f"### 📸 {idx + 1}번 약 사진")
        image = Image.open(uploaded_file)
        st.image(image, caption=f"{idx + 1}번 이미지", use_column_width=True)

        # Vision API 이미지 처리
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        content = buffered.getvalue()
        vision_image = vision.Image(content=content)
        response = vision_client.text_detection(image=vision_image)
        texts = response.text_annotations

        if texts:
            extracted_text = texts[0].description.replace('\n', ' ')
            st.text_area("📝 인식된 텍스트:", extracted_text, height=100)

            # 검색 키워드 추출 (간단하게 첫 5단어 중 길이가 긴 단어 사용)
            keyword = "".join([w for w in extracted_text.split() if len(w) > 3][:1])

            # 의약품 API 호출
            params = {
                "serviceKey": DRUG_API_KEY,
                "itemName": keyword,
                "type": "json",
                "numOfRows": 1,
                "pageNo": 1
            }
            api_response = requests.get(DRUG_API_URL, params=params)

            ingr = None
            if api_response.status_code == 200:
                try:
                    item = api_response.json()['body']['items'][0]
                    ingr = item.get("efcyQesitm", None)
                    st.success("✅ 의약품 정보 조회 성공")
                    st.write("**효능 및 성분 요약:**")
                    st.write(ingr)
                except:
                    st.warning("⚠️ 의약품 API에서 정보를 찾을 수 없습니다. GPT가 판단합니다.")
            else:
                st.error("❌ API 요청 실패")

            ingredient_infos.append((keyword, ingr or extracted_text))

        else:
            st.warning("❌ 텍스트를 인식하지 못했습니다.")

    # --- GPT 분석 ---
    if len(ingredient_infos) >= 2:
        st.markdown("---")
        st.subheader("🤖 GPT 분석: 복합 복용 주의사항")

        structured_list = "\n".join([
            f"{idx+1}번 약: {name}\n  - 성분: {ingredient}"
            for idx, (name, ingredient) in enumerate(ingredient_infos)
        ])

        prompt = f"""
사용자가 아래의 약들을 함께 복용 중입니다.
각 약의 이름과 주요 성분은 다음과 같습니다:

{structured_list}

이 약들을 함께 복용할 때 주의해야 할 점, 부작용 가능성, 성분 간 상호작용을 복약 전문가로서 정리해 주세요.
과학적이되, 일반인이 이해할 수 있는 말로 설명해 주세요.
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

else:
    st.info("📤 하나 이상의 약 사진을 업로드해주세요.")
