# 식품 법령 개정 모니터

식약처의 식품 법령 개정 공고(법/시행령/시행규칙 + 입법·행정예고)를 매주 자동 수집해 아카이브하는 시스템입니다. (법제처·식품안전나라 연동은 2026-07-22 제외 — 설계서.md "데이터 소스 변경 이력" 참고)

**사이트**: https://primexx98-sudo.github.io/FOODLAW-MONITORING/

## 빠른 시작

1. 이 저장소를 GitHub에 push
2. Settings → Pages → `/docs` 폴더로 배포 설정
3. (선택) Settings → Secrets → `GEMINI_API_KEY`(Gemini API 키, 무료 발급 https://aistudio.google.com/apikey, 항목 요약 생성용) 등록
4. Actions → `주간 식품 법령 수집` → `Run workflow` 로 첫 실행

자세한 내용은 `설계서.md` 참고.
