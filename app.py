"""
Flask 메인 애플리케이션
실시간 형태 탐지 및 AR 오버레이 웹 애플리케이션
"""
import os
import cv2
import base64
import numpy as np
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from shape_detector import ShapeDetector
from video_overlay import VideoOverlay
from hand_detector import HandDetector

# Flask 앱 초기화
app = Flask(__name__)
app.config['SECRET_KEY'] = 'shadow-puppet-secret-key-2025'
# Python 3.13 호환성을 위해 threading 모드 사용
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 전역 변수
shape_detector = None
video_overlay = None
hand_detector = None
white_background_mode = False  # 흰색 배경 모드 (손 스켈레톤만 표시)
mirror_mode = True  # 좌우반전 모드 (거울처럼 보이기)

# 파일 경로
REFERENCE_IMAGE_PATH = 'files/rabbit reference.png'
VIDEO_PATH = 'files/rabbit bg.mov'


def initialize_detector():
    """
    형태 감지기, 비디오 오버레이, 손 감지기 초기화
    """
    global shape_detector, video_overlay, hand_detector
    
    try:
        # 파일 존재 확인
        if not os.path.exists(REFERENCE_IMAGE_PATH):
            print(f"경고: 참조 이미지를 찾을 수 없습니다: {REFERENCE_IMAGE_PATH}")
            print("files/ 폴더에 'rabbit reference.png' 파일을 추가해주세요.")
            return False
        
        if not os.path.exists(VIDEO_PATH):
            print(f"경고: 비디오 파일을 찾을 수 없습니다: {VIDEO_PATH}")
            print("files/ 폴더에 'rabbit bg.mov' 파일을 추가해주세요.")
            return False
        
        # 형태 감지기 초기화
        shape_detector = ShapeDetector(REFERENCE_IMAGE_PATH)
        print("✓ 형태 감지기 초기화 완료")
        
        # 비디오 오버레이 초기화
        video_overlay = VideoOverlay(VIDEO_PATH)
        print("✓ 비디오 오버레이 초기화 완료")
        
        # 손 감지기 초기화
        hand_detector = HandDetector()
        print("✓ 손 감지기 초기화 완료")
        
        return True
        
    except Exception as e:
        print(f"초기화 오류: {e}")
        return False


@app.route('/')
def index():
    """
    메인 페이지
    """
    # 감지기가 초기화되지 않았으면 시도
    if shape_detector is None or video_overlay is None:
        initialize_detector()
    
    return render_template('index.html')


@app.route('/api/status')
def status():
    """
    애플리케이션 상태 확인
    """
    is_ready = shape_detector is not None and video_overlay is not None
    
    return jsonify({
        'ready': is_ready,
        'reference_image': os.path.exists(REFERENCE_IMAGE_PATH),
        'video_file': os.path.exists(VIDEO_PATH)
    })


@socketio.on('connect')
def handle_connect():
    """
    클라이언트 연결
    """
    print(f"클라이언트 연결: {request.sid}")
    
    # 초기화 상태 전송
    is_ready = shape_detector is not None and video_overlay is not None
    emit('status', {'ready': is_ready})


@socketio.on('disconnect')
def handle_disconnect():
    """
    클라이언트 연결 해제
    """
    print(f"클라이언트 연결 해제: {request.sid}")


