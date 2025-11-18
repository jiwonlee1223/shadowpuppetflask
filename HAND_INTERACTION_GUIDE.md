# 손 인터랙션 기능 가이드 👋

## 개요

**손 인터랙션** 기능은 MediaPipe Hands를 사용하여 사용자의 손을 실시간으로 탐지하고, 손이 토끼 애니메이션에 닿으면 물리 시뮬레이션을 통해 애니메이션을 화면 밖으로 밀어내는 기능입니다.

## 작동 방식

### 1단계: 손 탐지
- MediaPipe Hands가 웹캠에서 손을 실시간으로 탐지합니다
- 최대 2개의 손을 동시에 탐지할 수 있습니다
- 손바닥 중심 좌표를 계산합니다

### 2단계: 충돌 감지
- 손바닥 중심이 토끼 애니메이션 영역 안에 들어가는지 확인
- 토끼 영역의 바운딩 박스를 사용하여 충돌 판정
- 충돌 시 밀어내는 방향 벡터 계산

### 3단계: 물리 시뮬레이션
- 충돌 방향으로 속도 벡터 생성
- 매 프레임마다 속도에 따라 위치 업데이트
- 마찰 계수를 적용하여 점진적으로 감속

### 4단계: 화면 밖으로 이동
- 애니메이션이 화면 경계를 벗어나면 사라짐
- "리셋" 버튼으로 다시 불러올 수 있음

## 물리 파라미터

### shape_detector.py에서 조정 가능

```python
# 밀어내기 파라미터
self.push_force = 15.0        # 밀어내는 힘 (클수록 강하게)
self.push_friction = 0.85     # 마찰 계수 (0~1, 높을수록 천천히 감속)
```

**권장 설정:**

| 효과 | push_force | push_friction | 설명 |
|------|------------|---------------|------|
| **부드러운 밀림** | 10.0 | 0.90 | 천천히 멀리 밀려남 |
| **균형 (기본)** | 15.0 | 0.85 | ⭐ 적당한 속도와 거리 |
| **강한 밀림** | 25.0 | 0.80 | 빠르게 멀리 날아감 |
| **즉시 튕김** | 50.0 | 0.70 | 손 대자마자 날아감 |

## 사용 예시

### 시나리오 1: 프레젠테이션
```
1. 토끼를 3초간 보여줌 → 영구 활성화
2. 토끼 애니메이션을 손으로 밀어냄
3. 화면 밖으로 사라짐
4. 청중: "와!" 👏
```

### 시나리오 2: 인터랙티브 퍼포먼스
```
1. 토끼 애니메이션 나타남
2. 공연자가 손으로 쳐내는 동작
3. 애니메이션이 날아감
4. 리셋 버튼으로 다시 시작
```

### 시나리오 3: 놀이/게임
```
1. 토끼를 여러 번 밀어내기
2. 얼마나 멀리 날려보낼 수 있을까?
3. 친구와 경쟁!
```

## 기술 상세

### MediaPipe Hands 설정

```python
self.hands = self.mp_hands.Hands(
    static_image_mode=False,        # 비디오 모드
    max_num_hands=2,                 # 최대 2개 손 탐지
    min_detection_confidence=0.5,    # 탐지 신뢰도 (0~1)
    min_tracking_confidence=0.5      # 추적 신뢰도 (0~1)
)
```

**파라미터 조정:**
- `max_num_hands`: 1 (1개 손만) ~ 2 (양손)
- `min_detection_confidence`: 0.3 (더 민감) ~ 0.7 (더 엄격)
- `min_tracking_confidence`: 0.3 (더 민감) ~ 0.7 (더 엄격)

### 충돌 감지 알고리즘

```python
# 1. 토끼 영역의 바운딩 박스 계산
min_x, max_x = min/max([corner[0] for corner in rabbit_corners])
min_y, max_y = min/max([corner[1] for corner in rabbit_corners])

# 2. 손바닥 중심이 박스 안에 있는지 확인
if min_x <= hand_x <= max_x and min_y <= hand_y <= max_y:
    collision = True  # 충돌!

# 3. 밀어내는 방향 계산
direction_x = hand_x - rabbit_center_x
direction_y = hand_y - rabbit_center_y
# 정규화
magnitude = sqrt(dx^2 + dy^2)
normalized_direction = (dx/magnitude, dy/magnitude)
```

### 물리 시뮬레이션

```python
# 매 프레임마다 실행

# 1. 충돌 시 속도 추가
if collision:
    velocity_x += direction_x * push_force
    velocity_y += direction_y * push_force

# 2. 위치 업데이트
offset_x += velocity_x
offset_y += velocity_y

# 3. 마찰 적용 (감속)
velocity_x *= friction  # 예: 0.85
velocity_y *= friction

# 4. 매우 작은 속도는 0으로
if abs(velocity_x) < 0.1:
    velocity_x = 0

# 5. 화면 밖 체크
if abs(offset_x) > screen_width or abs(offset_y) > screen_height:
    is_pushed_off_screen = True
```

## 데이터 흐름

