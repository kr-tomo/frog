# 스프라이트 교체·추가 가이드

`index.html` 맨 위의 `ASSETS`(공통)와 `THEME_ASSETS`(테마별) 매니페스트가 가리키는 경로에 이미지를 넣으면
임시 그래픽 대신 사용됩니다. 일부만 넣어도 되고, 판정(돌 타원, 터치 반경, 상어·얕은 물 영역)은 코드가 정하므로
이미지를 바꿔도 게임 규칙은 바뀌지 않습니다.

## 1) 테마(계절) 이미지 — `assets/themes/<테마 id>/`
기본 제공: `spring` `summer` `autumn` `winter`. 폴더 안 파일은 모든 테마가 같은 이름입니다.

| 파일 | 설명 | 권장 크기 |
|---|---|---|
| `water.webp` | 강 배경 (불투명) | 1080×1920 |
| `island_start.webp` | 아래(출발) 섬. **위쪽 가장자리가 해안선**, 위는 투명 | 1080×340 |
| `island_goal.webp` | 위(도착) 섬. **아래쪽 가장자리가 해안선**, 결승선(체크무늬) 포함 | 1080×220 |
| `stone.png` | 돌 (타원에 맞춰 늘려 그려짐, 3:1 권장, 그림자는 코드가 그림) | 600×200 |
| `stone_slippery.png` | 미끄러운 돌 (한눈에 젖은/얼음 느낌이 나게) | 600×200 |
| `shallow.png` | 얕은 물을 처음 밟은 뒤 나타나는 희미한 그림자 | 240×160 |
| `particles.png` | 계절 입자 4종을 가로로 이어 붙인 시트 (꽃잎/반짝임/낙엽/눈) | 256×64 (64×64 × 4) |
| `icon.png` | 설정 화면의 계절 아이콘 | 96×96 |

- 테마 폴더에 없는 파일은 **기본 테마(spring) 폴더의 같은 파일**로 대신 표시됩니다.
- 확장자는 `index.html`의 `THEME_ASSETS[...].src`에서 바꿀 수 있습니다 (png/webp/jpg 모두 가능).

### 새 테마 추가 (예: `night`)
1. `assets/themes/night/` 폴더를 만들고 위 파일을 넣는다 (일부만 넣어도 됨).
2. `index.html`의 `CONFIG.themes`에 항목 한 줄 추가: `{ id: 'night', name: '밤', pal: {...}, particles: {...} }`
   (`pal`은 이미지가 없을 때 쓰는 임시 색, `particles`는 입자 종류/개수/속도)
3. `sw.js`의 `THEMES`에 `'night'`를 추가하고 `VERSION`을 올린다 (오프라인 미리 받기용, 생략해도 동작).
설정 화면의 테마 카드는 `CONFIG.themes`를 따라 자동으로 늘어납니다.

## 2) 공통 이미지 — `assets/`
| 경로 | 설명 | 권장 크기 |
|---|---|---|
| `shark.png` | 상어. **오른쪽을 보는** 4프레임 시트(가로로 이어 붙임). 왼쪽으로 갈 땐 코드가 뒤집음 | 1024×128 (256×128 × 4) |
| `frogs/<id>/<상태>.png` | 개구리. id: `balanced` `power` `precise` `leaper` `steady`, 상태: `idle` `charge` `jump` `land` `splash` `slip` `win` `lose` (`idle` 하나만 있어도 전부 대체) | 128×128, **위쪽을 보는 모양** |
| `fx/shadow.png` `fx/splash.png` `fx/ripple.png` `fx/dust.png` `fx/confetti.png` | 이펙트 (splash 8프레임, ripple 6, dust 5, confetti 4 — 가로로 이어 붙임) | 프레임당 약 140×110 |
| `ui/gauge_bg.png` `ui/gauge_fill.png` | 차징 게이지 | 64×12 |
| `ui/arrow.png` | 방향 화살표 (위쪽을 향함, 길이는 자동 조절) | 26×60 |
| `ui/ring_p1.png` `ui/ring_p2.png` `ui/badge_p1.png` `ui/badge_p2.png` | 플레이어 링·라벨 | 약 86×53 / 44×24 |
| `ui/btn.png` `ui/btn_sub.png` `ui/btn_icon.png` `ui/panel.png` `ui/card.png` `ui/card_selected.png` `ui/title.png` | 버튼·패널·카드·로고 | 자유(늘려 그림) |
| `ui/toggle_on.png` `ui/toggle_off.png` | 설정 화면 스위치 | 78×40 |
| `ui/icon_opt_shark.png` `icon_opt_slippery.png` `icon_opt_shallow.png` | 옵션 아이콘 | 44×44 |
| `ui/icon_pause.png` `ui/icon_sound_on.png` `ui/icon_sound_off.png` | 아이콘 | 28~30px |
| `ui/count_3.png` `count_2.png` `count_1.png` `go.png` | 카운트다운 | 자유 |

## 3) 계절 이미지 다시 만들기
`python3 tools/make_assets.py [spring|summer|autumn|winter|shark]` — 이 폴더의 계절 이미지와 상어를 만든 스크립트입니다
(Pillow·numpy·scipy 필요). 색이나 장식을 바꿔 다시 생성하거나 새 계절을 추가할 때 참고하세요.
