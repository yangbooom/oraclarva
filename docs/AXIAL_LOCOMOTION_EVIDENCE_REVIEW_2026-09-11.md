# Oraclarva 축방향 전진·후진 운동 문헌 감사

- 작성일: 2026-09-11 UTC
- 조사 범위: 사용자가 지정한 7편의 원문, 그 논문들이 인용한 축방향 운동 관련 핵심 연구, 공개 데이터·코드
- 목적: 좌우·상하 조향보다 먼저 전진과 후진의 감각–신경–근육–몸체–환경 폐루프를 근거 기반으로 다시 설계한다.
- 제품 결정: Android UI 작업은 동결한다. 이 문서는 과학 코어 구현의 근거 문서이며, 2026-09-12의 v1 보정 결과는 아래 구현 결과 절에 별도로 기록한다.

## 결론

현재 Oraclarva의 전진은 신경·근육 파동의 방향은 대체로 맞지만, 순이동을 만드는 지면 상호작용은 `negative_x_retention` 형태의 합성 방향성 고정 장치에 크게 의존한다. 이는 연구용 임시 모델로는 쓸 수 있어도 유충의 실제 접촉 역학이라고 주장할 수 없다.

문헌이 지지하는 다음 구조는 다음과 같다.

1. 전진과 후진은 동일 파동의 부호만 뒤집는 운동이 아니다.
2. 전진에는 A27h–GDL 계열의 분절 파동 회로와 Ifb-Fwd 계열의 분절간 피드백이 관여한다.
3. 후진 선택에는 MDN이 A18b 계열을 활성화하는 동시에 Pair1을 통해 전진 A27h 계열을 억제하는 병렬 구조가 관여한다.
4. 후진 파동의 분절내 근육 이완에는 Ifb-Bwd의 이른 억제와 Canon/A18g의 더 늦은 억제가 서로 다른 시점에 기여할 가능성이 높다.
5. 거의 모든 몸벽 근육은 전진과 후진에 모두 동원된다. 방향 차이는 근육의 켜짐/꺼짐 여부보다 일부 근육군의 상대 위상에서 생긴다.
6. 전진 중에는 종축 근육과 횡축 근육의 모집이 동일 시점이 아니다. L3에서는 파동 사이에 여러 분절의 LT 근육이 함께 활성화되는 별도의 interwave 단계도 관찰된다.
7. 지면 접촉은 고정된 한 방향 마찰이 아니다. L2 실험에서는 분절별 denticle band가 놓인 protopodium이 파동에 맞추어 들리고, 접히고, 다시 심어지는 동적 고정점으로 작용한다.
8. 공개된 1–7 µN의 protopodial 지면 반력은 L2의 수직 반력이다. 이것을 L1의 수평 추진력이나 근육 `Fmax`로 복사하면 안 된다.

따라서 다음 구현 목표는 “전진 애니메이션 개선”이 아니라 **서로 구분된 전진·후진 신경 경로가 근육 상대 위상과 동적 접촉 상태를 만들고, 그 결과로 순이동 방향이 나온다는 것을 재현하는 축방향 폐루프 v1**이다.

## 2026-09-12 구현·검증 결과

축방향 폐루프 v1은 위 근거를 따라 구현됐다. 후방 접촉은 A27h-like
A6→A1 경로를, 전방 접촉은 MDN→A18b-like A1→A6 경로와 Pair1 억제를
활성화한다. 두 경로는 동일한 A1–A6 MN/근육 identity에 수렴한다.

구현 중 발견한 중요한 오류는 transverse(`T`) 근육 활성까지 분절의
종축 단축과 축 방향 힘에 평균하던 것이었다. v1에서는 T 활성은 연속
접촉 해제에만 쓰고 DL/DO/VA/VL/VO 활성만 축 역학에 투영한다. A1–A6
atlas 앞쪽에 접촉점이 없어 후진 첫 파를 고정하지 못하는 문제는
`A18b:A1 → motor_proxy:T3_transverse_backward` 접촉 전용 프록시로
닫았다. 이 프록시는 축 힘이 0이며 실제 L1 MN/근육 identity라고
주장하지 않는 `ANATOMY_DERIVED`/`MODEL_FITTED` 가설이다.

Greaney L1 12개 calibration 동물의 p10–p90 범위에 대해 속도, 보폭,
주기, 주파수, A6–A1 파속과 A1–A6 각각의 수축 진폭·단축속도·지속시간·
duty 29개 필수 비교가 통과했다. 왜곡·역미끄러짐·인과추적 게이트도
통과했다. 반면 이미 공개되어 독립적이지 않은 6개 held-out 진단은
4개 비교가 실패하므로 release validation으로 사용하지 않는다.

Greaney가 보여준 비균일 adjacent delay를 calibration median에 맞춘
후보도 시험했지만 보폭·진행효율·retrace가 동시에 나빠져 폐기했다.
현재 균일 지연에서 5개 adjacent-delay 진단 중 4개가 실패한다는 사실을
산출물에 남긴다. 즉 v1은 정량 calibration을 통과한 연구 근사이지,
비균일 coordination이나 후진 L1 정량 행동이 검증된 최종 모델이 아니다.

## 조사 방법과 판정 기준

### 포함 범위

- 원문에서 확인 가능한 신경 정체성, 연결 방향, 신경전달물질, 활동 순서
- 몸벽 근육의 상대 모집 순서와 행동 방향별 차이
- 자유 운동, 반고정, 분리 CNS, EM 재구성 사이의 조건 차이
- 공개 원자료와 코드의 위치 및 라이선스
- L1 모델에 직접 사용할 수 있는 항목과 다른 발달 단계에서 구조적 prior로만 쓸 항목

### 증거 등급

