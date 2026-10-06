# 스프라이트 교체 가이드

`index.html`의 `ASSETS` 매니페스트가 가리키는 경로에 PNG를 넣으면 임시 그래픽 대신 사용됩니다. 일부만 넣어도 됩니다(나머지는 임시 그래픽).
판정(돌 타원, 터치 반경)은 코드가 정하므로 이미지를 바꿔도 게임 규칙은 변하지 않습니다.

| 경로 | 설명 | 권장 크기 |
|---|---|---|
| `water.png` | 강 배경 | 540×960 |
| `island_start.png` | 아래(출발) 섬 — 하단 여유 포함 | 540×170 |
| `island_goal.png` | 위(도착) 섬 | 540×110 |
| `stone.png` | 돌 (타원에 맞춰 늘려 그려짐, 가로:세로 = 2:1 권장) | 300×150 |
| `frogs/<id>/<상태>.png` | 개구리. id: `balanced` `power` `precise` `leaper` `steady`, 상태: `idle` `charge` `jump` `land` `splash` `win` `lose` | 64×64, **위쪽을 보는 모양** |
| `fx/shadow.png` `fx/splash.png` `fx/ripple.png` `fx/dust.png` `fx/confetti.png` | 이펙트 (splash 8프레임, ripple 6, dust 5, confetti 4 — 가로로 이어 붙임) | 프레임당 약 140×110 |
| `ui/gauge_bg.png` `ui/gauge_fill.png` | 차징 게이지 | 64×12 |
| `ui/arrow.png` | 방향 화살표 (위쪽을 향함, 길이는 자동 조절) | 26×60 |
| `ui/ring_p1.png` `ui/ring_p2.png` `ui/badge_p1.png` `ui/badge_p2.png` | 플레이어 링·라벨 | 72×44 / 44×24 |
| `ui/btn.png` `ui/btn_sub.png` `ui/btn_icon.png` | 버튼 | 자유(늘려 그림) |
| `ui/panel.png` `ui/card.png` `ui/card_selected.png` `ui/title.png` | 패널·카드·로고 | 자유 |
| `ui/icon_pause.png` `ui/icon_sound_on.png` `ui/icon_sound_off.png` | 아이콘 | 28~30px |
| `ui/count_3.png` `count_2.png` `count_1.png` `go.png` | 카운트다운 | 자유 |

개구리는 `idle.png` 하나만 넣어도 모든 상태에 쓰입니다.
