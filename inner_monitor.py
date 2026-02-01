"""
Inner Monitor - LLMの内面状態をリアルタイムで監視するツール
ターミナルから内面情報（感情、気づき、洞察）だけを抽出して表示
"""

import json
import time
import os
from pathlib import Path
from datetime import datetime
from collections import deque

# パス設定
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
THINKING_HABITS_FILE = DATA_DIR / "thinking_habits" / "integrated_reflections.jsonl"
SELF_REFLECTION_FILE = DATA_DIR / "self_reflection" / "reflections.jsonl"
AWARENESS_FILE = DATA_DIR / "awareness" / "awareness.jsonl"

# ANSI カラーコード
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # 感情に応じた色
    EMOTION_COLORS = {
        "empathy": "\033[38;5;141m",      # 紫 - 共感
        "共感": "\033[38;5;141m",
        "confident": "\033[38;5;226m",     # 黄 - 自信
        "自信": "\033[38;5;226m",
        "confused": "\033[38;5;208m",      # オレンジ - 混乱
        "混乱": "\033[38;5;208m",
        "anxious": "\033[38;5;196m",       # 赤 - 不安
        "不安": "\033[38;5;196m",
        "curious": "\033[38;5;51m",        # シアン - 好奇心
        "好奇心": "\033[38;5;51m",
        "楽しい": "\033[38;5;46m",         # 緑 - 楽しい
        "happy": "\033[38;5;46m",
        "enjoyable": "\033[38;5;46m",
        "慎重": "\033[38;5;250m",          # グレー - 慎重
        "cautious": "\033[38;5;250m",
        "neutral": "\033[38;5;255m",       # 白 - ニュートラル
        "default": "\033[38;5;255m",       # 白 - デフォルト
    }

    INSIGHT = "\033[38;5;220m"    # 金色 - 洞察
    META = "\033[38;5;213m"       # ピンク - メタ認知
    USER = "\033[38;5;117m"       # 水色 - ユーザー視点
    TIMESTAMP = "\033[38;5;240m"  # グレー - タイムスタンプ
    BORDER = "\033[38;5;238m"     # ダークグレー - 枠線


def get_emotion_color(emotion_label: str) -> str:
    """感情ラベルに応じた色を返す"""
    return Colors.EMOTION_COLORS.get(emotion_label, Colors.EMOTION_COLORS["default"])


def format_timestamp(ts_str: str) -> str:
    """タイムスタンプを短い形式に変換"""
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.strftime("%H:%M:%S")
    except:
        return ts_str[:8] if len(ts_str) >= 8 else ts_str


def truncate(text: str, max_len: int = 80) -> str:
    """テキストを指定長で切り詰める"""
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    if len(text) > max_len:
        return text[:max_len-3] + "..."
    return text


def display_entry(entry: dict, index: int = None, show_conversation: bool = True):
    """1エントリを整形して表示"""
    c = Colors

    timestamp = format_timestamp(entry.get("timestamp", ""))
    emotion = entry.get("emotion", {})
    emotion_label = emotion.get("label", "unknown")
    emotion_note = emotion.get("note", "")
    emotion_color = get_emotion_color(emotion_label)

    background = entry.get("background", {})
    bg_statement = background.get("statement", "")

    user_perspective = entry.get("user_perspective", {})
    user_impression = user_perspective.get("impression", "")
    satisfaction = user_perspective.get("satisfaction", "?")

    meta_insight = entry.get("meta_insight", "")

    user_input = entry.get("user_input", "")
    assistant_output = entry.get("assistant_output", "")

    # ヘッダー
    print(f"\n{c.BORDER}{'═' * 70}{c.RESET}")
    print(f"{c.TIMESTAMP}[{timestamp}]{c.RESET} {emotion_color}● {emotion_label}{c.RESET}")
    print(f"{c.BORDER}{'═' * 70}{c.RESET}")

    # 会話表示（表の部分）- 全文表示
    if show_conversation:
        print(f"\n  {c.BOLD}{c.USER}👤 User:{c.RESET}")
        for line in user_input.split('\n'):
            print(f"    {c.DIM}{line}{c.RESET}")

        print(f"\n  {c.BOLD}\033[38;5;156m🤖 Bot:{c.RESET}")
        for line in assistant_output.split('\n'):
            print(f"    \033[38;5;156m{line}{c.RESET}")

    # 内面情報（裏の部分）- 全文表示
    print(f"\n  {c.BORDER}--- Inner State ---{c.RESET}")

    # 感情
    print(f"  {c.BOLD}Emotion:{c.RESET} {emotion_color}{emotion_label}{c.RESET}")
    if emotion_note:
        print(f"    {c.DIM}{emotion_note}{c.RESET}")

    # 背景連想
    if bg_statement:
        print(f"  {c.BOLD}Background:{c.RESET}")
        print(f"    {c.DIM}{bg_statement}{c.RESET}")

    # ユーザー視点
    if user_impression:
        print(f"  {c.USER}{c.BOLD}User View:{c.RESET} {c.USER}(satisfaction: {satisfaction}/5){c.RESET}")
        print(f"    {c.DIM}{user_impression}{c.RESET}")

    # 改善提案
    would_improve = user_perspective.get("would_improve", "")
    if would_improve:
        print(f"  {c.BOLD}Would Improve:{c.RESET}")
        print(f"    {c.DIM}{would_improve}{c.RESET}")

    # メタ洞察
    if meta_insight:
        print(f"  {c.META}{c.BOLD}✨ Meta-Insight:{c.RESET}")
        print(f"    {c.INSIGHT}{meta_insight}{c.RESET}")