|표기|이 문서에서의 의미|모델 사용|
|---|---|---|
|`L1_DIRECT`|L1 동물 또는 L1 EM에서 직접 얻은 결과|해당 관측 범위 안에서 직접 제약 가능|
|`L1_ANATOMY`|L1 EM의 정체성·연결·형태|연결 토폴로지에 사용 가능; 효능·지연·막 상수는 별도 fitting|
|`L2_FUNCTION`|L2 자유 운동 또는 생리 결과|정성적 기능과 상대 위상 prior; L1 절대값 전용 금지|
|`L3_FUNCTION`|L3 자유 운동·분리 CNS·생리 결과|회로 기능 가설과 상대 순서 prior; L1 절대값 전용 금지|
|`EMBRYO_DEVELOPMENT`|배아기 회로 발달 결과|성숙 L1 runtime 방정식의 직접 상수로 사용 금지|
|`MODEL_ONLY`|문헌의 계산 모델 또는 Oraclarva 가정|검증 가능한 hypothesis 또는 fitted 값으로만 표시|

### 해석 제한

- calcium 신호는 spike와 같지 않고, spike는 근육 수축과 같지 않다.
- EM synapse 수는 생리적 시냅스 강도와 같지 않다.
- optogenetic activation으로 행동이 유발된다는 사실만으로 그 뉴런이 자연 상태에서 유일한 필요조건이라는 결론을 내리지 않는다.
- 분리 CNS의 fictive rhythm은 감각·접촉 폐루프가 없는 상태다.
- L2/L3의 길이, 힘, 속도, 시간상수는 L1 절대 파라미터가 아니다.
- “command-like neuron”은 행동 함수를 직접 호출하라는 뜻이 아니다. 모델에서는 실제 하위 연결과 동역학을 통해 결과가 나와야 한다.

## 사용자가 지정한 7편

### 1. Cooney et al. 2023 — rolling escape의 신경근육 기반

이 연구는 SCAPE microscopy로 구르기와 기어가기의 몸벽 근육 활성 패턴을 비교했다. 구르기는 여러 분절이 거의 동시에, 몸 둘레 방향으로 비대칭적으로 동원되는 반면, 기어가기는 전후축을 따라 분절간 비동기 파동이 진행하고 좌우가 비교적 대칭적이다. LT와 ventral acute 근육이 종축 근육 파동과 분리되어 동원될 수 있으며, 저자들은 이런 근육군이 hydrostatic skeleton의 강성 조절에 기여할 가능성을 논의한다.[^1]

Oraclarva에 유용한 부분은 3D 몸벽 근육을 단일 “segment contraction” 값으로 평탄화하면 안 된다는 점이다. 그러나 주 연구 대상은 축방향 기어가기보다 rolling escape이고, 주 SCAPE 표본의 정확한 stage를 본문만으로 L1이라고 확정할 수 없다. 신경 침묵 실험에도 여러 stage가 섞인다. 그러므로 다음만 허용한다.

- 허용: 근육군의 공간적 분리, 좌우 대칭/비대칭을 검증하는 미래 3D 참조
- 보류: crawling comparator의 작은 표본을 L1 모집 위상의 정량 기준으로 사용
- 금지: rolling 회로 또는 activation 크기를 축방향 전진·후진 기본값으로 사용

분석 코드는 공개 GitHub 저장소에 있으나 명시적 라이선스 파일이 확인되지 않았고, 저장소에 보이는 것은 분석 스크립트와 일부 예제 `.mat` 파일이다.[^2] 앱 코드에 복사하기 전 저작권 조건을 별도로 판정해야 한다.

### 2. Carreira-Rosario et al. 2018 — MDN의 후진 선택

이 논문은 후진에 가장 직접적인 회로 근거다. 양측 MDN은 cholinergic descending neuron이며, L1 CNS EM에서 두 개의 병렬 하위 경로가 확인된다.[^3]

- MDN → A18b: 후진 중 활동하는 cholinergic premotor 계열을 흥분
- MDN → Pair1: GABAergic Pair1을 흥분
- Pair1 → A27h: 전진 중 활동하는 cholinergic A27h를 억제

즉 후진은 “전진 파동을 역재생”하는 것이 아니라, 후진 경로를 올리면서 전진 경로를 누르는 선택 구조를 가진다. 약 300 ms의 MDN 자극 뒤에도 여러 초의 완전한 후진 파동이 이어졌다는 결과는 MDN을 프레임마다 속도를 명령하는 actuator로 보기보다, 하위 VNC 동역학의 상태를 바꾸는 trigger로 보는 편이 맞음을 시사한다.

중요한 한계도 있다.

- EM은 L1이지만 다수 기능 실험은 L3이고 일부 intact calcium은 L2/L3다.
- MDN에 들어오는 자연 감각 경로는 완성되지 않았다. 논문은 MDN의 모든 입력을 재구성하지 않았고, head touch에서 MDN으로 가는 경로도 다단계로 남아 있다.
- A18b의 필요성을 모든 분절에서 단독으로 입증한 것은 아니다.

따라서 L1 모델에는 MDN–A18b, MDN–Pair1–A27h의 부호와 방향을 넣을 수 있다. 반면 MDN threshold, 시냅스 gain, 지속시간은 `MODEL_FITTED`여야 한다.

### 3. Pulver et al. 2015 — fictive locomotion의 방향성 파동

분리한 L3 CNS도 감각 입력 없이 posterior→anterior forward wave, anterior→posterior backward wave, 좌우 비대칭 anterior activity를 자발적으로 만든다. 이는 VNC 자체가 방향성 리듬을 생성할 능력을 가진다는 강한 근거다.[^4]

다만 분리 CNS의 주기는 intact behavior보다 약 10배 느렸다. 논문의 intact L3에서는 전진·후진 파동 자체가 약 1초였고, fictive preparation에서 얻은 절대 지연은 수 초 규모다. 이를 L1의 막 시간상수나 분절 지연으로 복사하면 안 된다.

