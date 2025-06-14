import streamlit as st
from google.cloud import vision
from google.oauth2 import service_account
from PIL import Image
import io
import requests
import xml.etree.ElementTree as ET
import openai

# 인증 설정
google_creds = dict(st.secrets["google_cloud"])
google_creds["private_key"] = google_creds["private_key"].replace("\\\\n", "\n")
credentials = service_account.Credentials.from_service_account_info(google_creds)
vision_client = vision.ImageAnnotatorClient(credentials=credentials)

openai.api_key = st.secrets["openai"]["api_key"]
drug_api_key = st.secrets["drug_api"]["service_key"]

# 제목
st.title("💊 약사봇 - 복약 안전 도우미")

# 다중 이미지 업로드
uploaded_files = st.file_uploader("💡 복용 중인 약의 사진을 모두 업로드해주세요", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

drug_infos = []
drug_names = []

if uploaded_files:
    for uploaded_file in uploaded_files:
        st.image(uploaded_file, caption=f"업로드: {uploaded_file.name}", use_column_width=True)

        # Vision API: 텍스트 추출
        image = Image.open(uploaded_file)
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        vision_image = vision.Image(content=buffered.getvalue())
        response = vision_client.text_detection(image=vision_image)
        texts = response.text_annotations

        if not texts:
            st.warning(f"❌ 텍스트를 인식하지 못했습니다: {uploaded_file.name}")
            continue

        extracted_text = texts[0].description.strip()
        keyword = extracted_text.split("\n")[0]
        drug_names.append(keyword)
        st.markdown(f"🔍 **추정 약 이름:** `{keyword}`")

        # 식약처 API 요청
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

                st.success(f"✅ `{keyword}` 정보 수집 완료")
                st.markdown(f"**효능:** {efcy}")
                st.markdown(f"**복용법:** {useMethod}")
                st.markdown(f"**주의사항:** {atpn}")
            else:
                st.warning(f"📭 `{keyword}` 에 대한 의약품 정보를 찾을 수 없습니다.")
        else:
            st.error("🚫 식약처 API 호출 실패")

# GPT를 통한 상호작용 위험 분석
if len(drug_infos) >= 2:
    st.subheader("🤖 GPT 분석: 복합 복용 주의사항")

    all_ingredients = "\n".join(
        [f"- {drug['name']} ({drug['ingredient'] or '성분 정보 없음'})" for drug in drug_infos]
    )

    prompt = f"""
다음은 한 사용자가 복용 중인 약 리스트입니다. 각각의 약 성분을 고려할 때, 같이 복용할 경우 주의해야 할 상호작용이나 부작용 가능성을 알려주세요.  
간단한 용어로 설명해주세요.

{all_ingredients}
    """

    with st.spinner("GPT가 약 성분을 분석 중입니다..."):
        completion = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "너는 약학 지식을 가진 복약 도우미야."},
                {"role": "user", "content": prompt}
            ]
        )
        result = completion.choices[0].message.content.strip()
        st.markdown("🧠 **GPT 분석 결과:**")
        st.info(result)
