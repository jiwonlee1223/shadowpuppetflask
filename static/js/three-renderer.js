/**
 * Three.js 3D 렌더러
 * GLB 모델 로드, 애니메이션 재생, 웹캠 합성
 */

class ThreeRenderer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error('컨테이너를 찾을 수 없습니다:', containerId);
            return;
        }
        
        // Three.js 기본 요소
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.model = null;
        this.pivot = null;  // 피벗 그룹 (이동용)
        this.mixer = null;  // 애니메이션 믹서
        this.clock = new THREE.Clock();
        
        // 모델 상태
        this.isLoaded = false;
        this.isFlipped = false;
        
        // 모델 위치/스케일
        this.modelPosition = { x: 0, y: 0, z: 0 };
        this.modelScale = 1.0;
        this.modelRotation = { x: 0, y: 0, z: 0 };
        this.baseScale = 1.0;
        
        // 애니메이션
        this.animations = {};
        this.currentAction = null;
        this.currentAnimName = '';  // 현재 애니메이션 이름
        
        // 디버그 UI 생성
        this.createDebugUI();
        
        // 이동 상태
        this.isRunning = false;         // 달리는 중인지
        this.runTarget = { x: 0, y: 0 }; // 목표 위치
        this.runSpeed = 0.2;            // 달리기 속도
        this.facingDirection = 1;       // 바라보는 방향 (1: 오른쪽, -1: 왼쪽)
        this.hasEntered = false;        // 초기화 완료 여부
        this.isPalmTarget = false;      // 손바닥으로 이동 중인지
        this.palmCooldown = 0;          // 손바닥 감지 쿨다운
        this.isPalmVisible = false;     // 현재 손바닥이 보이는지
        this.wasOnPalm = false;         // 손바닥 위에 있었는지
        
        // 초기화
        this.init();
    }
    
    /**
     * Three.js 씬 초기화
     */
    init() {
        // 컨테이너 크기 (이미지와 동일하게)
        const outputImage = document.getElementById('output-image');
        let width = this.container.clientWidth || 640;
        let height = this.container.clientHeight || 480;
        
        // 이미지가 있으면 그 크기 사용
        if (outputImage && outputImage.clientWidth > 0) {
            width = outputImage.clientWidth;
            height = outputImage.clientHeight;
        }
        
        console.log(`📐 Three.js 컨테이너 크기: ${width}x${height}`);
        
        // 씬 생성
        this.scene = new THREE.Scene();
        // 투명 배경 (웹캠과 합성하기 위해)
        this.scene.background = null;
        
        // 카메라 (원근 카메라) - 더 넓은 시야
        this.camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
        this.camera.position.z = 15;  // 카메라를 더 멀리 배치
        
        // 렌더러 (투명 배경 활성화)
        this.renderer = new THREE.WebGLRenderer({ 
            alpha: true,  // 투명 배경
            antialias: true 
        });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.renderer.setClearColor(0x000000, 0);  // 완전 투명
        
        // 캔버스를 컨테이너에 추가
        this.renderer.domElement.style.position = 'absolute';
        this.renderer.domElement.style.top = '0';
        this.renderer.domElement.style.left = '0';
        this.renderer.domElement.style.width = '100%';
        this.renderer.domElement.style.height = '100%';
        this.renderer.domElement.style.pointerEvents = 'none';  // 클릭 이벤트 통과
        this.renderer.domElement.style.zIndex = '10';  // 웹캠 이미지 위에 표시
        this.container.appendChild(this.renderer.domElement);
        
        // 조명 추가
        this.addLights();
        
        // 디버그 헬퍼 추가 (경계 표시)
        this.addDebugHelpers();
        
        // 윈도우 리사이즈 핸들러
        window.addEventListener('resize', () => this.onWindowResize());
        
        // 이미지 로드 시 크기 재조정
        if (outputImage) {
            outputImage.addEventListener('load', () => this.onWindowResize());
        }
        
        // 애니메이션 루프 시작
        this.animate();
        
        console.log('✅ Three.js 렌더러 초기화 완료');
    }
    
    /**
     * 디버그 UI 생성
     */
    createDebugUI() {
        // 디버그 패널 생성
        const debugPanel = document.createElement('div');
        debugPanel.id = 'cat-debug-panel';
        debugPanel.style.cssText = `
            position: fixed;
            top: 10px;
            left: 10px;
            background: rgba(0, 0, 0, 0.8);
            color: #00ff00;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            padding: 10px 15px;
            border-radius: 8px;
            z-index: 9999;
            min-width: 200px;
        `;
        debugPanel.innerHTML = `
            <div style="font-weight: bold; margin-bottom: 5px;">🐱 Cat Debug</div>
            <div>애니메이션: <span id="debug-anim-name">-</span></div>
            <div>상태: <span id="debug-state">대기</span></div>
            <div>위치: <span id="debug-position">-</span></div>
            <div>손바닥 보임: <span id="debug-palm-visible">❌</span></div>
            <div>손바닥 위: <span id="debug-on-palm">❌</span></div>
        `;
        document.body.appendChild(debugPanel);
        
        console.log('🔧 디버그 UI 생성됨');
    }
    
    /**
     * 디버그 UI 업데이트
     */
    updateDebugUI() {
        const animName = document.getElementById('debug-anim-name');
        const state = document.getElementById('debug-state');
        const position = document.getElementById('debug-position');
        const palmVisible = document.getElementById('debug-palm-visible');
        const onPalm = document.getElementById('debug-on-palm');
        
        if (animName) animName.textContent = this.currentAnimName || '-';
        if (state) {
            if (this.isRunning) {
                state.textContent = this.isPalmTarget ? '🖐️ 손바닥으로 이동' : '👆 탭 위치로 이동';
                state.style.color = '#ffff00';
            } else if (this.wasOnPalm) {
                state.textContent = '🖐️ 손바닥 위 대기';
                state.style.color = '#ff66ff';
            } else {
                state.textContent = '😺 대기';
                state.style.color = '#00ff00';
            }
        }
        if (position) {
            position.textContent = `(${this.modelPosition.x.toFixed(1)}, ${this.modelPosition.y.toFixed(1)})`;
        }
        if (palmVisible) {
            palmVisible.textContent = this.isPalmVisible ? '✅' : '❌';
            palmVisible.style.color = this.isPalmVisible ? '#00ff00' : '#ff6666';
        }
        if (onPalm) {
            onPalm.textContent = this.wasOnPalm ? '✅' : '❌';
            onPalm.style.color = this.wasOnPalm ? '#00ff00' : '#ff6666';
        }
    }
    
    /**
     * 조명 추가
     */
    addLights() {
        // 환경광 (전체적으로 밝게) - 강도 높임!
        const ambientLight = new THREE.AmbientLight(0xffffff, 1.5);
        this.scene.add(ambientLight);
        
        // 방향광 (메인 조명)
        const directionalLight = new THREE.DirectionalLight(0xffffff, 1.2);
        directionalLight.position.set(5, 10, 7.5);
        this.scene.add(directionalLight);
        
        // 반대편 보조광
        const fillLight = new THREE.DirectionalLight(0xffffff, 0.8);
        fillLight.position.set(-5, 5, -5);
        this.scene.add(fillLight);
        
        // 아래에서 위로 비추는 보조광 (그림자 완화)
        const bottomLight = new THREE.DirectionalLight(0xffffff, 0.5);
        bottomLight.position.set(0, -5, 5);
        this.scene.add(bottomLight);
    }
    
    /**
     * 🔧 디버그 헬퍼 추가 (경계 표시)
     */
    addDebugHelpers() {
        // 축 표시 (빨강=X, 초록=Y, 파랑=Z)
        const axesHelper = new THREE.AxesHelper(5);
        this.scene.add(axesHelper);
        
        // 원점에 구체 표시
        const originGeometry = new THREE.SphereGeometry(0.3, 16, 16);
        const originMaterial = new THREE.MeshBasicMaterial({ color: 0xffff00 });
        const originSphere = new THREE.Mesh(originGeometry, originMaterial);
        originSphere.position.set(0, 0, 0);
        this.scene.add(originSphere);
        
        // 경계 표시 (사각형 테두리)
        const boundaryMaterial = new THREE.LineBasicMaterial({ color: 0x00ff00, linewidth: 2 });
        
        // 경계 좌표
        const minX = -15, maxX = 15;
        const minY = -8, maxY = 8;
        
        // 사각형 테두리
        const boundaryPoints = [
            new THREE.Vector3(minX, minY, 0),
            new THREE.Vector3(maxX, minY, 0),
            new THREE.Vector3(maxX, maxY, 0),
            new THREE.Vector3(minX, maxY, 0),
            new THREE.Vector3(minX, minY, 0)  // 닫기
        ];
        const boundaryGeometry = new THREE.BufferGeometry().setFromPoints(boundaryPoints);
        const boundaryLine = new THREE.Line(boundaryGeometry, boundaryMaterial);
        this.scene.add(boundaryLine);
        
        // 코너에 위치 표시 구체
        const cornerPositions = [
            { x: minX, y: minY, label: '좌하' },
            { x: maxX, y: minY, label: '우하' },
            { x: maxX, y: maxY, label: '우상' },
            { x: minX, y: maxY, label: '좌상' },
            { x: 0, y: 0, label: '중앙' },
            { x: 10, y: -2, label: '고양이' }  // 고양이 위치
        ];
        
        cornerPositions.forEach(pos => {
            const sphereGeo = new THREE.SphereGeometry(0.5, 8, 8);
            const sphereMat = new THREE.MeshBasicMaterial({ 
                color: pos.label === '고양이' ? 0xff0000 : 0x00ffff 
            });
            const sphere = new THREE.Mesh(sphereGeo, sphereMat);
            sphere.position.set(pos.x, pos.y, 0);
            this.scene.add(sphere);
        });
        
        console.log('🔧 디버그 헬퍼 추가됨');
        console.log('   - 🟡 노란 구체: 원점 (0, 0, 0)');
        console.log('   - 🟢 초록 사각형: 이동 가능 경계 (-15~15, -8~8)');
        console.log('   - 🔵 청록 구체: 코너 위치');
        console.log('   - 🔴 빨간 구체: 고양이 위치 (10, -2)');
    }
    
    /**
     * GLB 모델 로드
     * @param {string} modelPath - GLB 파일 경로
     */
    loadModel(modelPath) {
        const loader = new THREE.GLTFLoader();
        
        console.log('🔄 GLB 모델 로딩 중:', modelPath);
        
        loader.load(
            modelPath,
            (gltf) => {
                // 기존 모델/피벗 제거
                if (this.pivot) {
                    this.scene.remove(this.pivot);
                }
                
                this.model = gltf.scene;
                
                // 모델 크기 계산
                const box = new THREE.Box3().setFromObject(this.model);
                const size = box.getSize(new THREE.Vector3());
                const center = box.getCenter(new THREE.Vector3());
                
                console.log('📦 모델 원본 크기:', size);
                console.log('📍 모델 원본 중심:', center);
                
                // 모델 크기 자동 조정 - 크게!
                const maxDim = Math.max(size.x, size.y, size.z);
                this.baseScale = 4 / maxDim;
                this.model.scale.setScalar(this.baseScale);
                
                // 모델을 원점으로 이동 (중심 정렬)
                this.model.position.set(
                    -center.x * this.baseScale,
                    -center.y * this.baseScale,
                    -center.z * this.baseScale
                );
                
                // 피벗 그룹 생성 (이동/회전용)
                this.pivot = new THREE.Group();
                this.pivot.add(this.model);
                this.scene.add(this.pivot);
                
                // 피벗 초기 위치
                this.pivot.position.set(0, 0, 0);
                
                console.log('📍 피벗 생성 완료');
                console.log('📏 모델 스케일:', this.baseScale);
                
                // 애니메이션 설정
                this.animations = {};
                this.currentAction = null;
                
                if (gltf.animations && gltf.animations.length > 0) {
                    this.mixer = new THREE.AnimationMixer(this.model);
                    
                    // 모든 애니메이션 저장
                    gltf.animations.forEach((clip) => {
                        this.animations[clip.name] = this.mixer.clipAction(clip);
                        console.log('📝 애니메이션 등록:', clip.name);
                    });
                    
                    // 🏃 등장 애니메이션: 뛰어서 나타남!
                    this.startEntranceAnimation();
                    
                } else {
                    console.log('⚠️ 애니메이션 없음 - 정적 모델');
                }
                
                this.isLoaded = true;
                console.log('✅ 모델 로드 완료!');
                console.log(`   - 애니메이션 수: ${gltf.animations.length}`);
                console.log('   - 사용 가능한 애니메이션:', Object.keys(this.animations));
            },
            (progress) => {
                const percent = (progress.loaded / progress.total * 100).toFixed(1);
                console.log(`📦 로딩 진행: ${percent}%`);
            },
            (error) => {
                console.error('❌ GLB 로드 오류:', error);
            }
        );
    }
    
    /**
     * 애니메이션 루프
     */
    animate() {
        requestAnimationFrame(() => this.animate());
        
        const delta = this.clock.getDelta();
        
        // 애니메이션 믹서 업데이트
        if (this.mixer) {
            this.mixer.update(delta);
        }
        
        // 이동 업데이트
        this.updateMovement();
        
        // 디버그 UI 업데이트
        this.updateDebugUI();
        
        // 피벗 위치/회전 업데이트
        if (this.pivot) {
            // 피벗 위치 직접 설정
            this.pivot.position.x = this.modelPosition.x;
            this.pivot.position.y = this.modelPosition.y;
            this.pivot.position.z = this.modelPosition.z;
            
            // 회전 처리
            let targetRotation;
            if (this.isRunning) {
                // 달릴 때: 옆모습 (이동 방향 바라봄)
                // facingDirection 1 = 오른쪽으로 이동 = +90도 회전
                // facingDirection -1 = 왼쪽으로 이동 = -90도 회전
                targetRotation = this.facingDirection > 0 ? Math.PI / 2 : -Math.PI / 2;
                this.pivot.rotation.y += (targetRotation - this.pivot.rotation.y) * 0.2;
            } else {
                // 멈춰있을 때: 정면 (카메라 바라봄)
                targetRotation = 0;
                this.pivot.rotation.y += (targetRotation - this.pivot.rotation.y) * 0.1;
            }
        }
        
        // 렌더링
        this.renderer.render(this.scene, this.camera);
    }
    
    /**
     * 모델 위치 설정 (화면 좌표 → 3D 좌표)
     * @param {number} screenX - 화면 X 좌표 (0~1)
     * @param {number} screenY - 화면 Y 좌표 (0~1)
     */
    setModelPosition(screenX, screenY) {
        // 화면 좌표를 3D 좌표로 변환
        // screenX, screenY는 0~1 범위 (화면 비율)
        this.modelPosition.x = (screenX - 0.5) * 8;  // -4 ~ 4
        this.modelPosition.y = -(screenY - 0.5) * 6; // -3 ~ 3 (Y축 반전)
    }
    
    /**
     * 모델 스케일 설정
     * @param {number} scale - 스케일 값 (기본 스케일의 배수)
     */
    setModelScale(scale) {
        if (this.pivot && this.baseScale) {
            this.pivot.scale.setScalar(scale);
        }
    }
    
    /**
     * 좌우 반전 토글
     */
    toggleFlip() {
        this.isFlipped = !this.isFlipped;
        console.log('🔄 3D 모델 좌우 반전:', this.isFlipped ? '반전됨' : '원본');
    }
    
    /**
     * 애니메이션 전환
     * @param {string} animName - 애니메이션 이름
     * @param {number} fadeTime - 전환 시간 (초)
     */
    playAnimation(animName, fadeTime = 0.3) {
        if (!this.animations || !this.animations[animName]) {
            console.warn('⚠️ 애니메이션을 찾을 수 없음:', animName);
            console.log('   - 사용 가능:', Object.keys(this.animations));
            return;
        }
        
        const newAction = this.animations[animName];
        
        if (this.currentAction === newAction) {
            return; // 이미 재생 중
        }
        
        // 부드러운 전환
        if (this.currentAction) {
            this.currentAction.fadeOut(fadeTime);
        }
        
        newAction.reset();
        newAction.fadeIn(fadeTime);
        newAction.play();
        
        this.currentAction = newAction;
        this.currentAnimName = animName;  // 현재 애니메이션 이름 저장
        console.log('🎬 애니메이션 전환:', animName);
    }
    
    /**
     * 사용 가능한 애니메이션 목록 반환
     */
    getAnimationList() {
        return Object.keys(this.animations || {});
    }
    
    /**
     * 🐱 등장: 화면 중앙에서 Idle 상태로 시작
     */
    startEntranceAnimation() {
        console.log('🐱 고양이 등장! Idle 상태로 대기');
        
        // 화면 중앙에 위치
        this.modelPosition.x = 0;
        this.modelPosition.y = -2;
        
        // 카메라 방향 바라봄
        this.facingDirection = 0;
        
        this.hasEntered = true;
        
        // Idle 애니메이션 시작
        setTimeout(() => {
            this.playAnimation('IdleA', 0.5);
            console.log('😺 Idle 상태로 대기 중...');
        }, 100);
    }
    
    /**
     * 👆 검지로 찌른 위치로 뛰어가기
     * @param {number} screenX - 화면 X 좌표 (0~1)
     * @param {number} screenY - 화면 Y 좌표 (0~1)
     */
    runToPosition(screenX, screenY) {
        if (!this.hasEntered) return;
        if (this.isRunning) return;  // 이미 달리는 중이면 무시
        
        // 화면 좌표를 3D 좌표로 변환
        // 경계: X는 -15 ~ 15, Y는 -8 ~ 8
        const targetX = (screenX - 0.5) * 30;  // -15 ~ 15
        const targetY = -(screenY - 0.5) * 16; // -8 ~ 8 (Y축 반전)
        
        console.log(`👆 검지 탭! 목표 위치: (${targetX.toFixed(1)}, ${targetY.toFixed(1)})`);
        
        // 목표 위치 설정
        this.runTarget.x = targetX;
        this.runTarget.y = targetY;
        this.isRunning = true;
        this.isPalmTarget = false;  // 일반 이동
        
        // 이동 방향에 따라 바라보는 방향 설정
        const dx = targetX - this.modelPosition.x;
        this.facingDirection = dx > 0 ? 1 : -1;  // 이동 방향 바라봄 (오른쪽=1, 왼쪽=-1)
        
        // 달리기 애니메이션
        this.playAnimation('Run_Forward', 0.2);
    }
    
    /**
     * 🖐️ 손바닥 상태 업데이트 (매 프레임 호출)
     * @param {boolean} palmVisible - 손바닥이 보이는지
     * @param {number} screenX - 화면 X 좌표 (0~1)
     * @param {number} screenY - 화면 Y 좌표 (0~1)
     */
    updatePalmState(palmVisible, screenX = 0, screenY = 0) {
        const wasPalmVisible = this.isPalmVisible;
        this.isPalmVisible = palmVisible;
        
        if (palmVisible) {
            // 손바닥이 보임
            if (!this.isRunning && !this.wasOnPalm) {
                // 아직 손바닥으로 이동 안 함 → 이동 시작
                this.runToPalm(screenX, screenY);
            } else if (this.wasOnPalm && !this.isRunning) {
                // 손바닥 위에 있고, 이동 중이 아니면 → 손바닥 위치 따라가기
                const targetX = (screenX - 0.5) * 30;
                const targetY = -(screenY - 0.5) * 16;
                
                // 거리가 멀면 다시 이동
                const dx = targetX - this.modelPosition.x;
                const dy = targetY - this.modelPosition.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance > 3) {  // 3 이상 떨어지면 다시 이동
                    this.runToPalm(screenX, screenY);
                }
            }
        } else {
            // 손바닥이 사라짐
            if (wasPalmVisible && this.wasOnPalm) {
                // 손바닥 위에 있다가 손바닥이 사라짐 → IdleA로 전환
                console.log('🖐️ 손바닥 사라짐 → IdleA로 전환');
                this.playAnimation('IdleA', 0.5);
                this.wasOnPalm = false;
            }
        }
    }
    
    /**
     * 🖐️ 손바닥으로 뛰어가기
     * @param {number} screenX - 화면 X 좌표 (0~1)
     * @param {number} screenY - 화면 Y 좌표 (0~1)
     */
    runToPalm(screenX, screenY) {
        if (!this.hasEntered) return;
        if (this.isRunning) return;  // 이미 달리는 중이면 무시
        
        // 화면 좌표를 3D 좌표로 변환
        const targetX = (screenX - 0.5) * 30;  // -15 ~ 15
        const targetY = -(screenY - 0.5) * 16; // -8 ~ 8 (Y축 반전)
        
        console.log(`🖐️ 손바닥으로 이동! 목표 위치: (${targetX.toFixed(1)}, ${targetY.toFixed(1)})`);
        
        // 목표 위치 설정
        this.runTarget.x = targetX;
        this.runTarget.y = targetY;
        this.isRunning = true;
        this.isPalmTarget = true;  // 손바닥으로 이동!
        
        // 이동 방향에 따라 바라보는 방향 설정
        const dx = targetX - this.modelPosition.x;
        this.facingDirection = dx > 0 ? 1 : -1;
        
        // 달리기 애니메이션
        this.playAnimation('Run_Forward', 0.2);
    }
    
    /**
     * 상태 업데이트 (animate에서 호출)
     */
    updateMovement() {
        if (!this.isRunning) return;
        
        // 목표까지의 거리 계산
        const dx = this.runTarget.x - this.modelPosition.x;
        const dy = this.runTarget.y - this.modelPosition.y;
        const distance = Math.sqrt(dx * dx + dy * dy);
        
        if (distance > 0.5) {
            // 목표를 향해 이동
            const moveX = (dx / distance) * this.runSpeed;
            const moveY = (dy / distance) * this.runSpeed;
            
            this.modelPosition.x += moveX;
            this.modelPosition.y += moveY;
            
            // 이동 방향에 따라 바라보는 방향 업데이트
            if (Math.abs(dx) > 0.1) {
                this.facingDirection = dx > 0 ? 1 : -1;  // 오른쪽=1, 왼쪽=-1
            }
        } else {
            // 도착!
            this.modelPosition.x = this.runTarget.x;
            this.modelPosition.y = this.runTarget.y;
            this.isRunning = false;
            
            // 카메라 쪽 바라보기 (정면)
            this.facingDirection = 0;
            
            // 손바닥으로 이동한 경우: IdleB 유지 (손바닥 사라질 때까지)
            if (this.isPalmTarget) {
                this.playAnimation('IdleB', 0.3);
                console.log('🖐️ 손바닥에 도착! IdleB 상태 (손바닥 사라질 때까지 유지)');
                this.wasOnPalm = true;  // 손바닥 위에 있음!
                this.isPalmTarget = false;
            } else {
                // 일반 이동: IdleA로 전환
                this.playAnimation('IdleA', 0.3);
                console.log('😺 도착! Idle 상태로 대기');
            }
        }
    }
    
    /**
     * 모델 표시/숨기기
     * @param {boolean} visible - 표시 여부
     */
    setVisible(visible) {
        if (this.pivot) {
            this.pivot.visible = visible;
        }
    }
    
    /**
     * 윈도우 리사이즈 핸들러
     */
    onWindowResize() {
        const outputImage = document.getElementById('output-image');
        let width = this.container.clientWidth || 640;
        let height = this.container.clientHeight || 480;
        
        // 이미지가 있으면 그 크기 사용
        if (outputImage && outputImage.clientWidth > 0) {
            width = outputImage.clientWidth;
            height = outputImage.clientHeight;
        }
        
        if (width > 0 && height > 0) {
            this.camera.aspect = width / height;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(width, height);
        }
    }
    
    /**
     * 리소스 정리
     */
    dispose() {
        if (this.renderer) {
            this.renderer.dispose();
        }
        if (this.pivot) {
            this.scene.remove(this.pivot);
        }
        console.log('Three.js 렌더러 정리 완료');
    }
}

// 전역 인스턴스
let threeRenderer = null;

