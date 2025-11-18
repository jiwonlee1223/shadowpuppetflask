# Shadow Puppet AR - 프로젝트 요약 📋

## 프로젝트 개요

실시간 웹캠에서 특정 형태를 탐지하고, 탐지된 형태 위에 비디오를 증강현실(AR) 스타일로 오버레이하는 Flask 기반 웹 애플리케이션입니다.

## 핵심 기술

### 백엔드 (Python/Flask)

#### 1. `shape_detector.py` - 형태 탐지 엔진
**주요 기능:**
- ✅ Hu Moments 기반 형태 매칭
- ✅ 적응형 임계값 및 모폴로지 연산
- ✅ 히스테리시스 잠금 메커니즘 (12프레임 진입 / 8프레임 탈출)
- ✅ 지수 이동 평균(EMA) 기반 부드러운 추적
- ✅ Photoshop 스타일 레벨 조정 (5개 파라미터)
- ✅ 면적/종횡비 필터링

**주요 메서드:**
- `detect(frame)` - 프레임에서 형태 탐지
- `apply_levels(image)` - 레벨 조정 적용
- `set_levels(...)` - 레벨 파라미터 설정
- `reset()` - 추적 상태 리셋

#### 2. `video_overlay.py` - 비디오 오버레이 엔진
**주요 기능:**
- ✅ 원근 변환(Perspective Transform)
- ✅ 곱하기 블렌드 모드 합성
- ✅ 자동 비디오 루핑
- ✅ 참조 이미지 비율 기반 프레임 크기 계산

**주요 메서드:**
- `overlay(base_frame, frame_corners)` - 비디오 오버레이
- `set_frame(frame_idx)` - 특정 프레임 이동
- `reset()` - 비디오 리셋

#### 3. `app.py` - Flask 메인 애플리케이션
**주요 기능:**
- ✅ Flask-SocketIO를 사용한 실시간 양방향 통신
- ✅ Base64 인코딩/디코딩
- ✅ 프레임 처리 및 결과 전송
- ✅ 레벨/임계값 동적 조정
- ✅ 상태 관리 및 에러 핸들링

**주요 엔드포인트:**
- `GET /` - 메인 페이지
- `GET /api/status` - 애플리케이션 상태

**주요 Socket.IO 이벤트:**
- `video_frame` - 비디오 프레임 수신 및 처리
- `set_levels` - 레벨 조정
- `set_thresholds` - 임계값 설정
- `reset_detector` - 감지기 리셋

### 프론트엔드 (HTML/CSS/JavaScript)

#### 1. `templates/layout.html` - 레이아웃 템플릿
**주요 기능:**
- ✅ Bootstrap 5 기반 반응형 디자인
- ✅ 네비게이션 바 (연결 상태 표시)
- ✅ Font Awesome 아이콘
- ✅ 공통 레이아웃 구조

#### 2. `templates/index.html` - 메인 페이지
**주요 기능:**
- ✅ 실시간 AR 뷰 (비디오 컨테이너)
- ✅ 제어 패널 (시작/정지/리셋)
- ✅ 탐지 설정 (임계값 슬라이더)
- ✅ 레벨 조정 (5개 슬라이더)
- ✅ 상태 오버레이 (잠금 상태, FPS)
- ✅ 탐지 정보 표시

#### 3. `static/js/socket-handler.js` - WebSocket 핸들러
**주요 기능:**
- ✅ Socket.IO 연결 관리
- ✅ 이벤트 리스너 등록
- ✅ 데이터 송수신
- ✅ 연결 상태 UI 업데이트

**주요 메서드:**
- `connect()` - 서버 연결
- `sendFrame(base64Image)` - 프레임 전송
- `setLevels(levels)` - 레벨 설정
- `setThresholds(thresholds)` - 임계값 설정
- `resetDetector()` - 리셋 요청

