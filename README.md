# 식품 법령 개정 모니터

식약처의 식품 법령 개정 공고(법/시행령/시행규칙 + 입법·행정예고)를 매주 자동 수집해 아카이브하는 시스템입니다. (법제처·식품안전나라 연동은 2026-07-22 제외 — 설계서.md "데이터 소스 변경 이력" 참고)

**사이트**: https://primexx98-sudo.github.io/FOODLAW-MONITORING/

## 빠른 시작

1. 이 저장소를 GitHub에 push
2. Settings → Pages → `/docs` 폴더로 배포 설정
3. (선택) Settings → Secrets → `GROQ_API_KEY`(Groq API 키, 무료 발급 https://console.groq.com/keys, 항목 요약 생성용) 등록
4. Actions → `주간 식품 법령 수집` → `Run workflow` 로 첫 실행

자세한 내용은 `설계서.md` 참고. 법령자료(지정 법령·고시 원문+조문 diff) 서브탭도 이 저장소 안에서
함께 운영됩니다 — 설계서.md "법령자료 서브탭 신설" 섹션 참고.

3개 대시보드(건식트랜드+식품법령모니터+법령자료)를 하나로 묶은 전체 개요는
`Desktop\업무\건강기능식품 통합 대시보드\설계서.md` 참고.
