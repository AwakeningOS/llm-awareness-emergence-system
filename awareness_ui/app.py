"""
LLM Awareness Emergence System - Gradio App
Main application file (Gradio 6.x compatible)

Simplified UI:
- Chat with 6-axis analysis display
- Insight-only reflection
- User free-text feedback
"""

import gradio as gr
from pathlib import Path
import time
import logging
import json

from .config import load_config, save_config
from .api import AwarenessBackend
from .utils.formatters import format_insight_list

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Data directory
DATA_DIR = Path(__file__).parent.parent / "data"

# Custom CSS
CUSTOM_CSS = """
.chat-container { height: 500px !important; }
.axis-display {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-radius: 10px;
    padding: 15px;
    margin: 5px 0;
    font-family: monospace;
}
.axis-bar {
    display: flex;
    align-items: center;
    margin: 8px 0;
}
.axis-label {
    width: 100px;
    font-size: 0.85em;
}
.axis-value {
    width: 40px;
    text-align: center;
    font-weight: bold;
}
.insight-card {
    background: #2d2d44;
    border-radius: 8px;
    padding: 15px;
    margin: 10px 0;
    border-left: 4px solid #9c27b0;
}
.feedback-box {
    background: #1e3a5f;
    border-radius: 8px;
    padding: 15px;
    margin: 10px 0;
}
"""


def format_axes_display(axes: dict, title: str = "") -> str:
    """Format 6-axis data for display"""
    if not axes:
        return ""

    axis_info = [
        ("analysis_overview", "分析－俯瞰", "分析", "俯瞰"),
        ("individual_collective", "個　－集団", "個　", "集団"),
        ("empathy_responsibility", "共感－責任", "共感", "責任"),
        ("cooperation_independence", "協調－自立", "協調", "自立"),
        ("stability_transformation", "安定－変容", "安定", "変容"),
        ("divergence_convergence", "拡散－収束", "拡散", "収束"),
    ]

    lines = []
    if title:
        lines.append(f"**{title}**\n")

    for key, name, neg_label, pos_label in axis_info:
        value = axes.get(key, 0)
        # Create visual bar (20 chars wide)
        bar_pos = int((value + 5) / 10 * 20)
        bar = "░" * bar_pos + "█" + "░" * (20 - bar_pos)
        sign = "+" if value > 0 else ""
        lines.append(f"{neg_label} [{bar}] {pos_label} **{sign}{value}**")

    return "\n\n".join(lines)


