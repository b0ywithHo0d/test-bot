import streamlit as st
import openai
import base64
import requests
import json
from PIL import Image
from io import BytesIO

# ✅ API 키 설정
openai.api_key = st.secrets["openai_api_key"]["openai_api_key"]
drug_api_key = st.secrets["service_key"]["drug_api_key"]

# ✅ Streamlit UI
st.title("💊 약 사진 분석 & 성분 상호작용 체크봇")

uploaded_images = st.file_uploader("📷 약 사진을 하나 이상 업로드하세요", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

if uploaded_images:
    extracted_ingredients = []

    for idx, img_file in enumerate(uploaded_images):
        st.image(img_file, caption=f"약 이미지 {idx + 1}", use_column_width=True)

        # OpenAI Vision API 호출
        base64_image = base64.b64encode(img_file.getvalue()).decode("utf-8")
        vision_response = openai.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "이 약의 주성분을 텍스트로 추출해줘."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                    ],
                }
            ],
            max_tokens=300
        )

        extracted_text = vision_response.choices[0].message.content.strip()
        extracted_ingredients.append((f"약 {idx + 1}", extracted_text))
        st.markdown(f"🧾 **약 {idx + 1} 성분 추출:**\n```\n{extracted_text}\n```")

    # ✅ 의약품 API 정보 확인
    st.markdown("---")
    st.subheader("📡 e약은요 API로 성분 정보 조회")

    for name, text in extracted_ingredients:
        st.markdown(f"🔍 **{name}**")
        query = text.split("\n")[0]  # 가장 대표되는 줄만 사용 (보통 성분 이름일 확률 높음)
        url = f"https://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"
        params = {
            "serviceKey": drug_api_key,
            "itemName": query,
            "type": "json",
            "pageNo": 1,
            "numOfRows": 1
        }
        try:
            res = requests.get(url, params=params, timeout=5)
            data = res.json()
            if "body" in data["response"] and "items" in data["response"]["body"]:
                item = data["response"]["body"]["items"][0]
                st.markdown(f"💡 **{item['itemName']}**")
                st.markdown(f"- **효능/효과:** {item.get('efcyQesitm', '정보 없음')}")
                st.markdown(f"- **주의사항:** {item.get('atpnQesitm', '정보 없음')}")
            else:
                st.warning(f"'{query}'에 대한 정보를 찾을 수 없습니다. GPT가 분석한 성분 정보를 기반으로 대체 분석합니다.")
        except Exception as e:
            st.error(f"API 오류 발생: {e}")

    # ✅ GPT를 통한 성분 상호작용 분석
    st.markdown("---")
    st.subheader("🧠 GPT 상호작용 분석")

    full_ingredient_summary = "\n".join([f"{name} 성분: {text}" for name, text in extracted_ingredients])

    analysis_prompt = f"""
다음은 여러 약의 주요 성분 목록입니다. 이 약들을 함께 복용할 때 성분 간 상호작용으로 발생할 수 있는 위험 요소나 주의사항을 알려주세요. 의학적으로 신뢰할 수 있는 일반적인 수준의 조언이면 좋겠습니다. 단순히 겹치는 성분, 과다복용 가능성, 금기 조합 등을 중점으로 알려줘.
"""

    interaction_response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "너는 약학 전문가로, 약 성분의 상호작용에 대해 조언해주는 역할이야."},
            {"role": "user", "content": analysis_prompt}
        ],
        temperature=0.7,
        max_tokens=700
    )

    st.markdown("🧪 **GPT 분석 결과:**")
    st.info(interaction_response.choices[0].message.content.strip())



