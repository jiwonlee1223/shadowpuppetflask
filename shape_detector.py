"""
형태 감지 모듈
OpenCV의 Hu Moments 기반 형태 매칭을 사용하여 실시간으로 특정 형태를 탐지합니다.
"""
import cv2
import numpy as np
import time


class ShapeDetector:
    """
    실시간 형태 탐지 클래스
    - Hu Moments 기반 형태 매칭
    - 히스테리시스 기반 잠금 메커니즘
    - 지수 이동 평균(EMA)을 사용한 부드러운 추적
    - 명도/채도 조정
    """
    
    def __init__(self, reference_image_path):
        """
        초기화
        
        Args:
            reference_image_path: 참조 이미지 경로 (탐지할 형태)
        """
        # 참조 이미지 로드
        self.reference_image = cv2.imread(reference_image_path)
        if self.reference_image is None:
            raise ValueError(f"참조 이미지를 로드할 수 없습니다: {reference_image_path}")
        
        # 참조 윤곽선 추출
        self.reference_contour = self._extract_reference_contour()
        if self.reference_contour is None:
            raise ValueError("참조 이미지에서 유효한 윤곽선을 찾을 수 없습니다")
        
        # 명도/채도 조정 파라미터
        self.brightness = 0  # -100 ~ +100
        self.saturation = 0  # -100 ~ +100
        
        # 히스테리시스 파라미터
        self.threshold_enter = 0.25  # 잠금 진입 임계값 (낮을수록 엄격)
        self.threshold_exit = 0.50   # 잠금 해제 임계값 (더 관대함)
        self.lock_count_enter = 12   # 잠금 진입 필요 프레임 수
        self.lock_count_exit = 8     # 잠금 해제 필요 프레임 수
        
        # 잠금 상태
        self.is_locked = False
        self.good_frames = 0
        self.bad_frames = 0
        
        # 영구 활성화 (3초 이상 탐지 시)
        self.permanent_activation_time = 3.0  # 3초
        self.locked_start_time = None
        self.is_permanently_active = False
        self.last_valid_result = None  # 마지막 유효한 탐지 결과 저장
        
        # 애니메이션 잡기 및 드래그 (손 인터랙션)
        self.drag_offset_x = 0.0  # X축 드래그 오프셋
        self.drag_offset_y = 0.0  # Y축 드래그 오프셋
        self.is_grabbed = False  # 잡혔는지 여부
        self.grab_hand_position = None  # 잡은 손의 위치
        self.last_hand_position = None  # 마지막 손 위치 (부드러운 이동)
        self.drag_smoothing = 0.3  # 드래그 스무딩 계수 (0~1, 낮을수록 부드러움)
        self.is_pushed_off_screen = False  # 화면 밖으로 나갔는지 여부
        self.screen_width = 640  # 화면 너비 (초기값)
        self.screen_height = 480  # 화면 높이 (초기값)
        
        # 부드러운 추적을 위한 EMA
        self.smoothed_cx = None
        self.smoothed_cy = None
        self.smoothed_angle = None
        self.smoothed_scale = None
        self.smoothed_frame_cx = None
        self.smoothed_frame_cy = None
        
        self.alpha = 0.3          # 일반 EMA 계수
        self.alpha_frame = 0.5    # 프레임 중심 EMA 계수 (더 부드럽게)
    
    def _extract_reference_contour(self):
        """
        참조 이미지에서 가장 큰 윤곽선 추출
        
        Returns:
            참조 윤곽선 (numpy array)
        """
        gray = cv2.cvtColor(self.reference_image, cv2.COLOR_BGR2GRAY)
        
        # 적응형 임계값
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )
        
        # 모폴로지 연산으로 노이즈 제거
        kernel = np.ones((3, 3), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
        
        # 윤곽선 찾기
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
        
        # 가장 큰 윤곽선 반환
        return max(contours, key=cv2.contourArea)
    
    def apply_brightness_saturation(self, image):
        """
        명도/채도 조정 적용
        
        Args:
            image: 입력 이미지 (BGR 컬러 또는 그레이스케일)
        
        Returns:
            조정된 이미지
        """
        # 조정 값이 기본값이면 원본 반환
        if self.brightness == 0 and self.saturation == 0:
            return image
        
        # 그레이스케일이면 명도만 조정
        if len(image.shape) == 2:
            # 명도 조정 (단순 덧셈)
            if self.brightness != 0:
                img = image.astype(np.float32)
                img = img + self.brightness
                img = np.clip(img, 0, 255)
                return img.astype(np.uint8)
            return image
        
        # 컬러 이미지: HSV로 변환하여 조정
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)
        
        # 채도 조정 (S 채널)
        if self.saturation != 0:
            # -100 ~ +100을 0.0 ~ 2.0 배율로 변환
            sat_scale = 1.0 + (self.saturation / 100.0)
            hsv[:, :, 1] = hsv[:, :, 1] * sat_scale
            hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
        
        # 명도 조정 (V 채널)
        if self.brightness != 0:
            hsv[:, :, 2] = hsv[:, :, 2] + self.brightness
            hsv[:, :, 2] = np.clip(hsv[:, :, 2], 0, 255)
        
        # BGR로 다시 변환
        hsv = hsv.astype(np.uint8)
        result = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        
        return result
    
    def set_adjustment(self, brightness=None, saturation=None):
        """
        명도/채도 조정 파라미터 설정
        
        Args:
            brightness: 명도 (-100 ~ +100)
            saturation: 채도 (-100 ~ +100)
        """
        if brightness is not None:
            self.brightness = max(-100, min(100, int(brightness)))
        if saturation is not None:
            self.saturation = max(-100, min(100, int(saturation)))
    
    def apply_grab(self, hand_position, rabbit_center):
        """
        손으로 토끼 잡기
        
        Args:
            hand_position: 손의 현재 위치 (x, y)
            rabbit_center: 토끼의 중심 위치 (x, y)
        """
        if not self.is_grabbed:
            # 처음 잡을 때
            self.is_grabbed = True
            self.grab_hand_position = hand_position
            self.last_hand_position = hand_position
            print("🐰 토끼를 잡았습니다!")
        else:
            # 이미 잡고 있을 때 - 손의 이동량만큼 토끼 이동
            if self.last_hand_position:
                # 손의 이동량 계산
                delta_x = hand_position[0] - self.last_hand_position[0]
                delta_y = hand_position[1] - self.last_hand_position[1]
                
                # 부드러운 이동 (스무딩 적용)
                self.drag_offset_x += delta_x * self.drag_smoothing
                self.drag_offset_y += delta_y * self.drag_smoothing
            
            # 현재 손 위치 저장
            self.last_hand_position = hand_position
            self.grab_hand_position = hand_position
    
    def release_grab(self):
        """
        토끼 놓기
        """
        if self.is_grabbed:
            self.is_grabbed = False
            self.grab_hand_position = None
            self.last_hand_position = None
            print("🐰 토끼를 놓았습니다!")
    
    def update_drag_physics(self):
        """
        드래그 물리 업데이트 (매 프레임마다 호출)
        """
        # 화면 밖으로 나갔는지 확인
        if (abs(self.drag_offset_x) > self.screen_width or 
            abs(self.drag_offset_y) > self.screen_height):
            self.is_pushed_off_screen = True
    
    def detect(self, frame, hand_collision_data=None):
        """
        프레임에서 형태 탐지
        
        Args:
            frame: 입력 프레임 (BGR)
            hand_collision_data: 손 충돌 데이터 (선택적)
                {
                    'collision': bool,
                    'collision_point': tuple (x, y),
                    'rabbit_center': tuple (x, y)  # 추가
                }
        
        Returns:
            dict: {
                'found': bool - 형태를 찾았는지 여부
                'contour': numpy array - 탐지된 윤곽선
                'center': tuple - 중심점 (cx, cy)
                'angle': float - 회전 각도
                'scale': float - 스케일
                'score': float - 매칭 점수
                'frame_corners': list - 프레임 4개 코너 좌표
                'is_locked': bool - 잠금 상태
                'drag_offset': tuple - 드래그 오프셋 (x, y)
                'is_grabbed': bool - 잡힌 상태
                'is_pushed_off_screen': bool - 화면 밖 여부
            }
        """
        # 화면 크기 업데이트
        self.screen_height, self.screen_width = frame.shape[:2]
        
        # 손 잡기/드래그 처리
        if hand_collision_data and hand_collision_data.get('collision'):
            # 손이 토끼에 닿아있음 - 잡기
            hand_pos = hand_collision_data.get('collision_point')
            rabbit_center = hand_collision_data.get('rabbit_center')
            if hand_pos and rabbit_center:
                self.apply_grab(hand_pos, rabbit_center)
        else:
            # 손이 토끼에서 멀어짐 - 놓기
            if self.is_grabbed:
                self.release_grab()
        
        # 드래그 물리 업데이트
        self.update_drag_physics()
        # 그레이스케일 변환
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 가우시안 블러로 노이즈 제거 (커널 크기 축소 - 속도 향상)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        
        # 적응형 임계값
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )
        
        # 모폴로지 연산 (반복 횟수 줄임 - 속도 향상)
        kernel = np.ones((3, 3), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
        # MORPH_OPEN 생략 (속도 향상)
        
        # 윤곽선 찾기
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return self._no_detection_result()
        
        # 필터링 및 매칭
        best_match = None
        best_score = float('inf')
        
        frame_h, frame_w = frame.shape[:2]
        max_area = frame_h * frame_w * 0.5  # 프레임의 50%
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # 면적 필터
            if area < 2000 or area > max_area:
                continue
            
            # 종횡비 필터
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / float(h) if h > 0 else 0
            if aspect_ratio < 0.5 or aspect_ratio > 2.0:
                continue
            
            # 형태 매칭
            score = cv2.matchShapes(self.reference_contour, contour, cv2.CONTOURS_MATCH_I3, 0)
            
            if score < best_score:
                best_score = score
                best_match = contour
        
        # 히스테리시스 적용
        if best_match is not None:
            if not self.is_locked:
                # 잠금 해제 상태
                if best_score < self.threshold_enter:
                    self.good_frames += 1
                    if self.good_frames >= self.lock_count_enter:
                        self.is_locked = True
                        self.bad_frames = 0
                        # 잠금 시작 시간 기록
                        self.locked_start_time = time.time()
                else:
                    self.good_frames = 0
            else:
                # 잠금 상태
                if best_score > self.threshold_exit:
                    self.bad_frames += 1
                    if self.bad_frames >= self.lock_count_exit:
                        # 영구 활성화 모드가 아니면 잠금 해제
                        if not self.is_permanently_active:
                            self.is_locked = False
                            self.good_frames = 0
                            self.locked_start_time = None
                else:
                    self.bad_frames = 0
                
                # 3초 이상 잠금 상태 유지 시 영구 활성화
                if self.locked_start_time is not None:
                    elapsed = time.time() - self.locked_start_time
                    if elapsed >= self.permanent_activation_time:
                        self.is_permanently_active = True
        else:
            # 매칭 실패
            if self.is_locked:
                self.bad_frames += 1
                if self.bad_frames >= self.lock_count_exit:
                    # 영구 활성화 모드가 아니면 잠금 해제
                    if not self.is_permanently_active:
                        self.is_locked = False
                        self.good_frames = 0
                        self.locked_start_time = None
            else:
                self.good_frames = 0
        
        # 영구 활성화 모드: 마지막 유효한 결과 반환
        if self.is_permanently_active:
            if best_match is not None and self.is_locked:
                # 새로운 탐지 결과 저장
                result = self._extract_shape_info(best_match, best_score, frame.shape)
                result['is_locked'] = self.is_locked
                result['is_permanently_active'] = True
                self.last_valid_result = result
                return result
            elif self.last_valid_result is not None:
                # 탐지 실패 시 마지막 결과 반환
                return self.last_valid_result
        
        # 일반 모드: 잠금 상태가 아니면 탐지 결과 없음
        if not self.is_locked or best_match is None:
            return self._no_detection_result()
        
        # 탐지 성공 - 정보 추출
        result = self._extract_shape_info(best_match, best_score, frame.shape)
        result['is_locked'] = self.is_locked
        result['is_permanently_active'] = False
        
        return result
    
    def _extract_shape_info(self, contour, score, frame_shape):
        """
        탐지된 형태에서 정보 추출
        
        Args:
            contour: 윤곽선
            score: 매칭 점수
            frame_shape: 프레임 크기
        
        Returns:
            dict: 탐지 정보
        """
        # 모멘트 계산
        M = cv2.moments(contour)
        if M['m00'] == 0:
            return self._no_detection_result()
        
        # 중심점
        cx = M['m10'] / M['m00']
        cy = M['m01'] / M['m00']
        
        # 회전 각도
        angle = 0.5 * np.arctan2(2 * M['mu11'], M['mu20'] - M['mu02'])
        angle_deg = np.degrees(angle)
        
        # 스케일 계산
        ref_M = cv2.moments(self.reference_contour)
        ref_area = ref_M['m00']
        curr_area = M['m00']
        scale = np.sqrt(curr_area / ref_area) if ref_area > 0 else 1.0
        
        # 부드러운 추적 (EMA)
        if self.smoothed_cx is None:
            # 초기화
            self.smoothed_cx = cx
            self.smoothed_cy = cy
            self.smoothed_angle = angle_deg
            self.smoothed_scale = scale
        else:
            # EMA 적용
            self.smoothed_cx = self.alpha * cx + (1 - self.alpha) * self.smoothed_cx
            self.smoothed_cy = self.alpha * cy + (1 - self.alpha) * self.smoothed_cy
            self.smoothed_scale = self.alpha * scale + (1 - self.alpha) * self.smoothed_scale
            
            # 각도는 순환 평균
            angle_diff = angle_deg - self.smoothed_angle
            if angle_diff > 180:
                angle_diff -= 360
            elif angle_diff < -180:
                angle_diff += 360
            self.smoothed_angle += self.alpha * angle_diff
        
        # 프레임 코너 계산 (참조 이미지 비율 사용)
        # 상단:토끼:하단 = 100:294:38
        # 좌:토끼:우 = 207:364:200
        ref_h, ref_w = self.reference_image.shape[:2]
        
        # 토끼의 바운딩 박스
        rabbit_x, rabbit_y, rabbit_w, rabbit_h = cv2.boundingRect(self.reference_contour)
        
        # 프레임 크기 계산
        frame_w = rabbit_w + 207 + 200  # 좌 + 토끼 + 우
        frame_h = rabbit_h + 100 + 38   # 상 + 토끼 + 하
        
        # 프레임 중심 (부드러운 추적)
        frame_cx_raw = self.smoothed_cx
        frame_cy_raw = self.smoothed_cy
        
        if self.smoothed_frame_cx is None:
            self.smoothed_frame_cx = frame_cx_raw
            self.smoothed_frame_cy = frame_cy_raw
        else:
            self.smoothed_frame_cx = self.alpha_frame * frame_cx_raw + (1 - self.alpha_frame) * self.smoothed_frame_cx
            self.smoothed_frame_cy = self.alpha_frame * frame_cy_raw + (1 - self.alpha_frame) * self.smoothed_frame_cy
        
        # 프레임 4개 코너 (스케일 적용)
        scaled_frame_w = frame_w * self.smoothed_scale
        scaled_frame_h = frame_h * self.smoothed_scale
        
        half_w = scaled_frame_w / 2
        half_h = scaled_frame_h / 2
        
        # 회전 행렬
        angle_rad = np.radians(self.smoothed_angle)
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)
        
        # 4개 코너 (회전 적용)
        corners = []
        for dx, dy in [(-half_w, -half_h), (half_w, -half_h), 
                       (half_w, half_h), (-half_w, half_h)]:
            # 회전
            rx = dx * cos_a - dy * sin_a
            ry = dx * sin_a + dy * cos_a
            # 이동
            corners.append([
                self.smoothed_frame_cx + rx,
                self.smoothed_frame_cy + ry
            ])
        
        # 드래그 오프셋 적용
        dragged_corners = []
        for corner in corners:
            dragged_corners.append([
                corner[0] + self.drag_offset_x,
                corner[1] + self.drag_offset_y
            ])
        
        return {
            'found': True,
            'contour': contour,
            'center': (self.smoothed_cx + self.drag_offset_x, 
                      self.smoothed_cy + self.drag_offset_y),
            'angle': self.smoothed_angle,
            'scale': self.smoothed_scale,
            'score': score,
            'frame_corners': dragged_corners,
            'is_locked': True,
            'drag_offset': (self.drag_offset_x, self.drag_offset_y),
            'is_grabbed': self.is_grabbed,
            'is_pushed_off_screen': self.is_pushed_off_screen
        }
    
    def _no_detection_result(self):
        """
        탐지 실패 결과 반환
        """
        return {
            'found': False,
            'contour': None,
            'center': None,
            'angle': None,
            'scale': None,
            'score': None,
            'frame_corners': None,
            'is_locked': self.is_locked,
            'is_permanently_active': self.is_permanently_active,
            'drag_offset': (self.drag_offset_x, self.drag_offset_y),
            'is_grabbed': self.is_grabbed,
            'is_pushed_off_screen': self.is_pushed_off_screen
        }
    
    def reset(self):
        """
        추적 상태 리셋
        """
        self.is_locked = False
        self.good_frames = 0
        self.bad_frames = 0
        self.smoothed_cx = None
        self.smoothed_cy = None
        self.smoothed_angle = None
        self.smoothed_scale = None
        self.smoothed_frame_cx = None
        self.smoothed_frame_cy = None
        # 영구 활성화 모드 리셋
        self.is_permanently_active = False
        self.locked_start_time = None
        self.last_valid_result = None
        # 드래그 효과 리셋
        self.drag_offset_x = 0.0
        self.drag_offset_y = 0.0
        self.is_grabbed = False
        self.grab_hand_position = None
        self.last_hand_position = None
        self.is_pushed_off_screen = False

