"""
비디오 오버레이 모듈
탐지된 형태 위에 비디오를 증강현실 스타일로 오버레이합니다.
"""
import cv2
import numpy as np


class VideoOverlay:
    """
    비디오 오버레이 클래스
    - 원근 변환(Perspective Transform)을 사용한 비디오 워핑
    - 곱하기 블렌드 모드로 자연스러운 합성
    """
    
    def __init__(self, video_path):
        """
        초기화
        
        Args:
            video_path: 오버레이할 비디오 파일 경로
        """
        self.video_path = video_path
        self.video_capture = cv2.VideoCapture(video_path)
        
        if not self.video_capture.isOpened():
            raise ValueError(f"비디오 파일을 열 수 없습니다: {video_path}")
        
        # 비디오 정보
        self.video_width = int(self.video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.video_height = int(self.video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.video_capture.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
        
        self.current_frame_idx = 0
        self.current_video_frame = None
        
        # 좌우 반전 상태
        self.is_flipped = False
        
        # 첫 프레임 로드
        self._read_next_frame()
    
    def toggle_flip(self):
        """
        좌우 반전 토글
        """
        self.is_flipped = not self.is_flipped
        flip_status = "반전됨" if self.is_flipped else "원본"
        print(f"🔄 비디오 좌우 반전: {flip_status}")
    
    def _read_next_frame(self):
        """
        다음 비디오 프레임 읽기
        """
        ret, frame = self.video_capture.read()
        
        if not ret:
            # 비디오 끝에 도달하면 처음으로 돌아가기
            self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.video_capture.read()
            self.current_frame_idx = 0
        
        if ret:
            self.current_video_frame = frame
            self.current_frame_idx += 1
        
        return ret
    
    def overlay(self, base_frame, frame_corners):
        """
        비디오를 베이스 프레임에 오버레이
        
        Args:
            base_frame: 베이스 프레임 (BGR)
            frame_corners: 프레임 4개 코너 좌표 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                          (좌상단, 우상단, 우하단, 좌하단 순서)
        
        Returns:
            오버레이된 프레임
        """
        if self.current_video_frame is None:
            return base_frame
        
        # 다음 프레임 읽기
        self._read_next_frame()
        
        # 현재 비디오 프레임 (좌우 반전 적용)
        video_frame = self.current_video_frame.copy()
        if self.is_flipped:
            video_frame = cv2.flip(video_frame, 1)  # 1 = 좌우 반전
        
        # 소스 좌표 (비디오의 4개 코너)
        src_pts = np.float32([
            [0, 0],
            [self.video_width - 1, 0],
            [self.video_width - 1, self.video_height - 1],
            [0, self.video_height - 1]
        ])
        
        # 목적지 좌표 (탐지된 형태의 프레임 코너)
        dst_pts = np.float32(frame_corners)
        
        # 원근 변환 행렬 계산
        try:
            transform_matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
        except cv2.error:
            # 변환 실패 시 원본 반환
            return base_frame
        
        # 비디오 프레임 워핑
        frame_h, frame_w = base_frame.shape[:2]
        warped_video = cv2.warpPerspective(
            video_frame,
            transform_matrix,
            (frame_w, frame_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255)  # 흰색 배경
        )
        
        # 마스크 생성 (워핑된 영역)
        mask = cv2.warpPerspective(
            np.ones((self.video_height, self.video_width), dtype=np.uint8) * 255,
            transform_matrix,
            (frame_w, frame_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0,)
        )
        
        # 마스크를 3채널로 확장
        mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        
        # 곱하기 블렌드 모드 적용
        # result = (base_frame * warped_video) / 255
        base_float = base_frame.astype(np.float32)
        warped_float = warped_video.astype(np.float32)
        mask_float = mask_3ch.astype(np.float32) / 255.0
        
        # 블렌딩
        blended = (base_float * warped_float) / 255.0
        
        # 마스크 적용하여 오버레이 영역만 합성
        result = base_float.copy()
        result = result * (1 - mask_float) + blended * mask_float
        
        result = np.clip(result, 0, 255).astype(np.uint8)
        
        return result
    
    def set_frame(self, frame_idx):
        """
        특정 프레임으로 이동
        
        Args:
            frame_idx: 프레임 인덱스
        """
        frame_idx = max(0, min(frame_idx, self.total_frames - 1))
        self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        self.current_frame_idx = frame_idx
        self._read_next_frame()
    
    def reset(self):
        """
        비디오를 처음으로 리셋
        """
        self.set_frame(0)
    
    def release(self):
        """
        비디오 캡처 해제
        """
        if self.video_capture is not None:
            self.video_capture.release()
            self.video_capture = None
    
    def __del__(self):
        """
        소멸자
        """
        self.release()