또한 aCC가 LT motor neuron보다 먼저 활성화되며, 그 상대 위상이 전진과 후진에서 크게 다르지 않았다는 결과는 “파동 방향”과 “분절 내부의 종축→횡축 순서”를 별도 축으로 모델링해야 한다는 근거가 된다.

### 4. Kohsaka et al. 2019 — 방향별 intersegmental feedback

L1 whole-CNS ssTEM에서 두 방향별 2차 premotor interneuron과 공통 하위 모듈이 제시되었다.[^5]

- Ifb-Fwd/A01d3: 다음 posterior neuromere 쪽으로 투사
- Ifb-Bwd/A27k: 다음 anterior neuromere 쪽으로 투사
- 공통 하위 모듈: A02e/A02g, A01c/A01ci, A03g 및 관련 억제 경로
- 출력 효과: transverse MN을 흥분시키고 longitudinal MN을 억제하는 쪽으로 작용

이 투사 방향이 진행하는 운동파 방향의 반대라는 점이 중요하다. 저자들은 이를 각 분절이 이미 지나간 분절의 상태를 읽어 현재 분절 내부의 종축→횡축 전환을 정돈하는 피드백으로 해석한다. Ifb-Fwd와 Ifb-Bwd를 각각 차단하면 해당 방향에서 transverse contraction이 선택적으로 약해졌다.

그러나 기능 실험은 주로 L3이고, 원자료와 분석 코드는 “요청 시 제공”이다. 프로젝트 원칙상 이메일 요청을 하지 않으므로 논문 figure와 supplementary를 근거로 연결 부호와 기능 가설만 채택한다. calcium 상관계수나 L3 wave time은 L1 calibration target으로 쓰지 않는다.

### 5. Fushiki et al. 2016 — A27h–GDL 전진 파동 메커니즘

이 연구는 L1 EM과 L3 기능 실험을 결합해 전진 파동 propagation 회로를 제안한다.[^6]

- A27h: cholinergic excitatory premotor interneuron; 전진 중 선택적 활동
- A27h → aCC/RP5 등 longitudinal MN
- GDL/A27j2: segmental GABAergic interneuron; A27h를 억제
- proprioceptor vpda, vdaA, vdaC에서 A27h/GDL 계열로 들어오는 연결

GDL은 같은 분절의 motor activity보다 앞서고, 다음 posterior 분절의 aCC와 가까운 위상에 놓인다. wave front에서 국소 GDL을 활성화했을 때 다수 trial에서 파동이 멈춘 결과는 단순 흥분 사슬만이 아니라 적절한 억제가 propagation과 relaxation에 필요함을 보여준다.

이 회로는 Oraclarva 전진 파동의 최소 후보지만 완전한 CPG는 아니다. 논문 자체도 proprioceptive feedback이 중앙 회로가 만든 느리고 거친 파동을 빠르고 정밀하게 만든다고 해석한다. 그러므로 A27h/GDL을 미리 정한 phase oscillator로 강제하기보다, 분절 길이·장력 감각이 다시 회로에 들어가 phase를 교정하게 해야 한다.

### 6. Zeng et al. 2021 — 배아 pioneer circuit와 proprioceptive development

이 논문의 핵심은 성숙 L1이 움직일 때 계속 사용되는 runtime 회로가 아니라, 그 회로가 만들어지는 배아기의 critical period다.[^7]

A27h와 M neuron(후속 연구의 A19f)은 전기적으로 결합된 pioneer circuit를 이루며, 배아 후기의 proprioceptive experience와 gap junction activity가 정상적인 CPG 발달에 필요하다. M neuron의 plateau-like activity에는 intracellular calcium store/IP3 관련 기전이 제시된다. 하지만 저자들은 CPG가 확립된 후에는 이 발달 기전이 동일한 방식으로 필수적이지 않을 수 있음을 보인다.

따라서 다음 사용 구분이 필요하다.

- `EMBRYO_DEVELOPMENT`: A27h–M/A19f의 발생학적 관계, 활동 의존적 회로 성숙
- runtime 금지: 배아 plateau frequency, IP3 상수, gap-junction coupling을 성숙 L1 crawling 기본값으로 삽입
- validation 의미: 감각 피드백은 단순한 반사 보정이 아니라 운동 회로 자체의 발달과 정상 기능에 중요

원자료는 Mendeley Data에 CC BY 4.0으로 공개되어 있다.[^8] 다만 현재 공개 페이지에서 개별 파일 목록이 노출되지 않았으므로 전체 다운로드 전에 API 또는 manifest로 필요한 파일을 선별해야 한다.

### 7. McNulty et al. 2025 — 자유 운동 중 VNC 활동의 직접 관찰

CRASH2p는 움직이는 L2 유충의 CNS를 3D로 추적하면서 neural calcium activity와 행동을 동시에 측정한다. 모든 동물은 48–72 h AEL의 L2이며 크기와 spiracle morphology로 확인됐다.[^9]

축방향 모델에 특히 중요한 관측은 다음과 같다.

- A27h central process는 전진 중 posterior→anterior wave를 보이고 후진 중 크게 억제된다.
- 동일 driver line이 표지하는 lateral M/A19f 계열은 후진 중 anterior→posterior activity를 보인다.
- L1 EM에서 A19f는 MDN 바로 아래의 A18b 입력을 받고, 동시에 A27h의 직접 cholinergic 입력도 받는다.
- 서로 흥분성 연결이 존재하는데 L2 자유 운동에서는 A27h와 A19f가 반대 행동에서 활동하므로, 아직 빠진 local inhibition 또는 state-dependent gating이 필요하다.
- EL proprioceptive neuron은 전진 중 posterior→anterior activity pattern을 보인다.
- MDN activity는 자유 운동의 후진과 연관된다.

