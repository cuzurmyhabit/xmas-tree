#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HOLO XMAS TREE - 3D로 회전하는 홀로그램 ASCII 크리스마스 트리

  실행 :  python3 xmas_tree.py       (macOS / Linux)
          python xmas_tree.py        (Windows cmd / PowerShell / Windows Terminal)
  종료 :  Ctrl + C

  옵션 :  --fps 30           프레임 속도 (기본 24)
          --speed 1.5        회전 속도 배율 (기본 1.0)
          --no-intro         홀로그램 생성 연출 건너뛰기
          --no-resize        시작할 때 창 최대화 안 함
          --no-fireworks     불꽃놀이 끄기
          --no-aurora        오로라 끄기
          --256              256색 모드 강제 (색이 이상할 때)
          --truecolor        24bit 색 강제

  트리를 더 크게 보려면: 창을 최대화하고 글자 크기를 줄이세요 (macOS: Cmd + -, Windows: Ctrl + 휠).
  화면에 출력되는 글자는 전부 ASCII 라서 한글 Windows cmd 에서도 줄이 밀리지 않습니다.
  외부 라이브러리 없이 파이썬 표준 라이브러리만 사용합니다.
"""

import argparse
import colorsys
import datetime
import math
import os
import platform
import random
import shutil
import sys
import time

TAU = math.tau
HALF_PI = math.pi / 2
LIGHT_DIR = -0.65  # 왼쪽 앞에서 비추는 조명 (시선 기준 각도)

# --------------------------------------------------------------------------
# 터미널 준비
# --------------------------------------------------------------------------


def enable_windows_vt():
    if os.name != "nt":
        return
    try:
        import ctypes

        k32 = ctypes.windll.kernel32
        handle = k32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if k32.GetConsoleMode(handle, ctypes.byref(mode)):
            k32.SetConsoleMode(handle, mode.value | 0x0001 | 0x0004)
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
        try:  # macOS 26(Tahoe) 터미널부터 24bit 색 지원
            return int(platform.mac_ver()[0].split(".")[0]) >= 26
        except Exception:
            return False
    return False


def maximize_window(write):
    """창을 최대화 시도. 되돌릴 때 쓸 원래 크기를 돌려준다."""
    orig = shutil.get_terminal_size((0, 0))
    if os.name == "nt":
        try:
            import ctypes

            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
        except Exception:
            pass
    else:
        write("\x1b[9;1t")  # xterm 계열 '창 최대화' 요청 (지원하는 터미널만 반응)
    time.sleep(0.35)
    return orig


# --------------------------------------------------------------------------
# 색상 도우미
# --------------------------------------------------------------------------


def _c(v):
    return 0 if v < 0 else 255 if v > 255 else int(v)


def rgb(r, g, b):
    return (_c(r), _c(g), _c(b))


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


def smooth(x):
    x = 0.0 if x < 0 else 1.0 if x > 1 else x
    return x * x * (3 - 2 * x)


def rgb_to_256(r, g, b):
    if abs(r - g) < 12 and abs(g - b) < 12 and abs(r - b) < 12:
        if r < 6:
            return 16
        if r > 240:
            return 231
        return 232 + min(23, max(0, int(round((r - 8) / 10.0))))

    def q(v):
        if v < 48:
            return 0
        if v < 115:
            return 1
        return min(5, (v - 35) // 40)

    return 16 + 36 * q(r) + 6 * q(g) + q(b)


class Painter:
    def __init__(self, truecolor):
        self.tc = truecolor
        self._fg = {}
        self._bg = {}

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
# 데이터
# --------------------------------------------------------------------------

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

PINKS = [
    (255, 105, 180),  # hot pink
    (255, 20, 147),  # deep pink
    (255, 160, 205),  # baby pink
    (255, 190, 220),  # sakura
    (245, 80, 170),  # rose
    (255, 0, 190),  # neon magenta
]
PALETTE = [
    (255, 45, 45), (255, 205, 40), (60, 150, 255), (40, 235, 235),
    (255, 135, 25), (245, 245, 255), (175, 95, 255), (120, 255, 120),
] + PINKS + PINKS[:3]  # 핑크 비중을 크게
WHITE = (255, 255, 255)
GOLD = (255, 196, 50)
SILVER = (205, 220, 245)
PINK = (255, 105, 180)
HOT_PINK = (255, 20, 147)
HOLO = (90, 235, 255)
HOLO_DIM = (0, 110, 140)
GLITCH = "01#=+:%$&"
LEAF = "#*%^&*#^%8*^#&"
PINK_HUES = (0.89, 0.92, 0.95, 0.97)
STAR_TINTS = [(200, 210, 255), (255, 175, 220), (255, 230, 170), (170, 240, 255), (225, 190, 255)]

LIGHT_MODES = ["twinkle", "pink", "rainbow", "chase", "candy", "pulse", "sparkle"]
MODE_SECONDS = 6.0


def pink_hue(rng):
    return rng.choice(PINK_HUES) + rng.uniform(-0.015, 0.015)

# 연출 타이밍 (초)
BUILD_START = 0.5
BUILD_LEN = 3.8
BUILD_END = BUILD_START + BUILD_LEN
BANNER_START = BUILD_END + 0.35
SWEEP_EVERY = 13.0


def holiday_text():
    today = datetime.date.today()
    xmas = datetime.date(today.year, 12, 25)
    if today == xmas:
        a = "* It's Christmas Day! *"
    elif today < xmas:
        a = "D-%d until Christmas" % (xmas - today).days
    else:
        a = "Merry Christmas!"
    ny = today.year if (today.month == 1 and today.day <= 15) else today.year + 1
    return "~  %s   *   Happy New Year %d  ~" % (a, ny)


def star_polygon(ro, ri):
    pts = []
    for k in range(10):
        a = -HALF_PI + k * math.pi / 5
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


# --------------------------------------------------------------------------
# 불꽃놀이
# --------------------------------------------------------------------------


class Firework:
    def __init__(self, rng, x, y0, target_y):
        self.rng = rng
        self.x, self.y = float(x), float(y0)
        self.vy = -rng.uniform(0.9, 1.3)
        self.target = target_y
        self.hue = pink_hue(rng) if rng.random() < 0.45 else rng.random()
        self.style = rng.choice(["sphere", "rainbow", "ring", "willow", "double", "heart", "heart",
                                 "multi", "glitter", "pink", "pink"])
        self.trail = []
        self.parts = []
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
        n = rng.randint(70, 110)
        if self.style == "heart":  # 핑크 하트 모양 폭죽
            hue = pink_hue(rng) if rng.random() < 0.8 else 0.0
            n = 90
            for i in range(n):
                a = i / n * TAU
                hx = 16 * math.sin(a) ** 3 / 17.0
                hy = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)) / 17.0
                sp = 0.9
                life = rng.uniform(30, 40)
                self.parts.append([self.x, self.y, hx * sp * 2.0, hy * sp, life, life,
                                   hue + rng.uniform(-0.02, 0.02), self.x, self.y])
            for i in range(25):  # 안쪽 반짝이
                a = rng.uniform(0, TAU)
                sp = rng.uniform(0.05, 0.35)
                life = rng.uniform(15, 30)
                self.parts.append([self.x, self.y, math.cos(a) * sp * 2, math.sin(a) * sp, life, life,
                                   0.93, self.x, self.y])
            return
        for i in range(n):
            a = (i / n) * TAU + rng.uniform(-0.05, 0.05)
            if self.style == "ring":
                sp = 0.75 + rng.uniform(-0.04, 0.04)
            elif self.style == "double":
                sp = 0.8 if i % 2 else 0.4
            elif self.style == "willow":
                sp = rng.uniform(0.25, 0.7)
            else:
                sp = rng.uniform(0.15, 0.85)
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
            self.parts.append([self.x, self.y, math.cos(a) * sp * 2.0, math.sin(a) * sp,
                               life, life, hue, self.x, self.y])


# --------------------------------------------------------------------------
# 장면
# --------------------------------------------------------------------------


class Row:
    __slots__ = ("R", "pos", "U", "tex")


class Scene:
    def __init__(self, W, H, args, truecolor, t_start, intro=True):
        self.W, self.H = W, H
        self.args = args
        self.fancy = truecolor
        self.rng = random.Random(args.seed)
        self.message = holiday_text()
        self.t0 = t_start if intro else t_start - (BANNER_START + 3.0)
        self.ignited = not intro
        self.ignite_t = -99.0
        self.flash = 0
        self.ok = W >= 40 and H >= 18
        if not self.ok:
            return
        self._layout()
        if not self.ok:
            return
        self._build_sky()
        self._build_tree()
        self._build_gifts()
        self._build_snow()
        self._build_banner()
        self.fireworks = []
        self.shooting = []
        self.particles = []  # [x, y, vx, vy, life, maxlife, hue, sat, grav]
        self.glitch = None  # [y0, h, off, frames]
        self.next_volley = 1e9 if intro else BANNER_START + 6.0

    # ---------------- 배치 ----------------
    def _layout(self):
        W, H = self.W, self.H
        for big in ((W >= 92 and H >= 40), False):
            self.big = big
            self.banner_scale = 2 if (big and W >= 186) else 1
            banner_h = 5 if big else 1
            self.sub_y = H - 1
            self.banner_y = H - 2 - banner_h
            self.ground_y = self.banner_y - 2
            self.trunk_h = 3 if H >= 40 else 2
            self.Ro = 8 if H >= 44 else 6 if H >= 30 else 4
            self.star_y = self.Ro // 2 + 1
            self.tree_top = int(self.star_y + 0.405 * self.Ro) + 1
            self.tree_bottom = self.ground_y - self.trunk_h - 1
            self.tree_h = self.tree_bottom - self.tree_top + 1
            if self.tree_h >= 10:
                break
        if self.tree_h < 6:
            self.ok = False
            return
        self.cx = W // 2
        self.Rmax = max(4.0, min(W * 0.46 - 2, self.tree_h * 1.6))
        self.trunk_hw = max(1, int(self.Rmax / 8))
        self.obj_top = max(0, self.star_y - self.Ro // 2 - 1)

    def _radius(self, r):
        th = self.tree_h
        tiers = 5 if th >= 28 else 4 if th >= 16 else 3
        t_len = th / tiers
        base = (r + 1.5) / (th + 0.5) * self.Rmax
        tier = min(tiers - 1, int(r // t_len))
        pos = (r - tier * t_len) / t_len
        shrink = (1 - pos) * 0.26 * base if tier > 0 else 0
        return max(0.8, base - shrink), pos

    def _build_sky(self):
        rng = self.rng
        W, H, gy = self.W, self.H, self.ground_y
        top, mid, low = (2, 4, 18), (14, 14, 50), (4, 4, 12)
        self.sky = []
        for y in range(H):
            if y <= gy:
                c = mix(top, mid, y / max(1, gy))
            else:
                c = mix(mid, low, min(1.0, (y - gy) / 3.0))
            self.sky.append(c if self.fancy else (0, 0, 0))
        # 별: (x, y, 위상, 속도, 글자, 색, 큰별?)
        self.stars = []
        for _ in range(W * gy // 26):
            big = rng.random() < 0.06
            self.stars.append((rng.randrange(1, W - 1), rng.randrange(1, max(2, gy - 2)), rng.uniform(0, TAU),
                               rng.uniform(0.5, 3.0) if not big else rng.uniform(0.6, 1.4),
                               rng.choice("..'.+.`*"), rng.choice(STAR_TINTS), big))

    def _build_tree(self):
        rng = self.rng
        th = self.tree_h
        self.rows = []
        total_circ = 0.0
        for r in range(th):
            row = Row()
            row.R, row.pos = self._radius(r)
            row.U = max(6, int(TAU * row.R))
            total_circ += TAU * row.R
            tex = []
            for _ in range(row.U):
                c = rng.choice(LEAF)
                if rng.random() < 0.035:
                    c = rng.choice("*+")
                    col = (210, 230, 245)  # 가지 끝 눈
                else:
                    col = hsv(rng.uniform(0.26, 0.42), rng.uniform(0.65, 0.95), rng.uniform(0.7, 1.0))
                tex.append((c, col, rng.random()))
            row.tex = tex
            self.rows.append(row)

        # 오너먼트 (원뿔 표면 좌표: 행, 각도)
        self.ornaments = []
        for _ in range(int(total_circ * 0.065)):
            r = rng.randrange(2, th)
            p = rng.random()
            if p < 0.16:
                kind, col = "heart", rng.choice(PINKS + [(255, 40, 70)])
            elif p < 0.26:
                kind, col = "cane", (255, 40, 60)
            elif p < 0.36:
                kind, col = "bow", rng.choice(PINKS)
            elif p < 0.44:
                kind, col = "starorn", rng.choice([GOLD, (255, 240, 150), PINK])
            elif self.rows[r].R > 7 and p < 0.75:
                kind, col = "big", rng.choice(PALETTE)
            else:
                kind, col = "ball", rng.choice(PALETTE)
            self.ornaments.append((r, rng.uniform(0, TAU), col, kind, rng.uniform(0, TAU)))

        # 나선 장식: 반짝이 줄(tinsel) 2개 + 전구 줄 2개
        def helix(turns, phase, direction, spacing):
            pts = []
            s = 0.05
            while s < 1.0:
                rf = s * (th - 1)
                R = self.rows[int(rf)].R
                pts.append((int(rf), phase + direction * s * turns * TAU))
                s += spacing / math.hypot(R * turns * TAU, th * 2.0)
            return pts

        t1 = 3.5 if th >= 16 else 2.5
        self.tinsels = [
            (helix(t1, 0.0, 1, 0.6), GOLD, 1 * t1 * TAU / th),
            (helix(t1 * 0.85, 2.0, -1, 0.6), HOT_PINK, -1 * t1 * 0.85 * TAU / th),
            (helix(t1, 3.4, 1, 0.6), SILVER, 1 * t1 * TAU / th),
        ]
        self.lightstrings = []
        for (turns, phase, d) in ((t1 * 1.35, 1.0, 1), (t1 * 1.2, 4.0, -1), (t1 * 1.6, 5.5, 1)):
            pts = helix(turns, phase, d, 1.9)
            self.lightstrings.append([(r, ph, i, rng.choice(PALETTE), rng.uniform(0, TAU), rng.uniform(0.6, 1.6))
                                      for i, (r, ph) in enumerate(pts)])
        self.star_poly = star_polygon(self.Ro, self.Ro * 0.42)

    def _build_gifts(self):
        rng = self.rng
        self.gifts = []
        max_bh = max(1, self.trunk_h - 1)
        limit = self.Rmax + 6
        for side in (-1, 1):
            edge = self.cx + side * (self.trunk_hw + 2)
            for _ in range(4):
                w = rng.choice([5, 7, 7, 9, 11]) if self.Rmax > 20 else rng.choice([5, 7])
                bh = rng.randint(1, max_bh)
                if side < 0:
                    x0 = edge - w
                    if x0 < 1 or self.cx - x0 > limit:
                        break
                    edge = x0 - 2
                else:
                    x0 = edge
                    if x0 + w + 1 >= self.W - 1 or x0 + w - self.cx > limit:
                        break
                    edge = x0 + w + 3
                box = rng.choice([(200, 30, 40), (40, 90, 210), (130, 50, 200), (20, 150, 120),
                                  (220, 160, 20), (230, 80, 150), (255, 120, 190), (240, 60, 160),
                                  (255, 170, 210)])
                ribbon = rng.choice([(255, 215, 80), (255, 255, 255), (255, 60, 170)])
                if box[0] > 220 and box[2] > 140:  # 핑크 상자엔 금/흰 리본
                    ribbon = rng.choice([(255, 215, 80), (255, 255, 255)])
                self.gifts.append((x0, w, bh, box, ribbon))

    def _build_snow(self):
        n = max(40, self.W * self.ground_y // 22)
        self.snow = [self._new_flake(self.rng.uniform(0, self.ground_y)) for _ in range(n)]
        # 반짝이 색종이 (핑크 위주)
        self.confetti = [self._new_confetti(self.rng.uniform(0, self.ground_y))
                         for _ in range(max(15, self.W * self.ground_y // 90))]
        self.hearts = []  # 떠오르는 하트 [x, y, vy, phase, life, maxlife, color]

    def _new_confetti(self, y):
        rng = self.rng
        col = rng.choice(PINKS + PINKS + PALETTE + [GOLD, WHITE])
        return [rng.uniform(0, self.W), y, rng.uniform(0.15, 0.4), rng.uniform(0, TAU),
                rng.choice("*+'`.*~"), col, rng.uniform(2, 6)]

    def _new_flake(self, y):
        rng = self.rng
        if rng.random() < 0.45:
            return [rng.uniform(0, self.W), y, rng.uniform(0.35, 0.7), rng.uniform(0, TAU),
                    rng.choice("**.+'*"), rng.uniform(0.75, 1.0), True]
        return [rng.uniform(0, self.W), y, rng.uniform(0.12, 0.3), rng.uniform(0, TAU),
                rng.choice("..'."), rng.uniform(0.3, 0.55), False]

    def _build_banner(self):
        sc = self.banner_scale
        self.banner_px = []
        if not self.big:
            return
        gap = 1 if sc == 1 else 2
        width = sum((3 * sc) if c == " " else (5 * sc + gap) for c in BANNER) - gap
        x0 = (self.W - width) // 2
        self.banner_x0, self.banner_w = x0, width
        x = x0
        for c in BANNER:
            if c == " ":
                x += 3 * sc
                continue
            for r, line in enumerate(FONT[c]):
                for j, p in enumerate(line):
                    if p == "#":
                        for k in range(sc):
                            self.banner_px.append((x + j * sc + k, self.banner_y + r))
            x += 5 * sc + gap

    # ---------------- 상태 ----------------
    def _build_state(self, it):
        """(진행도 0..1, 스캔 라인 y)"""
        p = smooth((it - BUILD_START) / BUILD_LEN)
        top, bot = self.obj_top - 2, self.ground_y
        return p, bot - p * (bot - top)

    def _rot(self, it):
        sp = self.args.speed
        return sp * (0.65 * it + 0.5 * math.sin(it * 0.31)) + 5.5 * (1 - math.exp(-it / 1.3))

    # ---------------- 물리 ----------------
    def update(self, t, s):
        rng = self.rng
        W, gy = self.W, self.ground_y
        it = t - self.t0

        wind = 0.3 * math.sin(t * 0.13)
        for f in self.snow:
            f[1] += f[2] * s
            f[0] = (f[0] + (math.sin(t * 1.3 + f[3]) * 0.22 + wind) * s * (1.0 if f[6] else 0.5)) % W
            if f[1] >= gy:
                f[:] = self._new_flake(rng.uniform(-3, 0))
        for f in self.confetti:
            f[1] += f[2] * s
            f[0] = (f[0] + (math.sin(t * 2.1 + f[3]) * 0.35 + wind) * s) % W
            if f[1] >= gy:
                f[:] = self._new_confetti(rng.uniform(-3, 0))

        # 발판에서 떠오르는 핑크 하트
        if self.ignited and len(self.hearts) < 10 and rng.random() < 0.07 * s:
            side = rng.choice((-1, 1))
            x = self.cx + side * rng.uniform(self.trunk_hw + 3, self.rows[-1].R + 6)
            life = rng.uniform(40, 80)
            self.hearts.append([x, gy - 1.0, rng.uniform(0.25, 0.5), rng.uniform(0, TAU), life, life,
                                rng.choice(PINKS + [(255, 40, 70)])])
        for h in self.hearts:
            h[1] -= h[2] * s
            h[0] += math.sin(t * 2 + h[3]) * 0.25 * s
            h[4] -= s
        self.hearts = [h for h in self.hearts if h[4] > 0 and h[1] > 1]

        # 생성 중: 스캔 라인에서 홀로그램 불꽃이 튐
        p, scan = self._build_state(it)
        if 0 < p < 1:
            r = int(scan) - self.tree_top
            R = self.rows[r].R if 0 <= r < self.tree_h else self.Ro
            for _ in range(int(7 * s) + 1):
                life = rng.uniform(8, 18)
                hue = rng.uniform(0.48, 0.55) if rng.random() < 0.6 else pink_hue(rng)
                self.particles.append([self.cx + rng.uniform(-1, 1) * (R + 3), scan, rng.uniform(-0.6, 0.6),
                                       -rng.uniform(0.2, 1.0), life, life, hue, 0.6, 0.0])

        # 완성 순간: 별 점화 + 폭발
        if not self.ignited and it >= BUILD_END:
            self.ignited = True
            self.ignite_t = it
            self.flash = 5
            for i in range(220):
                a = rng.uniform(0, TAU)
                sp = rng.uniform(0.3, 1.8)
                life = rng.uniform(15, 40)
                hue = rng.uniform(0.08, 0.16) if i % 3 else pink_hue(rng)
                self.particles.append([self.cx, self.star_y, math.cos(a) * sp * 2, math.sin(a) * sp,
                                       life, life, hue, rng.uniform(0.3, 0.9), 0.02])
            self.next_volley = it + 3.0
        self.flash = max(0, self.flash - 1)

        keep = []
        for q in self.particles:
            q[0] += q[2] * s
            q[1] += q[3] * s
            q[2] *= 0.94
            q[3] = q[3] * 0.94 + q[8] * s
            q[4] -= s
            if q[4] > 0:
                keep.append(q)
        self.particles = keep

        if self.ignited and not self.args.no_fireworks:
            if len(self.fireworks) < 7 and rng.random() < 0.08 * s:
                self._spawn_firework()
            if it >= getattr(self, "next_volley", 1e9):  # 주기적으로 한꺼번에 팡팡팡
                for _ in range(rng.randint(4, 7)):
                    self._spawn_firework(anywhere=True)
                self.next_volley = it + rng.uniform(18, 26)
        for fw in self.fireworks:
            fw.step(s)
        self.fireworks = [fw for fw in self.fireworks if fw.alive()]

        if len(self.shooting) < 3 and rng.random() < 0.025 * s:
            d = rng.choice((-1, 1))
            x = rng.uniform(0, W * 0.4) if d > 0 else rng.uniform(W * 0.6, W)
            col = rng.choice([(255, 140, 210), (160, 220, 255), (255, 220, 140), (255, 90, 190)])
            self.shooting.append([x, rng.uniform(0, max(1, gy * 0.3)), d * rng.uniform(1.6, 2.6),
                                  rng.uniform(0.25, 0.5), [], col])
        for sh in self.shooting:
            sh[4].append((sh[0], sh[1]))
            sh[4] = sh[4][-12:]
            sh[0] += sh[2] * s
            sh[1] += sh[3] * s
        self.shooting = [sh for sh in self.shooting if -15 < sh[0] < W + 15 and sh[1] < gy * 0.6]

        # 홀로그램 글리치
        if self.glitch:
            self.glitch[3] -= 1
            if self.glitch[3] <= 0:
                self.glitch = None
        elif self.ignited and rng.random() < 0.025 * s:
            y0 = rng.randrange(self.tree_top, self.tree_bottom + 1)
            self.glitch = [y0, rng.randint(1, 3), rng.choice((-4, -3, -2, 2, 3, 4)), rng.randint(2, 4)]

    def _spawn_firework(self, anywhere=False):
        rng = self.rng
        zones = []
        for a, b in ((2, self.cx - self.Rmax - 4), (self.cx + self.Rmax + 4, self.W - 3)):
            if b - a >= 6:
                zones.append((a, b))
        if anywhere or not zones or rng.random() < 0.3:
            a, b = 2, self.W - 3  # 트리 뒤 하늘에서도 터짐
        else:
            a, b = rng.choice(zones)
        self.fireworks.append(Firework(rng, rng.uniform(a, b), self.ground_y - 1,
                                       rng.uniform(2, max(3, self.ground_y * 0.45))))

    # ---------------- 그리기 ----------------
    def render(self, t):
        W, H = self.W, self.H
        rng = self.rng
        gy, cx = self.ground_y, self.cx
        fancy = self.fancy
        it = t - self.t0
        rot = self._rot(it)
        mode = LIGHT_MODES[int(max(0.0, it - BUILD_END) / MODE_SECONDS) % len(LIGHT_MODES)]
        p_build, scan = self._build_state(it)
        ign = smooth((it - self.ignite_t) / 1.5) if self.ignited else 0.0

        ch = [[" "] * W for _ in range(H)]
        fg = [[WHITE] * W for _ in range(H)]
        bg = [[self.sky[y]] * W for y in range(H)]

        def put(x, y, c, col):
            if 0 <= x < W and 0 <= y < H:
                ch[y][x] = c
                fg[y][x] = col

        # ===== 하늘 =====
        if fancy:
            if not self.args.no_aurora:
                rows = max(1, int(gy * 0.55))
                w1 = [max(0.0, math.sin(x * 0.045 + t * 0.35 + math.sin(x * 0.017 - t * 0.21) * 2.2)) for x in range(W)]
                for y in range(rows):
                    fade = (1 - y / rows) ** 1.5
                    row = bg[y]
                    ph = t * 0.27 - y * 0.35
                    for x in range(W):
                        a = w1[x] * fade * 0.55
                        b = math.sin(x * 0.03 - ph)
                        b = b * fade * 0.45 if b > 0 else 0.0  # 핑크/보라 오로라
                        if a > 0.02 or b > 0.02:
                            base = row[x]
                            row[x] = quant((_c(base[0] + 120 * b), _c(base[1] + 95 * a + 10 * b),
                                            _c(base[2] + 45 * a + 80 * b)))
            if ign > 0:  # 별에서 뻗어 나가는 회전 광선
                sy, rad = self.star_y, min(48.0, W * 0.3)
                for y in range(0, min(H, self.tree_top + int(self.tree_h * 0.6))):
                    dyu = (y - sy) * 2.0
                    row = bg[y]
                    for x in range(max(0, int(cx - rad)), min(W, int(cx + rad) + 1)):
                        dxu = x - cx
                        d = math.hypot(dxu, dyu)
                        if d >= rad or d < 1:
                            continue
                        f = 1 - d / rad
                        ang = math.atan2(dyu, dxu)
                        ray = math.cos(9 * ang - t * 0.8)
                        k = ((ray ** 8 if ray > 0 else 0.0) * 0.6 + f * f * 0.4) * f * ign
                        if k > 0.015:
                            # 금빛 광선과 핑크 광선이 번갈아 회전
                            pk = 0.5 + 0.5 * math.sin(4.5 * ang - t * 0.4)
                            row[x] = quant(add(row[x], mix((140, 100, 25), (150, 30, 100), pk), k))
            if self.flash:
                k = self.flash / 5.0 * 0.6
                for y in range(H):
                    bg[y] = [quant(add(c, (90, 80, 60), k)) for c in bg[y]]

        for (x, y, ph, sp, c, tint, big) in self.stars:
            v = 0.5 + 0.5 * math.sin(t * sp + ph)
            v = v * v * v
            if big:  # 큰 별: 밝아질 때 십자 모양으로 번쩍
                col = mix(tint, WHITE, v * 0.6)
                if v > 0.55:
                    arm = scale(tint, v)
                    put(x - 1, y, "-", arm)
                    put(x + 1, y, "-", arm)
                    put(x, y - 1, "|" if v > 0.8 else "'", arm)
                    put(x, y + 1, "|" if v > 0.8 else ".", arm)
                    if v > 0.85:
                        put(x - 2, y, "-", scale(tint, 0.5))
                        put(x + 2, y, "-", scale(tint, 0.5))
                    if fancy:
                        bg[y][x] = quant(add(bg[y][x], tint, 0.25 * v))
                put(x, y, "*" if v > 0.4 else "+", scale(col, 0.35 + 0.65 * v))
            else:
                put(x, y, c, scale(tint, 0.15 + 0.85 * v))

        for sh in self.shooting:
            n = len(sh[4])
            for i, (tx, ty) in enumerate(sh[4]):
                k = (i + 1) / n
                put(int(tx), int(ty), "-" if k < 0.7 else "=", scale(sh[5], k))
                if rng.random() < 0.15:  # 떨어지는 불티
                    put(int(tx), int(ty) + 1, ".", scale(sh[5], k * 0.7))
            put(int(sh[0]), int(sh[1]), "*", WHITE)
            if fancy and 0 <= int(sh[1]) < H and 0 <= int(sh[0]) < W:
                bg[int(sh[1])][int(sh[0])] = quant(scale(sh[5], 0.5))

        for fw in self.fireworks:
            if not fw.exploded:
                for i, (tx, ty) in enumerate(fw.trail):
                    put(int(tx), int(ty), "|" if i > 2 else ".", scale((255, 200, 120), 0.3 + 0.15 * i))
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
                if fancy and f > 0.6 and 0 <= int(q[1]) < H and 0 <= int(q[0]) < W:
                    bg[int(q[1])][int(q[0])] = quant(add(bg[int(q[1])][int(q[0])], col, 0.18))
                put(int(q[7]), int(q[8]), ".", scale(col, 0.45))
                put(int(q[0]), int(q[1]), c, col)

        for f in self.snow:
            if not f[6]:
                put(int(f[0]), int(f[1]), f[4], scale((215, 228, 255), f[5]))

        # 하늘만 그려진 상태를 저장 (홀로그램 생성 연출에 사용)
        snap = [(ch[y][:], fg[y][:], bg[y][:]) for y in range(self.obj_top, gy)]

        # ===== 트리 (회전하는 3D 원뿔) =====
        top, th = self.tree_top, self.tree_h
        tree_bg = (24, 100, 42)  # 꽉 찬 잎 덩어리 색
        spans = {}
        for r in range(th):
            y = top + r
            row = self.rows[r]
            R = row.R
            wob = 0.03 + 0.07 * row.pos  # 층 아래쪽 가지 끝일수록 더 들쭉날쭉
            wl = R * (1 + wob * math.sin(7 * (rot - HALF_PI) + r * 0.3))  # 회전하는 가지 끝 실루엣
            wr = R * (1 + wob * math.sin(7 * (rot + HALF_PI) + r * 0.3))
            tierb = 0.68 + 0.32 * row.pos ** 0.7
            U, tex = row.U, row.tex
            xl = max(0, int(round(cx - wl)))
            xr = min(W - 1, int(round(cx + wr)))
            spans[y] = (xl, xr)
            chr_, fgr, bgr = ch[y], fg[y], bg[y]
            shim_t = t * 3 + r * 0.5
            for x in range(xl, xr + 1):
                d = x - cx
                dxn = d / (wl if d < 0 else wr)
                if dxn > 1:
                    dxn = 1.0
                elif dxn < -1:
                    dxn = -1.0
                a = math.asin(dxn)
                phi = a + rot
                c, base, rr = tex[int((phi % TAU) / TAU * U) % U]
                if x == xl:
                    c = "/"
                elif x == xr:
                    c = "\\"
                elif rr < abs(dxn) * 0.45 and c not in "*+":  # 옆으로 갈수록 바깥으로 처진 가지
                    c = "/" if d < 0 else "\\"
                diff = math.cos(a - LIGHT_DIR)
                # 가지 뭉치(클럼프) 명암: 표면에 붙어서 같이 회전
                clump = 0.8 + 0.2 * math.sin(phi * 11 + r * 1.7) * math.sin(phi * 5 - r * 0.9)
                b = (0.18 + 0.82 * (diff if diff > 0 else 0.0)) * tierb * clump * (0.9 + 0.1 * math.sin(shim_t + phi * 5))
                col = (_c(base[0] * (b + 0.3)), _c(base[1] * (b + 0.3)), _c(base[2] * (b + 0.3)))
                if dxn > 0.55:  # 오른쪽 뒤에서 비치는 푸른 림 라이트
                    rim = (dxn - 0.55) / 0.45 * 0.8
                    col = (_c(col[0] + 30 * rim), _c(col[1] + 90 * rim), _c(col[2] + 150 * rim))
                if rng.random() < 0.003:
                    c, col = "*", (235, 255, 240)
                chr_[x] = c
                fgr[x] = col
                if fancy:
                    bgr[x] = quant(scale(tree_bg, 0.3 + 1.0 * b), 4)
                elif b > 0.45:
                    bgr[x] = (0, 50, 0)

        def project(r, phi):
            rel = phi - rot
            return math.cos(rel), math.sin(rel), rel

        # 반짝이 줄 (나선)
        for pts, base, k in self.tinsels:
            for i, (r, phi) in enumerate(pts):
                c, s_, rel = project(r, phi)
                if c < 0.08:
                    continue
                R = self.rows[r].R
                x = int(round(cx + s_ * R * 0.97))
                slope = c * R * k
                sym = "~" if abs(slope) > 1.8 else ("\\" if slope > 0 else "/")
                lam = max(0.0, math.cos(rel - LIGHT_DIR))
                v = (0.3 + 0.7 * lam) * (0.55 + 0.45 * math.sin(i * 0.45 - t * 9)) * (0.4 + 0.6 * c)
                col = scale(base, 0.35 + v)
                if v > 0.9:
                    col = WHITE
                put(x, top + r, sym, col)

        # 전구 줄 (나선)
        hue_t = t * 0.15
        pulse = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(t * 5))
        for string in self.lightstrings:
            for (r, phi, idx, pc, ph, spd) in string:
                c, s_, rel = project(r, phi)
                if c < 0.12:
                    continue
                y = top + r
                x = int(round(cx + s_ * self.rows[r].R * 0.95))
                sym = "*"
                if mode == "twinkle":
                    col = scale(pc, 0.15 + 0.85 * max(0.0, math.sin(t * spd * 3 + ph)))
                elif mode == "rainbow":
                    col = hsv(idx * 0.04 - t * 0.7, 0.9, 1.0)
                elif mode == "chase":
                    col = pc if (idx - int(t * 14)) % 5 < 2 else scale(pc, 0.15)
                elif mode == "pulse":
                    col = hsv(hue_t + r * 0.01, 0.85, pulse)
                elif mode == "pink":  # 온통 핑크로 반짝반짝
                    tw_ = max(0.0, math.sin(t * spd * 4 + ph))
                    col = mix(PINKS[idx % len(PINKS)], WHITE, tw_ ** 6 * 0.7)
                    col = scale(col, 0.3 + 0.7 * tw_)
                elif mode == "candy":  # 핑크/화이트 번갈아 흐름
                    col = PINK if (idx + int(t * 8)) % 2 else (255, 240, 250)
                    if (idx + int(t * 8)) % 6 == 0:
                        col = HOT_PINK
                else:
                    if rng.random() < 0.15:
                        col, sym = WHITE, "+"
                    else:
                        col = (130, 110, 70)
                col = scale(col, 0.45 + 0.55 * c)
                put(x, y, sym, col)
                if fancy and 0 <= x < W and max(col) > 150:
                    bg[y][x] = quant(scale(col, 0.33))

        # 오너먼트
        for (r, phi, pc, kind, ph) in self.ornaments:
            c, s_, rel = project(r, phi)
            if c < 0.25:
                continue
            y = top + r
            x = int(round(cx + s_ * self.rows[r].R * 0.9))
            lam = max(0.0, math.cos(rel - LIGHT_DIR))
            col = scale(pc, 0.35 + 0.65 * lam * (0.6 + 0.4 * c))
            glint = lam > 0.8 and math.sin(t * 2 + ph) > 0.6
            core = mix(col, WHITE, 0.65) if glint else col
            if kind == "big" and c > 0.5:
                put(x - 1, y, "(", scale(col, 0.8))
                put(x, y, "@" if glint else "O", core)
                put(x + 1, y, ")", scale(col, 0.6))
                if fancy and 0 <= x < W:
                    bg[y][x] = quant(scale(col, 0.35))
            elif kind == "heart":  # 핑크 하트 <3
                beat = 0.75 + 0.25 * max(0.0, math.sin(t * 6 + ph)) ** 4
                hc = mix(scale(pc, beat), WHITE, 0.4) if glint else scale(pc, beat)
                put(x, y, "<", hc)
                put(x + 1, y, "3", hc)
                if fancy and 0 <= x < W - 1:
                    bg[y][x] = bg[y][x + 1] = quant(scale(pc, 0.3 * beat))
            elif kind == "cane":  # 지팡이 사탕: 빨강/흰색이 번갈아
                put(x, y, "J", col if int(t * 3 + ph) % 2 else scale(WHITE, 0.4 + 0.6 * lam))
            elif kind == "bow":  # 핑크 리본
                if c > 0.5:
                    put(x - 1, y, ">", col)
                    put(x, y, "o", core)
                    put(x + 1, y, "<", col)
                else:
                    put(x, y, "&", col)
            elif kind == "starorn":  # 반짝이는 작은 별
                sv = 0.5 + 0.5 * math.sin(t * 5 + ph)
                put(x, y, "*" if sv > 0.5 else "+", mix(col, WHITE, sv * 0.6))
            else:
                put(x, y, "@" if glint else "o", core)

        # 꼭대기 별 (3D 회전)
        sy, Ro = self.star_y, self.Ro
        rs = rot * 1.3 + 0.3
        cosr = math.cos(rs)
        fx = cosr if abs(cosr) > 0.1 else math.copysign(0.1, cosr)
        lit = 0.45 + 0.55 * ign
        face = 1.0 if cosr > 0 else 0.72
        sparkle_v = 0.9 + 0.1 * math.sin(t * 6)
        for y in range(max(0, sy - Ro // 2 - 1), min(H, sy + int(0.45 * Ro) + 2)):
            v = (y - sy) * 2.0
            for x in range(max(0, cx - Ro - 1), min(W, cx + Ro + 2)):
                u = (x - cx) / fx
                if not in_poly(u, v, self.star_poly):
                    continue
                dist = math.hypot(u, v) / Ro
                base = mix(GOLD, (255, 250, 225), max(0.0, 1 - dist) ** 1.5)
                if cosr < 0:  # 별 뒷면은 핑크빛
                    base = mix(base, (255, 90, 180), 0.55)
                elif dist > 0.7:  # 앞면 테두리에 핑크 광택
                    base = mix(base, (255, 120, 200), (dist - 0.7) / 0.3 * 0.5)
                shade = 0.8 + 0.2 * (-(x - cx) / (Ro + 1)) * (1 if cosr > 0 else -1)
                col = scale(base, lit * face * shade * sparkle_v)
                bg[y][x] = col
                ch[y][x] = " "
        put(cx, sy, "*", WHITE if self.ignited else (200, 200, 200))
        if self.ignited:
            for _ in range(18):
                a = rng.uniform(0, TAU)
                d = rng.uniform(Ro + 1, Ro * 2.6)
                px = int(round(cx + math.cos(a) * d))
                py = int(round(sy + math.sin(a) * d * 0.45))
                if 0 <= py < top and 0 <= px < W and ch[py][px] == " ":
                    put(px, py, rng.choice(".+'*`"), mix(rng.choice((GOLD, PINK, HOT_PINK, GOLD)), WHITE, rng.random()))

        # 기둥 (원기둥 음영)
        tw = self.trunk_hw
        for y in range(gy - self.trunk_h, gy):
            for x in range(cx - tw, cx + tw + 1):
                if not 0 <= x < W:
                    continue
                a = math.asin(max(-1.0, min(1.0, (x - cx) / (tw + 0.5))))
                b = 0.25 + 0.75 * max(0.0, math.cos(a - LIGHT_DIR))
                bg[y][x] = scale((115, 65, 28), b)
                put(x, y, "|:|!"[int((a + rot) * (tw + 1)) % 4], scale((70, 38, 14), 0.6 + b))

        # 선물 상자 (입체 상자)
        for (x0, w, bh, box, ribbon) in self.gifts:
            mid = x0 + w // 2
            rib = scale(ribbon, 0.85 + 0.15 * math.sin(t * 3 + x0))
            for i in range(bh):
                y = gy - bh + i
                for x in range(x0, x0 + w + 1):
                    if not 0 <= x < W:
                        continue
                    if x == x0 + w:  # 옆면
                        bg[y][x] = scale(box, 0.45)
                        put(x, y, "|" if i == bh // 2 else " ", scale(rib, 0.6))
                        continue
                    bg[y][x] = box if x < mid else scale(box, 0.82)
                    if i == bh // 2:
                        put(x, y, "+" if x == mid else "=", rib)
                    elif x == mid:
                        put(x, y, "|", rib)
                    else:
                        put(x, y, " ", rib)
            ly = gy - bh - 1  # 뚜껑 윗면
            for x in range(x0 + 1, x0 + w + 1):
                if 0 <= x < W and 0 <= ly < H:
                    bg[ly][x] = mix(box, WHITE, 0.25)
                    put(x, ly, "_", scale(box, 0.7))
            for j, cc in enumerate(">o<"):
                put(mid + j, ly, cc, rib)

        # ===== 홀로그램 생성 / 스윕 / 글리치 =====
        obj_x0 = max(0, int(cx - self.Rmax - 8))
        obj_x1 = min(W, int(cx + self.Rmax + 9))
        sweep = None
        if p_build >= 1:
            since = it - BUILD_END - 2.0
            if since > 0 and since % SWEEP_EVERY < 1.4:
                q = smooth((since % SWEEP_EVERY) / 1.4)
                sweep = gy - q * (gy - self.obj_top + 3)
        for y in range(self.obj_top, gy):
            sch, sfg, sbg = snap[y - self.obj_top]
            chr_, fgr, bgr = ch[y], fg[y], bg[y]
            if p_build < 1:
                d = y - scan
                if d < 0:  # 아직 안 만들어진 줄 -> 회전하는 와이어프레임
                    ch[y], fg[y], bg[y] = sch, sfg, sbg
                    self._wireframe(y, rot, t, ch, fg, bg, put)
                    continue
                if d < 1:
                    self._scanline(y, obj_x0, obj_x1, t, ch, fg, bg)
                    continue
                k = (d - 1) / 7.0
            elif sweep is not None and 0 <= y - sweep < 6:
                d = y - sweep
                if d < 1:
                    self._scanline(y, obj_x0, obj_x1, t, ch, fg, bg)
                    continue
                k = 0.35 + 0.65 * (d - 1) / 5.0
            else:
                k = 1.0
            if k < 1.0:
                for x in range(obj_x0, obj_x1):
                    if chr_[x] == sch[x] and bgr[x] == sbg[x]:
                        continue
                    if rng.random() < (1 - k) * 0.4:
                        chr_[x] = rng.choice(GLITCH)
                    fgr[x] = mix(HOLO, fgr[x], k)
                    if fancy:
                        bgr[x] = mix(bgr[x], (0, 70, 90), (1 - k) * 0.6)
                if k < 0.4 and rng.random() < 0.35:
                    off = rng.choice((-1, 1))
                    for arr in (chr_, fgr, bgr):
                        seg = arr[obj_x0:obj_x1]
                        arr[obj_x0:obj_x1] = seg[-off:] + seg[:-off]
        if self.glitch:
            y0, h, off, _ = self.glitch
            for y in range(y0, min(gy, y0 + h)):
                span = spans.get(y)
                if not span:
                    continue
                a, b = max(0, span[0] - 5), min(W, span[1] + 6)
                for arr in (ch[y], fg[y], bg[y]):
                    seg = arr[a:b]
                    arr[a:b] = seg[-off:] + seg[:-off]
                tint = (255, 60, 220) if off > 0 else HOLO
                for x in range(a, b):
                    if ch[y][x] != " ":
                        fg[y][x] = mix(fg[y][x], tint, 0.55)

        # ===== 홀로그램 발판 + 눈 덮인 땅 =====
        Rb = self.rows[-1].R
        snow_a, snow_b = (205, 215, 240), (120, 130, 170)
        pad_pulse = 1.0 if p_build < 1 else 0.55 + 0.25 * math.sin(it * 4)
        for x in range(W):
            bg[gy][x] = snow_a
            bg[gy + 1][x] = snow_b if fancy else (95, 95, 135)
            dx = abs(x - cx)
            if dx <= Rb + 6:
                # 핑크/하늘색 네온이 번갈아 흐르는 홀로그램 발판
                seg_pink = ((x - int(it * 25)) // 6) % 2 == 0
                neon = PINK if seg_pink else HOLO
                bg[gy][x] = quant(mix((40, 20, 60), scale(neon, 0.6), pad_pulse * 0.4 * (1 - dx / (Rb + 7))))
                put(x, gy, "=" if (x - int(it * 25)) % 5 else "-", scale(neon, 0.5 + 0.5 * pad_pulse))
                if dx <= Rb + 2:
                    bg[gy + 1][x] = quant(mix(snow_b, (70, 30, 80), 0.6)) if fancy else (60, 0, 80)
                    put(x, gy + 1, "-" if (x + int(it * 18)) % 3 else ".",
                        scale(HOLO if seg_pink else PINK, 0.35 + 0.35 * pad_pulse))
                continue
            sp = math.sin(x * 12.9898 + 78.233) * 43758.5453 % 1.0
            if sp > 0.82:
                v = 0.5 + 0.5 * math.sin(t * 3 + sp * 50)
                put(x, gy, "*" if v > 0.85 else ".", mix((150, 165, 210), WHITE, v))
            elif sp < 0.12:
                put(x, gy + 1, ".", (200, 210, 240))

        # ===== 파티클 (생성 불꽃, 점화 폭발) =====
        for q in self.particles:
            f = q[4] / q[5]
            c = "@" if f > 0.8 else "*" if f > 0.55 else "+" if f > 0.3 else "."
            put(int(q[0]), int(q[1]), c, hsv(q[6], q[7] * (1.2 - f), 0.4 + 0.6 * f))

        # 점화 충격파 링
        if self.ignited and 0 <= it - self.ignite_t < 0.9:
            k = (it - self.ignite_t) / 0.9
            rad = 4 + k * max(W, H * 2) * 0.55
            fade = 1 - k * 0.7
            for i in range(200):
                a = i / 200 * TAU
                col = scale(mix(WHITE, GOLD if i % 2 else HOT_PINK, k), fade)
                put(int(round(cx + math.cos(a) * rad)), int(round(self.star_y + math.sin(a) * rad * 0.5)),
                    "*" if i % 2 else "+", col)
                r2 = rad * 0.7  # 안쪽 핑크 링
                put(int(round(cx + math.cos(a) * r2)), int(round(self.star_y + math.sin(a) * r2 * 0.5)),
                    ".", scale(PINK, fade))

        # 떠오르는 하트
        for hx, hy, _, ph, life, mlife, hc in self.hearts:
            f = life / mlife
            v = min(1.0, f * 2.5) * (0.75 + 0.25 * math.sin(t * 6 + ph))
            col = scale(hc, v)
            xi, yi = int(hx), int(hy)
            put(xi, yi, "<", col)
            put(xi + 1, yi, "3", col)
            if fancy and 0 <= yi < H and 0 <= xi < W - 1:
                bg[yi][xi] = bg[yi][xi + 1] = quant(add(bg[yi][xi], hc, 0.25 * v))

        # 앞쪽 눈 + 반짝이 색종이
        for f in self.snow:
            if f[6]:
                xi, yi = int(f[0]), int(f[1])
                if 0 <= yi < gy and 0 <= xi < W and not (yi < self.tree_top and abs(xi - cx) <= Ro):
                    put(xi, yi, f[4], scale((235, 242, 255), f[5]))
        for f in self.confetti:
            xi, yi = int(f[0]), int(f[1])
            if 0 <= yi < gy and not (yi < self.tree_top and abs(xi - cx) <= Ro):
                v = 0.5 + 0.5 * math.sin(t * f[6] + f[3])
                put(xi, yi, f[4] if v > 0.3 else ".", mix(scale(f[5], 0.35 + 0.65 * v), WHITE, v ** 8 * 0.8))

        self._draw_banner(t, it, p_build, ch, fg, bg, put)
        return ch, fg, bg

    def _wireframe(self, y, rot, t, ch, fg, bg, put):
        r = y - self.tree_top
        if not 0 <= r < self.tree_h:
            return
        cx = self.cx
        R = self.rows[r].R
        flick = 0.7 + 0.3 * math.sin(t * 40 + y)
        if self.fancy:
            for x in range(max(0, int(cx - R)), min(self.W, int(cx + R) + 1)):
                bg[y][x] = mix(bg[y][x], (0, 30, 42), 0.7)
        for k in range(14):
            rel = k * TAU / 14 - rot
            c = math.cos(rel)
            x = int(round(cx + math.sin(rel) * R))
            if c > 0:
                put(x, y, ":", scale(HOLO, (0.35 + 0.6 * c) * flick))
            elif 0 <= x < self.W and ch[y][x] == " ":
                put(x, y, ".", scale(HOLO_DIM, 0.6))
        if r % 4 == 0:
            for x in range(int(cx - R), int(cx + R) + 1):
                if (x + int(t * 20)) % 2 == 0:
                    put(x, y, "-", scale(HOLO, 0.4 * flick))
        put(int(round(cx - R)), y, "/", scale(HOLO, flick))
        put(int(round(cx + R)), y, "\\", scale(HOLO, flick))

    def _scanline(self, y, x0, x1, t, ch, fg, bg):
        for x in range(x0, x1):
            ch[y][x] = "=" if (x + int(t * 60)) % 3 else "#"
            fg[y][x] = mix(HOLO, WHITE, 0.5 + 0.5 * math.sin(x * 0.7 + t * 30))
            if self.fancy:
                bg[y][x] = (0, 105, 130)

    def _draw_banner(self, t, it, p_build, ch, fg, bg, put):
        W = self.W
        rng = self.rng
        if p_build < 1:  # 생성 중 진행률 표시
            msg = "[ HOLOGRAM ]  projecting tree ...  %3d%%" % int(p_build * 100)
            x0 = (W - len(msg)) // 2
            for i, c in enumerate(msg):
                if c != " ":
                    put(x0 + i, self.sub_y, c, scale(HOLO, 0.6 + 0.4 * math.sin(t * 20 + i)))
            return
        wipe = (it - BANNER_START) / 1.0
        if wipe <= 0:
            return
        if self.big:
            x0, width = self.banner_x0, self.banner_w
            edge = x0 + wipe * (width + 4)
            sc = self.banner_scale
            shadow = (28, 22, 48) if self.fancy else (40, 40, 60)
            offs = [(1, 1)] if sc == 1 else [(1, 1), (2, 1)]
            for (px, py) in self.banner_px:
                if px >= edge:
                    continue
                for (ox, oy) in offs:
                    if 0 <= px + ox < W and py + oy < self.H:
                        bg[py + oy][px + ox] = shadow
            hl = x0 - 20 + ((t * 45) % (width + 40))
            pink_mode = int(t / 8) % 2 == 1  # 8초마다 무지개 <-> 핑크 네온
            for (px, py) in self.banner_px:
                if px >= edge or not 0 <= px < W:
                    continue
                v = 0.82 + 0.18 * math.sin(t * 4 + px * 0.3 / sc + py)
                if pink_mode:
                    h = 0.875 + 0.08 * math.sin(px * 0.06 / sc - t * 1.6 + py * 0.3)
                    col = hsv(h, 0.55 + 0.3 * math.sin(px * 0.11 / sc + t * 2), v)
                else:
                    col = hsv(px * 0.012 / sc - t * 0.25, 0.78, v)
                dh = abs(px - hl)
                if dh < 4:
                    col = mix(col, WHITE, (1 - dh / 4) * 0.75)
                bg[py][px] = quant(col, 4)
                if rng.random() < 0.02:
                    put(px, py, rng.choice("*+"), WHITE)
                else:
                    ch[py][px] = " "
            if wipe < 1:
                ex = int(edge)
                for py in range(self.banner_y - 1, self.banner_y + 6):
                    put(ex, py, "|", HOLO)
                    if self.fancy and 0 <= ex < W:
                        bg[py][ex] = (0, 110, 140)
        else:
            text = "* * *   M E R R Y   C H R I S T M A S   * * *"
            if len(text) > W - 2:
                text = "* MERRY CHRISTMAS *"
            x0 = (W - len(text)) // 2
            n = int(wipe * len(text))
            for i, c in enumerate(text[:n]):
                if c != " ":
                    put(x0 + i, self.banner_y, c, hsv(i * 0.035 - t * 0.4, 0.8, 1.0))

        n = int((it - BANNER_START - 0.8) * 45)
        if n <= 0:
            return
        msg = self.message[: max(0, W - 2)]
        x0 = (W - len(msg)) // 2
        for i, c in enumerate(msg[:n]):
            if c != " ":
                v = 0.55 + 0.45 * math.sin(i * 0.25 - t * 4)
                base = GOLD if (i // 12 + int(t * 1.5)) % 2 else PINK
                put(x0 + i, self.sub_y, c, mix(scale(base, 0.7), WHITE, v * v))
        if n < len(msg):
            put(x0 + n, self.sub_y, "_", HOLO)

    # ---------------- 문자열로 합치기 ----------------
    def frame(self, t, s, painter):
        if not self.ok:
            return self._too_small()
        self.update(t, s)
        ch, fg, bg = self.render(t)
        W, H = self.W, self.H
        out = ["\x1b[?2026h"]
        for y in range(H):
            out.append("\x1b[%d;1H" % (y + 1))
            lf = lb = None
            rc, rf, rb = ch[y], fg[y], bg[y]
            n = W if y < H - 1 else W - 1
            for x in range(n):
                b = rb[x]
                if b != lb:
                    out.append(painter.bg(b))
                    lb = b
                c = rc[x]
                if c != " ":
                    f = rf[x]
                    if f != lf:
                        out.append(painter.fg(f))
                        lf = f
                out.append(c)
        out.append("\x1b[0m\x1b[?2026l")
        return "".join(out)

    def _too_small(self):
        msg = "Please make the window bigger (min 40 x 18). Now: %d x %d" % (self.W, self.H)
        y = max(1, self.H // 2)
        x = max(1, (self.W - len(msg)) // 2 + 1)
        return "\x1b[0m\x1b[2J\x1b[%d;%dH\x1b[93m%s\x1b[0m" % (y, x, msg[: max(0, self.W - 1)])


# --------------------------------------------------------------------------
# 메인 루프
# --------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description="Rotating 3D hologram ASCII Christmas tree")
    ap.add_argument("--fps", type=float, default=24.0)
    ap.add_argument("--speed", type=float, default=1.0, help="rotation speed multiplier")
    ap.add_argument("--no-intro", action="store_true")
    ap.add_argument("--no-resize", action="store_true")
    ap.add_argument("--no-fireworks", action="store_true")
    ap.add_argument("--no-aurora", action="store_true")
    ap.add_argument("--256", dest="c256", action="store_true", help="force 256-color mode")
    ap.add_argument("--truecolor", action="store_true", help="force 24-bit color mode")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--frames", type=int, default=0, help=argparse.SUPPRESS)
    args = ap.parse_args()

    enable_windows_vt()
    truecolor = args.truecolor or (detect_truecolor() and not args.c256)
    painter = Painter(truecolor)
    fps = max(1.0, min(60.0, args.fps))
    step = 20.0 / fps

    out = sys.stdout

    def write(s):
        out.write(s)
        out.flush()

    orig = None
    if not args.no_resize and sys.stdout.isatty():
        orig = maximize_window(write)
    if os.name == "nt":
        os.system("title Merry Christmas")
    write("\x1b[?1049h\x1b[?25l\x1b[2J")
    try:
        size = None
        scene = None
        t0 = time.time()
        frames = 0
        while True:
            start = time.time()
            cur = shutil.get_terminal_size((100, 30))
            if cur != size:
                first = scene is None
                size = cur
                scene = Scene(cur.columns, cur.lines, args, truecolor, start - t0,
                              intro=(first or not scene.ok) and not args.no_intro)
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
            write("\x1b[9;0t\x1b[8;%d;%dt" % (orig.lines, orig.columns))  # 창 크기 원래대로
        print("Merry Christmas!  *  Happy New Year!")


if __name__ == "__main__":
    main()
