#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ASCII PORTRAIT - 사진을 화려한 컬러 ASCII 아트로 터미널에 띄우기

  실행 :  python3 portrait.py                  (사진이 파일 안에 들어 있어요)
          python3 portrait.py --image 사진.png  (다른 사진. macOS는 jpg/heic/webp도 가능)
  종료 :  Ctrl + C

  옵션 :  --mode photo       색 모드 고정 (photo, neon, rainbow, matrix, thermal, holo)
          --say "옹옹.|배고파 옹"  말풍선 대사 바꾸기 (| 로 구분)
          --no-gags          선글라스/어지러움 같은 개그 연출 끄기
          --no-tree          트리 장식(별, 전구, 오너먼트, 선물) 끄기
          --no-fireworks     배경 폭죽 끄기
          --text "HELLO"     아래에 글자 띄우기
          --fps 30           프레임 속도 (기본 24)
          --no-intro         홀로그램 생성 연출 건너뛰기
          --no-resize        시작할 때 창 최대화 안 함
          --256 / --truecolor

  사용 기법
    - 셀 단위 박스 샘플링 + 알파 마스크로 사람만 오려내기
    - 명암 정규화(퍼센타일 스트레칭) 후 70단계 밀도 램프로 글자 선택
    - Sobel 경계 검출로 눈/코/입 윤곽에 방향 글자( / \\ | - ) 배치
    - 24bit 글자색 + 배경색으로 원래 피부/머리 색 재현
  인물은 전부 ASCII 로 그리고, 말풍선 대사만 한글(2칸 글자)을 씁니다. 파이썬 표준 라이브러리만 사용합니다.
