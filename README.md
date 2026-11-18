# 🎄 HOLO XMAS TREE

터미널에서 3D로 회전하는 홀로그램 ASCII 크리스마스 트리.
설치할 것 없이 명령어 한 줄이면 바로 실행됩니다. (Python 3만 있으면 OK)

A rotating 3D hologram ASCII Christmas tree for your terminal — pink fireworks, hearts, aurora, snow and all.

**윈도우 처음이라면 → [그림 설명서](https://cuzurmyhabit.github.io/xmas-tree/)**

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

---

## 🪟 윈도우 왕초보 가이드

### 👉 [그림으로 보는 설명서 열기 (복사 버튼 있음)](https://cuzurmyhabit.github.io/xmas-tree/)

위 링크를 누르면 보기 좋게 꾸며진 설명서 페이지가 열려요. 아래는 같은 내용의 글 버전이에요.

까만 명령 창에 명령어 한 줄을 붙여넣으면 빙글빙글 도는 트리가 나와요. 아래 순서대로 따라만 하면 돼요.

> 걸리는 시간 약 5분 · 준비물: 윈도우 10/11 PC, 인터넷 · 무료

### 1. 파이썬 설치하기 (처음 한 번만)

트리를 움직이는 프로그램이에요. 이미 깔려 있으면 2번으로 넘어가도 돼요.

1. 왼쪽 아래 **시작 버튼**(윈도우 로고)을 누르세요.
2. **Microsoft Store**라고 쳐서 여세요.
3. 스토어 검색창에 **Python**을 치세요.
4. **Python 3.13**을 고르세요. 숫자가 다르면 가장 큰 숫자를 고르면 돼요. 만든 곳이 **Python Software Foundation**인지 확인하세요.
5. **받기**(또는 설치)를 누르고 끝날 때까지 기다리세요.

> 스토어를 못 쓰면 [python.org](https://www.python.org/downloads/)에서 받아도 돼요.
> 이때는 설치 첫 화면 아래의 **Add python.exe to PATH** 칸을 꼭 체크하세요.

### 2. 까만 명령 창 열기

1. 키보드에서 **윈도우 키**를 누르세요.
2. **cmd** 라고 치세요.
3. **Enter**를 누르세요.

까만 창이 뜨고 `C:\Users\이름>` 같은 글자가 보이면 성공이에요.

> 파이썬을 방금 설치했다면, 설치가 끝난 **뒤에** 창을 새로 열어야 해요.

### 3. 명령어 복사해서 붙여넣기

아래 명령어 박스 오른쪽 위의 복사 버튼을 누르세요.

```bash
curl -sL https://raw.githubusercontent.com/cuzurmyhabit/xmas-tree/main/xmas_tree.py | python -
```

1. 까만 창 안에서 **마우스 오른쪽 버튼**을 한 번 누르세요. 명령어가 붙여넣어져요. (`Ctrl + V`도 돼요.)
2. **Enter**를 누르세요.

창이 커지면서 트리가 아래에서 위로 쫘라락 만들어지면 완성이에요.

### 4. 구경하고 끄기

- **더 크고 촘촘하게:** `Ctrl`을 누른 채 **마우스 휠을 아래로** 굴리면 글자가 작아지면서 트리가 커져요.
- **창이 작으면:** 창 오른쪽 위 **□** 버튼으로 최대화하세요.
- **끄기:** `Ctrl + C`

다시 보고 싶으면 2번부터 또 하면 돼요. 파이썬은 다시 깔 필요 없어요.

### 창 맨 앞이 `PS`로 시작하면

윈도우 11은 cmd 대신 **PowerShell** 창이 열리기도 해요. 줄 맨 앞을 보고 맞는 명령어를 쓰세요.

| 창 맨 앞 | 쓸 명령어 |
| --- | --- |
| `C:\Users\...>` | 위 3번 명령어 그대로 |
| `PS C:\Users\...>` | `curl` 뒤에 `.exe`를 붙인 아래 명령어 |

```bash
curl.exe -sL https://raw.githubusercontent.com/cuzurmyhabit/xmas-tree/main/xmas_tree.py | python -
```

### 안 될 때

<details>
<summary><b>"python은(는) 내부 또는 외부 명령이 아닙니다"가 떠요</b></summary>

```
'python'은(는) 내부 또는 외부 명령, 실행할 수 있는 프로그램, 또는 배치 파일이 아닙니다.
```

파이썬이 아직 없거나, 설치 전에 연 창이에요.

1. 1번(파이썬 설치)을 하세요.
2. 까만 창을 닫고 새로 연 뒤 다시 붙여넣으세요.
3. 그래도 안 되면 명령어 맨 끝 `python -` 을 `py -` 로 바꿔서 해 보세요.

</details>

<details>
<summary><b>Enter를 눌렀더니 Microsoft Store가 열려요</b></summary>

파이썬이 아직 안 깔려 있다는 뜻이에요. 열린 스토어 화면에서 **받기**를 누르고, 다 깔리면 까만 창을 새로 열어 3번부터 다시 하세요.

</details>

<details>
<summary><b>빨간 글씨로 Invoke-WebRequest 오류가 나와요</b></summary>

PowerShell 창이에요. 위의 **PowerShell용 명령어**(`curl.exe`로 시작하는 것)를 쓰세요.

</details>

<details>
<summary><b>트리 대신 <code>[38;2;...</code> 같은 이상한 글자가 쏟아져요</b></summary>

윈도우가 아주 오래된 버전이라 색을 못 그리는 거예요.

1. Microsoft Store에서 **Windows Terminal**을 설치하세요.
2. Windows Terminal을 열고 PowerShell용 명령어로 다시 해 보세요.

</details>

<details>
<summary><b>색이 이상하거나 화면이 뚝뚝 끊겨요</b></summary>

명령어 맨 끝에 한 칸 띄고 옵션을 붙여서 다시 실행하세요.

- 색이 이상할 때: `--256`
- 끊길 때: `--fps 15`

예: `... | python - --fps 15`

</details>

<details>
<summary><b>아무 일도 안 일어나요</b></summary>

인터넷이 연결되어 있는지 확인하세요. 회사나 학교 컴퓨터는 이런 다운로드를 막아 두기도 해요. 그럴 땐 집 컴퓨터에서 해 보세요.

</details>

---

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