def create_app():
    """Create and configure the Gradio app"""

    # Load configuration
    config = load_config()

    # Set default API token if not configured
    if not config.get("lm_studio", {}).get("api_token"):
        config["lm_studio"]["api_token"] = "sk-lm-ZoRidPPH:nmeekbPgWJTN49so7vLY"

    # Initialize backend
    backend = AwarenessBackend(config, data_dir=DATA_DIR)

    # ========== Event Handlers ==========

    def send_message(user_input, chat_history):
        """Handle message send"""
        if not user_input.strip():
            return chat_history, "", "", "", ""

        chat_history = chat_history or []

        # Get response
        response, metadata = backend.send_message(user_input)

        # Update chat history
        chat_history.append({"role": "user", "content": user_input})
        chat_history.append({"role": "assistant", "content": response})

        # Get 6-axis analysis
        analysis = backend.get_current_analysis()

        input_axes_text = ""
        response_axes_text = ""

        if analysis:
            input_axes = analysis.get("input_axes", {})
            response_axes = analysis.get("response_axes", {})
            input_axes_text = format_axes_display(input_axes, "入力の6軸分析")
            response_axes_text = format_axes_display(response_axes, "応答人格の6軸")

        # Wait briefly for background reflection
        time.sleep(0.3)

        # Get reflection insight
        reflection = backend.get_current_reflection()
        insight_text = ""
        if reflection:
            insight = reflection.get("insight", "")
            if insight:
                insight_text = f"💭 **気づき**\n\n{insight}"
        else:
            insight_text = "*振り返り処理中...*"

        return chat_history, "", input_axes_text, response_axes_text, insight_text

    def refresh_insight():
        """Refresh insight display"""
        analysis = backend.get_current_analysis()
        reflection = backend.get_current_reflection()

        input_axes_text = ""
        response_axes_text = ""
        insight_text = ""

        if analysis:
            input_axes = analysis.get("input_axes", {})
            response_axes = analysis.get("response_axes", {})
            input_axes_text = format_axes_display(input_axes, "入力の6軸分析")
            response_axes_text = format_axes_display(response_axes, "応答人格の6軸")

        if reflection:
            insight = reflection.get("insight", "")
            if insight:
                insight_text = f"💭 **気づき**\n\n{insight}"

        return input_axes_text, response_axes_text, insight_text

    def submit_feedback(feedback_text):
        """Submit user free-text feedback"""
        if not feedback_text.strip():
            return "フィードバックを入力してください", ""

        success = backend.submit_user_feedback(feedback_text)
        if success:
            return "✅ フィードバックを保存しました（夢見モードで処理されます）", ""
        return "❌ 保存に失敗しました", feedback_text

    def clear_chat():
        """Clear conversation"""
        backend.clear_conversation()
        return [], "", "", ""

    def shutdown_server():
        """Shutdown the Gradio server"""
        import os
        os._exit(0)

    def test_connection(host, port, token):
        """Test LM Studio connection"""
        from .api import LMStudioAPI
        api = LMStudioAPI(host=host, port=int(port), api_token=token)
        result = api.check_connection()

        if result["status"] == "connected":
            models = ", ".join(result.get("loaded_model_names", [])) or "なし (JITモード)"
            return f"✅ 接続成功\nロード済みモデル: {models}"
        else:
            return f"❌ 接続失敗: {result.get('error', 'Unknown error')}"

    def save_settings(host, port, token, dream_threshold):
        """Save settings"""
        config["lm_studio"]["host"] = host
        config["lm_studio"]["port"] = int(port)
        config["lm_studio"]["api_token"] = token
        config["dreaming"]["memory_threshold"] = int(dream_threshold)

        if save_config(config):
            return "設定を保存しました"
        return "設定の保存に失敗しました"

    def get_dashboard_data():
        """Get dashboard statistics"""
        try:
            stats = backend.get_insights_stats()
            storage = backend.get_storage_info()
            insights = backend.get_recent_insights(10)
            reflections = backend.get_recent_reflections(10)
            user_feedbacks = backend.get_recent_user_feedback(5)

            # Format insights list
            insights_text = ""
            if insights:
                for entry in insights:
                    insight = entry.get("insight", "")
                    timestamp = entry.get("timestamp", "")[:16]
                    if insight:
                        insights_text += f"**[{timestamp}]**\n{insight[:150]}...\n\n---\n\n"
            insights_text = insights_text or "まだ気づきがありません"

            # Format reflections (new format - insight only)
            reflections_text = ""
            for r in reflections:
                insight = r.get("insight", "")
                timestamp = r.get("timestamp", "")[:16]
                if insight:
                    reflections_text += f"**[{timestamp}]**\n{insight[:150]}...\n\n---\n\n"
            reflections_text = reflections_text or "まだ振り返りデータがありません"

            # Format user feedback
            feedback_text = ""
            for f in user_feedbacks:
                feedback = f.get("feedback", "")
                timestamp = f.get("timestamp", "")[:16]
                if feedback:
                    feedback_text += f"**[{timestamp}]**\n{feedback}\n\n---\n\n"
            feedback_text = feedback_text or "まだユーザーフィードバックがありません"

            # Storage info text
            storage_text = f"""**📁 データ保存場所**
`{storage.get('data_dir', 'N/A')}`

**📊 蓄積データ**
| 項目 | 件数 |
|------|------|
| ChromaDBメモリ | {storage.get('memory_count', 0)} |
| 6軸分析ログ | {storage.get('analysis_count', 0)} |
| 振り返りログ | {storage.get('reflection_count', 0)} |
| ユーザーFB | {storage.get('feedback_count', 0)} |
| 夢見気づき | {storage.get('insights_count', 0)} |

**💾 ストレージ使用量**
- ChromaDB: {storage.get('chromadb_size_mb', 0)} MB
- 人格軸データ: {storage.get('personality_size_mb', 0)} MB
- **合計: {storage.get('total_size_mb', 0)} MB**
"""

            return (
                stats.get("total_insights", 0),
                stats.get("dream_cycles", 0),
                stats.get("memory_count", 0),
                stats.get("total_reflections", 0),
                stats.get("total_user_feedbacks", 0),
                insights_text,
                reflections_text,
                feedback_text,
                storage_text
            )
        except Exception as e:
            logger.error(f"Dashboard data error: {e}")
            return (0, 0, 0, 0, 0, f"エラー: {e}", "", "", "")

    def get_dream_status():
        """Get dreaming status"""
        threshold = backend.check_dream_threshold()
        stats = backend.dreaming.get_stats()

        current = threshold.get("current_count", 0)
        max_threshold = threshold.get("threshold", 50)
        progress = min(100, int(current / max_threshold * 100))

        # Get pending user feedbacks
        feedbacks = backend.get_recent_user_feedback(5)
        feedback_preview = ""
        if feedbacks:
            feedback_preview = "\n\n**処理待ちのユーザーフィードバック:**\n"
            for f in feedbacks[:3]:
                feedback_preview += f"- {f.get('feedback', '')[:50]}...\n"

        status_text = f"""
**メモリ数**: {current} / {max_threshold}
**進捗**: {progress}%
**夢見可能**: {"はい" if threshold.get("should_dream") else "いいえ"}

**過去の夢見**:
- 実行回数: {stats.get("dream_cycles", 0)}
- アーカイブ済み: {stats.get("total_archived_memories", 0)} 件
- 最終実行: {stats.get("last_dream", "なし")}
{feedback_preview}
"""
        return status_text, progress

    def trigger_dream():
        """Trigger dreaming"""
        result = backend.trigger_dream()

        if result.get("status") == "completed":
            insights = "\n".join([f"- {i}" for i in result.get("insights", [])])
            return f"""
✅ **夢見完了**

処理したメモリ: {result.get("memories_processed", 0)}
使用したユーザーFB: {result.get("user_feedbacks_used", 0)}
生成した気づき: {result.get("insights_generated", 0)}
削除したメモリ: {result.get("memories_deleted", 0)}
所要時間: {result.get("duration_seconds", 0):.1f}秒

**得られた気づき**:
{insights}
"""
        else:
            return f"❌ 夢見失敗: {result.get('reason', result.get('error', 'Unknown'))}"

    # ========== Build UI ==========

    with gr.Blocks(title="LLM Awareness Emergence System") as app:

        gr.Markdown("# 🧠 LLM Awareness Emergence System")
        gr.Markdown("*6軸人格分析と気づきを可視化するAIチャットシステム*")

        with gr.Tabs():
            # ========== Tab 1: Chat ==========
            with gr.Tab("💬 チャット"):
                with gr.Row():
                    # Chat Panel (wider)
                    with gr.Column(scale=3):
                        chatbot = gr.Chatbot(
                            label="会話",
                            height=500,
                            show_label=False
                        )
                        with gr.Row():
                            msg_input = gr.Textbox(
                                placeholder="メッセージを入力...",
                                show_label=False,
                                scale=5
                            )
                            send_btn = gr.Button("送信", variant="primary", scale=1)

                        with gr.Row():
                            clear_btn = gr.Button("🗑️ 会話をクリア", size="sm")
                            shutdown_btn = gr.Button("🛑 サーバー終了", variant="stop", size="sm")

                    # Analysis Panel
                    with gr.Column(scale=2):
                        gr.Markdown("### 📊 6軸分析")

                        input_axes_display = gr.Markdown(
                            value="*会話を始めると入力の6軸分析が表示されます*"
                        )

                        response_axes_display = gr.Markdown(
                            value=""
                        )

                        gr.Markdown("---")
                        gr.Markdown("### 💭 振り返りの気づき")

                        insight_display = gr.Markdown(
                            value="*応答後に気づきが表示されます*"
                        )

                        refresh_btn = gr.Button("🔄 更新", size="sm")

                        gr.Markdown("---")
                        gr.Markdown("### 📝 フィードバック")
                        gr.Markdown("*この応答についてあなたの感想を自由に記入してください*")

                        feedback_input = gr.Textbox(
                            placeholder="例: もっと具体的な回答が欲しかった / 共感してくれて嬉しかった / etc...",
                            lines=3,
                            show_label=False
                        )
                        feedback_btn = gr.Button("フィードバック送信", size="sm")
                        feedback_status = gr.Markdown("")

                # Event bindings
                send_btn.click(
                    send_message,
                    inputs=[msg_input, chatbot],
                    outputs=[chatbot, msg_input, input_axes_display, response_axes_display, insight_display]
                )
                msg_input.submit(
                    send_message,
                    inputs=[msg_input, chatbot],
                    outputs=[chatbot, msg_input, input_axes_display, response_axes_display, insight_display]
                )
                clear_btn.click(
                    clear_chat,
                    outputs=[chatbot, input_axes_display, response_axes_display, insight_display]
                )
                refresh_btn.click(
                    refresh_insight,
                    outputs=[input_axes_display, response_axes_display, insight_display]
                )
                feedback_btn.click(
                    submit_feedback,
                    inputs=[feedback_input],
                    outputs=[feedback_status, feedback_input]
                )
                shutdown_btn.click(
                    shutdown_server,
                    inputs=[],
                    outputs=[]
                )

            # ========== Tab 2: Dashboard ==========
            with gr.Tab("📊 ダッシュボード"):
                refresh_dashboard_btn = gr.Button("🔄 データを更新", variant="primary")

                with gr.Row():
                    total_insights = gr.Number(label="夢見気づき", interactive=False)
                    dream_cycles = gr.Number(label="夢見サイクル", interactive=False)
                    memory_count = gr.Number(label="ChromaDBメモリ", interactive=False)
                    total_reflections = gr.Number(label="振り返り数", interactive=False)
                    total_feedbacks = gr.Number(label="ユーザーFB数", interactive=False)

                with gr.Row():
                    # 左カラム: ストレージ情報
                    with gr.Column(scale=1):
                        gr.Markdown("### 💾 蓄積データ情報")
                        storage_display = gr.Markdown("*更新ボタンを押してください*")

                    # 中央カラム: 気づき
                    with gr.Column(scale=1):
                        gr.Markdown("### 💡 最近の気づき (夢見)")
                        insights_display = gr.Markdown("")

                with gr.Row():
                    # 左カラム: 振り返り
                    with gr.Column(scale=1):
                        gr.Markdown("### 🔄 最近の振り返り")
                        reflections_display = gr.Markdown("")

                    # 右カラム: ユーザーFB
                    with gr.Column(scale=1):
                        gr.Markdown("### 📝 ユーザーフィードバック")
                        feedbacks_display = gr.Markdown("")

                refresh_dashboard_btn.click(
                    get_dashboard_data,
                    outputs=[total_insights, dream_cycles, memory_count,
                            total_reflections, total_feedbacks,
                            insights_display, reflections_display, feedbacks_display,
                            storage_display]
                )

            # ========== Tab 3: Dreaming ==========
            with gr.Tab("🌙 夢見モード"):
                gr.Markdown("### 夢見モード - 記憶の整理と気づきの生成")
                gr.Markdown("*ユーザーフィードバックもここで処理され、LLMの学習に反映されます*")

                with gr.Row():
                    with gr.Column():
                        dream_status = gr.Markdown("")
                        dream_progress = gr.Slider(
                            minimum=0, maximum=100,
                            label="メモリ蓄積",
                            interactive=False
                        )

                    with gr.Column():
                        dream_btn = gr.Button("🌙 夢見を開始", variant="primary", size="lg")
                        dream_result = gr.Markdown("")

                check_status_btn = gr.Button("ステータス確認", size="sm")

                check_status_btn.click(
                    get_dream_status,
                    outputs=[dream_status, dream_progress]
                )
                dream_btn.click(
                    trigger_dream,
                    outputs=[dream_result]
                )

            # ========== Tab 4: Settings ==========
            with gr.Tab("⚙️ 設定"):
                gr.Markdown("### LM Studio 接続設定")

                with gr.Row():
                    host_input = gr.Textbox(
                        label="ホスト",
                        value=config.get("lm_studio", {}).get("host", "localhost")
                    )
                    port_input = gr.Number(
                        label="ポート",
                        value=config.get("lm_studio", {}).get("port", 1234)
                    )

                token_input = gr.Textbox(
                    label="APIトークン",
                    value=config.get("lm_studio", {}).get("api_token", ""),
                    type="password"
                )

                with gr.Row():
                    test_btn = gr.Button("接続テスト")
                    connection_status = gr.Textbox(label="接続状態", interactive=False)

                gr.Markdown("---")
                gr.Markdown("### 機能設定")

                dream_threshold = gr.Number(
                    label="夢見トリガー閾値（メモリ数）",
                    value=config.get("dreaming", {}).get("memory_threshold", 50)
                )

                save_btn = gr.Button("設定を保存", variant="primary")
                save_status = gr.Textbox(label="", interactive=False)

                test_btn.click(
                    test_connection,
                    inputs=[host_input, port_input, token_input],
                    outputs=[connection_status]
                )
                save_btn.click(
                    save_settings,
                    inputs=[host_input, port_input, token_input, dream_threshold],
                    outputs=[save_status]
                )

        # Load initial dashboard data
        app.load(
            get_dashboard_data,
            outputs=[total_insights, dream_cycles, memory_count,
                    total_reflections, total_feedbacks,
                    insights_display, reflections_display, feedbacks_display,
                    storage_display]
        )

    return app


def main():
    """Main entry point"""
    app = create_app()
    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        inbrowser=True,
        css=CUSTOM_CSS
    )


if __name__ == "__main__":
    main()
