"""
손 탐지 모듈
MediaPipe Hands를 사용하여 실시간으로 손을 탐지합니다.
"""
import cv2
import numpy as np
import mediapipe as mp


class HandDetector:
    """
    실시간 손 탐지 클래스
    - MediaPipe Hands 기반 (21개 손 랜드마크)
    - 손바닥 중심 좌표 추출
    - 검지 끝 탭 감지
    - 충돌 감지
    """
    
    def __init__(self):
        """
        초기화
        """
        # MediaPipe Hands 초기화
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils
        
        # 검지 탭 감지용 변수
        self.last_index_finger_inside = False  # 이전 프레임에서 검지가 안에 있었는지
        self.tap_cooldown = 0  # 탭 쿨다운 (연속 탭 방지)
        
        # 핀치 감지용 변수
        self.pinch_active = False  # 핀치 중인지
        self.pinch_start_distance = 0  # 핀치 시작 시 거리
        self.pinch_threshold = 50  # 핀치 시작 임계 거리 (픽셀)
        self.current_pinch_scale = 1.0  # 현재 핀치 스케일
        
    def detect(self, frame):
        """
        프레임에서 손 탐지 (MediaPipe 기반)
        
        Args:
            frame: 입력 프레임 (BGR)
        
        Returns:
            dict: {
                'hands_found': bool - 손을 찾았는지 여부
                'hand_centers': list - 손바닥 중심 좌표 리스트 [(x, y), ...]
                'index_finger_tips': list - 검지 끝 좌표 리스트 [(x, y), ...]
                'landmarks': list - 손 랜드마크 리스트
            }
        """
        # BGR to RGB (MediaPipe는 RGB 사용)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 손 탐지
        results = self.hands.process(rgb_frame)
        
        hand_centers = []
        index_finger_tips = []
        landmarks_list = []
        
        if results.multi_hand_landmarks:
            h, w, _ = frame.shape
            
            for hand_landmarks in results.multi_hand_landmarks:
                # 손바닥 중심 계산 (손목~중지 MCP 중간)
                # Landmark 0: 손목 (WRIST)
                # Landmark 9: 중지 MCP (MIDDLE_FINGER_MCP)
                wrist = hand_landmarks.landmark[0]
                middle_mcp = hand_landmarks.landmark[9]
                
                # 손바닥 중심 좌표
                cx = int((wrist.x + middle_mcp.x) / 2 * w)
                cy = int((wrist.y + middle_mcp.y) / 2 * h)
                
                hand_centers.append((cx, cy))
                landmarks_list.append(hand_landmarks)
                
                # 검지 끝 좌표 (Landmark 8: INDEX_FINGER_TIP)
                index_tip = hand_landmarks.landmark[8]
                index_x = int(index_tip.x * w)
                index_y = int(index_tip.y * h)
                index_finger_tips.append((index_x, index_y))
        
        # 탭 쿨다운 감소
        if self.tap_cooldown > 0:
            self.tap_cooldown -= 1
        
        # 손바닥 감지 (손가락 모두 펴짐)
        palm_detected = False
        palm_center = None
        
        # 핀치 감지 (손가락 상태도 확인)
        pinch_result = self._detect_pinch(landmarks_list, frame.shape[1], frame.shape[0])
        
        # 핀치가 활성화되지 않았을 때만 손바닥 감지 (상호 배제)
        if not pinch_result['active'] and results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                if self._is_palm_open(hand_landmarks):
                    palm_detected = True
                    # 손바닥 중심 계산
                    palm_center = self._get_palm_center(hand_landmarks, frame.shape[1], frame.shape[0])
                    break
        
        # 검지만 펴진 제스처 감지 (숫자 1)
        index_only_detected = False
        index_only_tip = None
        
        if not pinch_result['active'] and not palm_detected and results.multi_hand_landmarks:
            for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
                if self._is_index_only(hand_landmarks):
                    index_only_detected = True
                    # 검지 끝 좌표
                    if i < len(index_finger_tips):
                        index_only_tip = index_finger_tips[i]
                    break
        
        # 현재 감지된 제스처 로그 (디버그용)
        gesture = "없음"
        if pinch_result['active']:
            gesture = f"👌 핀치 (스케일: {pinch_result['scale']:.2f}x)"
        elif palm_detected:
            gesture = "🖐️ 손바닥"
        elif index_only_detected:
            gesture = "☝️ 검지"
        
        return {
            'hands_found': len(hand_centers) > 0,
            'hand_centers': hand_centers,
            'index_finger_tips': index_finger_tips,
            'landmarks': landmarks_list,
            'palm_detected': palm_detected,
            'palm_center': palm_center,
            'pinch_active': pinch_result['active'],
            'pinch_scale': pinch_result['scale'],
            'pinch_distance': pinch_result['distance'],
            'index_only_detected': index_only_detected,
            'index_only_tip': index_only_tip,
            'gesture': gesture
        }
    
    def _is_palm_open(self, hand_landmarks):
        """
        손바닥이 펴져있는지 확인 (모든 손가락이 펴짐)
        
        Args:
            hand_landmarks: MediaPipe 손 랜드마크
        
        Returns:
            bool: 손바닥이 펴져있으면 True
        """
        # 손가락 끝과 PIP(중간 관절) 랜드마크 인덱스
        # 손가락이 펴져있으면 TIP이 PIP보다 손목에서 더 멀리 있음
        
        landmarks = hand_landmarks.landmark
        
        # 손목 위치
        wrist = landmarks[0]
        
        # 각 손가락 확인 (엄지 제외 - 엄지는 다르게 체크)
        fingers_extended = []
        
        # 검지 (5=MCP, 6=PIP, 7=DIP, 8=TIP)
        # 손가락이 펴져있으면 TIP의 y가 PIP의 y보다 작음 (위쪽)
        fingers_extended.append(landmarks[8].y < landmarks[6].y)
        
        # 중지
        fingers_extended.append(landmarks[12].y < landmarks[10].y)
        
        # 약지
        fingers_extended.append(landmarks[16].y < landmarks[14].y)
        
        # 새끼
        fingers_extended.append(landmarks[20].y < landmarks[18].y)
        
        # 엄지 (x 좌표로 판단 - 오른손 기준)
        # 엄지가 펴져있으면 TIP이 MCP보다 바깥쪽
        thumb_extended = abs(landmarks[4].x - landmarks[2].x) > 0.05
        fingers_extended.append(thumb_extended)
        
        # 4개 이상의 손가락이 펴져있으면 손바닥
        extended_count = sum(fingers_extended)
        return extended_count >= 4
    
    def _is_index_only(self, hand_landmarks):
        """
        검지만 펴져있는지 확인 (숫자 1 제스처)
        
        Args:
            hand_landmarks: MediaPipe 손 랜드마크
        
        Returns:
            bool: 검지만 펴져있으면 True
        """
        landmarks = hand_landmarks.landmark
        
        # 검지: 펴져있어야 함 (TIP이 PIP보다 위)
        index_extended = landmarks[8].y < landmarks[6].y
        
        # 나머지 손가락: 접혀있어야 함 (TIP이 PIP보다 아래)
        middle_folded = landmarks[12].y > landmarks[10].y
        ring_folded = landmarks[16].y > landmarks[14].y
        pinky_folded = landmarks[20].y > landmarks[18].y
        
        # 엄지: 접혀있어야 함 (검지 쪽으로 향함)
        # 엄지 TIP과 검지 MCP 사이 거리가 가까워야 함
        thumb_folded = abs(landmarks[4].x - landmarks[2].x) < 0.08
        
        # 검지만 펴져있고, 나머지는 접혀있으면 True
        return index_extended and middle_folded and ring_folded and pinky_folded
    
    def _get_palm_center(self, hand_landmarks, width, height):
        """
        손바닥 중심 좌표 계산
        
        Args:
            hand_landmarks: MediaPipe 손 랜드마크
            width: 프레임 너비
            height: 프레임 높이
        
        Returns:
            tuple: (x, y) 손바닥 중심 좌표
        """
        landmarks = hand_landmarks.landmark
        
        # 손바닥 중심: MCP 관절들의 중심
        # 검지 MCP(5), 중지 MCP(9), 약지 MCP(13), 새끼 MCP(17)
        palm_x = (landmarks[5].x + landmarks[9].x + landmarks[13].x + landmarks[17].x) / 4
        palm_y = (landmarks[5].y + landmarks[9].y + landmarks[13].y + landmarks[17].y) / 4
        
        return (int(palm_x * width), int(palm_y * height))
    
    def _detect_pinch(self, landmarks_list, width, height):
        """
        핀치 제스처 감지 (엄지-검지 거리로 스케일 조절)
        
        핀치 조건:
        1. 엄지와 검지 끝이 가까움 (50px 이하)
        2. 나머지 손가락(중지, 약지, 새끼) 중 최소 2개가 접혀있음
        → 손바닥을 펴고 있을 때는 핀치로 인식되지 않음!
        
        Args:
            landmarks_list: MediaPipe 손 랜드마크 리스트
            width: 프레임 너비
            height: 프레임 높이
        
        Returns:
            dict: {
                'active': bool - 핀치 활성 상태
                'scale': float - 스케일 값 (1.0 기준)
                'distance': float - 엄지-검지 거리 (픽셀)
            }
        """
        if not landmarks_list:
            # 손이 없으면 핀치 해제
            if self.pinch_active:
                print("👌 핀치 해제 (손 없음)")
            self.pinch_active = False
            return {'active': False, 'scale': 1.0, 'distance': 0}
        
        # 첫 번째 손 사용
        hand_landmarks = landmarks_list[0]
        landmarks = hand_landmarks.landmark
        
        # 엄지 끝 (Landmark 4)
        thumb_tip = landmarks[4]
        thumb_x = thumb_tip.x * width
        thumb_y = thumb_tip.y * height
        
        # 검지 끝 (Landmark 8)
        index_tip = landmarks[8]
        index_x = index_tip.x * width
        index_y = index_tip.y * height
        
        # 엄지-검지 거리 계산
        dx = thumb_x - index_x
        dy = thumb_y - index_y
        distance = np.sqrt(dx * dx + dy * dy)
        
        # 나머지 손가락 상태 확인 (중지, 약지, 새끼)
        # 손가락이 접혀있으면 TIP의 y가 PIP의 y보다 큼 (아래쪽)
        middle_folded = landmarks[12].y > landmarks[10].y  # 중지
        ring_folded = landmarks[16].y > landmarks[14].y    # 약지
        pinky_folded = landmarks[20].y > landmarks[18].y   # 새끼
        
        folded_count = sum([middle_folded, ring_folded, pinky_folded])
        
        # 핀치 조건: 엄지-검지 가깝고 + 나머지 손가락 중 2개 이상 접혀있음
        is_pinch_gesture = distance < self.pinch_threshold and folded_count >= 2
        
        # 핀치 시작
        if is_pinch_gesture:
            if not self.pinch_active:
                # 핀치 시작!
                self.pinch_active = True
                self.pinch_start_distance = distance
                self.current_pinch_scale = 1.0
                print(f"👌 핀치 시작! 거리: {distance:.1f}px, 접힌 손가락: {folded_count}개")
        else:
            # 핀치 중이면 스케일 계산 (손가락 상태와 관계없이 계속)
            if self.pinch_active:
                # 거리 변화에 따른 스케일 계산
                # 거리가 멀어지면 확대, 가까워지면 축소
                # 기준: 100px = 2배, 200px = 3배, ...
                scale_factor = 1.0 + (distance - self.pinch_threshold) / 100.0
                self.current_pinch_scale = max(0.3, min(5.0, scale_factor))  # 0.3 ~ 5.0 제한
        
        # 핀치 비활성화 조건: 너무 멀어지거나 손바닥을 완전히 폄
        if self.pinch_active:
            # 조건 1: 거리가 너무 멀어짐
            if distance > 300:
                print(f"👌 핀치 해제! (거리 초과) 최종 스케일: {self.current_pinch_scale:.2f}")
                self.pinch_active = False
            # 조건 2: 모든 손가락이 펴짐 (손바닥 제스처로 전환)
            elif folded_count == 0:
                print(f"👌 핀치 해제! (손바닥으로 전환) 최종 스케일: {self.current_pinch_scale:.2f}")
                self.pinch_active = False
        
        return {
            'active': self.pinch_active,
            'scale': self.current_pinch_scale if self.pinch_active else 1.0,
            'distance': distance
        }
    
    def check_index_tap(self, index_finger_tips, rabbit_corners):
        """
        검지 끝이 토끼 영역을 탭했는지 감지
        
        Args:
            index_finger_tips: 검지 끝 좌표 리스트 [(x, y), ...]
            rabbit_corners: 토끼 프레임 4개 코너
        
        Returns:
            bool: 탭이 감지되었으면 True
        """
        if not index_finger_tips or rabbit_corners is None:
            self.last_index_finger_inside = False
            return False
        
        # 쿨다운 중이면 탭 무시
        if self.tap_cooldown > 0:
            return False
        
        # 검지 끝이 토끼 영역 안에 있는지 확인
        corners_np = np.array(rabbit_corners, dtype=np.float32)
        
        current_inside = False
        for (ix, iy) in index_finger_tips:
            distance = cv2.pointPolygonTest(corners_np, (ix, iy), True)
            if distance >= 0:  # 내부 또는 경계
                current_inside = True
                break
        
        # 탭 감지: 이전에 밖에 있다가 안으로 들어옴
        tap_detected = current_inside and not self.last_index_finger_inside
        
        # 상태 업데이트
        self.last_index_finger_inside = current_inside
        
        # 탭이 감지되면 쿨다운 설정 (약 0.5초, 15프레임)
        if tap_detected:
            self.tap_cooldown = 15
            print("👆 검지 탭 감지!")
        
        return tap_detected
    
    def check_collision(self, hand_centers, rabbit_corners, rabbit_center=None):
        """
        손과 토끼 애니메이션 충돌 감지
        
        Args:
            hand_centers: 손바닥 중심 좌표 리스트 [(x, y), ...]
            rabbit_corners: 토끼 프레임 4개 코너 [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
            rabbit_center: 토끼 중심 좌표 (x, y) (선택적)
        
        Returns:
            dict: {
                'collision': bool - 충돌 여부
                'collision_point': tuple (x, y) - 충돌한 손의 위치
                'rabbit_center': tuple (x, y) - 토끼 중심
            }
        """
        if not hand_centers or rabbit_corners is None:
            return {
                'collision': False,
                'collision_point': None,
                'rabbit_center': rabbit_center
            }
        
        # 토끼 중심이 제공되지 않았으면 코너로부터 계산
        if rabbit_center is None:
            rabbit_center_x = sum(corner[0] for corner in rabbit_corners) / 4
            rabbit_center_y = sum(corner[1] for corner in rabbit_corners) / 4
            rabbit_center = (rabbit_center_x, rabbit_center_y)
        
        # 각 손에 대해 충돌 검사
        for hand_center in hand_centers:
            hx, hy = hand_center
            
            # Point-in-Polygon 테스트 (토끼 프레임 내부인지 확인)
            # OpenCV의 pointPolygonTest 사용
            corners_np = np.array(rabbit_corners, dtype=np.float32)
            distance = cv2.pointPolygonTest(corners_np, (hx, hy), True)
            
            # 거리가 0 이상이면 내부 (0: 경계, >0: 내부, <0: 외부)
            # 손이 토끼 프레임 내부에 있을 때만 충돌로 인식
            if distance >= 0:  # 프레임 내부 또는 경계
                return {
                    'collision': True,
                    'collision_point': hand_center,
                    'rabbit_center': rabbit_center
                }
        
        return {
            'collision': False,
            'collision_point': None,
            'rabbit_center': rabbit_center
        }
    
    def draw_hands(self, frame, hand_centers):
        """
        프레임에 손 위치 그리기 (디버그용)
        
        Args:
            frame: 입력 프레임
            hand_centers: 손바닥 중심 좌표 리스트
        
        Returns:
            프레임 (손 위치 표시됨)
        """
        for cx, cy in hand_centers:
            # 손바닥 중심에 원 그리기
            cv2.circle(frame, (cx, cy), 15, (0, 255, 0), 3)
            cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
        
        return frame
    
    def draw_landmarks(self, frame, landmarks_list):
        """
        프레임에 손가락 관절(21개 랜드마크) 그리기 - 미니멀 스타일
        
        Args:
            frame: 입력 프레임
            landmarks_list: MediaPipe 손 랜드마크 리스트
        
        Returns:
            프레임 (손가락 관절 표시됨)
        """
        h, w, _ = frame.shape
        
        # 손가락 연결 정의 (MediaPipe Hand Connections)
        connections = [
            # 엄지
            (0, 1), (1, 2), (2, 3), (3, 4),
            # 검지
            (0, 5), (5, 6), (6, 7), (7, 8),
            # 중지
            (0, 9), (9, 10), (10, 11), (11, 12),
            # 약지
            (0, 13), (13, 14), (14, 15), (15, 16),
            # 새끼
            (0, 17), (17, 18), (18, 19), (19, 20),
            # 손바닥 가로 연결
            (5, 9), (9, 13), (13, 17)
        ]
        
        # 미니멀 스타일 색상 (흰색/연한 회색)
        line_color = (220, 220, 220)  # 연한 회색 선
        joint_color = (255, 255, 255)  # 흰색 관절
        tip_color = (255, 255, 255)    # 흰색 손가락 끝
        
        for hand_landmarks in landmarks_list:
            # 랜드마크 좌표 추출
            points = []
            for landmark in hand_landmarks.landmark:
                x = int(landmark.x * w)
                y = int(landmark.y * h)
                points.append((x, y))
            
            # 연결선 그리기 (얇은 흰색 선)
            for start_idx, end_idx in connections:
                cv2.line(frame, points[start_idx], points[end_idx], 
                        line_color, 1, cv2.LINE_AA)
            
            # 관절 포인트 그리기 (작은 흰색 점)
            for idx, (x, y) in enumerate(points):
                if idx in [4, 8, 12, 16, 20]:  # 손가락 끝
                    cv2.circle(frame, (x, y), 3, tip_color, -1, cv2.LINE_AA)
                else:
                    cv2.circle(frame, (x, y), 2, joint_color, -1, cv2.LINE_AA)
        
        return frame
    
    def release(self):
        """
        리소스 해제
        """
        if self.hands:
            self.hands.close()
    
    def __del__(self):
        """
        소멸자
        """
        self.release()
