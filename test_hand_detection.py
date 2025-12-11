"""
손 감지 테스트 스크립트
MediaPipe가 손을 제대로 감지하는지 시각적으로 확인합니다.
"""
import cv2
import mediapipe as mp
import sys

def find_camera():
    """사용 가능한 카메라 찾기"""
    print("\n카메라 검색 중...")
    
    for index in range(5):  # 0~4번 카메라 시도
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)  # DirectShow 사용 (Windows)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                print(f"  ✅ 카메라 {index}번 발견!")
                return cap, index
            cap.release()
        else:
            print(f"  ❌ 카메라 {index}번 없음")
    
    return None, -1

def main():
    print("=" * 50)
    print("MediaPipe 손 감지 테스트")
    print("=" * 50)
    print("\n[조작법]")
    print("  - 'q' 키: 종료")
    print("  - 손을 웹캠에 보여주세요!")
    
    # MediaPipe Hands 초기화
    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles
    
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )
    
    # 사용 가능한 카메라 찾기
    cap, camera_index = find_camera()
    
    if cap is None:
        print("\n" + "=" * 50)
        print("웹캠을 찾을 수 없습니다!")
        print("=" * 50)
        print("\n[해결 방법]")
        print("  1. 웹캠이 연결되어 있는지 확인")
        print("  2. 다른 프로그램(브라우저, Zoom 등)에서 웹캠을 사용 중이면 종료")
        print("  3. 장치 관리자에서 카메라 드라이버 확인")
        print("\n아무 키나 누르면 종료...")
        input()
        return
    
    print(f"\n카메라 {camera_index}번 사용 중...")
    print("손을 카메라에 보여주세요!\n")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("프레임 읽기 실패")
            break
        
        # 좌우 반전 (거울 모드)
        frame = cv2.flip(frame, 1)
        
        # BGR -> RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 손 감지
        results = hands.process(rgb_frame)
        
        # 상태 표시
        h, w, _ = frame.shape
        
        if results.multi_hand_landmarks:
            hand_count = len(results.multi_hand_landmarks)
            
            # 손 랜드마크 그리기
            for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                # 21개 랜드마크와 연결선 그리기
                mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    mp_drawing_styles.get_default_hand_landmarks_style(),
                    mp_drawing_styles.get_default_hand_connections_style()
                )
                
                # 손바닥 중심 계산 (손목 + 중지 MCP 중간)
                wrist = hand_landmarks.landmark[0]
                middle_mcp = hand_landmarks.landmark[9]
                
                cx = int((wrist.x + middle_mcp.x) / 2 * w)
                cy = int((wrist.y + middle_mcp.y) / 2 * h)
                
                # 손바닥 중심에 큰 원 그리기
                cv2.circle(frame, (cx, cy), 20, (0, 255, 0), 3)
                cv2.circle(frame, (cx, cy), 8, (0, 0, 255), -1)
                
                # 손 번호 표시
                cv2.putText(frame, f"Hand {idx + 1}", (cx - 30, cy - 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                # 좌표 표시
                cv2.putText(frame, f"({cx}, {cy})", (cx - 40, cy + 40),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
            
            # 상태 메시지 (감지됨)
            status_text = f"DETECTED: {hand_count} hand(s)"
            cv2.rectangle(frame, (10, 10), (350, 60), (0, 150, 0), -1)
            cv2.putText(frame, status_text, (20, 45),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        else:
            # 상태 메시지 (감지 안됨)
            status_text = "NO HANDS DETECTED"
            cv2.rectangle(frame, (10, 10), (350, 60), (0, 0, 150), -1)
            cv2.putText(frame, status_text, (20, 45),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        # 안내 메시지
        cv2.putText(frame, "Press 'q' to quit", (10, h - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        
        # 화면 표시
        cv2.imshow('Hand Detection Test', frame)
        
        # 'q' 키로 종료
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # 정리
    cap.release()
    cv2.destroyAllWindows()
    hands.close()
    print("\n테스트 종료!")


if __name__ == '__main__':
    main()

