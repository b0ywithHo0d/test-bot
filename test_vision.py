import streamlit as st
from google.cloud import vision
from google.oauth2 import service_account
from PIL import Image
import io
import requests
import xml.etree.ElementTree as ET
from openai import OpenAI

# API 키 설정
google_creds = dict(st.secrets["google_cloud"])
google_creds["private_key"] = google_creds["private_key"].replace("\\\\n", "\n")
credentials = service_account.Credentials.from_service_account_info(google_creds)
vision_client = vision.ImageAnnotatorClient(credentials=credentials)

openai_client = OpenAI(api_key=st.secrets["openai"]["api_key"])
drug_api_key = st.secrets["drug_api"]["service_key"]

st.title("💊 약사봇 - 사진 기반 복약 위험 분석기")

uploaded_files = st.file_uploader(
    "📷 복용 중인 약 사진 여러 장을 업로드하세요", 
    type=["png", "jpg", "jpeg"], 
    accept_multiple_files=True
)

drug_infos = []
extracted_ingredients_all = []  # 전체 성분 누적 리스트
ocr_texts_per_image = []       # 각 사진별 원문 텍스트 저장

if uploaded_files:
    for uploaded_file in uploaded_files:
        st.image(uploaded_file, caption=uploaded_file.name, use_column_width=True)

        # 구글 비전 텍스트 추출
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
        ocr_texts_per_image.append((uploaded_file.name, extracted_text))

        # 사용자에게 원문 텍스트 보여주기
        with st.expander(f"📝 `{uploaded_file.name}`에서 추출된 텍스트 보기"):
            st.text(extracted_text)

        keyword = extracted_text.split("\n")[0]  # 첫 줄: 약 이름 추정
        st.markdown(f"🔍 **인식된 약 이름(추정):** `{keyword}`")

        # 식약처 API 조회
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
                ingr_raw = item.findtext("mainIngr") or ""

                ingr_list = [ingr.strip() for ingr in ingr_raw.replace('/', ',').split(',') if ingr.strip()]

                drug_infos.append({
                    "name": keyword,
                    "entp": entpName,
                    "effect": efcy,
                    "usage": useMethod,
                    "warning": atpn,
                    "ingredients": ingr_list
                })

                extracted_ingredients_all.extend(ingr_list)

                st.success(f"✅ `{keyword}` 정보 수집 완료")
                st.markdown(f"**효능:** {efcy}")
                st.markdown(f"**복용법:** {useMethod}")
                st.markdown(f"**주의사항:** {atpn}")
                st.markdown(f"**주요 성분:** {', '.join(ingr_list)}")
            else:
                st.warning(f"📭 `{keyword}` 관련 의약품 정보 없음 → 텍스트 기반 GPT 분석 예정")
                extracted_ingredients_all.append(keyword)
        else:
            st.error("🚫 식약처 API 호출 실패")

# 중복 제거
extracted_ingredients_all = list(set(extracted_ingredients_all))

# GPT 분석
if len(extracted_ingredients_all) >= 2:
    st.subheader("🤖 GPT 분석: 복합 복용 주의사항")

    # OCR 텍스트와 성분 정보를 GPT 프롬프트에 같이 넣기
    ocr_text_summary = "\n\n".join(
        [f"사진 파일명: {name}\n추출 텍스트:\n{txt}" for name, txt in ocr_texts_per_image]
    )

    ingredient_list_text = "\n".join([f"- {i}" for i in extracted_ingredients_all])

    prompt = f"""
사용자가 다음 사진들에서 추출된 텍스트와 해당 약 성분 목록을 바탕으로 여러 약을 함께 복용하고 있습니다.
복용 시 약들 간의 상호작용, 부작용, 주의사항 등을 약사 시점에서 간단명료하게 안내해주세요.

=== 사진별 OCR 텍스트 ===
{ocr_text_summary}

=== 약 성분 목록 ===
{ingredient_list_text}
"""

    with st.spinner("GPT가 분석 중입니다..."):
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "너는 약학 지식을 갖춘 복약 도우미야."},
                {"role": "user", "content": prompt}
            ]
        )
        st.write(response)
        result = response.choices[0].message.content.strip()
        st.markdown("🧠 **GPT 분석 결과:**")
        st.info(result)
