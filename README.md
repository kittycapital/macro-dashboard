# 📊 글로벌 매크로 대시보드

FRED API 기반 글로벌 매크로 경제 지표 대시보드. GitHub Actions로 매일 자동 업데이트.

## 📋 지표 목록

| 지표 | 데이터 소스 | 업데이트 주기 |
|---|---|---|
| 글로벌 M2 통화량 | FRED (M2SL 외) | 월간 |
| 연준 대차대조표 | FRED (WALCL) | 주간 |
| 미국 일드커브 | FRED (DGS 시리즈) | 일간 |
| 금융상황지수 NFCI | FRED (NFCI) | 주간 |
| G7+한국 기준금리 | FRED | 월간 |
| 국가부채/GDP | FRED + IMF | 분기/연간 |
| 글로벌 PMI | FRED (OECD CLI) | 월간 |

## 🚀 설정 방법

### 1. FRED API Key 발급 (무료)
1. https://fred.stlouisfed.org/docs/api/api_key.html 접속
2. 계정 생성 후 API Key 발급

### 2. GitHub 설정
1. 이 레포를 fork 또는 새 레포에 코드 업로드
2. Settings → Secrets and variables → Actions → New repository secret
   - Name: `FRED_API_KEY`
   - Value: 발급받은 API 키
3. Settings → Pages → Source: `main` branch, `/ (root)` 선택

### 3. 첫 데이터 수집
Actions 탭 → "매크로 대시보드 데이터 업데이트" → "Run workflow" 클릭

### 4. imweb 임베드
```html
<style>
  .macro-wrap{width:100%;overflow:hidden}
  .macro-wrap iframe{width:100%;border:none}
</style>
<div class="macro-wrap">
  <iframe id="macroFrame"
    src="https://YOUR_USERNAME.github.io/macro-dashboard/"
    scrolling="no"
  ></iframe>
</div>
<script>
window.addEventListener('message', e => {
  if(e.data?.type==='resize')
    document.getElementById('macroFrame').style.height = e.data.height+'px';
});
</script>
```

## 📁 파일 구조
```
macro-dashboard/
├── index.html           # 대시보드 HTML
├── fetch_data.py        # FRED 데이터 수집 스크립트
├── data/                # JSON 데이터 (자동 생성)
│   ├── m2.json
│   ├── fed_balance_sheet.json
│   ├── yield_curve.json
│   ├── nfci.json
│   ├── rates.json
│   ├── debt_gdp.json
│   └── pmi.json
└── .github/workflows/
    └── update-data.yml  # GitHub Actions (매일 07:00 KST)
```