이 논문은 고정 preparation에서 제안된 방향성 회로가 자유 운동 중에도 보인다는 강한 교차 검증이다. 동시에 A19f를 “후진 motor command” 한 개로 단순화하면 안 된다는 경고다. A19f는 ascending coordination과 head-sweep 조절에도 관련된다는 후속/인용 연구가 있어, 우선 관찰 가능한 중간 상태로 넣고 직접 motor gain을 크게 주지 않는 편이 안전하다.

논문은 Nature source data, 약 70 GB 규모의 Harvard Dataverse raw corpus, GPL-3.0 MATLAB 분석 코드를 공개한다.[^10][^11] Oraclarva는 전체 raw corpus보다 source data와 한 개의 대표 A27h/MDN/EL recording을 우선 감사해야 한다.

## 인용망에서 뽑은 우선 레퍼런스

### Zarin et al. 2019 — 전체 MN/PMN 분절과 방향별 근육 모집

이 연구는 L1 A1 한 분절에서 60 motor neuron과 236 premotor neuron을 재구성하고, 1령과 2령의 몸벽 근육 calcium imaging을 통해 전진·후진을 비교했다.[^12]

가장 중요한 결과는 모든 관찰 근육이 두 방향에서 모두 활성화되지만 일부 근육과 그 MN의 상대 모집 시점이 바뀐다는 것이다. 따라서 Oraclarva가 가져야 할 것은 `forward_muscles`와 `backward_muscles`라는 서로 배타적인 두 목록이 아니다. 동일한 muscle identity atlas 위에 방향별 timing modulation을 겹쳐야 한다.

논문 부록에는 MN/PMN reconstruction, neurotransmitter, PMN→MN 및 PMN→PMN connectivity의 machine-readable 자료가 있고, 공개 저장소에는 image processing, EM analysis, calcium analysis와 connectome-constrained RNN이 GPL-3.0으로 제공된다.[^13] RNN은 회로 제약과 관측을 대조하는 참고 모델로는 유용하지만, Oraclarva의 이동을 직접 결정하는 외부 policy로 사용하지 않는다.

발달 단계가 1령과 2령으로 섞인 calcium cohort는 현재 schema에서 `stage=unknown`으로 기록하고 `limitations`에 `mixed_L1_L2; relative_timing_only`를 명시해야 한다. L1 EM connectivity는 별도 source record로 분리한다.

### Hiramoto et al. 2021 — Canon/A18g와 후진 이완

Canon/A18g는 cholinergic ascending interneuron으로, 후진에서 motor wave보다 늦게 활성화되어 inhibitory premotor pathway를 통해 주로 longitudinal muscle relaxation을 촉진한다.[^14]

이 결과는 후진을 anterior→posterior excitation wave 하나로 구현하면 몸이 심하게 찌그러지거나 앞뒤로 되감기는 이유를 설명한다. 수축한 분절을 적절한 시간에 풀어 주는 별도 늦은 억제가 필요하다. 논문이 제안하는 구조에서 Ifb-Bwd 계열은 wave보다 약 한 분절 늦은 이른 억제, Canon은 약 2–4 분절 늦은 relaxation control을 담당한다.

L1 EM의 연결 토폴로지는 사용할 수 있지만 기능·행동 수치는 다른 stage이므로 절대 지연으로 복사하지 않는다. 구현에서는 두 지연을 L1 kinematics에 맞추는 `MODEL_FITTED` phase window로 둔다.

### Liu et al. 2023 — metachronal wave 사이의 동시 LT 활성

L3 자유 운동에서는 posterior→anterior longitudinal wave 사이에 A2–A7 LT2 근육이 여러 분절에서 동시에 활성화되는 interwave phase가 관찰됐다. 이동 속도 0.35–1.23 mm/s 범위에서 stride frequency 차이는 wave 자체보다 interwave duration 변화와 더 강하게 연결됐다.[^15]

이는 현재 모델의 연속적인 종축 파동만으로는 실제 stride 구조가 부족할 수 있음을 뜻한다. 다만 전부 L3이므로 다음처럼 사용한다.

- 상대 구조 prior: longitudinal metachronal phase 뒤 transverse stabilization phase
- 금지: L3 speed, cycle duration, LT force를 L1 기본값으로 사용
- 공개 데이터: Zenodo dataset을 선택적으로 감사해 timing trace와 annotation schema만 재사용 가능성 평가[^16]

### Booth et al. 2024 — protopodia와 동적 접촉

이 연구는 유충의 ventral denticle band가 단순한 거친 표면이 아니라, 접히고 펼쳐지는 큰 cuticular protrusion인 protopodium 위에 놓인다는 것을 보여준다.[^17]

전진 시 각 protopodium은 다음 순서를 보인다.

1. stance 중 기질에 심어져 분절을 지지한다.
2. posterior denticle row가 anterior row를 향해 움직인다.
3. 접촉면이 invaginate되어 denticle을 감춘 채 substrate에서 떨어진다.
4. 몸 앞쪽으로 이동한다.
5. 다시 펼쳐지고 기질에 심어진다.

후진에서는 이 heel-to-toe 같은 AP latency가 반대로 진행한다. 자유 운동 WARP 측정은 L2에서 수행되었고, 분절 protopodium의 수직 지면 반력은 약 1–7 µN였다. 개별 denticle 수준은 약 1–48 nN 범위였다. 접촉면적과 반력은 비선형적으로 연관됐다.

이 연구가 직접 측정한 것은 주로 수직 stress/GRF다. 저자와 peer review도 수평 추진이 어느 지점에서 생성되는지는 해결하지 못했다고 명시한다. protopodia는 근육이 만든 반대 방향 힘을 버티는 동적 anchor로 해석되며, 주변 수막의 표면장력도 접촉에 영향을 줄 수 있다.