"""

import argparse
import base64
import colorsys
import math
import os
import platform
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unicodedata
import zlib

TAU = math.tau

# 내장 사진의 얼굴 위치 (잘라낸 사진 기준 0~1 비율)
FACE = {
    "eyes": [(0.467, 0.466), (0.694, 0.485)],
    "eye_w": 0.05,
    "mouth": (0.568, 0.693),
    "mouth_w": 0.072,
    "cheeks": [(0.42, 0.585), (0.735, 0.585)],
}

# (개그, 대사) - 한 장면에 6.5초씩 차례로
SKITS = [("talk", "\uc639\uc639. \ub098\ub294 \ud2b8\ub9ac\ub2e4 \uc639"), ("talk", "\uc0ac\ub791\ud574 \uc639 <3"), ("talk", "\ubc18\uc9dd\ubc18\uc9dd \uc639?"), ("shades", "\uc639. (\uba4b\uc9d0)"),
         ("blush", "\ubd80\ub044 >_< \uc639"), ("talk", "\uba54\ub9ac \ud06c\ub9ac\uc2a4\ub9c8\uc2a4 \uc639\uc639!"), ("dizzy", "\uc5b4\uc9c0\ub7ec\uc6cc \uc639..."),
         ("shock", "\uc639?!?!"), ("disco", "\uc639\uc639\uc639~ \uc2e0\ub09c\ub2e4~"), ("talk", "\ub098 \uadc0\uc5fd\uc9c0? \uc639")]
SKIT_LEN = 6.5
TYPE_CPS = 9.0


def cw(c):
    return 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1


def text_w(s):
    return sum(cw(c) for c in s)
RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
WHITE = (255, 255, 255)
PINK = (255, 105, 180)
HOT_PINK = (255, 20, 147)
HOLO = (90, 235, 255)
GOLD = (255, 200, 60)
PINKS = [(255, 105, 180), (255, 20, 147), (255, 160, 205), (255, 190, 220), (245, 80, 170), (255, 0, 190)]
GLITCH = "01#=+:%$&"
MATRIX_CHARS = "0123456789ABCDEFXYZ$#@%&*+=<>"
BULBS = [(255, 45, 45), (255, 205, 40), (60, 150, 255), (120, 255, 120), (40, 235, 235), (175, 95, 255),
         (245, 245, 255)] + PINKS + PINKS
LIGHT_MODES = ["twinkle", "pink", "rainbow", "chase", "candy", "pulse"]


def star_polygon(ro, ri):
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        r = ro if k % 2 == 0 else ri
        pts.append((math.cos(a) * r, math.sin(a) * r))
    return pts


def in_poly(u, v, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > v) != (yj > v) and u < (xj - xi) * (v - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


# 배너용 5x5 블록 폰트
FONT = {
    "M": ["#...#", "##.##", "#.#.#", "#...#", "#...#"],
    "E": ["#####", "#....", "####.", "#....", "#####"],
    "R": ["####.", "#...#", "####.", "#..#.", "#...#"],
    "Y": ["#...#", ".#.#.", "..#..", "..#..", "..#.."],
    "C": [".####", "#....", "#....", "#....", ".####"],
    "H": ["#...#", "#...#", "#####", "#...#", "#...#"],
    "I": ["#####", "..#..", "..#..", "..#..", "#####"],
    "S": [".####", "#....", ".###.", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#.."],
    "A": [".###.", "#...#", "#####", "#...#", "#...#"],
}
BANNER = "MERRY CHRISTMAS"
PINK_HUES = (0.89, 0.92, 0.95, 0.97)


def pink_hue(rng):
    return rng.choice(PINK_HUES) + rng.uniform(-0.015, 0.015)


class Firework:
    def __init__(self, rng, x, y0, target_y):
        self.rng = rng
        self.x, self.y = float(x), float(y0)
        self.vy = -rng.uniform(0.9, 1.3)
        self.target = target_y
        self.hue = pink_hue(rng) if rng.random() < 0.45 else rng.random()
        self.style = rng.choice(["sphere", "rainbow", "ring", "willow", "double", "heart", "heart",
                                 "multi", "glitter", "pink", "pink"])
        self.trail, self.parts = [], []
        self.exploded = False
        self.flash = 0

    def alive(self):
        return (not self.exploded) or bool(self.parts)

    def step(self, s):
        if not self.exploded:
            self.trail.append((self.x, self.y))
            self.trail = self.trail[-5:]
            self.y += self.vy * s
            self.x += self.rng.uniform(-0.15, 0.15) * s
            if self.y <= self.target:
                self.explode()
            return
        self.flash = max(0, self.flash - 1)
        g = {"willow": 0.022, "heart": 0.008}.get(self.style, 0.035)
        drag = {"willow": 0.93, "heart": 0.955}.get(self.style, 0.95)
        keep = []
        for p in self.parts:
            p[7], p[8] = p[0], p[1]
            p[0] += p[2] * s
            p[1] += p[3] * s
            p[2] *= drag
            p[3] = p[3] * drag + g * s
            p[4] -= s
            if p[4] > 0:
                keep.append(p)
        self.parts = keep

    def explode(self):
        rng = self.rng
        self.exploded = True
        self.flash = 2
        if self.style == "heart":
            hue = pink_hue(rng) if rng.random() < 0.8 else 0.0
            for i in range(90):
                a = i / 90 * TAU
                hx = 16 * math.sin(a) ** 3 / 17.0
                hy = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)) / 17.0
                life = rng.uniform(30, 40)
                self.parts.append([self.x, self.y, hx * 1.8, hy * 0.9, life, life,
                                   hue + rng.uniform(-0.02, 0.02), self.x, self.y])
            return
        n = rng.randint(70, 110)
        for i in range(n):
            a = (i / n) * TAU + rng.uniform(-0.05, 0.05)
            sp = {"ring": 0.75, "double": 0.8 if i % 2 else 0.4}.get(self.style) or\
                (rng.uniform(0.25, 0.7) if self.style == "willow" else rng.uniform(0.15, 0.85))
            if self.style == "rainbow":
                hue = i / n
            elif self.style == "double":
                hue = self.hue + (0.5 if i % 2 else 0)
            elif self.style == "multi":
                hue = rng.random()
            elif self.style == "pink":
                hue = pink_hue(rng)
            elif self.style == "glitter":
                hue = rng.choice((0.12, 0.13, 0.93))
            else:
                hue = self.hue + rng.uniform(-0.05, 0.05)
            life = rng.uniform(35, 55) if self.style == "willow" else rng.uniform(22, 40)
            self.parts.append([self.x, self.y, math.cos(a) * sp * 2.0, math.sin(a) * sp, life, life, hue, self.x, self.y])


# (모드, 초) - photo 가 가장 오래, 나머지는 사이사이에
TIMELINE = [("photo", 10), ("neon", 5), ("photo", 9), ("rainbow", 5), ("photo", 9),
            ("matrix", 6), ("photo", 9), ("thermal", 5), ("photo", 9), ("holo", 5)]
TRANSITION = 0.9
INTRO_START, INTRO_LEN = 0.4, 3.0
INTRO_END = INTRO_START + INTRO_LEN

# --------------------------------------------------------------------------
# 터미널
# --------------------------------------------------------------------------


def enable_windows_vt():
    if os.name != "nt":
        return
    try:
        import ctypes

        k32 = ctypes.windll.kernel32
        h = k32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if k32.GetConsoleMode(h, ctypes.byref(mode)):
            k32.SetConsoleMode(h, mode.value | 0x0001 | 0x0004)
    except Exception:
        pass
    os.system("")


def detect_truecolor():
    if os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
        return True
    if os.environ.get("WT_SESSION") or os.name == "nt":
        return True
    tp = os.environ.get("TERM_PROGRAM", "")
    if tp in ("iTerm.app", "vscode", "WezTerm", "ghostty", "WarpTerminal", "Hyper"):
        return True
    if tp == "Apple_Terminal":
        try:
            return int(platform.mac_ver()[0].split(".")[0]) >= 26
        except Exception:
            return False
    return False


def maximize_window(write):
    orig = shutil.get_terminal_size((0, 0))
    if os.name == "nt":
        try:
            import ctypes

            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 3)
        except Exception:
            pass
    else:
        write("\x1b[9;1t")
    time.sleep(0.35)
    return orig


# --------------------------------------------------------------------------
# 색
# --------------------------------------------------------------------------


def _c(v):
    return 0 if v < 0 else 255 if v > 255 else int(v)


def scale(c, k):
    return (_c(c[0] * k), _c(c[1] * k), _c(c[2] * k))


def add(a, b, k=1.0):
    return (_c(a[0] + b[0] * k), _c(a[1] + b[1] * k), _c(a[2] + b[2] * k))


def mix(a, b, k):
    return (_c(a[0] + (b[0] - a[0]) * k), _c(a[1] + (b[1] - a[1]) * k), _c(a[2] + (b[2] - a[2]) * k))


def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))
    return (int(r * 255), int(g * 255), int(b * 255))


def quant(c, step=6):
    return (c[0] // step * step, c[1] // step * step, c[2] // step * step)


def gradient(stops, x):
    x = 0.0 if x < 0 else 1.0 if x > 1 else x
    p = x * (len(stops) - 1)
    i = min(len(stops) - 2, int(p))
    return mix(stops[i], stops[i + 1], p - i)


def smooth(x):
    x = 0.0 if x < 0 else 1.0 if x > 1 else x
    return x * x * (3 - 2 * x)


NEON = [(25, 0, 45), (120, 0, 120), (255, 40, 150), (255, 140, 210), (255, 238, 250)]
THERMAL = [(0, 0, 40), (70, 0, 150), (210, 0, 120), (255, 90, 0), (255, 220, 0), (255, 255, 230)]


def rgb_to_256(r, g, b):
    if abs(r - g) < 12 and abs(g - b) < 12 and abs(r - b) < 12:
        if r < 6:
            return 16
        if r > 240:
            return 231
        return 232 + min(23, max(0, int(round((r - 8) / 10.0))))

    def q(v):
        return 0 if v < 48 else 1 if v < 115 else min(5, (v - 35) // 40)

    return 16 + 36 * q(r) + 6 * q(g) + q(b)


class Painter:
    def __init__(self, truecolor):
        self.tc = truecolor
        self._fg, self._bg = {}, {}

    def fg(self, c):
        s = self._fg.get(c)
        if s is None:
            s = "\x1b[38;2;%d;%d;%dm" % c if self.tc else "\x1b[38;5;%dm" % rgb_to_256(*c)
            if len(self._fg) > 60000:
                self._fg.clear()
            self._fg[c] = s
        return s

    def bg(self, c):
        s = self._bg.get(c)
        if s is None:
            s = "\x1b[48;2;%d;%d;%dm" % c if self.tc else "\x1b[48;5;%dm" % rgb_to_256(*c)
            if len(self._bg) > 60000:
                self._bg.clear()
            self._bg[c] = s
        return s


# --------------------------------------------------------------------------
# 이미지 읽기 (PNG 직접 해독 + macOS sips 로 다른 형식 변환)
# --------------------------------------------------------------------------


def decode_png(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("PNG \ud30c\uc77c\uc774 \uc544\ub2c8\uc5d0\uc694")
    pos, idat = 8, []
    w = h = bd = ct = il = None
    while pos < len(data):
        ln, typ = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if typ == b"IHDR":
            w, h, bd, ct, _, _, il = struct.unpack(">IIBBBBB", body)
        elif typ == b"IDAT":
            idat.append(body)
        elif typ == b"IEND":
            break
    if bd != 8 or ct not in (2, 6) or il != 0:
        raise ValueError("8bit RGB/RGBA PNG \ub9cc \uc77d\uc744 \uc218 \uc788\uc5b4\uc694")
    bpp = 4 if ct == 6 else 3
    raw = zlib.decompress(b"".join(idat))
    stride = w * bpp
    out = bytearray(w * h * 4)
    prev = bytearray(stride)
    i = 0
    for y in range(h):
        f = raw[i]
        i += 1
        line = bytearray(raw[i:i + stride])
        i += stride
        if f == 1:
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x - bpp]) & 255
        elif f == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 255
        elif f == 3:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 255
        elif f == 4:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        o = y * w * 4
        if bpp == 4:
            out[o:o + w * 4] = line
        else:
            for x in range(w):
                out[o + x * 4:o + x * 4 + 3] = line[x * 3:x * 3 + 3]
                out[o + x * 4 + 3] = 255
        prev = line
    return w, h, out


def downsample(img, tw):
    w, h, px = img
    if w <= tw:
        return img
    th = max(1, int(h * tw / w))
    out = bytearray(tw * th * 4)
    for j in range(th):
        y0, y1 = j * h // th, max(j * h // th + 1, (j + 1) * h // th)
        for i in range(tw):
            x0, x1 = i * w // tw, max(i * w // tw + 1, (i + 1) * w // tw)
            s = [0, 0, 0, 0]
            n = 0
            for yy in range(y0, y1):
                b = yy * w * 4
                for xx in range(x0, x1):
                    k = b + xx * 4
                    s[0] += px[k]; s[1] += px[k + 1]; s[2] += px[k + 2]; s[3] += px[k + 3]
                    n += 1
            o = (j * tw + i) * 4
            out[o:o + 4] = bytes(v // n for v in s)
    return tw, th, out


def mask_white_background(img):
    """\uc54c\ud30c\uac00 \uc5c6\ub294 \uc0ac\uc9c4\uc774\uba74, \uac00\uc7a5\uc790\ub9ac\uc640 \uc774\uc5b4\uc9c4 \ud770 \ubc30\uacbd\uc744 \ud22c\uba85 \ucc98\ub9ac."""
    w, h, px = img
    if any(px[k] < 250 for k in range(3, len(px), 4)):
        return img  # 이미 투명 배경이 있음
    px = bytearray(px)

    def whiteish(k):
        r, g, b = px[k], px[k + 1], px[k + 2]
        return min(r, g, b) > 228 and max(r, g, b) - min(r, g, b) < 22

    seen = bytearray(w * h)
    stack = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    while stack:
        x, y = stack.pop()
        if not (0 <= x < w and 0 <= y < h) or seen[y * w + x]:
            continue
        seen[y * w + x] = 1
        k = (y * w + x) * 4
        if not whiteish(k):
            continue
        px[k + 3] = 0
        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return w, h, px


def load_image(path):
    data = None
    if not path.lower().endswith(".png") and shutil.which("sips"):
        tmp = os.path.join(tempfile.mkdtemp(), "img.png")
        subprocess.run(["sips", "-s", "format", "png", "--resampleWidth", "260", path, "--out", tmp],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        path = tmp
    with open(path, "rb") as f:
        data = f.read()
    return mask_white_background(downsample(decode_png(data), 260))


def load_embedded():
    raw = zlib.decompress(base64.b64decode(DATA))
    w, h = struct.unpack(">HH", raw[:4])
    return w, h, bytearray(raw[4:])


# --------------------------------------------------------------------------
# 장면
# --------------------------------------------------------------------------


class Scene:
    def __init__(self, W, H, img, args, truecolor, t_start, intro=True, face=None):
        self.W, self.H = W, H
        self.args = args
        self.face = face
        self.lines = [s for s in (args.say.split("|") if args.say else []) if s.strip()]
        self.fancy = truecolor
        self.rng = random.Random()
        self.t0 = t_start if intro else t_start - INTRO_END - 1.0
        self.burst_done = not intro
        self.ok = W >= 30 and H >= 16
        if not self.ok:
            return
        self._layout(img)
        self._sample(img)
        self._build_bg()
        self.hearts, self.particles, self.sparkles, self.shooting = [], [], [], []
        self.glitch = None
        self.flash = 0
        self.drops = [self.rng.uniform(-self.R, self.R) for _ in range(self.C)]
        self.drop_speed = [self.rng.uniform(0.4, 1.1) for _ in range(self.C)]
        self.floaters = []  # 떠오르는 "옹"
        self.fireworks = []
        self.next_volley = INTRO_END + 2.0
        self._build_banner()
        self._face_grid()
        self.tree = not args.no_tree
        if self.tree:
            self._build_decor()
        self.snow = [self._new_snow(self.rng.uniform(0, H)) for _ in range(max(20, W * H // 45))]

    def _new_snow(self, y):
        rng = self.rng
        front = rng.random() < 0.4
        return [rng.uniform(0, self.W), y, rng.uniform(0.3, 0.6) if front else rng.uniform(0.1, 0.25),
                rng.uniform(0, TAU), rng.choice("**.+'") if front else rng.choice("..'."),
                rng.uniform(0.75, 1.0) if front else rng.uniform(0.3, 0.55)]

    # ---------- 트리 장식 ----------
    def _build_decor(self):
        rng = self.rng
        R, C, inside = self.R, self.C, self.inside
        spans = []
        for j in range(R):
            xs = [i for i in range(C) if inside[j][i]]
            spans.append((xs[0], xs[-1]) if xs else None)
        self.spans = spans

        # 늘어진 줄: (종류, 왼쪽 높이, 오른쪽 높이, 처짐)
        specs = [("lights", 0.16, 0.19, 1.5), ("pink", 0.27, 0.24, 2.0), ("lights", 0.36, 0.40, 2.5),
                 ("gold", 0.52, 0.58, 3.0), ("lights", 0.64, 0.60, 4.0), ("silver", 0.72, 0.77, 3.5),
                 ("lights", 0.80, 0.84, 4.0), ("pink", 0.88, 0.92, 3.0), ("lights", 0.95, 0.93, 2.0)]
        self.garlands = []
        for k, (kind, fa, fb, sag) in enumerate(specs):
            ja, jb = int(fa * R), int(fb * R)
            if not (0 <= ja < R and 0 <= jb < R) or not spans[ja] or not spans[jb]:
                continue
            xl, xr = spans[ja][0], spans[jb][1]
            pts = []
            for i in range(xl, xr + 1):
                u = (i - xl) / max(1, xr - xl)
                pts.append((i, ja + (jb - ja) * u, 4 * u * (1 - u)))
            cols = [rng.choice(BULBS) for _ in pts]
            self.garlands.append((kind, pts, sag * R / 50.0, k, cols))

        # 오너먼트 (얼굴은 피해서)
        cand = [(i, j) for (i, j) in self.cells if j > 3 and not self._protected(i, j)]
        self.ornaments = []
        for _ in range(int(len(cand) * 0.05)):
            i, j = rng.choice(cand)
            p = rng.random()
            if p < 0.14:
                kind, col = "heart", rng.choice(PINKS + [(255, 40, 70)])
            elif p < 0.24:
                kind, col = "cane", (255, 40, 60)
            elif p < 0.34:
                kind, col = "bow", rng.choice(PINKS)
            elif p < 0.44:
                kind, col = "star", rng.choice([GOLD, (255, 240, 150), PINK])
            elif p < 0.75:
                kind, col = "big", rng.choice(BULBS)
            else:
                kind, col = "ball", rng.choice(BULBS)
            self.ornaments.append((i, j, kind, col, rng.uniform(0, TAU)))

        # 머리/어깨 위에 쌓인 눈
        self.caps = [(i, j) for (i, j) in self.cells
                     if (j == 0 or not inside[j - 1][i]) and not self._protected(i, j) and rng.random() < 0.85]

        # 머리 꼭대기 별
        top = next((j for j in range(R) if spans[j]), 0)
        sp = spans[top] or (0, C - 1)
        self.star_at = ((sp[0] + sp[1]) / 2.0, top)
        self.star_poly = star_polygon(self.Ro, self.Ro * 0.42)

        # 발밑 선물 상자 (화면 좌표, 들썩이지 않음)
        self.gifts = []
        bottom = spans[R - 1] or (0, C - 1)
        base_y = self.y0 + R - 1
        max_bh = 3 if R >= 40 else 2
        for side in (-1, 1):
            edge = self.x0 + (bottom[0] - 2 if side < 0 else bottom[1] + 2)
            for _ in range(4):
                w = rng.choice([7, 9, 9, 11])
                bh = rng.randint(1, max_bh)
                if side < 0:
                    gx = edge - w
                    if gx < 1:
                        break
                    edge = gx - 3
                else:
                    gx = edge
                    if gx + w + 1 >= self.W - 1:
                        break
                    edge = gx + w + 3
                box = rng.choice([(200, 30, 40), (40, 90, 210), (130, 50, 200), (20, 150, 120), (220, 160, 20),
                                  (255, 120, 190), (240, 60, 160), (255, 170, 210)])
                ribbon = rng.choice([(255, 215, 80), (255, 255, 255), (255, 60, 170)])
                self.gifts.append((gx, base_y, w, bh, box, ribbon))

    def _spawn_firework(self):
        rng = self.rng
        left = (2, self.x0 + 4)
        right = (self.x0 + self.C - 4, self.W - 3)
        zones = [z for z in (left, right) if z[1] - z[0] >= 6] or [(2, self.W - 3)]
        a, b = rng.choice(zones) if rng.random() < 0.8 else (2, self.W - 3)
        top_limit = max(3, int(self.H * 0.45))
        self.fireworks.append(Firework(rng, rng.uniform(a, b), self.H - 2, rng.uniform(2, top_limit)))

    def _build_banner(self):
        """\ud06c\uac8c \uc4f0\ub294 MERRY CHRISTMAS (\uae00\uc790\ub9c8\ub2e4 \ub530\ub85c \ucda4\ucd94\uac8c \uae00\uc790 \ubc88\ud638\ub3c4 \uc800\uc7a5)."""
        W, H = self.W, self.H
        self.banner_px = []
        self.banner_small = W < 92 or H < 30
        if self.banner_small:
            return
        sc = 2 if W >= 186 else 1
        gap = sc
        width = sum((3 * sc) if c == " " else (5 * sc + gap) for c in BANNER) - gap
        x0 = (W - width) // 2
        self.banner_y = H - 9
        self.banner_x0, self.banner_w, self.banner_sc = x0, width, sc
        x = x0
        k = 0
        for c in BANNER:
            if c == " ":
                x += 3 * sc
                continue
            for r, line in enumerate(FONT[c]):
                for j, p in enumerate(line):
                    if p == "#":
                        for d in range(sc):
                            self.banner_px.append((x + j * sc + d, r, k))
            x += 5 * sc + gap
            k += 1

    def _draw_banner(self, t, it, ch, fg, bg, put):
        W, H = self.W, self.H
        rng = self.rng
        wipe = (it - INTRO_END - 0.3) / 1.2
        if wipe <= 0:
            return
        if self.banner_small:
            text = "* MERRY CHRISTMAS *"
            x0 = (W - len(text)) // 2
            n = int(min(1.0, wipe) * len(text))
            for k, c in enumerate(text[:n]):
                if c != " ":
                    put(x0 + k, H - 1, c, hsv(k * 0.05 - t * 0.5, 0.75, 1.0))
            return
        x0, width, sc = self.banner_x0, self.banner_w, self.banner_sc
        edge = x0 + wipe * (width + 4)
        pink_mode = int(t / 8) % 2 == 1
        hl = x0 - 20 + ((t * 45) % (width + 40))
        shadow = (28, 18, 45) if self.fancy else (40, 40, 60)
        placed = []
        for (px, r, k) in self.banner_px:
            if px >= edge or not 0 <= px < W:
                continue
            dy = int(round(math.sin(t * 4 - k * 0.6) * 0.75))  # 글자마다 통통 튀는 웨이브
            py = self.banner_y + r + dy
            if 0 <= py < H:
                placed.append((px, py, k))
        for (px, py, k) in placed:  # 그림자
            if px + 1 < W and py + 1 < H:
                bg[py + 1][px + 1] = shadow
                ch[py + 1][px + 1] = " "
        for (px, py, k) in placed:
            v = 0.82 + 0.18 * math.sin(t * 4 + px * 0.3 / sc + py)
            if pink_mode:
                col = hsv(0.875 + 0.08 * math.sin(px * 0.06 / sc - t * 1.6 + py * 0.3),
                          0.55 + 0.3 * math.sin(px * 0.11 / sc + t * 2), v)
            else:
                col = hsv(px * 0.012 / sc - t * 0.25, 0.78, v)
            dh = abs(px - hl)
            if dh < 4:
                col = mix(col, WHITE, (1 - dh / 4) * 0.75)
            bg[py][px] = quant(col, 4)
            if rng.random() < 0.02:
                ch[py][px], fg[py][px] = rng.choice("*+"), WHITE
            else:
                ch[py][px] = " "
        if wipe < 1:
            ex = int(edge)
            for py in range(self.banner_y - 1, self.banner_y + 7):
                put(ex, py, "|", HOLO)
                if self.fancy and 0 <= ex < W and 0 <= py < H:
                    bg[py][ex] = (0, 110, 140)

    def _protected(self, i, j):
        """\uc5bc\uad74(\ub208~\uc785)\uc740 \uc7a5\uc2dd\uc774 \uac00\ub9ac\uc9c0 \uc54a\uac8c."""
        if not self.face:
            return False
        fx, fy, fhw, fhh = self.face_box
        return ((i + 0.5 - fx) / fhw) ** 2 + ((j + 0.5 - fy) / fhh) ** 2 <= 1

    def _face_grid(self):
        """\uc5bc\uad74 \ubd80\uc704\ub97c \uaca9\uc790 \uc88c\ud45c\ub85c (\uc0ac\uc9c4\uc774 \ubc14\ub00c\uba74 \uc785\ub9cc \ub300\ub7b5 \uac00\uc6b4\ub370\ub85c)."""
        C, R = self.C, self.R
        f = self.face
        if f:
            self.eyes = [(x * C, y * R) for x, y in f["eyes"]]
            self.eye_hw = max(1.6, f["eye_w"] * C)
            self.mouth = (f["mouth"][0] * C, f["mouth"][1] * R)
            self.mouth_hw = max(2.0, f["mouth_w"] * C)
            self.cheeks = [(x * C, y * R) for x, y in f["cheeks"]]
        else:
            self.eyes = []
            self.eye_hw = 2.0
            self.mouth = (0.5 * C, 0.55 * R)
            self.mouth_hw = 3.0
            self.cheeks = []
        self.eye_hh = max(0.9, 0.028 * R)
        if self.eyes:
            ex = (self.eyes[0][0] + self.eyes[1][0]) / 2
            ey = (self.eyes[0][1] + self.eyes[1][1]) / 2
            my = self.mouth[1]
            self.face_box = (ex, (ey + my) / 2, (self.eyes[1][0] - self.eyes[0][0]) / 2 + self.eye_hw * 2.6,
                             (my - ey) / 2 + 3.2)

    # ---------- 배치 ----------
    def _layout(self, img):
        iw, ih, _ = img
        W, H = self.W, self.H
        cap = 1 if self.args.text else 0
        self.Ro = 8 if H >= 44 else 6 if H >= 32 else 4
        star_rows = 0 if self.args.no_tree else self.Ro // 2 + 2  # 머리 위 별 자리 (별은 머리에 살짝 걸침)
        avail_h = H - 2 - cap - star_rows
        R = avail_h
        C = int(round(R * iw / ih * 2.0))
        if C > W - 4:
            C = W - 4
            R = int(round(C / (iw / ih * 2.0)))
        self.R, self.C = max(4, R), max(4, C)
        spare = W - self.C
        self.x0 = max(1, spare // 2 - min(12, spare // 3))  # 오른쪽에 말풍선 자리
        self.y0 = 1 + star_rows + (avail_h - self.R) // 2
        self.cap_y = H - 1

    def _sample(self, img):
        iw, ih, px = img
        R, C = self.R, self.C
        inside = [[False] * C for _ in range(R)]
        col = [[(0, 0, 0)] * C for _ in range(R)]
        lum = [[0.0] * C for _ in range(R)]
        lums = []
        for j in range(R):
            y0 = j * ih // R
            y1 = max(y0 + 1, (j + 1) * ih // R)
            for i in range(C):
                x0 = i * iw // C
                x1 = max(x0 + 1, (i + 1) * iw // C)
                sr = sg = sb = sa = 0
                n = 0
                for yy in range(y0, y1):
                    base = yy * iw * 4
                    for xx in range(x0, x1):
                        k = base + xx * 4
                        a = px[k + 3]
                        sr += px[k] * a
                        sg += px[k + 1] * a
                        sb += px[k + 2] * a
                        sa += a
                        n += 1
                if sa > n * 255 * 0.45:
                    c = (sr / sa, sg / sa, sb / sa)
                    inside[j][i] = True
                    col[j][i] = (_c(c[0]), _c(c[1]), _c(c[2]))
                    l = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
                    lum[j][i] = l
                    lums.append(l)
        lums.sort()
        lo = lums[int(len(lums) * 0.02)] if lums else 0
        hi = lums[int(len(lums) * 0.985)] if lums else 255
        rng = max(1.0, hi - lo)
        ln = [[0.0] * C for _ in range(R)]
        for j in range(R):
            for i in range(C):
                if inside[j][i]:
                    v = (lum[j][i] - lo) / rng
                    ln[j][i] = max(0.0, min(1.0, v)) ** 0.9

        # Sobel 경계 (눈/코/입 윤곽)
        edge = [[None] * C for _ in range(R)]
        mags = []
        for j in range(1, R - 1):
            for i in range(1, C - 1):
                if not inside[j][i]:
                    continue
                ok = all(inside[j + dy][i + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1))
                if not ok:
                    continue
                g = ln
                gx = (g[j - 1][i + 1] + 2 * g[j][i + 1] + g[j + 1][i + 1]) - (g[j - 1][i - 1] + 2 * g[j][i - 1] + g[j + 1][i - 1])
                gy = (g[j + 1][i - 1] + 2 * g[j + 1][i] + g[j + 1][i + 1]) - (g[j - 1][i - 1] + 2 * g[j - 1][i] + g[j - 1][i + 1])
                m = math.hypot(gx, gy)
                edge[j][i] = (m, gx, gy)
                mags.append(m)
        mags.sort()
        thr = mags[int(len(mags) * 0.88)] if mags else 9
        chars = [[" "] * C for _ in range(R)]
        n = len(RAMP) - 1
        for j in range(R):
            for i in range(C):
                if not inside[j][i]:
                    continue
                c = RAMP[max(1, int(ln[j][i] * n))]
                e = edge[j][i]
                if e and e[0] > thr and e[0] > 0.9:
                    # 경계 방향에 맞는 글자 (화면 셀은 세로로 2배 길쭉함)
                    ang = math.degrees(math.atan2(e[2], e[1] * 2.0)) % 180
                    c = "|" if ang < 22.5 or ang >= 157.5 else "/" if ang < 67.5 else "-" if ang < 112.5 else "\\"
                    c = {"|": "-", "-": "|", "/": "\\", "\\": "/"}[c]  # 기울기 -> 윤곽선 방향
                chars[j][i] = c
        self.inside, self.col, self.ln, self.chars = inside, col, ln, chars
        self.cells = [(i, j) for j in range(R) for i in range(C) if inside[j][i]]
        self.bright = [(i, j) for (i, j) in self.cells if ln[j][i] > 0.62]

        # 실루엣 주변 림 글로우 거리
        rim = {}
        frontier = [(self.x0 + i, self.y0 + j) for (i, j) in self.cells]
        occupied = set(frontier)
        for d in (1, 2, 3):
            nxt = []
            for (x, y) in frontier:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    p = (x + dx, y + dy)
                    if p not in occupied and 0 <= p[0] < self.W and 0 <= p[1] < self.H:
                        occupied.add(p)
                        rim[p] = d
                        nxt.append(p)
            frontier = nxt
        self.rim = rim
        self.screen_mask = set((self.x0 + i, self.y0 + j) for (i, j) in self.cells)

    def _build_bg(self):
        rng = self.rng
        W, H = self.W, self.H
        top, bot = (4, 2, 18), (24, 8, 40)
        self.sky = [mix(top, bot, y / max(1, H - 1)) if self.fancy else (0, 0, 0) for y in range(H)]
        self.stars = []
        for _ in range(W * H // 28):
            x, y = rng.randrange(W), rng.randrange(H)
            if (x, y) in self.screen_mask:
                continue
            self.stars.append((x, y, rng.uniform(0, TAU), rng.uniform(0.6, 3.0), rng.choice("..'.+`*"),
                               rng.choice([(200, 210, 255), (255, 175, 220), (255, 230, 170), (170, 240, 255)]),
                               rng.random() < 0.06))
        self.confetti = [self._new_confetti(rng.uniform(0, H)) for _ in range(max(12, W * H // 110))]

    def _new_confetti(self, y):
        rng = self.rng
        return [rng.uniform(0, self.W), y, rng.uniform(0.12, 0.35), rng.uniform(0, TAU),
                rng.choice("*+'`.*~"), rng.choice(PINKS + PINKS + [GOLD, WHITE, HOLO]), rng.uniform(2, 6)]

    # ---------- 시간 ----------
    def _mode_at(self, it):
        if self.args.mode:
            return self.args.mode, self.args.mode, 99.0
        total = sum(s for _, s in TIMELINE)
        t = max(0.0, it - INTRO_END) % total
        acc = 0.0
        for k, (m, s) in enumerate(TIMELINE):
            if t < acc + s:
                return m, TIMELINE[k - 1][0], t - acc
            acc += s
        return TIMELINE[0][0], TIMELINE[-1][0], 0.0

    def _skit(self, it):
        """(\uac1c\uadf8 \uc885\ub958, \ub300\uc0ac, \uc7a5\uba74 \uc2dc\uc791 \ud6c4 \uacbd\uacfc \ucd08, \uc7a5\uba74 \ubc88\ud638)"""
        st = it - INTRO_END - 0.8
        if st < 0:
            return None, "", 0.0, -1
        k = int(st // SKIT_LEN)
        since = st - k * SKIT_LEN
        kind, line = SKITS[k % len(SKITS)]
        if self.lines:
            line = self.lines[k % len(self.lines)]
        if self.args.no_gags or not self.face:
            kind = "talk"
        return kind, line, since, k

    # ---------- 물리 ----------
    def update(self, t, s):
        rng = self.rng
        W, H = self.W, self.H
        it = t - self.t0

        # 개그 장면 시작할 때 터지는 것들
        kind, _, since, k = self._skit(it)
        if k >= 0 and k != getattr(self, "_last_skit", -1):
            self._last_skit = k
            mx, my = self.x0 + self.mouth[0], self.y0 + self.mouth[1]
            if kind == "heart":
                for _ in range(90):
                    a = rng.uniform(0, TAU)
                    sp = rng.uniform(0.4, 1.4)
                    life = rng.uniform(15, 30)
                    self.particles.append([mx, my - self.R * 0.2, math.cos(a) * sp * 2, math.sin(a) * sp,
                                           life, life, rng.choice((0.92, 0.94, 0.96))])
            if kind == "shock":
                self.flash = 4
        # 내리는 눈
        for f in self.snow:
            f[1] += f[2] * s
            f[0] = (f[0] + (math.sin(t * 1.3 + f[3]) * 0.2 + 0.15 * math.sin(t * 0.2)) * s) % W
            if f[1] >= H:
                f[:] = self._new_snow(rng.uniform(-3, 0))
        # 떠오르는 "옹"
        if it > INTRO_END and len(self.floaters) < 9 and rng.random() < 0.05 * s:
            x = rng.uniform(1, W - 3)
            life = rng.uniform(45, 80)
            self.floaters.append([x, H - 1.0, rng.uniform(0.2, 0.5), rng.uniform(0, TAU), life, life,
                                  rng.choice(PINKS + [GOLD, HOLO, (180, 255, 150)]), rng.choice(("\uc639", "\uc639", "\uc639\uc639", "<3"))])
        for fl in self.floaters:
            fl[1] -= fl[2] * s
            fl[0] += math.sin(t * 2.5 + fl[3]) * 0.3 * s
            fl[4] -= s
        self.floaters = [fl for fl in self.floaters if fl[4] > 0 and fl[1] > 0]
        for f in self.confetti:
            f[1] += f[2] * s
            f[0] = (f[0] + math.sin(t * 2.1 + f[3]) * 0.3 * s) % W
            if f[1] >= H:
                f[:] = self._new_confetti(rng.uniform(-3, 0))
        if it > INTRO_END and len(self.hearts) < 12 and rng.random() < 0.08 * s:
            side = rng.choice((-1, 1))
            x = (self.x0 - rng.uniform(2, max(3, self.x0 - 1))) if side < 0 else\
                (self.x0 + self.C + rng.uniform(1, max(2, W - self.x0 - self.C - 3)))
            life = rng.uniform(50, 90)
            self.hearts.append([x, H - 1.0, rng.uniform(0.2, 0.45), rng.uniform(0, TAU), life, life, rng.choice(PINKS)])
        for h in self.hearts:
            h[1] -= h[2] * s
            h[0] += math.sin(t * 2 + h[3]) * 0.25 * s
            h[4] -= s
        self.hearts = [h for h in self.hearts if h[4] > 0 and h[1] > 0]

        # 완성 순간 폭발
        if not self.burst_done and it >= INTRO_END:
            self.burst_done = True
            self.flash = 5
            edges = [p for p, d in self.rim.items() if d == 1]
            for _ in range(260):
                x, y = rng.choice(edges) if edges else (W / 2, H / 2)
                a = rng.uniform(0, TAU)
                sp = rng.uniform(0.3, 1.5)
                life = rng.uniform(12, 30)
                hue = rng.choice((0.92, 0.94, 0.12, 0.5))
                self.particles.append([x, y, math.cos(a) * sp * 2, math.sin(a) * sp, life, life, hue])
        self.flash = max(0, self.flash - 1)

        # 생성 중 스캔 라인 불꽃
        p = smooth((it - INTRO_START) / INTRO_LEN)
        if 0 < p < 1:
            sy = self.y0 + self.R - p * (self.R + 2)
            for _ in range(int(6 * s) + 1):
                life = rng.uniform(8, 16)
                self.particles.append([self.x0 + rng.uniform(0, self.C), sy, rng.uniform(-0.5, 0.5),
                                       -rng.uniform(0.2, 0.9), life, life, rng.choice((0.5, 0.52, 0.92))])
        keep = []
        for q in self.particles:
            q[0] += q[2] * s
            q[1] += q[3] * s
            q[2] *= 0.93
            q[3] = q[3] * 0.93 + 0.01 * s
            q[4] -= s
            if q[4] > 0:
                keep.append(q)
        self.particles = keep

        # 배경 폭죽 (인물 양옆 하늘에서 팡팡)
        if it > INTRO_END and not self.args.no_fireworks:
            if len(self.fireworks) < 6 and rng.random() < 0.07 * s:
                self._spawn_firework()
            if it >= self.next_volley:  # 가끔 한꺼번에 팡팡팡
                for _ in range(rng.randint(4, 7)):
                    self._spawn_firework()
                self.next_volley = it + rng.uniform(15, 22)
        for fw in self.fireworks:
            fw.step(s)
        self.fireworks = [fw for fw in self.fireworks if fw.alive()]

        # 반짝임
        if it > INTRO_END and self.bright:
            for _ in range(2):
                if rng.random() < 0.45 * s:
                    i, j = rng.choice(self.bright)
                    self.sparkles.append([i, j, 8.0])
        for sp in self.sparkles:
            sp[2] -= s
        self.sparkles = [sp for sp in self.sparkles if sp[2] > 0]

        if len(self.shooting) < 2 and rng.random() < 0.02 * s:
            d = rng.choice((-1, 1))
            x = rng.uniform(0, W * 0.3) if d > 0 else rng.uniform(W * 0.7, W)
            self.shooting.append([x, rng.uniform(0, H * 0.35), d * rng.uniform(1.6, 2.6), rng.uniform(0.2, 0.45),
                                  [], rng.choice([(255, 140, 210), (160, 220, 255), (255, 220, 140)])])
        for sh in self.shooting:
            sh[4].append((sh[0], sh[1]))
            sh[4] = sh[4][-10:]
            sh[0] += sh[2] * s
            sh[1] += sh[3] * s
        self.shooting = [sh for sh in self.shooting if -12 < sh[0] < W + 12 and sh[1] < H]

        for k in range(self.C):
            self.drops[k] += self.drop_speed[k] * s
            if self.drops[k] > self.R + 10:
                self.drops[k] = -rng.uniform(0, self.R * 0.6)

        if self.glitch:
            self.glitch[3] -= 1
            if self.glitch[3] <= 0:
                self.glitch = None
        elif it > INTRO_END and rng.random() < 0.02 * s:
            self.glitch = [rng.randrange(self.R), rng.randint(1, 3), rng.choice((-4, -3, -2, 2, 3, 4)), rng.randint(2, 4)]

    # ---------- 인물 색칠 ----------
    def _shade(self, mode, i, j, t, ch_):
        """(\uae00\uc790, \uae00\uc790\uc0c9, \ubc30\uacbd\uc0c9) \ubc18\ud658"""
        l = self.ln[j][i]
        c = self.col[j][i]
        if mode == "photo":
            fg = (_c(c[0] * 1.3 + 25), _c(c[1] * 1.3 + 25), _c(c[2] * 1.3 + 25))
            return ch_, fg, scale(c, 0.62)
        if mode == "neon":
            g = gradient(NEON, 0.12 + l * 0.88 + 0.04 * math.sin(t * 3 + j * 0.3))
            return ch_, g, scale(g, 0.45)
        if mode == "rainbow":
            g = hsv(l * 0.45 + (i + j) * 0.012 - t * 0.35, 0.75, 0.3 + 0.7 * l)
            return ch_, g, scale(g, 0.25)
        if mode == "thermal":
            g = gradient(THERMAL, l)
            return ch_, g, scale(g, 0.3)
        if mode == "matrix":
            d = self.drops[i] - j
            v = l * 0.55
            sym = ch_
            if 0 <= d < 9:
                v += (1 - d / 9) * 0.85
                if d < 1:
                    return self.rng.choice(MATRIX_CHARS), (220, 255, 220), (0, 40, 10)
                if self.rng.random() < 0.3:
                    sym = self.rng.choice(MATRIX_CHARS)
            return sym, (_c(30 * v), _c(255 * v), _c(80 * v)), (0, _c(30 * l), _c(8 * l))
        # holo
        scan = 0.55 if (j + int(t * 12)) % 3 == 0 else 1.0
        flick = 0.85 + 0.15 * math.sin(t * 50 + j)
        g = scale(mix((0, 90, 120), HOLO, 0.15 + l * 0.85), scan * flick)
        return ch_, mix(g, WHITE, l ** 4 * 0.6), scale(g, 0.4)

    # ---------- 그리기 ----------
    def render(self, t):
        W, H = self.W, self.H
        rng = self.rng
        it = t - self.t0
        fancy = self.fancy
        ch = [[" "] * W for _ in range(H)]
        fg = [[WHITE] * W for _ in range(H)]
        bg = [[self.sky[y]] * W for y in range(H)]

        def put(x, y, c, col):
            if 0 <= x < W and 0 <= y < H:
                ch[y][x] = c
                fg[y][x] = col

        # 오로라
        if fancy:
            rows = max(1, int(H * 0.6))
            w1 = [max(0.0, math.sin(x * 0.045 + t * 0.35 + math.sin(x * 0.017 - t * 0.21) * 2.2)) for x in range(W)]
            for y in range(rows):
                fade = (1 - y / rows) ** 1.5
                row = bg[y]
                ph = t * 0.27 - y * 0.35
                for x in range(W):
                    a = w1[x] * fade * 0.5
                    b = math.sin(x * 0.03 - ph)
                    b = b * fade * 0.45 if b > 0 else 0.0
                    if a > 0.02 or b > 0.02:
                        base = row[x]
                        row[x] = quant((_c(base[0] + 120 * b), _c(base[1] + 80 * a + 10 * b), _c(base[2] + 45 * a + 80 * b)))
            if self.flash:
                k = self.flash / 5.0 * 0.55
                for y in range(H):
                    bg[y] = [quant(add(c, (110, 70, 100), k)) for c in bg[y]]

        kind, line, since, _k = self._skit(it)
        active = kind is not None and 0.3 <= since < SKIT_LEN - 0.6
        if fancy and active and kind == "disco":  # 디스코 조명
            beat = max(0.0, math.sin(t * 10)) ** 2
            tint = hsv(t * 0.9, 0.85, 1.0)
            for y in range(H):
                bg[y] = [quant(add(c, tint, 0.22 * beat * (0.6 + 0.4 * math.sin(y * 0.4 + t * 6)))) for c in bg[y]]

        # 별, 별똥별
        for (x, y, ph, sp, c, tint, big) in self.stars:
            v = 0.5 + 0.5 * math.sin(t * sp + ph)
            v = v * v * v
            if big and v > 0.55:
                arm = scale(tint, v)
                put(x - 1, y, "-", arm)
                put(x + 1, y, "-", arm)
                put(x, y - 1, "|" if v > 0.8 else "'", arm)
                put(x, y + 1, "|" if v > 0.8 else ".", arm)
                put(x, y, "*", mix(tint, WHITE, v * 0.6))
            else:
                put(x, y, c, scale(tint, 0.15 + 0.85 * v))
        for sh in self.shooting:
            n = len(sh[4])
            for k, (tx, ty) in enumerate(sh[4]):
                put(int(tx), int(ty), "-" if k < n * 0.7 else "=", scale(sh[5], (k + 1) / n))
            put(int(sh[0]), int(sh[1]), "*", WHITE)

        # 배경 폭죽 (인물이 위에 그려지니 자연히 뒤로 숨음)
        for fw in self.fireworks:
            if not fw.exploded:
                for k, (tx, ty) in enumerate(fw.trail):
                    put(int(tx), int(ty), "|" if k > 2 else ".", scale((255, 200, 120), 0.3 + 0.15 * k))
                put(int(fw.x), int(fw.y), "^", (255, 240, 200))
                continue
            if fw.flash:
                for dy in (-1, 0, 1):
                    for dx in range(-3, 4):
                        put(int(fw.x) + dx, int(fw.y) + dy, "*" if dx == 0 or dy == 0 else ".", WHITE)
            glitter = fw.style == "glitter"
            for q in fw.parts:
                f = q[4] / q[5]
                if f < 0.25 and rng.random() < 0.35:
                    continue
                c = "@" if f > 0.78 else "*" if f > 0.5 else "+" if f > 0.25 else "."
                col = hsv(q[6], min(1.0, 0.3 + (1 - f) * 1.3), 0.35 + 0.65 * f ** 0.6)
                if glitter and rng.random() < 0.3:
                    c, col = "*", WHITE
                xi, yi = int(q[0]), int(q[1])
                put(int(q[7]), int(q[8]), ".", scale(col, 0.45))
                put(xi, yi, c, col)
                if fancy and f > 0.6 and 0 <= yi < H and 0 <= xi < W:
                    bg[yi][xi] = quant(add(bg[yi][xi], col, 0.18))

        # 색종이 (인물 밖에서만)
        for f in self.confetti:
            xi, yi = int(f[0]), int(f[1])
            if (xi, yi) in self.screen_mask:
                continue
            v = 0.5 + 0.5 * math.sin(t * f[6] + f[3])
            put(xi, yi, f[4] if v > 0.3 else ".", mix(scale(f[5], 0.35 + 0.65 * v), WHITE, v ** 8 * 0.8))
        for f in self.snow:
            xi, yi = int(f[0]), int(f[1])
            if (xi, yi) not in self.screen_mask:
                put(xi, yi, f[4], scale((225, 235, 255), f[5]))

        # 들썩들썩 (디스코는 신나게, 깜짝은 덜덜)
        offx = offy = 0
        if it > INTRO_END:
            offy = int(round(0.6 * math.sin(t * 2.4)))
            if active and kind == "disco":
                offy = int(round(math.sin(t * 10)))
                offx = int(round(2 * math.sin(t * 5)))
            elif active and kind == "shock" and since < 1.6:
                offx = rng.choice((-2, -1, 1, 2))

        # 림 글로우
        p_intro = smooth((it - INTRO_START) / INTRO_LEN)
        if it > INTRO_START:
            for (x, y), d in self.rim.items():
                x, y = x + offx, y + offy
                if not (0 <= x < W and 0 <= y < H):
                    continue
                if p_intro < 1 and y < self.y0 + self.R - p_intro * (self.R + 2):
                    continue
                k = (4 - d) / 3.0
                hue_mix = 0.5 + 0.5 * math.sin(t * 1.5 + y * 0.15 + x * 0.05)
                g = mix(HOT_PINK, HOLO, hue_mix)
                pulse = 0.55 + 0.45 * math.sin(t * 3 + (x + y) * 0.2)
                if fancy:
                    bg[y][x] = quant(add(bg[y][x], g, 0.35 * k * k * pulse))
                if d == 1 and ch[y][x] == " " and rng.random() < 0.25:
                    put(x, y, ".", scale(g, 0.6 + 0.4 * pulse))

        # 인물
        mode, prev, msince = self._mode_at(it)
        if active and kind == "disco":
            mode = prev = "rainbow"
        x0, y0, R = self.x0 + offx, self.y0 + offy, self.R
        trans_row = None
        if msince < TRANSITION and it > INTRO_END:
            trans_row = R - (msince / TRANSITION) * (R + 2)
        scan_row = R - p_intro * (R + 2) if p_intro < 1 else None
        chars = self.chars
        for (i, j) in self.cells:
            x, y = x0 + i, y0 + j
            if not (0 <= x < W and 0 <= y < H):
                continue
            c0 = chars[j][i]
            if scan_row is not None:  # 홀로그램 생성 중
                d = j - scan_row
                if d < 0:
                    if rng.random() < 0.12:
                        put(x, y, rng.choice("01:."), scale(HOLO if (i + j) % 3 else PINK, 0.35 + 0.3 * rng.random()))
                    elif fancy:
                        bg[y][x] = mix(bg[y][x], (0, 30, 45), 0.6)
                    continue
                if d < 1:
                    ch[y][x] = "=" if (i + int(t * 60)) % 3 else "#"
                    fg[y][x] = mix(HOLO, WHITE, 0.5 + 0.5 * math.sin(i * 0.7 + t * 30))
                    bg[y][x] = (0, 105, 130) if fancy else bg[y][x]
                    continue
                sym, f, b = self._shade("photo", i, j, t, c0)
                k = min(1.0, (d - 1) / 6.0)
                if k < 1:
                    if rng.random() < (1 - k) * 0.4:
                        sym = rng.choice(GLITCH)
                    f = mix(HOLO, f, k)
                    b = mix(b, (0, 70, 90), (1 - k) * 0.6)
            else:
                m = mode
                if trans_row is not None:
                    d = j - trans_row
                    if 0 <= d < 1:
                        ch[y][x] = "="
                        fg[y][x] = mix(PINK, WHITE, 0.6)
                        bg[y][x] = (90, 20, 70) if fancy else bg[y][x]
                        continue
                    m = mode if d >= 1 else prev
                sym, f, b = self._shade(m, i, j, t, c0)
                if rng.random() < 0.01:  # 살아있는 듯한 글자 떨림
                    sym = RAMP[max(1, min(len(RAMP) - 1, RAMP.find(sym) + rng.choice((-2, -1, 1, 2))))] if sym in RAMP else sym
            ch[y][x] = sym
            fg[y][x] = f
            bg[y][x] = b

        # 표정 개그 + 말하는 입
        talking = False
        if active and line:
            n = int((since - 0.3) * TYPE_CPS)
            if 0 <= n < len(line) and line[min(n, len(line) - 1)] not in " .?!~<>_()":
                talking = int(t * 11) % 2 == 0
        if p_intro >= 1 and self.tree:
            self._draw_decor(t, it, x0, y0, ch, fg, bg, put)
        if p_intro >= 1 and self.face:
            self._draw_face(kind if active else None, since, t, it, x0, y0, ch, fg, bg, put, talking)

        # 반짝임
        for (i, j, life) in self.sparkles:
            x, y = x0 + i, y0 + j
            v = life / 8.0
            col = mix(PINK, WHITE, v)
            put(x, y, "*", col)
            if v > 0.5:
                put(x - 1, y, "-", scale(col, 0.7))
                put(x + 1, y, "-", scale(col, 0.7))
            if v > 0.75:
                put(x, y - 1, "|", scale(col, 0.6))
                put(x, y + 1, "|", scale(col, 0.6))

        # 글리치
        if self.glitch:
            gj, gh, off, _ = self.glitch
            a, b = max(0, x0 - 4), min(W, x0 + self.C + 4)
            for j in range(gj, min(R, gj + gh)):
                y = y0 + j
                for arr in (ch[y], fg[y], bg[y]):
                    seg = arr[a:b]
                    arr[a:b] = seg[-off:] + seg[:-off]
                tint = HOT_PINK if off > 0 else HOLO
                for x in range(a, b):
                    if ch[y][x] != " ":
                        fg[y][x] = mix(fg[y][x], tint, 0.55)

        # 하트, 파티클
        for hx, hy, _, ph, life, mlife, hc in self.hearts:
            v = min(1.0, life / mlife * 2.5) * (0.75 + 0.25 * math.sin(t * 6 + ph))
            xi, yi = int(hx), int(hy)
            if (xi, yi) in self.screen_mask or (xi + 1, yi) in self.screen_mask:
                continue
            put(xi, yi, "<", scale(hc, v))
            put(xi + 1, yi, "3", scale(hc, v))
        for q in self.particles:
            f = q[4] / q[5]
            c = "@" if f > 0.8 else "*" if f > 0.55 else "+" if f > 0.3 else "."
            put(int(q[0]), int(q[1]), c, hsv(q[6], 0.75 * (1.2 - f), 0.4 + 0.6 * f))

        # 떠오르는 "옹"
        for fx_, fy_, _, ph, life, mlife, fc, word in self.floaters:
            xi, yi = int(fx_), int(fy_)
            if any((xi + d, yi) in self.screen_mask for d in range(text_w(word))):
                continue
            v = min(1.0, life / mlife * 2.5) * (0.7 + 0.3 * math.sin(t * 5 + ph))
            self._put_text(ch, fg, bg, xi, yi, word, lambda c: scale(fc, v), None)

        # MERRY CHRISTMAS 큰 글자
        if p_intro >= 1:
            self._draw_banner(t, it, ch, fg, bg, put)

        # 효과음 글자 + 말풍선
        if active and p_intro >= 1:
            self._draw_sfx(kind, since, t, x0, y0, ch, fg, bg)
        if kind is not None and p_intro >= 1:
            self._draw_bubble(line, since, t, x0, y0, ch, fg, bg)

        # 아래 글자
        if p_intro < 1:
            msg = "[ HOLOGRAM ]  scanning portrait ...  %3d%%" % int(p_intro * 100)
            xs = (W - len(msg)) // 2
            for k, c in enumerate(msg):
                if c != " ":
                    put(xs + k, H - 1, c, scale(HOLO, 0.6 + 0.4 * math.sin(t * 20 + k)))
        elif self.args.text:
            msg = self.args.text[: W - 2]
            n = int((it - INTRO_END - 0.5) * 30)
            xs = (W - len(msg)) // 2
            for k, c in enumerate(msg[:max(0, n)]):
                if c != " ":
                    put(xs + k, self.cap_y, c, hsv(0.9 + 0.1 * math.sin(k * 0.3 - t * 2), 0.7, 1.0))
        return ch, fg, bg

    # ---------- 트리 장식 그리기 ----------
    def _light(self, mode, idx, base, ph, t):
        if mode == "twinkle":
            return scale(base, 0.2 + 0.8 * max(0.0, math.sin(t * 3.5 + ph)))
        if mode == "pink":
            tw_ = max(0.0, math.sin(t * 4 + ph))
            return scale(mix(PINKS[idx % len(PINKS)], WHITE, tw_ ** 6 * 0.7), 0.3 + 0.7 * tw_)
        if mode == "rainbow":
            return hsv(idx * 0.05 - t * 0.7, 0.9, 1.0)
        if mode == "chase":
            return base if (idx // 3 - int(t * 12)) % 4 < 2 else scale(base, 0.15)
        if mode == "candy":
            k = (idx // 3 + int(t * 8))
            return HOT_PINK if k % 6 == 0 else (PINK if k % 2 else (255, 240, 250))
        return hsv(t * 0.15 + idx * 0.01, 0.85, 0.4 + 0.6 * (0.5 + 0.5 * math.sin(t * 5)))

    def _draw_decor(self, t, it, x0, y0, ch, fg, bg, put):
        W, H, R = self.W, self.H, self.R
        rng = self.rng
        fancy = self.fancy
        inside = self.inside
        mode = LIGHT_MODES[int(max(0.0, it - INTRO_END) / 6.0) % len(LIGHT_MODES)]

        # 눈 쌓인 머리/어깨
        for (i, j) in self.caps:
            x, y = x0 + i, y0 + j
            if 0 <= x < W and 0 <= y < H:
                v = 0.5 + 0.5 * math.sin(t * 3 + i * 1.7 + j)
                ch[y][x] = "*" if v > 0.92 else "."
                fg[y][x] = mix((200, 215, 245), WHITE, v)
                bg[y][x] = mix(bg[y][x], (225, 235, 255), 0.55)

        # 오너먼트
        for (i, j, kind, col, ph) in self.ornaments:
            x, y = x0 + i, y0 + j
            if not (0 <= x < W and 0 <= y < H):
                continue
            v = 0.8 + 0.2 * math.sin(t * 2 + ph)
            c = scale(col, v)
            glint = (t * 0.9 + ph) % 5.0 < 0.25
            core = mix(c, WHITE, 0.7) if glint else c
            if kind == "big":
                put(x - 1, y, "(", scale(c, 0.85))
                put(x, y, "@" if glint else "O", core)
                put(x + 1, y, ")", scale(c, 0.6))
                if fancy:
                    bg[y][x] = quant(scale(c, 0.4))
            elif kind == "heart" and x + 1 < W:
                beat = 0.75 + 0.25 * max(0.0, math.sin(t * 6 + ph)) ** 4
                put(x, y, "<", scale(col, beat))
                put(x + 1, y, "3", scale(col, beat))
                if fancy:
                    bg[y][x] = bg[y][x + 1] = quant(scale(col, 0.3 * beat))
            elif kind == "cane":
                put(x, y, "J", col if int(t * 3 + ph) % 2 else (240, 240, 240))
            elif kind == "bow":
                put(x - 1, y, ">", c)
                put(x, y, "o", core)
                put(x + 1, y, "<", c)
            elif kind == "star":
                sv = 0.5 + 0.5 * math.sin(t * 5 + ph)
                put(x, y, "*" if sv > 0.5 else "+", mix(c, WHITE, sv * 0.6))
            else:
                put(x, y, "@" if glint else "o", core)

        # 늘어진 전구 줄 / 반짝이 줄
        tins = {"gold": GOLD, "pink": HOT_PINK, "silver": (215, 225, 245)}
        for kind, pts, sag, k, cols in self.garlands:
            sw = sag * (1 + 0.15 * math.sin(t * 1.6 + k * 1.3))
            n = len(pts)
            for idx, (i, jy, w) in enumerate(pts):
                j = int(round(jy + sw * w))
                if not (0 <= j < R) or not inside[j][i] or self._protected(i, j):
                    continue
                x, y = x0 + i, y0 + j
                if not (0 <= x < W and 0 <= y < H):
                    continue
                nxt = pts[min(n - 1, idx + 1)]
                dj = (nxt[1] + sw * nxt[2]) - (jy + sw * w)
                sym = "~" if abs(dj) < 0.45 else ("\\" if dj > 0 else "/")
                if kind == "lights":
                    if idx % 2 == 0:
                        col = self._light(mode, idx, cols[idx], idx * 0.7 + k, t)
                        on = max(col) / 255
                        ch[y][x] = "o" if on < 0.75 else "@"
                        fg[y][x] = col
                        if fancy:
                            bg[y][x] = quant(mix(bg[y][x], col, 0.55 * on))
                            for dx in (-1, 1):  # 전구 불빛 번짐
                                xx = x + dx
                                if 0 <= xx < W:
                                    bg[y][xx] = quant(mix(bg[y][xx], col, 0.25 * on))
                    else:
                        ch[y][x] = "-" if sym == "~" else sym
                        fg[y][x] = (40, 120, 55)
                else:
                    base = tins[kind]
                    v = 0.55 + 0.45 * math.sin(idx * 0.6 - t * 9 + k)
                    if v > 0.96 or rng.random() < 0.02:
                        ch[y][x], fg[y][x] = "*", WHITE
                    else:
                        ch[y][x], fg[y][x] = sym, scale(base, 0.45 + 0.6 * v)
                    if fancy:
                        bg[y][x] = quant(mix(bg[y][x], base, 0.22 * v))

        # 머리 꼭대기 별 (3D 회전)
        sx, sj = self.star_at
        cx = int(round(x0 + sx))
        Ro = self.Ro
        sy = max(Ro // 2, y0 + sj - int(0.45 * Ro))
        lit = smooth((it - INTRO_END) / 0.8)
        if fancy and lit > 0:  # 금빛/핑크 광선
            rad = min(36.0, W * 0.25)
            for y in range(max(0, int(sy - rad / 2)), min(H, int(sy + rad / 3))):
                dyu = (y - sy) * 2.0
                row = bg[y]
                for x in range(max(0, int(cx - rad)), min(W, int(cx + rad) + 1)):
                    if (x, y) in self.screen_mask:
                        continue
                    dxu = x - cx
                    d = math.hypot(dxu, dyu)
                    if d >= rad or d < 1:
                        continue
                    f = 1 - d / rad
                    ang = math.atan2(dyu, dxu)
                    ray = math.cos(8 * ang - t * 0.9)
                    kk = ((ray ** 8 if ray > 0 else 0.0) * 0.6 + f * f * 0.4) * f * lit
                    if kk > 0.02:
                        pk = 0.5 + 0.5 * math.sin(4 * ang - t * 0.5)
                        row[x] = quant(add(row[x], mix((150, 105, 25), (160, 30, 110), pk), kk))
        cosr = math.cos(t * 1.1)
        fx = max(0.32, abs(cosr))  # 빙글 돌되 납작해지지 않게
        shine = (0.45 + 0.55 * lit) * (0.9 + 0.1 * math.sin(t * 6))
        for y in range(max(0, sy - Ro // 2 - 1), min(H, sy + int(0.45 * Ro) + 2)):
            v = (y - sy) * 2.0
            for x in range(max(0, cx - Ro - 1), min(W, cx + Ro + 2)):
                u = (x - cx) / fx
                if not in_poly(u, v, self.star_poly):
                    continue
                dist = math.hypot(u, v) / Ro
                col = mix(GOLD, (255, 250, 225), max(0.0, 1 - dist) ** 1.5)
                if cosr < 0:
                    col = mix(col, (255, 90, 180), 0.55)
                elif dist > 0.7:
                    col = mix(col, (255, 120, 200), (dist - 0.7) / 0.3 * 0.5)
                bg[y][x] = scale(col, shine * (1.0 if cosr > 0 else 0.75))
                ch[y][x] = " "
        put(cx, sy, "*", WHITE)
        if lit > 0:
            for _ in range(14):
                a = rng.uniform(0, TAU)
                d = rng.uniform(Ro + 1, Ro * 2.8)
                px = int(round(cx + math.cos(a) * d))
                py = int(round(sy + math.sin(a) * d * 0.45))
                if 0 <= py < H and 0 <= px < W and ch[py][px] == " " and (px, py) not in self.screen_mask:
                    put(px, py, rng.choice(".+'*`"), mix(rng.choice((GOLD, PINK, HOT_PINK, GOLD)), WHITE, rng.random()))

        # 선물 상자
        for (gx, gy, w, bh, box, ribbon) in self.gifts:
            mid = gx + w // 2
            rib = scale(ribbon, 0.85 + 0.15 * math.sin(t * 3 + gx))
            for r in range(bh):
                y = gy - bh + 1 + r
                if not 0 <= y < H:
                    continue
                for x in range(gx, gx + w + 1):
                    if not 0 <= x < W:
                        continue
                    if x == gx + w:
                        bg[y][x] = scale(box, 0.45)
                        ch[y][x] = " "
                        continue
                    bg[y][x] = box if x < mid else scale(box, 0.82)
                    if r == bh // 2:
                        put(x, y, "+" if x == mid else "=", rib)
                    elif x == mid:
                        put(x, y, "|", rib)
                    else:
                        ch[y][x] = " "
            ly = gy - bh
            if 0 <= ly < H:
                for x in range(gx + 1, gx + w + 1):
                    if 0 <= x < W:
                        bg[ly][x] = mix(box, WHITE, 0.25)
                        put(x, ly, "_", scale(box, 0.7))
                for jj, cc in enumerate(">o<"):
                    put(mid + jj, ly, cc, rib)

    # ---------- 개그 도우미 ----------
    def _put_text(self, ch, fg, bg, x, y, s, colf, bgc):
        """\ud55c\uae00\ucc98\ub7fc 2\uce78\uc9dc\ub9ac \uae00\uc790\ub3c4 \ub193\uc744 \uc218 \uc788\ub294 \uae00\uc790 \uc4f0\uae30."""
        if not 0 <= y < self.H:
            return
        for c in s:
            w = cw(c)
            if x < 0:
                x += w
                continue
            if x + w > self.W:
                break
            ch[y][x] = c
            fg[y][x] = colf(c)
            if bgc is not None:
                bg[y][x] = bgc
            if w == 2:
                ch[y][x + 1] = ""
                if bgc is not None:
                    bg[y][x + 1] = bgc
            x += w

    def _ellipse(self, cx, cy, hw, hh):
        out = []
        for j in range(int(cy - hh) - 1, int(cy + hh) + 2):
            for i in range(int(cx - hw) - 1, int(cx + hw) + 2):
                if ((i + 0.5 - cx) / hw) ** 2 + ((j + 0.5 - cy) / hh) ** 2 <= 1:
                    out.append((i, j))
        return out

    def _skin(self, ex, ey):
        i, j = int(ex), int(ey + self.eye_hh + 2)
        if 0 <= j < self.R and 0 <= i < self.C and self.inside[j][i]:
            return scale(self.col[j][i], 1.05)
        return (230, 185, 165)

    def _draw_face(self, kind, since, t, it, x0, y0, ch, fg, bg, put, talking):
        W, H = self.W, self.H

        def cell(i, j, c, f, b):
            x, y = x0 + i, y0 + j
            if 0 <= x < W and 0 <= y < H:
                ch[y][x] = c
                fg[y][x] = f
                bg[y][x] = b

        hw, hh = self.eye_hw, self.eye_hh
        blink = False  # 눈 깜빡임은 뺐음
        # 볼터치 (부끄 / 하트일 때 진하게, 평소엔 살짝)
        blush_k = 0.6 if kind in ("blush", "heart") else 0.18
        for (cx, cy) in self.cheeks:
            for (i, j) in self._ellipse(cx, cy, hw * 1.25, hh * 1.3):
                x, y = x0 + i, y0 + j
                if 0 <= x < W and 0 <= y < H and 0 <= j < self.R and 0 <= i < self.C and self.inside[j][i]:
                    bg[y][x] = mix(bg[y][x], (255, 90, 150), blush_k)
                    fg[y][x] = mix(fg[y][x], (255, 120, 170), blush_k)
            if kind == "blush":
                for d in (-2, 0, 2):
                    cell(int(cx) + d, int(cy), "/", (220, 40, 110), mix(self._skin(cx, cy - 3), (255, 90, 150), 0.6))

        for (ex, ey) in self.eyes:
            skin = self._skin(ex, ey)
            if blink:
                for (i, j) in self._ellipse(ex, ey, hw, hh):
                    cell(i, j, " ", skin, skin)
                for i in range(int(ex - hw), int(ex + hw) + 1):
                    cell(i, int(ey), "-", (70, 35, 30), skin)
            elif kind == "heart":
                beat = 1 + 0.3 * max(0.0, math.sin(t * 8)) ** 4
                col = mix(HOT_PINK, (255, 60, 120), 0.5 + 0.5 * math.sin(t * 6))
                for (i, j) in self._ellipse(ex, ey, hw * 1.2 * beat, hh * 1.4 * beat):
                    cell(i, j, " ", col, col)
                cell(int(ex) - 1, int(ey), "<", WHITE, col)
                cell(int(ex), int(ey), "3", WHITE, col)
            elif kind == "blush":
                for (i, j) in self._ellipse(ex, ey, hw, hh):
                    cell(i, j, " ", skin, skin)
                cell(int(ex), int(ey), ">" if ex < self.mouth[0] else "<", (50, 20, 20), skin)
            elif kind == "dizzy":
                white = (245, 245, 250)
                for (i, j) in self._ellipse(ex, ey, hw, hh * 1.1):
                    cell(i, j, " ", white, white)
                arm = "-\\|/"[int(t * 14) % 4]
                cell(int(ex), int(ey), "@", (20, 20, 30), white)
                cell(int(ex) - 1, int(ey), arm, (20, 20, 30), white)
                cell(int(ex) + 1, int(ey), arm, (20, 20, 30), white)
            elif kind == "shock":
                white = (252, 252, 252)
                for (i, j) in self._ellipse(ex, ey, hw * 1.35, hh * 1.6):
                    cell(i, j, " ", white, white)
                cell(int(ex), int(ey), "o", (0, 0, 0), white)

        if kind == "dizzy":  # 머리 위를 도는 별
            hx = x0 + (self.eyes[0][0] + self.eyes[1][0]) / 2
            hy = y0 + self.eyes[0][1] - self.R * 0.33
            for k in range(3):
                a = t * 4 + k * TAU / 3
                put(int(round(hx + math.cos(a) * self.C * 0.22)), int(round(hy + math.sin(a) * 2.2)), "*",
                    mix(GOLD, WHITE, 0.5 + 0.5 * math.sin(t * 9 + k)))
                a2 = a - 0.25
                put(int(round(hx + math.cos(a2) * self.C * 0.22)), int(round(hy + math.sin(a2) * 2.2)), "+",
                    scale(GOLD, 0.6))

        if kind == "shades":  # 위에서 툭 떨어지는 선글라스
            q = smooth((since - 0.3) / 0.7)
            settle = since - 1.0
            bounce = 0.8 * math.sin(settle * 12) * math.exp(-settle * 4) if settle > 0 else 0.0
            ey_avg = sum(e[1] for e in self.eyes) / len(self.eyes)
            gy = int(round((ey_avg - 0.6) * q + (-y0 - 4) * (1 - q) + bounce))
            dark = (12, 12, 18)
            lw = hw * 1.45
            for (ex, _ey) in self.eyes:
                for i in range(int(ex - lw), int(ex + lw) + 1):
                    cell(i, gy, " ", dark, dark)
                for i in range(int(ex - lw) + 1, int(ex + lw)):
                    cell(i, gy + 1, " ", dark, dark)
                cell(int(ex - lw) + 1, gy, "/", (235, 235, 255), dark)
                cell(int(ex - lw) + 2, gy, "/", (150, 150, 180), dark)
            a = int(self.eyes[0][0] + lw) + 1
            b = int(self.eyes[1][0] - lw)
            for i in range(a, b):
                cell(i, gy, "=", (70, 70, 85), dark)
            for i in range(int(self.eyes[0][0] - lw) - 3, int(self.eyes[0][0] - lw)):
                cell(i, gy, "-", (60, 60, 75), dark)
            for i in range(int(self.eyes[1][0] + lw) + 1, int(self.eyes[1][0] + lw) + 4):
                cell(i, gy, "-", (60, 60, 75), dark)

        # 입
        big = kind == "shock"
        open_ = talking or big or (kind == "disco" and math.sin(t * 10) > 0)
        if open_:
            mx, my = self.mouth
            mhh = 2.2 if big else (1.5 if int(t * 11) % 3 else 1.1)
            mhw = self.mouth_hw * (1.0 if big else 0.8)
            cells = self._ellipse(mx, my + 0.2, mhw, mhh)
            if cells:
                top = min(j for _, j in cells)
                bot = max(j for _, j in cells)
                for (i, j) in cells:
                    c = (70, 10, 25)
                    if j == top and not big and abs(i + 0.5 - mx) < mhw * 0.7:
                        c = (250, 245, 240)  # 윗니
                    elif j == bot and abs(i + 0.5 - mx) < mhw * 0.55:
                        c = (225, 90, 120)  # 혀
                    cell(i, j, " ", c, c)

    def _draw_sfx(self, kind, since, t, x0, y0, ch, fg, bg):
        word = {"heart": "\ub450\uadfc\ub450\uadfc", "dizzy": "\ube59\uae00\ube59\uae00", "shock": "\ud5c9!!", "disco": "\ub460\uce6b\ub460\uce6b",
                "blush": "///", "shades": "DEAL WITH IT"}.get(kind)
        if not word or since < 0.6:
            return
        ex, ey = self.eyes[0]
        x = int(x0 + ex - self.C * 0.42) + int(round(math.sin(t * 7)))
        y = int(y0 + ey - self.R * 0.28) + int(round(math.sin(t * 5) * 0.6))
        x = max(1, min(self.W - text_w(word) - 1, x))
        y = max(0, min(self.H - 2, y))
        base = t * 0.8
        self._put_text(ch, fg, bg, x, y, word,
                       lambda c: hsv(base + 0.07 * (ord(c) % 7), 0.6, 1.0), None)

    def _draw_bubble(self, line, since, t, x0, y0, ch, fg, bg):
        if not line or not (0.3 <= since < SKIT_LEN - 0.8):
            return
        W, H = self.W, self.H
        n = int((since - 0.3) * TYPE_CPS)
        shown = line[:max(0, n)]
        bw = text_w(line) + 10
        mx, my = x0 + self.mouth[0], y0 + self.mouth[1]
        bx = int(mx + self.C * 0.18)
        by = int(my - self.R * 0.36) - 2
        bx = max(1, min(W - bw - 2, bx))
        by = max(0, min(H - 8, by))
        if "!" in line and n >= len(line) and int(t * 20) % 2:
            bx += self.rng.choice((-1, 1))
        pop = since < 0.42
        paper = (255, 182, 220) if pop else (250, 248, 252)
        edge = HOT_PINK
        ink = (35, 20, 45)
        # 둥근 말풍선 (위아래는 한 칸 들여서)
        inner = bw - 2
        self._put_text(ch, fg, bg, bx + 1, by, "." + "-" * (inner - 2) + ".", lambda c: edge, paper)
        for r in (1, 2, 3):
            self._put_text(ch, fg, bg, bx, by + r, "(" + " " * inner + ")", lambda c: edge, paper)
        self._put_text(ch, fg, bg, bx + 1, by + 4, "`" + "-" * (inner - 2) + "'", lambda c: edge, paper)
        tx0 = bx + 5
        self._put_text(ch, fg, bg, tx0, by + 2, shown, lambda c: HOT_PINK if c == "\uc639" else ink, paper)
        if n < len(line) and int(t * 6) % 2:
            cx = tx0 + text_w(shown)
            if cx < bx + bw - 1:
                self._put_text(ch, fg, bg, cx, by + 2, "_", lambda c: ink, paper)

    def frame(self, t, s, painter):
        if not self.ok:
            msg = "Please make the window bigger (min 30 x 16)."
            return "\x1b[0m\x1b[2J\x1b[%d;1H\x1b[93m%s\x1b[0m" % (max(1, self.H // 2), msg[: max(0, self.W - 1)])
        self.update(t, s)
        ch, fg, bg = self.render(t)
        W, H = self.W, self.H
        out = ["\x1b[?2026h"]
        for y in range(H):
            out.append("\x1b[%d;1H" % (y + 1))
            lf = lb = None
            rc, rf, rb = ch[y], fg[y], bg[y]
            n = W if y < H - 1 else W - 1
            skip = False
            for x in range(n):
                if skip:  # 바로 앞 2칸 글자가 차지한 자리
                    skip = False
                    continue
                c = rc[x]
                if c == "":
                    c = " "  # 짝 잃은 자리 (덮어써진 한글의 뒤칸)
                elif c > "\x7f" and cw(c) == 2:
                    if x + 1 >= n:
                        c = " "
                    else:
                        skip = True
                b = rb[x]
                if b != lb:
                    out.append(painter.bg(b))
                    lb = b
                if c != " ":
                    f = rf[x]
                    if f != lf:
                        out.append(painter.fg(f))
                        lf = f
                out.append(c)
        out.append("\x1b[0m\x1b[?2026l")
        return "".join(out)


# --------------------------------------------------------------------------
# 메인
# --------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description="Colorful animated ASCII portrait")
    ap.add_argument("--image", help="\ub2e4\ub978 \uc0ac\uc9c4 \ud30c\uc77c (PNG, macOS\ub294 jpg/heic/webp\ub3c4)")
    ap.add_argument("--mode", choices=["photo", "neon", "rainbow", "matrix", "thermal", "holo"])
    ap.add_argument("--text", default="")
    ap.add_argument("--say", default="", help='\ub9d0\ud48d\uc120 \ub300\uc0ac, | \ub85c \uad6c\ubd84 (\uc608: "\uc639\uc639.|\ubc30\uace0\ud30c \uc639")')
    ap.add_argument("--no-gags", action="store_true")
    ap.add_argument("--no-tree", action="store_true", help="\ud2b8\ub9ac \uc7a5\uc2dd \ub044\uae30")
    ap.add_argument("--no-fireworks", action="store_true", help="\ubc30\uacbd \ud3ed\uc8fd \ub044\uae30")
    ap.add_argument("--fps", type=float, default=24.0)
    ap.add_argument("--no-intro", action="store_true")
    ap.add_argument("--no-resize", action="store_true")
    ap.add_argument("--256", dest="c256", action="store_true")
    ap.add_argument("--truecolor", action="store_true")
    ap.add_argument("--frames", type=int, default=0, help=argparse.SUPPRESS)
    args = ap.parse_args()

    img = load_image(args.image) if args.image else load_embedded()
    face = None if args.image else FACE
    enable_windows_vt()
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # 말풍선 한글
        except Exception:
            pass
    truecolor = args.truecolor or (detect_truecolor() and not args.c256)
    painter = Painter(truecolor)
    fps = max(1.0, min(60.0, args.fps))
    step = 20.0 / fps
    out = sys.stdout

    def write(s):
        out.write(s)
        out.flush()

    orig = maximize_window(write) if (not args.no_resize and sys.stdout.isatty()) else None
    write("\x1b[?1049h\x1b[?25l\x1b[2J")
    try:
        size = scene = None
        t0 = time.time()
        frames = 0
        while True:
            start = time.time()
            cur = shutil.get_terminal_size((100, 40))
            if cur != size:
                first = scene is None
                size = cur
                scene = Scene(cur.columns, cur.lines, img, args, truecolor, start - t0,
                              intro=(first or not scene.ok) and not args.no_intro, face=face)
                write("\x1b[0m\x1b[2J")
            write(scene.frame(start - t0, step, painter))
            frames += 1
            if args.frames and frames >= args.frames:
                break
            spent = time.time() - start
            if spent < 1.0 / fps:
                time.sleep(1.0 / fps - spent)
    except KeyboardInterrupt:
        pass
    finally:
        write("\x1b[0m\x1b[?25h\x1b[?1049l")
        if orig and orig.columns and os.name != "nt":
            write("\x1b[9;0t\x1b[8;%d;%dt" % (orig.lines, orig.columns))


DATA = (
    "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"
    "k+uKV0whR4iPS/o+KSG5cGTPbo3wH+qfRjzYviorfWDXDpvq1qj1E2sBOdM6JjpO6wKJCczz1x4o2jPNql0ydQxmf+V5FVt9kdnz"
    "aUvGbkxu8l/1NTZavCyX0d3qx6x4YF/Op2hvapcqCibY/R9xL5NLUJ4vGNsurxWM5jDv134ntv7KZv83jw0XMtrD8CDjUzT4of8X"
    "Wx22iUvSB80YNe8hVydX5QvOVVy0Toa58L7evtoPnLMB3FytXrNRoSF4sWE9DO3YBhtnj8OHR7fjK9HPj26dw4/3LuHH+1fx0/3r"
    "+FmO310SPDi2HysnjYU3fV6VKpYt+3J48D8uox/srDxlM++8kp3dX8YU/2/wwGBC3cQYDG/XEuP/n+bOPEzO6jrzUndXV1fX2t3V"
    "1Wv1VtX7qtaGJCQWGRAgJBBCAiQhsW/GYDYLMEYxNmDAG9gQlhiDV+R4wQvxRjzBjjO2STLx8iQZx84kJI4zM87jmWQYjx24c3/v"
    "/U7pU0cmi0HyH99T3bUv333ve855z3t2n+Hedsk295vXnu8+fOtr3SfwgLzzBvfZu65zn7/nRvd7973JfePhO6VP/ItPP+Z++OUn"
    "3V9/9XPu+W980R/PuB9+9XfcH376w+5j99zq7jz/THf5a1a5jdPDbr7subnnsH0+Npvwe9mQjxXQGuHPNalcwoj2Y3qLmK8qz2P8"
    "DVn/g+PiBtWBcfkgwxGI6Ykr4Ald/nchNujrCb1NOc8PGuuTqhMQK5Q8DjQ3UlfO628OfNfxU4IjgBXECWCBZjkNhdltS2dXMMNR"
    "eqWu9rK8mAf7q25oaPTnM5Mzf3Tnrddd9KPnvlI8ElpF8ge/8/i7Zt7/jjue3H7mlhfgBUNDzLUOWEDMQJ2B/h78ReQr4v8GD8xP"
    "iHXC/6YBsP3U8v42V9Vy76Y5MAyw+N1qftT30Xug+dOMRYsXonmK8sFsqDtk/Lrwb1vDcc2ivZ6t/7gnUtwLntviNRLLF1p+kc+x"
    "OJoPb33b8n6iVonHRtQbBS6oziB9a04+8fxN/bq7s0f+PfTRtkrH1O6GPE9YPj3ubjj/HPf1j73P/fiPfs/Hzn/o/s8Pv+P+719+"
    "T8c//tf/4n78rWfdj77+e+6G885T7iCdqI90yUGL+HJ4sDj6fg54gywK3kHiEHW/Ej+I/w79pRb3uu2nuTfu3OJu3Xmau+vCre6B"
    "a3a7x2+61H3k1ivdb++7yn3qLde6L/j44dkHbnfPvf9e9+2P0dP1hPve5/e773zht90fP73ffePjj7vPPni3e/D6izS7ktnxJ4wN"
    "uJluzw/aS67s8ZVaY280H4k84tjIuJv18QHz01h36IfxKiNOYC3SZ0RvwYh6EavqPcLLgHnQo8MTyjvA3/o95yAvDJ7jg4BGuT3K"
    "EzLDFZ0Rvsvs8+QS4AnEANzWmivqfrwGs95mp5f7OGG1W+kPXq81VxJOoYvo76++tHR+2d/evvfqe7/y4fvHnNtff6TqC7/5tn1P"
    "blh//Av9/WE+Kwc5BHp+6AvGS9X8Ec1PqKmpueZRTu7Q8MH2ZIvBDSOsHmcaRYvDTY9Qm8eWifzUmoMvAvE4mCAPu3rzyQ4a+8X/"
    "Crc1nLGYwfDA4n7ribLcA9dr1kOkS+L9xT3Xza+NzwfGGYegRqo5E9QVWttCv6bnmIEXFGpaNnop8eiFf+LdD08oRZ7g6NzAiE4f"
    "XxE7rFu61L3h4t3uPz/1Ufd3f/z77p/+4jvun37gj7/4tvuHP33O/e03f8/98Gv/yW0+7tiabyKaw8YYHhwyVohpBupqfYl2n8UH"
    "1RB+VY6QbUq4Xaesd2/cs93dvOM0d8uOU93te7a4d/v4/+HrL3BP3HKZ+8htr3Mfe8vr3VN3v8F94b7b3Jc8T3jmsXe6Zx6/333+"
    "sXe7zz50r/v4O/a5h2+63N154WZ37amr3bZl425dpd+NdXW6we5eabyYucL3SW1RnMDz/pXLVwkbCpk27c9ohMqRF7rlDbhkbXZ3"
    "9KlGST2SPmnyjpWBqnK/ifpG4To+68kE/a05/3t1hvkrfv9P+/+JDzqFEUXFHvQrMfe1s71X/qlwE/U5zq70mDPrH9/jzwmPZd0D"
    "Hrum3MjIqN+Hq/90/vYtn37Pb9y43n3/+8kjggdPPT5z1e4dT46NjLygWc09/bW5bMQJ+CdTf4Q3gBHiCPmg5U02Jmv7pvHsuLYv"
    "zs1tjzV9otX4LDcZnwUf+gibI5+UxhpXaPDnO7kDW6MLOcHCc9JiEuMIcTxQHEPNoCGaweTXf970A9Qek00H5rhGeZLwmYKXGpch"
    "1uDzZlQ/oD8T7YF0bNm8+p6yzTnlooJ/Rj5wBv8/tWzpEVqL8t2hro3nEj0Q3XhS+etnhofd1eed7R6+41b33Gd/2/3ke8+5//0X"
    "f+L+x3e/6THi6+65z3/WTZruwMdTaIsao9psfdSnWNMGxPDA1v8BPdGBY9ErhQfql1rs1i+bc3v3nO1u3XOme+N5p7ubzj3N3X7h"
    "NveO157nHrjuQvfo3kvdY7dc4T5w21XuI54rfPSuG92Td9/sPnL3Le6Jt77BPXrr1e49Ps54y0Wb3C3b1rkrT1jqzpgbdkd7PKh2"
    "4WVUUf9SyX9/6A7mZua1t5PXn4l0RuT8Ooo9WpNwBeYt8Tc4MCx+MBzVC4akI2JPl554YlY1BLyRUsm0Zi8kG9GhNUtjVMi16RIe"
    "QO4gn24RVwBPqDe0M8PBxyq81ng0n4UDTGpv8fFFoUO9DfAR8KDc0/eLTSe+5ltvf9MNZzn3fOrI1BsfmLnxsoufnBwff6HXcyNw"
    "gHWPfyJ4wCVY0F8e1Dxn/ieGCHMM8jWfU9vnbR+1vibjCvH43daWxeGGB5ZryKsfKCf/E/USpgJXSCTAgcUH9Se9XK7bYgJwxt6D"
    "NA9oJshp+LWrOe/UMVQbCHUN9nqLE6w2au83KZxIRv6N9fJWw3OF7yMh33e8NYpBt4KHM32Ung+AA6lU8HOV5yQ6pXSoQZJTpGbO"
    "PtTib8O/o7OjU3WI8cFBd8axR7t33HSd++Hv/6773z/4rvvv3/6G+5/f/UP34Qfe4+PUpihvEPxTVYeJvJXro3rBL8ODl/vuflVu"
    "UAde+8vRco+75hyPBedvc7edf5ZqkFzefeVu967XX+Dee8PF7uG9l7lHb77c/ZbHhUduudI97C/fe8Ml7u3X7HFvvcQ/btdGt3fb"
    "Me7ajcvcxcfMuM1LRtyy/rKPR7qUy5/0HJ9cDPwArZHy+35/hvuTx+Oy5Ncm9cUyngSVSWECPH6oz8fG/WPCCfQCrGPWNZx/enJO"
    "miHqh+jI+C0b6ul3zbshj0N4rhM7kA8ET+iDQLPY3tYprQPaSHocyRsQmxCrgA9gAdyiHU/3csWNjkwojz88NPziSSes/+69b7pp"
    "l/uTP0kfmfzBAzM3X3npk0tm514AC5ipAB/Ao5h4gevKHifAhnI5zHeGM4QZC/gdhVnK+KRZXtF6CSxvaHzbtINxXyPDD+tftvwC"
    "67WjGHrOM/Lx4fENB+UCX67HOY4J9h6UL6Q3jXmR/r1TJyT+J2epXEXkpS4fA95r9D4t5pHfaiIpj0V81eiPJG4Kfu0+hiJG8DhG"
    "LoB1zfnCPABwAl82bjNPVzxZ6J233AJ6BbSy5By7O6hDwtX87+HP+aPm5twFW85wf/CZT7gfffub7u/98ePvPOeuvvB8re8m9S7V"
    "q4c5UU9uv06HuFTkHbg4dtQdwr/gFceDiI8VMml33uaT3I17tvq44Sx303lb/OVWd9eVu9w7rj7f3Xfdxe7BGy/R8YDHhndfe4F7"
    "+1XnuTs9DuzbvdntPXuDu/7MY93rT1/lrjhp1u0+ZtptmBt1lY6S35dbFIOT7wq+RW3KB9IbQJzA3ovmINQD+1VnII/I/CT+BheY"
    "i8B6pU8Zvg9+UDekJwENU3VoVLOc4QvEc+QPOv3vQ28isWDOYwf3Re/A6/Ca2eaC9AzyQBgcV/6S1wKLigW/ZnycwGtQi0AjKX2E"
    "5wgTo5MvrVm95s8vOPesS7762Q+1HG6tIvqDZz0/2Pf6K5887phjXujT7PZe/3m7a7kD6gvECJz3Rb+GumNz2sAK7kdczEw0fJdZ"
    "M6bPieuPrF8pnluI+6IZhhif78CDsdiu2CEl/XLYwxsP0du8UJu88IjrFpS3wEun1KHeFPM0wfsCPSS5TF6vIVaLsM8CJwAH+C6Y"
    "6RT0SVn5scELMums/ifWwL+pRXPms8KJlLwWwrzpmt878ydTaeUeS20dqjMko7ok5zd6OWKJIX9+r1m60t18xaXug/fd4/7yG8+6"
    "7z37Zbd8ekrrWvnWRXU1vVG9cQO+o1cwDvj340HoaTjp6GXu2l1b3N7dW91NHhNu9sftl+1wb7tqt3v7685377zmfM8V9rh3eBy4"
    "+4qd7g6w4LzN7mZhwfEeC9a5q05d6S5+zRJ3ztppN1/t0wzNdAq/yqxf373qVVQur7tfmDBWnVDdH/919vrqwKj25wG/X/d09Nfq"
    "DGH/ntWstc5Sj7g+eUH8TaZ8vIGPSb88DSakHaHuwHxn1jIxQtZzhSL6w1LoTQBXOsDzclWcgNfp763qdeAg6WQuPNbjWEu2Xf7s"
    "/eVKxBOm3PjYxF+tW73itv3SLh9ej9WQP3hk5u433vjRY9euFR4QE+CZrlnIeM4w2z7fojXAfJNSR1dtXhOxg+YztLVrNgv4YXu8"
    "9SgZz47r/xZqBeLnkNUJc5HHiOJycflQ109F/ieGB8YXXo4jxGc4q5cK/ZCPSbgMfawp8QL5qCt/kVNewTRKpqvGY5UYiTXP2oYn"
    "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"
)

if __name__ == "__main__":
    main()
