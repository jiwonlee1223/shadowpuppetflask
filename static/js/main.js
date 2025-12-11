/**
 * 메인 JavaScript
 * 웹캠 캡처, UI 제어, 실시간 처리
 */

// 전역 변수
let webcam = null;
let inputCanvas = null;
let inputContext = null;
let outputImage = null;
let isRunning = false;
let animationFrameId = null;

// FPS 계산
let frameCount = 0;
let lastFpsUpdate = Date.now();
let currentFps = 0;

// 조정 디바운스 타이머
let adjustmentDebounceTimer = null;
let thresholdsDebounceTimer = null;

// 성능 최적화
let processingFrame = false;  // 서버 처리 중 플래그
let frameSkipCounter = 0;     // 프레임 스킵 카운터
const FRAME_SKIP = 1;         // 1 = 모든 프레임, 2 = 2프레임마다 1번, 3 = 3프레임마다 1번

// 사운드
let meowSounds = [];
let meowSleepingSound = null;

/**
 * 초기화
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('Shadow Puppet AR 초기화...');
    
    // DOM 요소
    webcam = document.getElementById('webcam');
    inputCanvas = document.getElementById('input-canvas');
    inputContext = inputCanvas.getContext('2d');
    outputImage = document.getElementById('output-image');
    
    // Socket.IO 연결
    socketHandler.connect();
    
    // 콜백 설정
    socketHandler.onProcessedFrame = handleProcessedFrame;
    socketHandler.onError = handleError;
    socketHandler.onStatusChange = handleStatusChange;
    
    // 이벤트 리스너 등록
    setupEventListeners();
    
    // 웹캠 초기화
    initWebcam();
    
    // Three.js 3D 렌더러 초기화
    initThreeRenderer();
    
    // 사운드 초기화
    initSounds();
});

/**
 * Three.js 렌더러 초기화
 */
function initThreeRenderer() {
    console.log('🎮 Three.js 렌더러 초기화 중...');
    
    // 렌더러 생성
    threeRenderer = new ThreeRenderer('threejs-container');
    
    // GLTF 모델 로드 (scene.gltf - 다양한 애니메이션 포함)
    threeRenderer.loadModel('/static/models/scene.gltf');
}

/**
 * 사운드 초기화
 */
function initSounds() {
    console.log('🔊 사운드 초기화 중...');
    
    // 여러 야옹 소리 로드
    const soundFiles = ['meow.mp3', 'meow2.mp3', 'meow3.mp3'];
    soundFiles.forEach(file => {
        const sound = new Audio(`/static/sounds/${file}`);
        sound.volume = 0.5;  // 볼륨 50%
        meowSounds.push(sound);
    });
    
    // 잠자는 소리 로드 (루프 재생)
    meowSleepingSound = new Audio('/static/sounds/meow-purring.mp3');
    meowSleepingSound.volume = 0.5;
    meowSleepingSound.loop = true;  // 반복 재생
    
    console.log(`🔊 ${meowSounds.length}개의 사운드 + 잠자는 소리 로드 완료`);
    
    // Three.js 렌더러에 잠자기 콜백 연결
    setupSleepCallbacks();
}

/**
 * 잠자기 콜백 설정
 */
function setupSleepCallbacks() {
    // threeRenderer가 초기화될 때까지 대기
    const checkRenderer = setInterval(() => {
        if (threeRenderer) {
            clearInterval(checkRenderer);
            
            // 잠들기 시작 시 소리 재생
            threeRenderer.onSleepStart = () => {
                console.log('🔊 잠자는 소리 재생 시작');
                if (meowSleepingSound) {
                    meowSleepingSound.currentTime = 0;
                    meowSleepingSound.play().catch(e => console.warn('잠자는 소리 재생 실패:', e));
                }
            };
            
            // 잠에서 깰 때 소리 정지
            threeRenderer.onSleepEnd = () => {
                console.log('🔊 잠자는 소리 정지');
                if (meowSleepingSound) {
                    meowSleepingSound.pause();
                    meowSleepingSound.currentTime = 0;
                }
            };
            
            console.log('🔊 잠자기 콜백 연결 완료');
        }
    }, 100);
}