따라서 현재 `negative_x_retention=1`, `positive_x_retention=0` 같은 전역 ratchet를 실측 마찰이라고 부르면 안 된다. 다음 continuous contact model로 대체하되, L2 힘은 L1 절대값으로 복사하지 않는다.

- 분절마다 sequestration 정도, denticle 노출, contact area를 연속 상태량으로 계산
- `stance`, `sequestering`, `swing`, `planting`은 결과를 분석할 때만 붙이는 phase label이며 FSM 전이 조건으로 사용하지 않음
- 접촉 중 마찰/접착은 등방 상수가 아니라 normal load, contact area, denticle orientation의 함수
- 전진/후진 방향은 마찰 부호를 직접 바꾸지 않고 wave와 contact-state timing의 반전에서 발생
- L2 WARP data는 형태와 상대 timing calibration; L1 계수는 `MODEL_FITTED`

연구 데이터는 University of St Andrews Research Data Repository에 공개되어 있으나 figure archive 중 일부는 수백 MB에서 수십 GB 규모다.[^18] 먼저 metadata, figure source table, 낮은 용량의 대표 forward/backward trace만 선별해야 한다.

### Greaney et al. 2026 — L1 전후축의 비균일 coordination

이 연구는 Oraclarva가 가장 직접적으로 사용할 수 있는 현재의 L1 kinematic benchmark다. 18마리 L1에서 T3–A7 분절을 추적했으며, L2 17마리와 비교했다.[^19]

주요 결과는 “같은 모듈이 일정한 지연으로 복제된다”는 균일 파동 모델이 충분하지 않다는 점이다.

- T3의 contraction amplitude가 복부 분절보다 작다.
- shortening rate는 mid-body A4/A5와 T3에서 느리다.
- posterior segment의 contraction duration이 더 길고 A5가 특히 길다.
- neighboring segment phase delay가 전후축에서 비균일하다.
- 크기와 채널 벽 접촉 차이를 분리해도 L1/L2의 비균일 패턴이 유지된다.

따라서 L1 timing target은 uniform segment delay가 아니라 이 데이터의 분절별 amplitude, rate, duration, phase-delay distribution이어야 한다. 이 저장소에 이미 들어온 Greaney 자료를 회귀 기준의 중심으로 유지한다.

### Sun et al. 2022 — 측정 기반 neuromechanical model

이 논문은 전신 viscoelasticity, contraction force, mass, length를 물리적으로 측정해 1D neuromechanical model을 구성했다.[^20] 하지만 모든 측정은 L3이다. 보고된 길이, 질량, 점탄성 계수, 전체 수축력은 L1 기본값이 될 수 없다.

허용되는 사용은 다음뿐이다.

- standard linear solid 같은 constitutive form 후보
- 어떤 물성을 별도 파라미터로 측정·fit해야 하는지에 대한 실험 설계
- 공개 kinematic data와의 모델 형식 비교[^21]

금지되는 사용은 L3의 수치 계수를 스케일 설명 없이 L1 `MEASURED_PUBLISHED`로 등록하는 것이다.

### Jonaitis et al. 2024 preprint — A19f의 ascending coordination

McNulty et al.의 reference 76은 A19f가 단순 후진 generator가 아니라 premotor input을 받는 ascending interneuron이며, 전진·head sweep 등 여러 motor program의 조정에 관여할 가능성을 제시한다.[^22] optogenetic activation은 head sweep을 줄이고 전진을 느리게 하며, inhibition은 head sweep을 늘리는 방향의 결과가 보고됐다.

이는 아직 preprint이므로 낮은 확신으로 기록한다. A19f를 후진 상태의 관찰 marker 및 후보 ascending feedback node로는 둘 수 있지만, A19f→MN 직접 gain을 가정하지 않는다.

## 통합된 축방향 폐루프 명세

### 전진 경로

```text
환경/내부 상태
  → 감각 변환(후방·분절 strain, EL/class-I proprioception 등)
  → 전진 VNC 상태
  → A27h 계열 흥분 + GDL 계열 억제 타이밍
  → Ifb-Fwd와 공통 분절내 모듈
  → longitudinal MN 우선, transverse MN 후속/보정
  → 몸벽 근육 수축·이완
  → protopodium의 posterior→anterior swing/planting 진행
  → 몸체 변형과 지면 반력
  → 새 strain/contact가 proprioception으로 되먹임
```

전진은 posterior→anterior neural/muscle wave를 가져야 한다. 하지만 모든 분절을 같은 oscillator phase offset으로 복제하지 않고, Greaney L1의 T3–A7 비균일 amplitude/rate/duration/phase를 허용해야 한다.

### 후진 경로

```text
전방 접촉/위험 감각의 미확정 다단계 경로
  → MDN
  ├─→ A18b 및 후진 premotor 계열 활성
  └─→ Pair1 ─| A27h 전진 계열
       ↓
  anterior→posterior excitation wave
  + Ifb-Bwd 이른 억제
  + Canon/A18g 늦은 relaxation
  → 방향별 근육 상대 위상
  → protopodium의 반대 순서 swing/planting
  → 후진 변위와 감각 되먹임
```

여기서 `backward=true`가 motor function에 직접 전달되어서는 안 된다. 전방 감각 입력이 MDN membrane dynamics를 바꾸고, 하위 연결을 통해 전진 회로를 억제하고 후진 회로를 활성화한 결과로 anterior→posterior wave가 발생해야 한다.

자연 감각에서 MDN까지의 완전한 L1 연결은 아직 확보되지 않았다. 이 구간은 `HYPOTHESIS`로 명시하고, touch/압력 transducer → 다단계 excitatory relay → MDN이라는 최소 가설을 사용하더라도 relay identity를 실측이라고 표기하지 않는다.

