/**
 * WebSocket 핸들링 모듈
 * Socket.IO를 사용한 실시간 통신
 */

class SocketHandler {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.onStatusChange = null;
        this.onProcessedFrame = null;
        this.onError = null;
    }
    
    /**
     * Socket.IO 연결 초기화
     */
    connect() {
        this.socket = io();
        
        // 연결 이벤트
        this.socket.on('connect', () => {
            console.log('서버에 연결되었습니다.');
            this.isConnected = true;
            this.updateConnectionStatus(true);
        });
        
        // 연결 해제 이벤트
        this.socket.on('disconnect', () => {
            console.log('서버와의 연결이 끊어졌습니다.');
            this.isConnected = false;
            this.updateConnectionStatus(false);
        });
        
        // 상태 업데이트
        this.socket.on('status', (data) => {
            console.log('📡 서버 상태:', data);
            if (this.onStatusChange) {
                this.onStatusChange(data);
            }
        });
        
        // 처리된 프레임 수신
        this.socket.on('processed_frame', (data) => {
            if (this.onProcessedFrame) {
                this.onProcessedFrame(data);
            }
        });
        
        // 에러 수신
        this.socket.on('error', (data) => {
            console.error('서버 에러:', data.message);
            if (this.onError) {
                this.onError(data.message);
            }
        });
        
        // 명도/채도 조정 업데이트 확인
        this.socket.on('adjustment_updated', (data) => {
            console.log('✅ 명도/채도가 업데이트되었습니다.');
        });
        
        // 임계값 업데이트 확인
        this.socket.on('thresholds_updated', (data) => {
            console.log('임계값이 업데이트되었습니다.');
        });
        
        // 감지기 리셋 확인
        this.socket.on('detector_reset', (data) => {
            console.log('감지기가 리셋되었습니다.');
        });
    }
    
    /**
     * 연결 상태 UI 업데이트
     */
    updateConnectionStatus(connected) {
        const statusIcon = document.querySelector('#connection-status i');
        const statusText = document.getElementById('status-text');
        
        if (connected) {
            statusIcon.className = 'fas fa-circle text-success me-1';
            statusText.textContent = '연결됨';
        } else {
            statusIcon.className = 'fas fa-circle text-danger me-1';
            statusText.textContent = '연결 끊김';
        }
    }
    
    /**
     * 비디오 프레임 전송
     * @param {string} base64Image - Base64 인코딩된 이미지
     */
    sendFrame(base64Image) {
        if (!this.isConnected) {
            console.warn('서버에 연결되지 않았습니다.');
            return;
        }
        
        this.socket.emit('video_frame', {
            image: base64Image
        });
    }
    
    /**
     * 명도/채도 조정 파라미터 전송
     * @param {object} adjustment - 명도/채도 파라미터
     */
    setAdjustment(adjustment) {
        if (!this.isConnected) {
            console.warn('서버에 연결되지 않았습니다.');
            return;
        }
        
        this.socket.emit('set_adjustment', adjustment);
    }
    
    /**
     * 임계값 설정 전송
     * @param {object} thresholds - 임계값 파라미터
     */
    setThresholds(thresholds) {
        if (!this.isConnected) {
            console.warn('서버에 연결되지 않았습니다.');
            return;
        }
        
        this.socket.emit('set_thresholds', thresholds);
    }
    
    /**
     * 감지기 리셋 요청
     */
    resetDetector() {
        if (!this.isConnected) {
            console.warn('서버에 연결되지 않았습니다.');
            return;
        }
        
        this.socket.emit('reset_detector');
    }
    
    /**
     * 연결 끊기
     */
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
        }
    }
}

// 전역 인스턴스
const socketHandler = new SocketHandler();