/**
 * 웹캠 초기화
 */
async function initWebcam() {
    try {
        // 성능을 위해 해상도를 낮춤 (필요시 조정 가능)
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: 640 },   // 1280 → 640으로 낮춤 (2배 빠름)
                height: { ideal: 360 },  // 16:9 비율 (720 → 360으로 낮춤)
                facingMode: 'user'
            }
        });
        
        webcam.srcObject = stream;
        
        // 비디오 메타데이터 로드 대기
        await new Promise((resolve) => {
            webcam.onloadedmetadata = resolve;
        });
        
        // 캔버스 크기 설정
        inputCanvas.width = webcam.videoWidth;
        inputCanvas.height = webcam.videoHeight;
        
        console.log(`웹캠 초기화 완료: ${webcam.videoWidth}x${webcam.videoHeight}`);
        
        // 오버레이 숨기기
        document.getElementById('no-video-overlay').style.display = 'none';
        
    } catch (error) {
        console.error('웹캠 접근 오류:', error);
        alert('웹캠에 접근할 수 없습니다. 브라우저 설정을 확인해주세요.');
    }
}

/**
 * 이벤트 리스너 설정
 */
function setupEventListeners() {
    // 시작 버튼
    document.getElementById('btn-start').addEventListener('click', startProcessing);
    
    // 정지 버튼
    document.getElementById('btn-stop').addEventListener('click', stopProcessing);
    
    // 리셋 버튼
    document.getElementById('btn-reset').addEventListener('click', resetDetector);
    
    // 명도/채도 조정 슬라이더
    setupAdjustmentSlider('brightness');
    setupAdjustmentSlider('saturation');
    
    // 임계값 슬라이더
    setupThresholdSlider('threshold-enter');
    setupThresholdSlider('threshold-exit');
    
    // 초기화 버튼
    document.getElementById('btn-reset-adjustment').addEventListener('click', resetAdjustment);
}

/**
 * 명도/채도 슬라이더 설정
 */
function setupAdjustmentSlider(sliderId) {
    const slider = document.getElementById(sliderId);
    const valueDisplay = document.getElementById(`${sliderId}-value`);
    
    slider.addEventListener('input', (e) => {
        const value = parseInt(e.target.value);
        valueDisplay.textContent = value;
        
        // 디바운스 적용 (300ms)
        clearTimeout(adjustmentDebounceTimer);
        adjustmentDebounceTimer = setTimeout(() => {
            sendAdjustment();
        }, 300);
    });
}

/**
 * 임계값 슬라이더 설정
 */
function setupThresholdSlider(sliderId) {
    const slider = document.getElementById(sliderId);
    const valueDisplay = document.getElementById(`${sliderId}-value`);
    
    slider.addEventListener('input', (e) => {
        const value = parseFloat(e.target.value);
        valueDisplay.textContent = value.toFixed(2);
        
        // 디바운스 적용 (500ms)
        clearTimeout(thresholdsDebounceTimer);
        thresholdsDebounceTimer = setTimeout(() => {
            sendThresholds();
        }, 500);
    });
}

/**
 * 명도/채도 조정 전송
 */
function sendAdjustment() {
    const adjustment = {
        brightness: parseInt(document.getElementById('brightness').value),
        saturation: parseInt(document.getElementById('saturation').value)
    };
    
    console.log('🎨 명도/채도 조정 전송:', adjustment);
    socketHandler.setAdjustment(adjustment);
}

/**
 * 임계값 전송
 */
function sendThresholds() {
    const thresholds = {
        threshold_enter: parseFloat(document.getElementById('threshold-enter').value),
        threshold_exit: parseFloat(document.getElementById('threshold-exit').value)
    };
    
    socketHandler.setThresholds(thresholds);
}

/**
 * 명도/채도 초기화
 */