#### 4. `static/js/main.js` - 메인 JavaScript
**주요 기능:**
- ✅ 웹캠 초기화 (MediaStream API)
- ✅ Canvas 기반 프레임 캡처
- ✅ Base64 인코딩 및 전송
- ✅ FPS 계산 및 표시
- ✅ UI 이벤트 핸들링
- ✅ 디바운스 처리 (슬라이더)

**주요 함수:**
- `initWebcam()` - 웹캠 초기화
- `startProcessing()` - 처리 시작
- `stopProcessing()` - 처리 정지
- `processFrame()` - 프레임 처리 루프
- `handleProcessedFrame(data)` - 결과 프레임 수신

#### 5. `static/css/style.css` - 커스텀 스타일
**주요 기능:**
- ✅ 반응형 디자인 (모바일/태블릿/데스크톱)
- ✅ 카드 스타일링
- ✅ 비디오 컨테이너 레이아웃
- ✅ 상태 오버레이
- ✅ 애니메이션 효과 (pulse, hover)
- ✅ 커스텀 스크롤바

## 데이터 흐름

```
[웹캠] → [Canvas] → [Base64] → [Socket.IO]
   ↓                                ↓
[MediaStream]              [Flask-SocketIO]
                                     ↓
                            [ShapeDetector]
                                     ↓
                            [VideoOverlay]
                                     ↓
                            [Base64] ← [처리된 프레임]
                                     ↓
                            [Socket.IO] → [클라이언트]
                                            ↓
                                     [<img> 태그 업데이트]
```

## 알고리즘 상세

### 형태 탐지 파이프라인

1. **입력:** BGR 프레임 (웹캠)
2. **그레이스케일 변환**
3. **가우시안 블러** (5x5 커널)
4. **레벨 조정** (선택적)
   - 입력 범위 정규화
   - 감마 보정
   - 출력 범위 매핑
5. **적응형 임계값** (ADAPTIVE_THRESH_GAUSSIAN_C)
6. **모폴로지 연산**
   - Close (2회)
   - Open (1회)
7. **윤곽선 추출** (RETR_EXTERNAL)
8. **필터링**
   - 면적: 2000 ~ 프레임의 50%
   - 종횡비: 0.5 ~ 2.0
9. **형태 매칭** (CONTOURS_MATCH_I3)
10. **히스테리시스 적용**
    - 잠금 해제 → 잠금: 좋은 매칭 12프레임
    - 잠금 → 잠금 해제: 나쁜 매칭 8프레임
11. **부드러운 추적** (EMA)
    - 중심점 (alpha=0.3)
    - 각도 (순환 평균)
    - 스케일 (alpha=0.3)
    - 프레임 중심 (alpha=0.5)
12. **출력:** 탐지 정보 (중심, 각도, 스케일, 프레임 코너)

### 비디오 오버레이 파이프라인

1. **입력:** 베이스 프레임, 프레임 코너 (4개)
2. **비디오 프레임 읽기** (자동 루핑)
3. **소스/목적지 좌표 설정**
   - 소스: 비디오 4개 코너
   - 목적지: 탐지된 프레임 코너
4. **원근 변환 행렬 계산** (getPerspectiveTransform)
5. **비디오 프레임 워핑** (warpPerspective)
6. **마스크 생성** (워핑된 영역)
7. **곱하기 블렌드**
   - `blended = (base * warped) / 255`
8. **마스크 적용 합성**
9. **출력:** 합성된 프레임

## 파라미터 튜닝 가이드

### 히스테리시스 (shape_detector.py)
```python
threshold_enter = 0.25      # ↓ 낮을수록 엄격
threshold_exit = 0.50       # ↑ 높을수록 관대
lock_count_enter = 12       # ↑ 높을수록 안정적
lock_count_exit = 8         # ↓ 낮을수록 빠른 해제
```

### EMA 스무딩 (shape_detector.py)
```python
alpha = 0.3                 # ↓ 낮을수록 부드러움
alpha_frame = 0.5           # ↓ 낮을수록 부드러움
```

