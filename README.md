# Synthetic Image QC Log Portfolio

> 대량 이미지 검수 QC 로그를 **합성 데이터**로 재현하고, 검증 스크립트와 **CI로 집계 정합성을 자동 점검**하는 데이터 QC 포트폴리오

[![validate](https://github.com/2nyoung-0529/synthetic-image-qc-portfolio/actions/workflows/validate.yml/badge.svg)](https://github.com/2nyoung-0529/synthetic-image-qc-portfolio/actions/workflows/validate.yml)

**한국어** | [English](README.en.md)

대량 이미지 검수 업무를 가정하여 설계한 **합성 데이터 기반 QC 로그 포트폴리오**입니다. 작업자·일자별 생산성, 승인/드롭 결과, 드롭 사유와 배치 단위 처리 이력을 재현 가능한 형태로 구성했습니다.

> 이 저장소의 데이터, 작업자 ID, 경로, 배치 ID 및 수치는 모두 포트폴리오 설명을 위해 생성한 합성(synthetic) 데이터입니다. 실제 기업, 기관, 국방 사업, 시설, 장비 또는 운영 환경을 나타내지 않습니다.

## 프로젝트에서 보여주는 역량

- 이벤트 로그와 일일 요약 간 집계 정합성 검증
- 코드북 기반 QC 사유 표준화
- 검수량·드롭률·처리시간 KPI 산출
- 공개 가능한 형태의 익명화 및 데이터 문서화
- 검증 스크립트를 통한 재현 가능한 데이터 품질 관리

## 핵심 결과

| 지표 | 결과 | 계산 방식 |
|---|---:|---|
| 총 검수 이미지 | 95,510장 | 일일 검수량 합계 |
| 승인 이미지 | 54,168장 | 일일 승인량 합계 |
| 드롭 이미지 | 41,342장 | 일일 드롭량 합계 |
| 전체 드롭률 | 43.3% | 드롭 ÷ 검수 |
| 작업자 1인·일 평균 검수량 | 7,959장 | 총 검수량 ÷ 12 worker-days |
| 이미지당 가중 평균 QC 시간 | 1.73초 | 배치 검수량으로 가중 평균 |

주요 드롭 사유는 폴더 구조 오류 43.0%, 시계열 라벨 오류 31.0%입니다. 원본 샘플에서 상세 사유가 분리되지 않았던 2,475장은 기존 항목에 임의 배분하지 않고 `OTHER_MANUAL`로 명시했습니다.

> 전체 드롭률 43.3%는 실제 운영 지표가 아니라, 다양한 드롭 사유와 검증 로직을 한 데이터셋에서 보여주기 위해 의도적으로 높게 설정한 합성 값입니다. 실제 파이프라인에서는 성숙도에 따라 훨씬 낮은 드롭률을 기대할 수 있습니다.

### 드롭 사유 분포

![드롭 사유 분포](charts/drop_reason_distribution.png)

### 일자별 검수량

![일자별 검수량](charts/daily_review_volume.png)

### 작업자별 드롭률

![작업자별 드롭률](charts/worker_drop_rate.png)

## 데이터 구성

### `data/qc_daily_summary.csv`

작업자·일자별 검수 실적과 드롭 사유 분해를 제공합니다. `TOTAL` 행은 포함하지 않으며, 집계는 분석 과정에서 계산합니다.

핵심 검증식:

```text
reviewed_images = accepted_images + dropped_images
dropped_images = sum(all drop reason columns)
drop_rate = dropped_images / reviewed_images
```

### `data/qc_action_log.csv`

48개 배치의 처리 이벤트 예시입니다. `main_drop_code`는 배치의 대표 드롭 사유이며, 승인과 드롭 이미지가 함께 존재하는 배치는 `PARTIAL_PASS`로 표현합니다. `workflow_status`는 배치 전체의 품질 판정이 아니라 후속 처리 단계입니다.

#### QC 로그 샘플 (앞 5개 배치)

가독성을 위해 전체 17개 컬럼 중 핵심 컬럼만 표시했습니다. 아래 값은 원본 CSV의 앞 5개 행과 동일합니다.

| event_ts | worker_id | batch_id | environment_condition | batch_reviewed | batch_accepted | batch_dropped | main_drop_code |
|---|---|---|---|---:|---:|---:|---|
| 2025-03-12 09:43:00 | QC001 | 20250312_01_B1 | rain_wetroad | 2,296 | 1,427 | 869 | LOW_VISIBILITY |
| 2025-03-12 11:50:00 | QC001 | 20250312_01_B2 | day_clear | 2,296 | 1,355 | 941 | LOW_VISIBILITY |
| 2025-03-12 13:04:00 | QC001 | 20250312_01_B3 | day_clear | 2,296 | 1,391 | 905 | LOW_VISIBILITY |
| 2025-03-12 15:44:00 | QC001 | 20250312_01_B4 | night_lowlight | 2,296 | 1,391 | 905 | IMAGE_CONTENT_AMBIGUITY |
| 2025-03-12 09:03:00 | QC002 | 20250312_02_B1 | mixed_indoor_outdoor | 1,882 | 1,117 | 765 | DUPLICATE_CORRUPT |

> `environment_condition`은 배치의 촬영 조건이고 `main_drop_code`는 배치의 대표 드롭 사유로, 둘은 직접적인 인과관계가 아닙니다. 예를 들어 `day_clear` 배치라도 대표 사유가 `LOW_VISIBILITY`일 수 있는데, 이는 해당 배치에서 저시야 드롭이 가장 많았다는 의미이지 촬영 조건이 저시야였다는 뜻이 아닙니다.

[전체 QC 처리 로그 보기](data/qc_action_log.csv)

### `data/drop_codebook.csv`

로그 코드와 의미를 정의합니다. 모든 `main_drop_code`는 코드북에 존재하도록 검증합니다.

### `data/summary_statistics.csv`

핵심 지표와 계산식을 기계 처리 가능한 형태로 제공합니다. 비율은 `%` 문자열이 아니라 0~1 범위의 숫자로 저장합니다.

## 검증 방법

Python 3 환경에서 저장소 루트를 인자로 전달합니다.

```bash
python tools/validate_data.py .
```

검증 항목:

- 일일 행별 검수·승인·드롭 산술 일치
- 총 드롭과 세부 사유 합계 일치
- 배치 행별 검수·승인·드롭 산술 일치
- 배치 로그의 작업자·일자별 합계와 일일 요약 일치
- 모든 대표 드롭 코드의 코드북 존재 여부

이 검증은 매 푸시·PR마다 GitHub Actions에서 자동 실행되며, 상단의 `validate` 배지가 최신 실행 결과를 나타냅니다.

## 데이터 재현

`data/`의 CSV는 큐레이션된 대표 스냅샷이며, 동일한 스키마와 정합성 규칙을 만족하는 데이터셋을 코드로 다시 만들 수 있습니다.

```bash
# 동일 seed에서 결정론적으로 재현되는 데이터셋 생성 → build/data 에 기록 후 검증
python tools/generate_qc_dataset.py --seed 20250312 --out build/data
python tools/validate_data.py build

# 차트 재생성(matplotlib 필요) → build/charts
pip install -r requirements.txt
python tools/make_charts.py --data data --out build/charts
```

`Makefile`로도 동일하게 실행할 수 있습니다.

```bash
make validate    # 커밋된 데이터 정합성 검증
make generate    # 합성 데이터 재생성 후 검증
make charts      # 차트 재생성
```

- `generate_qc_dataset.py`는 **표준 라이브러리만** 사용하며, 같은 `--seed`에서는 항상 동일한 결과를 만듭니다.
- 드롭 사유 6분류는 총 드롭 수에서 고정 비율로 분해되고, 배치 합계는 항상 일일 요약과 일치하도록 생성됩니다(→ `validate_data.py` 통과).
- 생성기는 커밋된 `data/`를 **덮어쓰지 않으며**, 기본적으로 `build/`(gitignore) 아래에 기록합니다. `--out data`로 지정하면 제자리 재생성도 가능합니다.
- 생성기가 만드는 값은 커밋된 스냅샷과 숫자까지 동일하진 않습니다(설계 의도). 재현되는 것은 **데이터 구조와 정합성**이며, 대표 스냅샷은 `data/`로 고정합니다.

## 리포트 및 산출물

분석 결과를 공유용 문서로도 제공합니다.

- [`reports/qc_analysis.xlsx`](reports/qc_analysis.xlsx) — 지표·피벗·드롭 사유 분해를 담은 분석 워크북
- [`reports/qc_summary_report.pdf`](reports/qc_summary_report.pdf) — 핵심 결과를 요약한 1페이지 리포트

## 폴더 구조

```text
synthetic-image-qc-portfolio/
├── README.md
├── LICENSE
├── Makefile
├── requirements.txt
├── data/
│   ├── drop_codebook.csv
│   ├── qc_action_log.csv
│   ├── qc_daily_summary.csv
│   ├── summary_statistics.csv
│   └── validation_manifest.json
├── charts/
│   ├── daily_review_volume.png
│   ├── drop_reason_distribution.png
│   └── worker_drop_rate.png
├── tools/
│   ├── validate_data.py
│   ├── generate_qc_dataset.py
│   └── make_charts.py
└── reports/
    ├── qc_analysis.xlsx
    └── qc_summary_report.pdf
```

## 데이터 설계 원칙과 한계

- 데이터는 실제 업무 구조를 설명하기 위한 합성 예시이며 운영 성과를 주장하지 않습니다.
- `main_drop_code`는 배치 대표 사유이므로 배치 내 모든 드롭 이미지의 개별 사유를 뜻하지 않습니다.
- `OTHER_MANUAL`은 원본 합성 샘플에 상세 분류가 없던 잔여 드롭이며, 향후 실제 파이프라인에서는 필수 상세 사유 입력으로 대체할 수 있습니다.
- NAS 경로는 구조 설명을 위한 가상 경로이며 실제 서버 정보가 아닙니다.

## License

코드와 합성 데이터는 [MIT License](LICENSE)에 따라 사용할 수 있습니다.
