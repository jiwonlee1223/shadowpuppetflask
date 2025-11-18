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
        
    def detect(self, frame):
        """
        프레임에서 손 탐지 (MediaPipe 기반)
        
        Args:
            frame: 입력 프레임 (BGR)
        
        Returns:
            dict: {
                'hands_found': bool - 손을 찾았는지 여부
                'hand_centers': list - 손바닥 중심 좌표 리스트 [(x, y), ...]
                'landmarks': list - 손 랜드마크 리스트
            }
        """
        # BGR to RGB (MediaPipe는 RGB 사용)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 손 탐지
        results = self.hands.process(rgb_frame)
        
        hand_centers = []
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
        
        return {
            'hands_found': len(hand_centers) > 0,
            'hand_centers': hand_centers,
            'landmarks': landmarks_list
        }
    
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
