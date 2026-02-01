"""
Formatting utilities for UI display
"""


def get_emotion_color(emotion: str) -> str:
    """Get color for emotion label"""
    colors = {
        "empathy": "#9c27b0",
        "enjoyable": "#4caf50",
        "confident": "#ffc107",
        "confused": "#ff9800",
        "anxious": "#f44336",
        "cautious": "#2196f3",
        "neutral": "#9e9e9e",
    }
    return colors.get(emotion.lower(), "#9e9e9e")


def get_emotion_badge_html(emotion: str, note: str = "") -> str:
    """Generate HTML for emotion badge"""
    color = get_emotion_color(emotion)
    note_html = f'<span style="color: #888; font-style: italic; margin-left: 10px;">{note}</span>' if note else ""

    return f"""
    <div style="display: flex; align-items: center; gap: 10px; margin: 10px 0;">
        <span style="
            background-color: {color};
            color: white;
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 14px;
        ">
            {emotion}
        </span>
        {note_html}
    </div>
    """


def format_reflection_display(reflection: dict) -> str:
    """Format reflection data for display"""
    if not reflection:
        return "まだ内省データがありません"

    parts = []

    # Emotion
    emotion = reflection.get("emotion", {})
    if emotion:
        label = emotion.get("label", "unknown")
        note = emotion.get("note", "")
        forcing = "⚠️ 無理な回答" if emotion.get("forcing") else ""
        parts.append(f"**感情**: {label} {forcing}")
        if note:
            parts.append(f"  _{note}_")

    # Background
    background = reflection.get("background", {})
    if background:
        statement = background.get("statement", "")
        source = background.get("source", "")
        confidence = background.get("confidence", "")
        if statement:
            parts.append(f"\n**背景**: {statement}")
            parts.append(f"  (ソース: {source}, 確信度: {confidence})")

    # User perspective
    user_perspective = reflection.get("user_perspective", {})
    if user_perspective:
        satisfaction = user_perspective.get("satisfaction", 0)
        impression = user_perspective.get("impression", "")
        would_improve = user_perspective.get("would_improve")

        parts.append(f"\n**ユーザー視点**: 満足度 {satisfaction}/5")
        if impression:
            parts.append(f"  _{impression}_")
        if would_improve:
            parts.append(f"  💡 改善点: {would_improve}")

    # Meta-insight
    meta_insight = reflection.get("meta_insight")
    if meta_insight:
        parts.append(f"\n**✨ メタ洞察**: {meta_insight}")

    return "\n".join(parts)


def format_insight_list(insights: list) -> str:
    """Format insights list for display"""
    if not insights:
        return "まだ気づきがありません"

    lines = []
    for i, entry in enumerate(reversed(insights[-10:]), 1):
        timestamp = entry.get("timestamp", "")[:10]
        insight = entry.get("insight", "")
        lines.append(f"{i}. [{timestamp}] {insight}")

    return "\n".join(lines)