function resetAdjustment() {
    document.getElementById('brightness').value = 0;
    document.getElementById('saturation').value = 0;
    
    document.getElementById('brightness-value').textContent = '0';
    document.getElementById('saturation-value').textContent = '0';
    
    sendAdjustment();
}

/**
 * 처리 시작
 */
function startProcessing() {
    if (isRunning) return;
    
    console.log('🚀 처리 시작...');
    isRunning = true;
    
    document.getElementById('btn-start').disabled = true;
    document.getElementById('btn-stop').disabled = false;
    
    // 초기 조정 값 및 임계값 전송
    console.log('📤 초기 명도/채도 및 임계값 전송...');
    sendAdjustment();
    sendThresholds();
    
    // 프레임 처리 루프 시작
    processFrame();
}

/**
 * 처리 정지
 */
function stopProcessing() {
    if (!isRunning) return;
    
    console.log('처리 정지...');
    isRunning = false;
    
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }
    
    document.getElementById('btn-start').disabled = false;
    document.getElementById('btn-stop').disabled = true;
}

/**
 * 감지기 리셋
 */
function resetDetector() {
    console.log('감지기 리셋...');
    socketHandler.resetDetector();
}

/**
 * 프레임 처리 루프
 */
function processFrame() {
    if (!isRunning) return;
    
    try {
        // 프레임 스킵 (성능 향상)
        frameSkipCounter++;
        if (frameSkipCounter >= FRAME_SKIP && !processingFrame) {
            frameSkipCounter = 0;
            
            // 웹캠 프레임을 캔버스에 그리기
            inputContext.drawImage(webcam, 0, 0, inputCanvas.width, inputCanvas.height);
            
            // 캔버스를 Base64로 인코딩 (JPEG 품질 60%로 낮춤)
            const base64Image = inputCanvas.toDataURL('image/jpeg', 0.6);
            
            // 서버 처리 중 플래그 설정
            processingFrame = true;
            
            // 서버로 전송
            socketHandler.sendFrame(base64Image);
        }
        
        // FPS 계산
        frameCount++;
        const now = Date.now();
        if (now - lastFpsUpdate >= 1000) {
            currentFps = frameCount;
            frameCount = 0;
            lastFpsUpdate = now;
            
            document.getElementById('fps-counter').textContent = `FPS: ${currentFps}`;
        }
        
    } catch (error) {
        console.error('프레임 처리 오류:', error);
        processingFrame = false;  // 오류 시 플래그 해제
    }
    
    // 다음 프레임 요청
    animationFrameId = requestAnimationFrame(processFrame);
}

/**
 * 처리된 프레임 수신 핸들러
 */