```
[웹캠 프레임]
    ↓
[MediaPipe Hands] → [손 좌표 추출]
    ↓                      ↓
[Shape Detector]    [충돌 감지]
    ↓                      ↓
[토끼 영역]  ←───  [충돌 여부 + 방향]
    ↓
[물리 시뮬레이션]
    ↓
[밀림 오프셋 적용]
    ↓
[Video Overlay]
    ↓
[최종 프레임]
```

## UI 표시

### 상태 메시지

```javascript
if (detection.is_pushed_off_screen) {
    // "📤 화면 밖으로 밀려남!" (노란색)
} else if (detection.found) {
    // "탐지됨 | 점수: 0.123 | ... | 👋 손: 1개"
} else {
    // "탐지 대기 중... | 👋 손: 1개 감지됨"
}
```

### 손 랜드마크 표시 (디버그)

app.py에서 주석 해제:

```python
# 손 그리기 (선택적 - 디버그용)
if hand_result['landmarks']:
    result_frame = hand_detector.draw_hands(result_frame, hand_result['landmarks'])
```

이렇게 하면 손의 21개 랜드마크가 화면에 그려집니다.

## 성능 영향

### MediaPipe Hands 추가로 인한 영향

| 항목 | 변화 |
|------|------|
| **처리 시간** | +10~15ms |
| **FPS 감소** | -3~5 FPS |
| **CPU 사용률** | +10~15% |
| **메모리** | +50MB |

**권장:**
- 성능이 중요하면 `FRAME_SKIP = 2` 설정
- 또는 손 탐지를 일시적으로 비활성화

### 최적화 팁

1. **탐지 신뢰도 높이기**
   ```python
   min_detection_confidence=0.7  # 0.5 → 0.7
   ```
   더 엄격하게 탐지 → 처리 횟수 감소

2. **1개 손만 탐지**
   ```python
   max_num_hands=1  # 2 → 1
   ```
   처리량 50% 감소

3. **모델 복잡도 낮추기** (향후 확장 가능)
   ```python
   model_complexity=0  # 0 (빠름) ~ 1 (정확함)
   ```

## 문제 해결

### 손이 탐지되지 않아요
1. **조명 확인** - 밝은 곳에서 사용
2. **손바닥 보이기** - 손등보다 손바닥이 더 잘 탐지됨
3. **신뢰도 낮추기** - `min_detection_confidence=0.3`

### 충돌 감지가 안 돼요
1. **토끼가 영구 활성화되었는지 확인** (노란색 배지)
2. **손을 토끼 영역 중앙에 가져가기**
3. **충돌 영역을 넓히기** (향후 확장 가능)

### 밀림이 너무 약해요/강해요
```python
# shape_detector.py
self.push_force = 25.0  # 15.0 → 25.0 (더 강하게)
```

### 너무 빨리/느리게 멈춰요
```python
# shape_detector.py
self.push_friction = 0.90  # 0.85 → 0.90 (더 천천히 멈춤)
```

### 화면 밖으로 안 나가요
- 화면 크기가 작으면 더 빨리 나감
- `push_force`를 높이거나 `push_friction`을 낮추기

## 고급 기능 (향후 확장 가능)

### 1. 손 제스처 인식
```python
# 특정 제스처로 다른 효과
if gesture == "peace_sign":
    # 토끼를 끌어당김
elif gesture == "fist":
    # 강하게 밀어냄
```

### 2. 여러 방향 밀기
```python
# 손의 이동 방향 추적
hand_velocity = current_position - previous_position
# 속도 방향으로 밀어냄
```

### 3. 반복 충돌
```python
# 손으로 계속 때리기
hit_count += 1
push_force *= (1 + hit_count * 0.1)  # 콤보 효과
```

### 4. 다른 객체 추가
```python
# 여러 개의 토끼
rabbits = [rabbit1, rabbit2, rabbit3]
# 각각 독립적으로 밀림
```

## 디버그 모드

### app.py에서 손 시각화 활성화

```python
# 주석 해제
if hand_result['landmarks']:
    result_frame = hand_detector.draw_hands(result_frame, hand_result['landmarks'])
```

**표시되는 것:**
- 21개 손 랜드마크 (점)
- 손가락 연결선
- 손바닥 중심

### 충돌 영역 시각화 (향후 추가 가능)

```python
# 토끼 바운딩 박스 그리기
cv2.rectangle(frame, (min_x, min_y), (max_x, max_y), (0, 255, 0), 2)

# 손바닥 중심 표시
for hand_center in hand_centers:
    cv2.circle(frame, hand_center, 10, (255, 0, 0), -1)
```

## 요약

✅ **MediaPipe Hands** → 👋 **손 탐지**  
✅ **충돌 감지** → 💥 **방향 계산**  
✅ **물리 시뮬레이션** → 🚀 **밀려남**  
✅ **화면 밖** → 📤 **사라짐**

**인터랙티브한 AR 경험을 즐기세요!** 🎭✨

---

**문제가 있으면 README.md와 다른 가이드를 참고하세요.**

