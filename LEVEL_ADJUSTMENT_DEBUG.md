# 레벨 조정 디버그 가이드 🐛

## 문제 확인

레벨 조정 기능이 작동하지 않을 때 다음 사항을 확인하세요.

## ✅ 구현 상태

레벨 조정 기능은 **완전히 구현**되어 있습니다:

### 1. 백엔드 (Python)
- **shape_detector.py**
  - `apply_levels()`: 111-141번째 줄
  - `set_levels()`: 143-164번째 줄
  - `detect()` 함수에서 호출: 266번째 줄

- **app.py**
  - `handle_set_levels()`: 229-267번째 줄

### 2. 프론트엔드 (JavaScript)
- **main.js**
  - `sendLevels()`: 160-171번째 줄
  - `setupLevelSlider()`: 122-136번째 줄

- **socket-handler.js**
  - `setLevels()`: 109-116번째 줄

## 🔍 디버깅 방법

### 1. 브라우저 콘솔 확인

**F12** 키를 누르고 **Console** 탭을 확인하세요.

**예상 로그:**
```
🚀 처리 시작...
📤 초기 레벨 및 임계값 전송...
🎨 레벨 전송: {input_black: 0, input_white: 255, gamma: 1, ...}
✅ 레벨이 업데이트되었습니다.
```

### 2. 서버 터미널 확인

**python app.py**를 실행한 터미널에서:

**예상 로그:**
```
🎨 레벨 조정: input_black=0, input_white=255, gamma=1.0, output_black=0, output_white=255
```

### 3. 슬라이더 움직이기

슬라이더를 움직일 때마다:

**브라우저 콘솔:**
```
🎨 레벨 전송: {input_black: 30, input_white: 255, ...}
```

**서버 터미널:**
```
🎨 레벨 조정: input_black=30, input_white=255, ...
```

## 🐛 일반적인 문제

### 문제 1: "시작" 버튼을 누르지 않음

**증상:** 슬라이더를 움직여도 아무 일도 안 일어남

**원인:** 처리가 시작되지 않아서 프레임이 전송되지 않음

**해결:**
```
1. "시작" 버튼 클릭
2. 슬라이더 조정
3. 효과 확인
```

### 문제 2: 서버 연결 안 됨

**증상:** 브라우저 콘솔에 "서버에 연결되지 않았습니다" 경고

**확인:**
```javascript
// 콘솔에서 확인
socketHandler.isConnected  // true여야 함
```

**해결:**
```
1. 페이지 새로고침 (F5)
2. 서버 재시작: python app.py
3. 브라우저 캐시 삭제
```

### 문제 3: 레벨 값이 전송되지 않음

**증상:** 슬라이더 움직여도 콘솔에 로그 없음

**확인:**
```javascript
// 브라우저 콘솔에서 수동 전송 테스트
sendLevels()
```

**해결:**
```html
<!-- HTML 슬라이더 ID 확인 -->
<input id="input-black" ...>  <!-- ID가 정확해야 함 -->
```

### 문제 4: 효과가 너무 미미함

**증상:** 슬라이더를 움직여도 변화가 보이지 않음

**원인:** 조명 조건이 좋아서 레벨 조정이 필요 없음

**테스트:**
```
1. Input Black: 50으로 설정
2. Input White: 200으로 설정
3. 명확한 차이가 보여야 함
```

## 📊 효과 확인 방법

### 극단적인 값으로 테스트

#### 테스트 1: 밝게 만들기
```
Input Black: 0
Input White: 150 ← 낮춤
Gamma: 1.0
Output Black: 0
Output White: 255
```
→ **화면이 전체적으로 밝아져야 함**

#### 테스트 2: 어둡게 만들기
```
Input Black: 100 ← 높임
Input White: 255
Gamma: 1.0
Output Black: 0
Output White: 255
```
→ **화면이 전체적으로 어두워져야 함**

#### 테스트 3: 대비 강하게
```
Input Black: 50
Input White: 200
Gamma: 1.5 ← 높임
Output Black: 0
Output White: 255
```
→ **윤곽선이 더 명확해져야 함**

## 🔧 강제 테스트 방법

### 브라우저 콘솔에서 직접 테스트