function handleProcessedFrame(data) {
    // 서버 처리 완료 플래그 해제
    processingFrame = false;
    
    // 결과 이미지 표시
    outputImage.src = data.image;
    
    // 탐지 정보 업데이트
    const detection = data.detection;
    
    // 검지 탭 감지 → 해당 위치로 뛰어가기!
    const hands = data.hands || {};
    const screenWidth = 640;
    const screenHeight = 360;  // 16:9 비율
    
    if (threeRenderer && threeRenderer.isLoaded && hands.tap_detected && hands.tap_position) {
        // 화면 좌표를 0~1 비율로 변환
        const normalizedX = hands.tap_position[0] / screenWidth;
        const normalizedY = hands.tap_position[1] / screenHeight;
        
        console.log(`👆 검지 탭! 화면 위치: (${normalizedX.toFixed(2)}, ${normalizedY.toFixed(2)})`);
        
        // 고양이에게 해당 위치로 이동하라고 알림
        threeRenderer.runToPosition(normalizedX, normalizedY);
        
        // 야옹 소리 랜덤 재생
        if (meowSounds.length > 0) {
            const randomIndex = Math.floor(Math.random() * meowSounds.length);
            const sound = meowSounds[randomIndex];
            sound.currentTime = 0;  // 처음부터 재생
            sound.play().catch(e => console.warn('사운드 재생 실패:', e));
        }
    }
    
    // 손바닥 상태 업데이트 (매 프레임)
    if (threeRenderer && threeRenderer.isLoaded) {
        if (hands.palm_detected && hands.palm_center) {
            const normalizedX = hands.palm_center[0] / screenWidth;
            const normalizedY = hands.palm_center[1] / screenHeight;
            
            // 손바닥 보임 → 상태 업데이트
            threeRenderer.updatePalmState(true, normalizedX, normalizedY);
        } else {
            // 손바닥 안 보임 → 상태 업데이트
            threeRenderer.updatePalmState(false);
        }
        
        // 👌 핀치 스케일 업데이트
        if (hands.pinch_active) {
            threeRenderer.updatePinchScale(true, hands.pinch_scale);
        } else {
            threeRenderer.updatePinchScale(false, 1.0);
        }
    }
    
    // 잠금 상태 표시
    const lockStatus = document.getElementById('lock-status');
    if (detection.is_grabbed) {
        lockStatus.innerHTML = '<i class="fas fa-hand-rock me-1"></i>잡음!';
        lockStatus.className = 'badge bg-danger';
    } else if (detection.is_permanently_active) {
        lockStatus.innerHTML = '<i class="fas fa-star me-1"></i>영구 활성';
        lockStatus.className = 'badge bg-warning text-dark';
    } else if (detection.is_locked) {
        lockStatus.innerHTML = '<i class="fas fa-lock me-1"></i>잠금';
        lockStatus.className = 'badge bg-success';
    } else {
        lockStatus.innerHTML = '<i class="fas fa-unlock me-1"></i>잠금 해제';
        lockStatus.className = 'badge bg-secondary';
    }
    
    // 탐지 정보 표시
    const detectionInfo = document.getElementById('detection-info');
    
    if (detection.is_pushed_off_screen) {
        detectionInfo.innerHTML = '<strong class="text-warning">📤 화면 밖으로 밀려남!</strong>';
        detectionInfo.className = 'text-warning';
        // 모델 숨기기
        if (threeRenderer) threeRenderer.setVisible(false);
    } else if (detection.found) {
        const score = detection.score ? detection.score.toFixed(3) : 'N/A';
        const angle = detection.angle ? detection.angle.toFixed(1) : 'N/A';
        const scale = detection.scale ? detection.scale.toFixed(2) : 'N/A';
        const handInfo = hands.found ? ` | 👋 손: ${hands.count}개` : '';
        const modelInfo = threeRenderer && threeRenderer.isLoaded ? ' | 🐱 3D 모델' : '';
        
        detectionInfo.innerHTML = `
            <strong>탐지됨</strong> | 
            점수: ${score} | 
            각도: ${angle}° | 
            스케일: ${scale}x${handInfo}${modelInfo}
        `;
        detectionInfo.className = 'text-success';
    } else {
        const handInfo = hands.found ? ` | 👋 손: ${hands.count}개 감지됨` : '';
        detectionInfo.innerHTML = `탐지 대기 중...${handInfo}`;
        detectionInfo.className = 'text-muted';
    }
}

/**
 * 에러 핸들러
 */
function handleError(message) {
    console.error('에러:', message);
    // Toast 알림 또는 경고 표시 가능
}

/**
 * 상태 변경 핸들러
 */
function handleStatusChange(status) {
    console.log('상태 변경:', status);
    
    if (!status.ready) {
        alert('서버가 준비되지 않았습니다. 필수 파일(참조 이미지, 비디오)을 확인해주세요.');
    }
}

/**
 * 페이지 언로드 시 정리
 */
window.addEventListener('beforeunload', () => {
    stopProcessing();
    socketHandler.disconnect();
    
    // 웹캠 스트림 정지
    if (webcam && webcam.srcObject) {
        const tracks = webcam.srcObject.getTracks();
        tracks.forEach(track => track.stop());
    }
    
    // Three.js 정리
    if (threeRenderer) {
        threeRenderer.dispose();
    }
});