### motor neuron과 근육

근육 맵은 방향별로 복제하지 않는다.

```text
동일 L1 muscle identity atlas
  + 방향별 PMN/MN 활성 위상
  + 근육군별 activation/relaxation dynamics
  + attachment에서 계산한 rest length
  + fitted global stress/activation parameters
  = 방향별로 다른 변형 패턴
```

최소한 longitudinal과 transverse 두 근육군을 분리해야 한다. 이후 Zarin의 machine-readable PMN→MN 연결과 muscle timing을 이용해 muscle 2, 11, 18 및 VO 계열처럼 방향별 timing 차이가 큰 identity를 우선 세분화한다. mixed L1/L2 activity를 L1 단일 동물의 절대 phase로 오인하지 않도록 uncertainty를 유지한다.

### 지면 접촉

전역 방향성 retention은 아래와 같이 단계적으로 제거한다.

```text
현재: 축 방향에 따라 속도를 일방적으로 보존/제거하는 전역 synthetic ratchet

목표: 각 ventral segment의 local contact patch
      normal penetration/contact area
      denticle/protopodium orientation
      continuous sequestration/contact variables
      tangential friction or adhesion
      surface-film contribution(후순위)
```

중요한 구현 원칙은 `forward`일 때 마찰 방향을 뒤집는 코드가 없어야 한다는 것이다. 동일 접촉 방정식에서 근육파와 접촉 timing이 달라져 순변위 방향이 달라져야 한다.

## 구현 우선순위

### Phase A — 공개 원자료 선별 감사

1. Zarin eLife supplementary에서 PMN→MN, PMN→PMN, neurotransmitter, MN/PMN reconstruction 파일을 내려받아 checksum과 license를 기록한다.
2. Zarin calcium 자료는 L1/L2를 표본 단위로 분리할 metadata가 있는지 확인한다. 분리 불가능하면 `stage=unknown` 및 상대 위상 전용으로 등록한다.
3. McNulty Nature source data를 먼저 받고, raw Harvard Dataverse에서는 대표 A27h, MDN, EL recording 각 하나의 파일명·크기·checksum만 감사한다.
4. Booth data repository에서 forward/backward protopodium tracking과 force source table의 최소 파일만 선별한다. 대용량 figure archive 전체 다운로드는 하지 않는다.
5. Hiramoto의 machine-readable source data 여부를 확인해 Canon phase와 sample metadata를 기록한다.
6. Liu Zenodo에서 LT/interwave timing table만 선별한다.

### Phase B — provenance manifest 분리

한 논문을 하나의 source record로 뭉치지 않는다. 예를 들어 Zarin은 최소 세 개로 나눈다.

- `zarin_2019_l1_a1_em_connectivity`: `stage=L1`, `L1_ANATOMY`
- `zarin_2019_mixed_l1_l2_muscle_activity`: `stage=unknown`, relative timing only
- `zarin_2019_rnn_reference_code`: `MODEL_ONLY`, external-policy use forbidden

Booth 역시 L3 lateral morphology와 L2 ventral kinematics/force를 별도 record로 둔다. 현재 manifest enum을 유지해 `allowed_uses`에는 `reference`, `calibration`만 쓰고, `limitations`에 `relative_timing_only; no_L1_absolute_force`를 명시한다.

### Phase C — 축방향 neural reference model

첫 구현은 전체 3,016 neuron brain을 무리하게 모두 넣지 않는다. 검증 가능한 최소 subnet으로 시작한다.

- 공통: proprioceptor proxy, identified relay가 없는 감각 구간, MN pools
- 전진: A27h, GDL, Ifb-Fwd, A02e/A02g 공통 모듈
- 후진: MDN, Pair1, A18b, Ifb-Bwd, Canon/A18g
- 후보 관찰 노드: A19f

각 edge는 `observed_connection`, `observed_sign`, `fitted_weight`, `stage`를 따로 보존한다. 알려진 연결의 존재와 우리가 fit한 효능을 한 필드로 합치지 않는다.

### Phase D — 방향별 근육 phase model

- 동일 muscle atlas를 공유한다.
- forward/backward에서 activation onset을 다르게 만드는 것은 PMN/MN output이다.
- longitudinal activation, transverse activation, relaxation gate를 별도 상태로 둔다.
- 모든 수축은 활성 MN과 그 상류 신경 발화로 역추적할 수 있어야 한다.
- muscle activation time constant는 확인 전까지 fitted range다.

### Phase E — local dynamic contact

- ventral contact patch를 A1–A8에 둔다.
- patch는 normal contact와 local deformation으로만 힘을 낸다.
- plant/lift transition은 근육에 의한 local geometry와 strain threshold에서 생긴다.
- anterior/posterior 방향은 접촉 방정식의 입력이 아니다.
- L2 force data에는 stage-scaled fit이 필요하며, scaling law 자체도 기록한다.

### Phase F — 검증과 병변 시험

|검증|기대 결과|주 근거|
|---|---|---|
|기본 전진|posterior→anterior neural/muscle wave, 양의 순변위|Fushiki, McNulty, Greaney|
|기본 후진|anterior→posterior wave, 음의 순변위|Carreira-Rosario, McNulty|
|MDN 활성 증가|A18b 계열 증가, Pair1 증가, A27h 감소|Carreira-Rosario|
|Pair1 병변|후진 선택 중 전진 억제가 약해져 혼합/비정상 파동|Carreira-Rosario|
|A27h 병변|전진 propagation 저하, 후진은 상대적으로 보존|Fushiki, McNulty|
|GDL 병변|전진 파동이 느리거나 부정확해짐|Fushiki|
|Ifb-Fwd 병변|전진 transverse coordination 선택적 저하|Kohsaka|
|Ifb-Bwd 병변|후진 transverse coordination 선택적 저하|Kohsaka|
|Canon 병변|후진에서 longitudinal relaxation 지연|Hiramoto|
|proprioception 제거|중앙 파동은 남을 수 있으나 속도·정밀도 저하|Fushiki, Zeng|
|contact lift 고정|큰 역미끄러짐 또는 순변위 소실|Booth 기반 예측|
|전역 ratchet 제거 후에도 전진|동적 접촉이 실제로 추진에 기여한다는 모델 내부 검증|Oraclarva 검증 게이트|