```javascript
// 1. 연결 상태 확인
console.log('연결 상태:', socketHandler.isConnected);

// 2. 강제로 레벨 전송
socketHandler.setLevels({
    input_black: 50,
    input_white: 200,
    gamma: 1.5,
    output_black: 0,
    output_white: 255
});

// 3. 결과 확인
// 서버 터미널에 로그가 나타나야 함
```

### Python 콘솔에서 직접 테스트

서버 실행 중에 다른 터미널에서:

```python
# test_levels.py
import cv2
import numpy as np

# 테스트 이미지 생성
img = np.random.randint(0, 256, (480, 640), dtype=np.uint8)

# 레벨 조정 적용
input_black = 50
input_white = 200
gamma = 1.5

img_float = img.astype(np.float32)
img_adjusted = (img_float - input_black) / (input_white - input_black) * 255
img_adjusted = np.clip(img_adjusted, 0, 255)
img_adjusted = np.power(img_adjusted / 255.0, gamma) * 255
img_adjusted = img_adjusted.astype(np.uint8)

print(f"원본 평균: {img.mean():.2f}")
print(f"조정 후 평균: {img_adjusted.mean():.2f}")
```

## 📈 정상 동작 체크리스트

- [ ] 서버가 실행 중
- [ ] 브라우저가 서버에 연결됨 (녹색 "연결됨" 표시)
- [ ] "시작" 버튼을 클릭함
- [ ] 웹캠이 작동 중
- [ ] 슬라이더를 움직일 때 브라우저 콘솔에 로그 나타남
- [ ] 슬라이더를 움직일 때 서버 터미널에 로그 나타남
- [ ] 극단적인 값(50/200)에서 화면 변화 확인됨

## 🎯 실제 사용 시나리오

### 시나리오 1: 어두운 환경

**문제:** 토끼가 잘 안 보임 (어두움)

**해결:**
```
Input Black: 0
Input White: 150 ← 낮춰서 밝게
Gamma: 0.7 ← 낮춰서 밝게
```

### 시나리오 2: 밝은 환경

**문제:** 형태가 뭉개짐 (너무 밝음)

**해결:**
```
Input Black: 50 ← 높여서 어둡게
Input White: 255
Gamma: 1.3 ← 높여서 대비 강화
```

### 시나리오 3: 낮은 대비

**문제:** 토끼와 배경 구분이 안 됨

**해결:**
```
Input Black: 30
Input White: 220
Gamma: 1.5 ← 높여서 대비 강화
```

## 🔍 고급 디버깅

### 네트워크 탭 확인

**F12** → **Network** 탭 → **WS** (WebSocket)

**확인할 내용:**
- `set_levels` 이벤트가 전송되는지
- 서버 응답이 오는지

### Vue/React DevTools (해당 없음)

이 프로젝트는 Vanilla JavaScript를 사용합니다.

### 서버 로그 레벨 높이기

더 자세한 로그를 원하면:

```python
# app.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📝 문제 리포트 템플릿

문제가 계속되면 다음 정보를 제공하세요:

```
### 환경
- OS: Windows/Mac/Linux
- Python 버전: 3.13
- 브라우저: Chrome/Firefox/etc

### 증상
- 무엇을 했을 때 문제가 발생하나요?
- 어떤 증상이 나타나나요?

### 로그
- 브라우저 콘솔 로그:
```javascript
여기에 붙여넣기
```

- 서버 터미널 로그:
```
여기에 붙여넣기
```

### 시도한 해결책
- [ ] 페이지 새로고침
- [ ] 서버 재시작
- [ ] 극단적인 값 테스트
- [ ] 브라우저 콘솔 수동 테스트
```

## 요약

레벨 조정 기능은 **정상적으로 구현**되어 있습니다. 

**디버깅 체크리스트:**
1. ✅ 서버 실행 중
2. ✅ 브라우저 연결됨
3. ✅ "시작" 버튼 클릭
4. ✅ 슬라이더 이동 시 콘솔 로그 확인
5. ✅ 극단적인 값(50/200)으로 테스트

**문제가 계속되면:**
- 브라우저 콘솔과 서버 터미널의 로그를 확인
- 위의 "강제 테스트 방법" 실행
- 이 문서의 체크리스트 확인

---

**레벨 조정이 잘 작동해야 합니다!** 🎨✨

