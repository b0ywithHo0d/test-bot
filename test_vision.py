from google.cloud import vision
from google.oauth2 import service_account

def test_vision_api(key_path="gcp_key.json"):
    try:
        # 인증 정보 로드
        credentials = service_account.Credentials.from_service_account_file(key_path)
        client = vision.ImageAnnotatorClient(credentials=credentials)

        # 테스트용 이미지 URL (아래 이미지에는 "Hello"라는 텍스트가 있음)
        image_uri = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Hello_world_in_various_languages.svg/1024px-Hello_world_in_various_languages.svg.png"
        image = vision.Image()
        image.source.image_uri = image_uri

        # 텍스트 감지 요청
        response = client.text_detection(image=image)

        if response.error.message:
            print("API 호출 에러:", response.error.message)
            return False

        texts = response.text_annotations
        if not texts:
            print("텍스트가 감지되지 않았습니다.")
            return False

        print("검출된 텍스트 중 첫번째(전체 텍스트):")
        print(texts[0].description)
        return True

    except Exception as e:
        print("Vision API 테스트 중 예외 발생:", e)
        return False


if __name__ == "__main__":
    success = test_vision_api()
    if success:
        print("Google Vision API 테스트 성공!")
    else:
        print("Google Vision API 테스트 실패!")