### 수치 검증 지표

- Greaney L1 T3–A7 분절별 contraction amplitude/rate/duration distribution
- neighboring phase-delay distribution과 비균일성
- stride당 CoM 순변위와 최대 retrace
- head와 tail 각각의 displacement phase
- longitudinal→transverse 상대 activation onset
- 각 ventral patch의 stance/swing duty cycle
- neural wave, muscle activation, segment shortening, contact force 사이의 causal lag
- 동일 자극에서 Python reference와 C++ native core의 방향·phase·변위 일치

## 채택하지 않는 단순화

- `crawlForward()` 또는 `crawlBackward()`가 위치를 바꾸는 구조
- 전진 trajectory를 시간 반전해 후진으로 쓰는 구조
- 한 개의 traveling sine wave를 모든 분절·근육에 동일하게 적용
- MDN 하나가 직접 몸체 velocity를 쓰는 구조
- 모든 body-wall muscle을 하나의 longitudinal actuator로 합치는 구조
- 전진/후진에 따라 마찰 계수의 부호를 외부에서 바꾸는 구조
- L2 protopodial 1–7 µN을 L1 muscle force로 사용
- L3 fictive delay, 속도, 점탄성, contraction force를 L1 절대값으로 사용
- Zarin의 RNN을 외부 정책망으로 연결해 이동을 결정하게 하는 구조
- embryo A27h–M gap-junction/IP3 dynamics를 성숙 L1 runtime의 사실로 취급

## 공개 데이터 취득 판단

|자료|stage|공개성|이번 판단|
|---|---|---|---|
|Zarin eLife supplementary|L1 EM; mixed L1/L2 calcium|논문 부록 + GPL-3.0 코드|최우선 소용량 다운로드|
|McNulty Nature source data|L2|논문 source data|최우선 다운로드|
|McNulty Harvard Dataverse|L2|공개, 약 70 GB|대표 파일만 선택|
|CRASH2p code|L2 analysis|GPL-3.0|분석 재현 참고; native runtime에 직접 포함 불필요|
|Booth St Andrews dataset|주요 force/ventral kinematics L2; 일부 lateral morphology L3|CC BY 연구 데이터|source table/대표 trace만 선택|
|Liu Zenodo|L3|공개|LT 상대 timing만 선택|
|Zeng Mendeley|embryo/newly hatched context|CC BY 4.0|발달 근거; runtime calibration 후순위|
|Kohsaka raw/code|L1 EM + L3 function|요청 시 제공|프로젝트의 공개 다운로드 전용 원칙상 요청하지 않음|
|Cooney example/code|stage 불명확/mixed|코드 저장소 라이선스 불명확|참조만; 재배포/복사 보류|

## 남은 불확실성

1. 자연스러운 전방 기계감각에서 L1 MDN까지 이어지는 완전한 synaptic path가 아직 없다.
2. A18b 이후 각 muscle-specific MN으로 이어지는 후진 경로가 모든 분절에서 완전하지 않다.
3. A19f가 후진 wave generation, ascending coordination, head-sweep control 사이에서 맡는 역할이 아직 완전히 분리되지 않았다.
4. L1의 protopodium geometry, contact area, 수직·수평 반력은 직접 측정되지 않았다.
5. Booth의 WARP는 수직 반력을 잘 측정하지만 수평 traction의 직접 지도를 제공하지 않는다.
6. LT interwave phase가 L1에서도 L3와 같은 기능을 하는지 직접 확인해야 한다.
7. L1 개별 근육의 CSA, attachment, specific force, activation time constant는 여전히 실측 atlas가 아니다.
8. L1 free-crawling에서 neural activity와 full-body contact mechanics를 동시에 측정한 단일 dataset은 확보되지 않았다.

이 불확실성은 기능을 막는 이유가 아니라 provenance를 분리해야 하는 이유다. 토폴로지는 L1 EM에서, 상대 기능은 L2/L3에서, 절대 L1 운동학은 Greaney에서, 미지의 물성은 bounded fitting으로 가져오되 UI와 문서에서 그 출처를 명확히 보여야 한다.

## 다음 작업의 완료 조건

다음 코드 PR은 아래를 모두 만족해야 완료로 본다.

- 전진과 후진의 neural subnet이 별도이며 MDN/Pair1을 통한 상호 배제가 보인다.
- 운동 방향을 직접 지정하는 body command가 없다.
- 동일 muscle atlas를 두 방향이 공유하고 recruitment timing만 달라진다.
- 종축 수축 뒤 이완 경로가 있어 몸이 한 방향으로 계속 찌그러지지 않는다.
- 전역 one-way retention을 제거하거나 명시적 legacy 비교 모드로 격리한다.
- local contact patch의 연속적인 sequestration/contact 값이 몸체 변형에서 계산되며, lift/plant phase는 사후 진단값으로만 파생된다.
- L1 Greaney 회귀와 direction/lesion test를 모두 통과한다.
- 모든 수축을 감각 입력과 선행 neural activity까지 trace할 수 있다.
- L2/L3/embryo 수치가 L1 `MEASURED_PUBLISHED`로 잘못 등록되지 않는다.