@socketio.on('video_frame')
def handle_video_frame(data):
    """
    비디오 프레임 처리
    
    Args:
        data: {
            'image': base64 인코딩된 이미지 데이터
        }
    """
    global shape_detector, video_overlay, hand_detector
    
    # 초기화 확인
    if shape_detector is None or video_overlay is None or hand_detector is None:
        emit('error', {'message': '시스템이 초기화되지 않았습니다.'})
        return
    
    try:
        # Base64 디코딩
        image_data = data.get('image', '')
        if not image_data:
            return
        
        # Data URL에서 실제 base64 데이터 추출
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        # Base64 -> 바이트
        image_bytes = base64.b64decode(image_data)
        
        # 바이트 -> NumPy 배열 -> OpenCV 이미지
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            emit('error', {'message': '프레임 디코딩 실패'})
            return
        
        # 좌우반전 (거울 모드)
        if mirror_mode:
            frame = cv2.flip(frame, 1)
        
        # 손 탐지
        hand_result = hand_detector.detect(frame)
        
        # 충돌 감지 (먼저 형태를 탐지하여 위치 확인)
        temp_detection = shape_detector.detect(frame)
        hand_collision_data = None
        
        # 탭 감지 플래그
        tap_detected = False
        tap_position = None
        
        if temp_detection['found'] and temp_detection['frame_corners'] is not None:
            # 토끼 중심 좌표도 함께 전달
            rabbit_center = temp_detection.get('center')
            collision_result = hand_detector.check_collision(
                hand_result['hand_centers'],
                temp_detection['frame_corners'],
                rabbit_center
            )
            if collision_result['collision']:
                hand_collision_data = collision_result
            
            # 검지 탭 감지
            index_tips = hand_result.get('index_finger_tips', [])
            if hand_detector.check_index_tap(index_tips, temp_detection['frame_corners']):
                tap_detected = True
                # 터치 위치 저장 (첫 번째 검지)
                if index_tips:
                    tap_position = index_tips[0]
        
        # 형태 탐지 (손 충돌 데이터 포함)
        detection_result = shape_detector.detect(frame, hand_collision_data)
        
        # 결과 프레임 생성
        if white_background_mode:
            # 흰색 배경 모드: 웹캠 화면 대신 흰색 배경
            result_frame = np.full_like(frame, 255)  # 흰색 배경
        else:
            # 일반 모드: 웹캠 프레임 복사 + 명도/채도 조정
            result_frame = frame.copy()
            result_frame = shape_detector.apply_brightness_saturation(result_frame)
        
        # 손가락 관절(랜드마크) 그리기
        if hand_result['landmarks']:
            result_frame = hand_detector.draw_landmarks(result_frame, hand_result['landmarks'])
        
        # 비디오 오버레이 비활성화 - 3D 모델(Three.js)만 사용
        # if (detection_result['found'] and 
        #     detection_result['frame_corners'] is not None and
        #     not detection_result.get('is_pushed_off_screen', False)):
        #     result_frame = video_overlay.overlay(result_frame, detection_result['frame_corners'])
        
        # 결과 프레임을 Base64로 인코딩 (품질 70으로 낮춤 - 속도 향상)
        _, buffer = cv2.imencode('.jpg', result_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        result_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # 결과 전송
        emit('processed_frame', {
            'image': f'data:image/jpeg;base64,{result_base64}',
            'detection': {
                'found': detection_result['found'],
                'is_locked': detection_result['is_locked'],
                'is_permanently_active': detection_result.get('is_permanently_active', False),
                'score': detection_result['score'],
                'center': detection_result['center'],
                'angle': detection_result['angle'],
                'scale': detection_result['scale'],
                'is_grabbed': detection_result.get('is_grabbed', False),
                'is_pushed_off_screen': detection_result.get('is_pushed_off_screen', False),
                'drag_offset': detection_result.get('drag_offset', (0, 0)),
                'is_flipped': video_overlay.is_flipped
            },
            'hands': {
                'found': hand_result['hands_found'],
                'count': len(hand_result['hand_centers']),
                'index_tips': hand_result.get('index_finger_tips', []),
                'tap_detected': tap_detected,
                'tap_position': tap_position,
                'palm_detected': hand_result.get('palm_detected', False),
                'palm_center': hand_result.get('palm_center', None),
                'pinch_active': hand_result.get('pinch_active', False),
                'pinch_scale': hand_result.get('pinch_scale', 1.0),
                'pinch_distance': hand_result.get('pinch_distance', 0)
            }
        })
        
    except Exception as e:
        print(f"프레임 처리 오류: {e}")
        emit('error', {'message': f'프레임 처리 오류: {str(e)}'})


@socketio.on('set_adjustment')
def handle_set_adjustment(data):
    """
    명도/채도 조정 파라미터 설정
    
    Args:
        data: {
            'brightness': int (-100 ~ +100),
            'saturation': int (-100 ~ +100)
        }
    """
    global shape_detector
    
    if shape_detector is None:
        emit('error', {'message': '형태 감지기가 초기화되지 않았습니다.'})
        return
    
    try:
        # 조정 값 로깅
        print(f"🎨 명도/채도 조정: brightness={data.get('brightness')}, "
              f"saturation={data.get('saturation')}")
        
        shape_detector.set_adjustment(
            brightness=data.get('brightness'),
            saturation=data.get('saturation')
        )
        
        emit('adjustment_updated', {'success': True})
        
    except Exception as e:
        print(f"명도/채도 조정 오류: {e}")
        emit('error', {'message': f'명도/채도 조정 오류: {str(e)}'})


@socketio.on('reset_detector')
def handle_reset_detector():
    """
    형태 감지기 리셋
    """
    global shape_detector, video_overlay
    
    if shape_detector:
        shape_detector.reset()
    
    if video_overlay:
        video_overlay.reset()
    
    emit('detector_reset', {'success': True})


@socketio.on('set_thresholds')
def handle_set_thresholds(data):
    """
    히스테리시스 임계값 설정
    
    Args:
        data: {
            'threshold_enter': float,
            'threshold_exit': float
        }
    """
    global shape_detector
    
    if shape_detector is None:
        emit('error', {'message': '형태 감지기가 초기화되지 않았습니다.'})
        return
    
    try:
        if 'threshold_enter' in data:
            shape_detector.threshold_enter = float(data['threshold_enter'])
        
        if 'threshold_exit' in data:
            shape_detector.threshold_exit = float(data['threshold_exit'])
        
        emit('thresholds_updated', {'success': True})
        
    except Exception as e:
        print(f"임계값 설정 오류: {e}")
        emit('error', {'message': f'임계값 설정 오류: {str(e)}'})


@socketio.on('set_white_background')
def handle_set_white_background(data):
    """
    흰색 배경 모드 설정 (웹캠 배경 숨기고 손 스켈레톤만 표시)
    
    Args:
        data: {
            'enabled': bool
        }
    """
    global white_background_mode
    
    try:
        white_background_mode = data.get('enabled', False)
        print(f"🎨 흰색 배경 모드: {'활성화' if white_background_mode else '비활성화'}")
        emit('white_background_updated', {'enabled': white_background_mode})
        
    except Exception as e:
        print(f"흰색 배경 모드 설정 오류: {e}")
        emit('error', {'message': f'흰색 배경 모드 설정 오류: {str(e)}'})


@socketio.on('set_mirror_mode')
def handle_set_mirror_mode(data):
    """
    좌우반전(거울) 모드 설정
    
    Args:
        data: {
            'enabled': bool
        }
    """
    global mirror_mode
    
    try:
        mirror_mode = data.get('enabled', True)
        print(f"🪞 거울 모드: {'활성화' if mirror_mode else '비활성화'}")
        emit('mirror_mode_updated', {'enabled': mirror_mode})
        
    except Exception as e:
        print(f"거울 모드 설정 오류: {e}")
        emit('error', {'message': f'거울 모드 설정 오류: {str(e)}'})


if __name__ == '__main__':
    print("=" * 60)
    print("Shadow Puppet AR - 실시간 형태 탐지 및 비디오 오버레이")
    print("=" * 60)
    
    # 폴더 생성
    os.makedirs('files', exist_ok=True)
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('static/images', exist_ok=True)
    
    # 초기화
    print("\n시스템 초기화 중...")
    initialized = initialize_detector()
    
    if not initialized:
        print("\n⚠ 경고: 필수 파일이 없습니다.")
        print("다음 파일을 files/ 폴더에 추가해주세요:")
        print("  - rabbit reference.png (참조 이미지)")
        print("  - rabbit bg.mov (오버레이 비디오)")
        print("\n애플리케이션은 실행되지만 파일이 추가될 때까지 작동하지 않습니다.")
    
    print("\n서버 시작...")
    print("브라우저에서 http://localhost:5000 을 열어주세요.")
    print("=" * 60)
    
    # 서버 실행
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