### 필터링 (shape_detector.py)
```python
min_area = 2000             # 최소 면적
max_area = frame_area * 0.5 # 최대 면적
min_aspect = 0.5            # 최소 종횡비
max_aspect = 2.0            # 최대 종횡비
```

### 레벨 조정 (UI에서 조정 가능)
```python
input_black = 0-255         # 입력 검은색 포인트
input_white = 0-255         # 입력 흰색 포인트
gamma = 0.1-9.99           # 감마 값
output_black = 0-255        # 출력 검은색 포인트
output_white = 0-255        # 출력 흰색 포인트
```

## 성능 최적화

### 현재 구현
- ✅ Eventlet을 사용한 비동기 처리
- ✅ JPEG 압축 (품질 85%)
- ✅ 프레임 디바운싱 없음 (최대 FPS)

### 추가 최적화 가능
- 🔲 프레임 건너뛰기 (예: 2프레임마다 처리)
- 🔲 멀티스레딩 (프레임 처리 병렬화)
- 🔲 GPU 가속 (CUDA)
- 🔲 이미지 해상도 다운샘플링

## 확장 가능성

### 기능 추가
- 🔲 여러 형태 동시 탐지
- 🔲 사용자 정의 참조 이미지 업로드
- 🔲 비디오 효과 (필터, 블렌드 모드)
- 🔲 녹화 기능 (프레임 저장)
- 🔲 스크린샷 기능
- 🔲 다양한 블렌드 모드 (Add, Screen, Overlay)

### 플랫폼 확장
- 🔲 모바일 앱 (React Native)
- 🔲 데스크톱 앱 (Electron)
- 🔲 WebRTC 지원 (P2P)

## 의존성

### Python 패키지
```
Flask==3.0.0               # 웹 프레임워크
Flask-SocketIO==5.3.5      # 실시간 통신
opencv-python==4.8.1.78    # 컴퓨터 비전
numpy==1.26.2              # 수치 연산
Pillow==10.1.0             # 이미지 처리
python-engineio==4.8.0     # Socket.IO 엔진
python-socketio==5.10.0    # Socket.IO 서버
eventlet==0.33.3           # 비동기 처리
```

### 프론트엔드 라이브러리 (CDN)
- Bootstrap 5.3.0
- Socket.IO 4.5.4
- Font Awesome 6.4.0

## 브라우저 호환성

### 지원됨 ✅
- Chrome 90+
- Firefox 90+
- Edge 90+
- Safari 14+
- Opera 75+

### 필수 API
- MediaStream API
- Canvas API
- WebSocket
- ES6+ JavaScript

## 보안 고려사항

### 현재 구현
- ✅ CORS 허용 (개발 환경)
- ✅ localhost 제한 가능

### 프로덕션 배포 시 필요
- 🔲 HTTPS 적용
- 🔲 CORS 정책 강화
- 🔲 인증/권한 시스템
- 🔲 Rate Limiting
- 🔲 입력 검증 강화

## 테스트

### 수동 테스트 체크리스트
- [ ] 웹캠 초기화
- [ ] 형태 탐지 (다양한 조명)
- [ ] 비디오 오버레이
- [ ] 레벨 조정 효과
- [ ] 임계값 조정 효과
- [ ] 잠금 메커니즘 (안정성)
- [ ] FPS 성능
- [ ] 반응형 디자인 (모바일)

### 자동 테스트 (향후 추가 가능)
- 🔲 단위 테스트 (pytest)
- 🔲 통합 테스트
- 🔲 E2E 테스트 (Selenium)

## 문서

- **README.md** - 전체 프로젝트 문서
- **QUICKSTART.md** - 빠른 시작 가이드
- **PROJECT_SUMMARY.md** - 이 문서 (기술 요약)

## 라이선스

교육 목적으로 제공됩니다.

---

**Shadow Puppet AR v1.0** - 2025