## Sources

[^1]: Cooney, P. C. et al. (2023). “Neuromuscular basis of Drosophila larval rolling escape behavior.” *PNAS* 120. DOI: [10.1073/pnas.2303641120](https://doi.org/10.1073/pnas.2303641120). [Open full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC10743538/).
[^2]: Cooney et al. analysis repository. [cooneypc4/larval_escape_manuscript](https://github.com/cooneypc4/larval_escape_manuscript).
[^3]: Carreira-Rosario, A., Zarin, A. A., Clark, M. Q. et al. (2018). “MDN brain descending neurons coordinately activate backward and inhibit forward locomotion.” *eLife* 7:e38554. DOI: [10.7554/eLife.38554](https://doi.org/10.7554/eLife.38554).
[^4]: Pulver, S. R. et al. (2015). “Imaging fictive locomotor patterns in larval Drosophila.” *Journal of Neurophysiology* 114:2564–2577. DOI: [10.1152/jn.00731.2015](https://doi.org/10.1152/jn.00731.2015). [Open full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC4637366/).
[^5]: Kohsaka, H. et al. (2019). “Regulation of forward and backward locomotion through intersegmental feedback circuits in Drosophila larvae.” *Nature Communications* 10:2654. DOI: [10.1038/s41467-019-10695-y](https://doi.org/10.1038/s41467-019-10695-y).
[^6]: Fushiki, A. et al. (2016). “A circuit mechanism for the propagation of waves of muscle contraction in Drosophila.” *eLife* 5:e13253. DOI: [10.7554/eLife.13253](https://doi.org/10.7554/eLife.13253).
[^7]: Zeng, X. et al. (2021). “An electrically coupled pioneer circuit enables motor development via proprioceptive feedback in Drosophila embryos.” *Current Biology* 31:5327–5340.e5. DOI: [10.1016/j.cub.2021.10.005](https://doi.org/10.1016/j.cub.2021.10.005). [Accepted manuscript](https://research-repository.st-andrews.ac.uk/bitstream/10023/26208/1/Zeng_2021_CB_Electrically_AAM.pdf).
[^8]: Zeng et al. raw data. Mendeley Data v1, CC BY 4.0. DOI: [10.17632/mh3nzy64nc.1](https://doi.org/10.17632/mh3nzy64nc.1).
[^9]: McNulty, P. et al. (2025). “Closed-loop two-photon functional imaging in a freely moving animal.” *Nature Communications* 16:5950. DOI: [10.1038/s41467-025-60648-x](https://doi.org/10.1038/s41467-025-60648-x).
[^10]: McNulty et al. data. Harvard Dataverse. DOI: [10.7910/DVN/ZNJ8U9](https://doi.org/10.7910/DVN/ZNJ8U9).
[^11]: McNulty et al. analysis code, GPL-3.0. [GershowLab/CRASH2p](https://github.com/GershowLab/CRASH2p).
[^12]: Zarin, A. A. et al. (2019). “A multilayer circuit architecture for the generation of distinct locomotor behaviors in Drosophila.” *eLife* 8:e51781. DOI: [10.7554/eLife.51781](https://doi.org/10.7554/eLife.51781).
[^13]: Zarin et al. analysis/data repository, GPL-3.0. [alitwinkumar/larval_locomotion](https://github.com/alitwinkumar/larval_locomotion).
[^14]: Hiramoto, M. et al. (2021). “Regulation of coordinated muscular relaxation in Drosophila larvae by a pattern-regulating intersegmental circuit.” *Nature Communications* 12:2943. DOI: [10.1038/s41467-021-23273-y](https://doi.org/10.1038/s41467-021-23273-y).
[^15]: Liu, Y. et al. (2023). “Synchronous multi-segmental activity between metachronal waves controls locomotion speed in Drosophila larvae.” *eLife* 12:e83328. DOI: [10.7554/eLife.83328](https://doi.org/10.7554/eLife.83328).
[^16]: Liu et al. dataset. Zenodo. DOI: [10.5281/zenodo.7052205](https://doi.org/10.5281/zenodo.7052205).
[^17]: Booth, J. H. et al. (2024). “Optical mapping of ground reaction force dynamics in freely behaving Drosophila melanogaster larvae.” *eLife* 12:RP87746. DOI: [10.7554/eLife.87746](https://doi.org/10.7554/eLife.87746). [Open full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC11265794/).
[^18]: Booth et al. research dataset, CC BY. University of St Andrews Research Data Repository. DOI: [10.17630/f2a655d8-85c7-4bc0-b01b-b6f67aab2f07](https://doi.org/10.17630/f2a655d8-85c7-4bc0-b01b-b6f67aab2f07).
[^19]: Greaney, M. R. et al. (2026). “Multiple Scales of Coordination along the Body Axis during Drosophila Larval Locomotion.” *Journal of Neuroscience*. DOI: [10.1523/JNEUROSCI.1623-25.2026](https://doi.org/10.1523/JNEUROSCI.1623-25.2026). [Open full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC13107222/).
[^20]: Sun, X. et al. (2022). “A neuromechanical model of multiple network locomotor control in Drosophila larvae based on physical measurements.” *BMC Biology* 20:130. DOI: [10.1186/s12915-022-01336-w](https://doi.org/10.1186/s12915-022-01336-w). [Open full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC9199175/).
[^21]: Sun et al. kinematic dataset. Figshare. DOI: [10.6084/m9.figshare.19289594](https://doi.org/10.6084/m9.figshare.19289594).
[^22]: Jonaitis, J. et al. (2024). “Steering From the Rear: Coordination of Central Pattern Generators Underlying Navigation.” bioRxiv preprint. DOI: [10.1101/2024.06.17.598162](https://doi.org/10.1101/2024.06.17.598162).