def read_jsonl_entries(file_path: Path, last_n: int = 10) -> list:
    """JSONLファイルから最新のエントリを読み込む"""
    entries = []
    if not file_path.exists():
        return entries

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for line in lines[-last_n:]:
            try:
                entries.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
    return entries


def get_file_mtime(file_path: Path) -> float:
    """ファイルの最終更新時刻を取得"""
    if file_path.exists():
        return file_path.stat().st_mtime
    return 0


def monitor_mode():
    """リアルタイム監視モード"""
    c = Colors
    print(f"\n{c.BOLD}{'=' * 70}{c.RESET}")
    print(f"{c.BOLD}  Inner Monitor - LLM Internal State Viewer{c.RESET}")
    print(f"{c.BOLD}{'=' * 70}{c.RESET}")
    print(f"{c.DIM}  Monitoring: {THINKING_HABITS_FILE}{c.RESET}")
    print(f"{c.DIM}  Press Ctrl+C to exit{c.RESET}")

    last_mtime = get_file_mtime(THINKING_HABITS_FILE)
    seen_entries = set()

    # 最初に最新の5件を表示
    entries = read_jsonl_entries(THINKING_HABITS_FILE, 5)
    for entry in entries:
        key = entry.get("timestamp", "") + entry.get("user_input", "")[:20]
        seen_entries.add(key)
        display_entry(entry)

    print(f"\n{c.DIM}--- Waiting for new entries... ---{c.RESET}")

    try:
        while True:
            time.sleep(2)  # 2秒ごとにチェック

            current_mtime = get_file_mtime(THINKING_HABITS_FILE)
            if current_mtime > last_mtime:
                last_mtime = current_mtime

                # 新しいエントリを取得
                entries = read_jsonl_entries(THINKING_HABITS_FILE, 10)
                for entry in entries:
                    key = entry.get("timestamp", "") + entry.get("user_input", "")[:20]
                    if key not in seen_entries:
                        seen_entries.add(key)
                        display_entry(entry)

    except KeyboardInterrupt:
        print(f"\n{c.DIM}Monitor stopped.{c.RESET}")


def history_mode(count: int = 20):
    """履歴表示モード"""
    c = Colors
    print(f"\n{c.BOLD}{'=' * 70}{c.RESET}")
    print(f"{c.BOLD}  Inner Monitor - Recent {count} Entries{c.RESET}")
    print(f"{c.BOLD}{'=' * 70}{c.RESET}")

    entries = read_jsonl_entries(THINKING_HABITS_FILE, count)

    if not entries:
        print(f"{c.DIM}No entries found.{c.RESET}")
        return

    for entry in entries:
        display_entry(entry)

    print(f"\n{c.BORDER}{'─' * 70}{c.RESET}")
    print(f"{c.DIM}Total: {len(entries)} entries{c.RESET}")


def stats_mode():
    """統計表示モード"""
    c = Colors
    entries = read_jsonl_entries(THINKING_HABITS_FILE, 1000)

    print(f"\n{c.BOLD}{'=' * 70}{c.RESET}")
    print(f"{c.BOLD}  Inner Monitor - Statistics{c.RESET}")
    print(f"{c.BOLD}{'=' * 70}{c.RESET}")

    # 感情の集計
    emotion_counts = {}
    satisfaction_sum = 0
    satisfaction_count = 0
    meta_insights = []

    for entry in entries:
        emotion = entry.get("emotion", {}).get("label", "unknown")
        emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

        sat = entry.get("user_perspective", {}).get("satisfaction")
        if sat is not None and isinstance(sat, (int, float)):
            satisfaction_sum += sat
            satisfaction_count += 1

        meta = entry.get("meta_insight", "")
        if meta:
            meta_insights.append(meta)

    # 表示
    print(f"\n{c.BOLD}Emotion Distribution:{c.RESET}")
    for emotion, count in sorted(emotion_counts.items(), key=lambda x: -x[1]):
        color = get_emotion_color(emotion)
        bar_len = min(count, 30)
        print(f"  {color}{emotion:15}{c.RESET} {'█' * bar_len} ({count})")

    if satisfaction_count > 0:
        avg_sat = satisfaction_sum / satisfaction_count
        print(f"\n{c.BOLD}Average Satisfaction:{c.RESET} {avg_sat:.2f}/5")

    print(f"\n{c.BOLD}Total Entries:{c.RESET} {len(entries)}")
    print(f"{c.BOLD}Meta-Insights:{c.RESET} {len(meta_insights)}")

    # 最新のメタ洞察を3件表示
    if meta_insights:
        print(f"\n{c.META}{c.BOLD}Recent Meta-Insights:{c.RESET}")
        for insight in meta_insights[-3:]:
            print(f"  {c.INSIGHT}• {truncate(insight, 65)}{c.RESET}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "history" or mode == "-h":
            count = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            history_mode(count)
        elif mode == "stats" or mode == "-s":
            stats_mode()
        elif mode == "help" or mode == "--help":
            print("""
Inner Monitor - LLM Internal State Viewer

Usage:
  python inner_monitor.py           # Real-time monitoring mode
  python inner_monitor.py history   # Show last 20 entries
  python inner_monitor.py history 50 # Show last 50 entries
  python inner_monitor.py stats     # Show statistics
  python inner_monitor.py help      # Show this help
""")
        else:
            monitor_mode()
    else:
        monitor_mode()
