"""
손 탐지 모듈
OpenCV 기반 피부색 탐지를 사용하여 실시간으로 손을 탐지합니다.
"""
import cv2
import numpy as np


class HandDetector:
    """
    실시간 손 탐지 클래스
    - OpenCV 피부색 탐지 기반
    - 손바닥 중심 좌표 추출
    - 충돌 감지
    """
    
    def __init__(self):
        """
        초기화
        """
        # 피부색 범위 (HSV)
        self.lower_skin = np.array([0, 20, 70], dtype=np.uint8)
        self.upper_skin = np.array([20, 255, 255], dtype=np.uint8)
        
    def detect(self, frame):
        """
        프레임에서 손 탐지 (피부색 기반)
        
        Args:
            frame: 입력 프레임 (BGR)
        
        Returns:
            dict: {
                'hands_found': bool - 손을 찾았는지 여부
                'hand_centers': list - 손바닥 중심 좌표 리스트 [(x, y), ...]
                'landmarks': list - 빈 리스트 (호환성)
            }
        """
        # BGR to HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # 피부색 마스크 생성
        mask = cv2.inRange(hsv, self.lower_skin, self.upper_skin)
        
        # 노이즈 제거
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        
        # 가우시안 블러
        mask = cv2.GaussianBlur(mask, (5, 5), 0)
        
        # 윤곽선 찾기
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        hand_centers = []
        
        if contours:
            # 가장 큰 2개 윤곽선을 손으로 간주
            sorted_contours = sorted(contours, key=cv2.contourArea, reverse=True)[:2]
            
            for contour in sorted_contours:
                area = cv2.contourArea(contour)
                
                # 최소 면적 필터 (손 크기)
                if area > 3000:
                    # 윤곽선 중심 계산
                    M = cv2.moments(contour)
                    if M['m00'] != 0:
                        cx = int(M['m10'] / M['m00'])
                        cy = int(M['m01'] / M['m00'])
                        hand_centers.append((cx, cy))
        
        return {
            'hands_found': len(hand_centers) > 0,
            'hand_centers': hand_centers,
            'landmarks': []  # 호환성을 위한 빈 리스트
        }
    
    def check_collision(self, hand_centers, rabbit_corners, rabbit_center=None):
        """
        손과 토끼 영역의 충돌 감지
        
        Args:
            hand_centers: 손바닥 중심 좌표 리스트 [(x, y), ...]
            rabbit_corners: 토끼 영역의 4개 코너 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            rabbit_center: 토끼 중심 좌표 (선택적)
        
        Returns:
            dict: {
                'collision': bool - 충돌 여부
                'collision_point': tuple - 충돌한 손의 좌표 (x, y) 또는 None
                'rabbit_center': tuple - 토끼 중심 좌표 (x, y) 또는 None
            }
        """
        if not hand_centers or rabbit_corners is None:
            return {
                'collision': False,
                'collision_point': None,
                'rabbit_center': None
            }
        
        # 토끼 영역의 중심 계산
        if rabbit_center is None:
            rabbit_center_x = sum([c[0] for c in rabbit_corners]) / 4
            rabbit_center_y = sum([c[1] for c in rabbit_corners]) / 4
            rabbit_center = (rabbit_center_x, rabbit_center_y)
        else:
            rabbit_center_x, rabbit_center_y = rabbit_center
        
        # 토끼 영역의 바운딩 박스 계산
        x_coords = [c[0] for c in rabbit_corners]
        y_coords = [c[1] for c in rabbit_corners]
        
        min_x = min(x_coords)
        max_x = max(x_coords)
        min_y = min(y_coords)
        max_y = max(y_coords)
        
        # 각 손에 대해 충돌 검사
        for hand_center in hand_centers:
            hx, hy = hand_center
            
            # 바운딩 박스 내부에 있는지 확인
            if min_x <= hx <= max_x and min_y <= hy <= max_y:
                # 충돌 발생! 손이 토끼를 잡음
                return {
                    'collision': True,
                    'collision_point': hand_center,
                    'rabbit_center': rabbit_center
                }
        
        return {
            'collision': False,
            'collision_point': None,
            'rabbit_center': None
        }
    
    def draw_hands(self, frame, hand_centers):
        """
        프레임에 손 중심점 그리기 (디버그용)
        
        Args:
            frame: 입력 프레임 (BGR)
            hand_centers: 손 중심 좌표 리스트
        
        Returns:
            손 그림이 그려진 프레임
        """
        for center in hand_centers:
            # 손 중심에 원 그리기
            cv2.circle(frame, center, 20, (0, 255, 0), 3)
            cv2.circle(frame, center, 5, (0, 0, 255), -1)
        
        return frame
    
    def release(self):
        """
        리소스 해제 (호환성)
        """
        pass
    
    def __del__(self):
        """
        소멸자
        """
        self.release()

