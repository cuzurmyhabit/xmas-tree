# 🎄 HOLO XMAS TREE

터미널에서 3D로 회전하는 홀로그램 ASCII 크리스마스 트리.
설치할 것 없이 명령어 한 줄이면 바로 실행됩니다. (Python 3만 있으면 OK)

A rotating 3D hologram ASCII Christmas tree for your terminal — pink fireworks, hearts, aurora, snow and all.

## 바로 실행하기

**macOS / Linux**

```bash
curl -sL https://raw.githubusercontent.com/cuzurmyhabit/xmas-tree/main/xmas_tree.py | python3 -
```

**Windows cmd**

```bash
curl -sL https://raw.githubusercontent.com/cuzurmyhabit/xmas-tree/main/xmas_tree.py | python -
```

**Windows PowerShell** (`curl` 대신 `curl.exe`)

```bash
curl.exe -sL https://raw.githubusercontent.com/cuzurmyhabit/xmas-tree/main/xmas_tree.py | python -
```

종료는 `Ctrl + C`.

## 내려받아서 실행하기

```bash
git clone https://github.com/cuzurmyhabit/xmas-tree.git
cd xmas-tree
python3 xmas_tree.py
```

Windows에서는 `tree.bat`을 더블클릭해도 됩니다.

## 옵션

옵션은 명령어 끝에 붙입니다. 한 줄 실행일 때는 `python3 -` 뒤에 붙이세요.
예: `curl -sL ... | python3 - --speed 2`

| 옵션 | 설명 |
| --- | --- |
| `--speed 2` | 회전 속도 배율 (기본 1) |
| `--fps 15` | 프레임 속도 (기본 24, 끊기면 낮추기) |
| `--no-intro` | 홀로그램 생성 연출 건너뛰기 |
| `--no-resize` | 시작할 때 창 최대화 안 함 |
| `--no-fireworks` | 불꽃놀이 끄기 |
| `--no-aurora` | 오로라 끄기 |
| `--256` | 색이 이상하게 나오면 256색 모드로 |

## 더 멋지게 보는 팁

- 창을 최대화하고 글자 크기를 줄이면(macOS `Cmd + -`, Windows `Ctrl + 마우스 휠`) 트리가 훨씬 크고 촘촘해집니다.
- 24bit 색을 지원하는 터미널(macOS 26 터미널, iTerm2, Windows Terminal 등)에서 오로라와 별빛 효과가 가장 화려하게 보입니다.
- 화면 글자는 전부 ASCII라 한글 Windows cmd에서도 줄이 밀리지 않습니다.
