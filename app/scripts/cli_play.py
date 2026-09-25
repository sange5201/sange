#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cli_play.py — 无 UI 命令行可玩验证（Sprint 1 退出标准 proof）。

证明 core 逻辑包可脱离 Kivy 独立运行：直接用 Board + 文本指令开局/揭示/标记/判胜负。
用法：
    python scripts/cli_play.py                 # 默认 初级
    python scripts/cli_play.py --level 中级
指令（每行一条）：
    r <row> <col>   揭示
    f <row> <col>   循环标记（无→旗→?→无）
    c <row> <col>   chord（需已翻开数字格）
    p               打印棋盘
    q               退出
"""
import argparse
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import LEVELS
from core.board import Board


def _glyph(b, r, c):
    if b.is_revealed(r, c):
        if b.is_mine(r, c):
            return "*" if b.is_triggered == (r, c) else "X"
        n = b.number_at(r, c)
        return "." if n == 0 else str(n)
    if b.is_flagged(r, c):
        return "F"
    if b.is_marked(r, c):
        return "?"
    return "#"


def print_board(b):
    header = "   " + "".join(f"{c%10}" for c in range(b.cols))
    print(header)
    for r in range(b.rows):
        print(f"{r:2d} " + "".join(_glyph(b, r, c) for c in range(b.cols)))
    print(f"剩余雷(含未插旗): {b.remaining_mines()}  状态: "
          + ("胜" if b.win else "负" if b.game_over else "进行中"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default="初级", choices=[k for k in LEVELS if k != "自定义"])
    ap.add_argument("--seed", type=int, default=None, help="固定随机种子（可复现）")
    args = ap.parse_args()

    cfg = LEVELS[args.level]
    rng = random.Random(args.seed) if args.seed is not None else random
    b = Board(cfg["rows"], cfg["cols"], cfg["mines"], rng=rng)
    print(f"扫雷命令行 · 难度={args.level} ({b.rows}x{b.cols}, 雷{b.mines})")
    print("指令: r/f/c <row> <col> | p 打印 | q 退出")
    print_board(b)

    while not b.game_over:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        parts = line.split()
        cmd = parts[0].lower()
        if cmd == "q":
            break
        elif cmd == "p":
            print_board(b)
        elif cmd in ("r", "f", "c") and len(parts) == 3:
            r, c = int(parts[1]), int(parts[2])
            if not (0 <= r < b.rows and 0 <= c < b.cols):
                print("坐标越界"); continue
            if cmd == "r":
                res = b.first_click(r, c) if not b.mines_placed else b.reveal(r, c)
                print(f"reveal -> {res['result']}")
            elif cmd == "f":
                b.cycle_mark(r, c)
            elif cmd == "c":
                res = b.chord(r, c)
                print(f"chord -> {res['result']}")
            print_board(b)
        else:
            print("未知指令")
    print("对局结束。")


if __name__ == "__main__":
    main()
