# 개구리 점프 (PWA)

두 사람이 한 화면에서 겨루는 개구리 징검다리 대결 게임. 번들러 없는 정적 파일이라 GitHub Pages에 그대로 올리면 됩니다.

## 파일 구성
| 파일 | 역할 |
|---|---|
| `index.html` | 게임 전체 (HTML+CSS+JS). 상단 `CONFIG`에서 밸런스 조절 |
| `manifest.webmanifest` | 웹 앱 매니페스트 (이름, 아이콘, 전체화면 설정) |
| `sw.js` | 서비스 워커 — 오프라인 실행, 업데이트 처리 |
| `icons/` | 192·512·maskable·apple-touch·favicon |
| `assets/` | 교체용 스프라이트 폴더 (비어 있어도 임시 그래픽으로 실행됨) |

## 배포 (GitHub Pages)
1. 이 폴더의 내용을 저장소 루트(또는 `docs/`)에 올립니다.
2. Settings → Pages 에서 해당 브랜치/폴더를 선택합니다.
3. `https://<계정>.github.io/<저장소>/` 로 접속 → 브라우저 메뉴의 "홈 화면에 추가/설치".
   - Android·데스크톱 Chrome: 타이틀 화면에 "앱으로 설치" 버튼이 나타납니다.
   - iPhone: Safari 공유 버튼 → "홈 화면에 추가".
- PWA는 **HTTPS**(또는 localhost)에서만 설치·오프라인이 동작합니다. `file://`로 열면 게임은 되지만 PWA 기능은 꺼집니다.
- 로컬 확인: `python3 -m http.server 8000` 후 `http://localhost:8000`

## 새 버전 배포
`sw.js` 맨 위 `VERSION` 값을 올리고 올리세요. 이미 설치된 앱은 다음 실행 때 새 파일로 바뀌며, 타이틀에 "새 버전 적용" 버튼이 보일 수 있습니다.

## 디버그 URL 파라미터
`?seed=123` 돌 배치 고정 · `?ratio=0.8` 돌 공비 · `?debug=1` 판정 영역 표시 · `?noassets=1` 이미지 로딩 끄기

## 스프라이트 교체
`assets/README.md` 참고.
