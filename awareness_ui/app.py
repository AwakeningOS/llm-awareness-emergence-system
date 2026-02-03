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

# Import Moltbook Agent and Integrated Agent
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from engines.moltbook_agent import MoltbookAgent
from engines.integrated_agent import IntegratedAgent

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

    # API token should be configured in user_config.json
    # Get it from LM Studio > Settings > Developer

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
        """Get dashboard statistics - focused on Moltbook activity"""
        try:
            # Get Moltbook integrated memory count
            integrated_memory_path = DATA_DIR / "integrated_memory.jsonl"
            moltbook_memory_count = 0
            if integrated_memory_path.exists():
                with open(integrated_memory_path, "r", encoding="utf-8") as f:
                    moltbook_memory_count = sum(1 for _ in f)

            # Get activity log stats
            activity_path = DATA_DIR / "integrated_activity.jsonl"
            total_cycles = 0
            total_comments = 0
            total_replies = 0
            total_posts = 0
            recent_reflections = []

            if activity_path.exists():
                with open(activity_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            act = json.loads(line)
                            total_cycles += 1
                            details = act.get("details", {})
                            steps = details.get("steps", {})

                            # Count actions
                            execution = steps.get("execution", {})
                            for r in execution.get("results", []):
                                rtype = r.get("type")
                                if r.get("result", {}).get("success"):
                                    if rtype == "comment":
                                        total_comments += 1
                                    elif rtype == "reply":
                                        total_replies += 1
                                    elif rtype == "post":
                                        total_posts += 1

                            # Collect reflections
                            reflection = steps.get("reflection", {})
                            if reflection.get("insight"):
                                recent_reflections.append({
                                    "timestamp": act.get("timestamp", "")[:16],
                                    "insight": reflection.get("insight", "")
                                })
                        except:
                            pass

            # Get dream insights
            insights_path = DATA_DIR / "insights.jsonl"
            dream_insights = []
            dream_count = 0
            if insights_path.exists():
                with open(insights_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            dream_count += 1
                            dream_insights.append(entry)
                        except:
                            pass

            # Format recent reflections (last 5)
            reflections_text = ""
            for r in recent_reflections[-5:][::-1]:
                reflections_text += f"**[{r['timestamp']}]**\n{r['insight'][:200]}...\n\n---\n\n"
            reflections_text = reflections_text or "まだ振り返りがありません"

            # Format dream insights (last 5)
            insights_text = ""
            for entry in dream_insights[-5:][::-1]:
                insight = entry.get("insight", "")
                timestamp = entry.get("timestamp", "")[:16]
                if insight:
                    insights_text += f"**[{timestamp}]**\n{insight[:200]}...\n\n---\n\n"
            insights_text = insights_text or "まだ夢見気づきがありません"

            # Dream threshold - combined memory from all sources
            dream_threshold = 10
            try:
                combined_counts = backend.get_total_memory_count()
                combined_memory = combined_counts["total"]
            except Exception:
                combined_memory = moltbook_memory_count
            dream_progress = min(100, int(combined_memory / dream_threshold * 100))

            return (
                combined_memory,
                dream_threshold,
                dream_progress,
                total_cycles,
                total_comments,
                total_replies,
                total_posts,
                dream_count,
                reflections_text,
                insights_text
            )
        except Exception as e:
            logger.error(f"Dashboard data error: {e}")
            return (0, 10, 0, 0, 0, 0, 0, 0, f"エラー: {e}", "")

    def get_dream_status():
        """Get dreaming status (unified)"""
        threshold = backend.check_dream_threshold()
        stats = backend.dreaming.get_stats()

        current = threshold.get("current_count", 0)
        max_threshold = threshold.get("threshold", 10)
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
        """Trigger unified dreaming across all memory sources"""
        try:
            counts = backend.get_total_memory_count()
            total = counts["total"]

            if total == 0:
                return "❌ 夢見失敗: 蓄積メモリがありません（チャット・Moltbook両方とも空）"

            result = backend.dreaming.dream(memory_limit=10)

            if result.get("status") == "completed":
                insights = "\n".join([f"- {i}" for i in result.get("insights", [])])
                return f"""
✅ **統合夢見完了**

📊 ソース: ChromaDB {counts['chromadb']}件 + Moltbook {counts['moltbook']}件
処理したメモリ: {result.get("memories_processed", 0)}件
生成した気づき: {result.get("insights_generated", 0)}件
フィードバック処理: {result.get("user_feedbacks_used", 0)}件
所要時間: {result.get("duration_seconds", 0):.1f}秒

**得られた気づき**:
{insights}
"""
            elif result.get("status") == "skipped":
                return f"⏭️ 夢見スキップ: {result.get('reason', 'Unknown')}"
            else:
                return f"❌ 夢見失敗: {result.get('reason', result.get('error', 'Unknown'))}"
        except Exception as e:
            logger.error(f"Dream trigger error: {e}")
            return f"❌ 夢見失敗: {e}"

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

                gr.Markdown("### 🧠 メモリ蓄積状況")
                with gr.Row():
                    memory_count = gr.Number(label="📦 蓄積メモリ数", interactive=False)
                    dream_threshold = gr.Number(label="🎯 夢見閾値", interactive=False)
                    dream_progress = gr.Slider(
                        minimum=0, maximum=100,
                        label="夢見までの進捗 (%)",
                        interactive=False
                    )

                gr.Markdown("### 🦞 Moltbook活動統計")
                with gr.Row():
                    total_cycles = gr.Number(label="🔄 総サイクル数", interactive=False)
                    total_comments = gr.Number(label="💬 コメント数", interactive=False)
                    total_replies = gr.Number(label="📩 返信数", interactive=False)
                    total_posts = gr.Number(label="📝 投稿数", interactive=False)
                    dream_count = gr.Number(label="🌙 夢見回数", interactive=False)

                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 🔄 最近の振り返り（サイクルごと）")
                        reflections_display = gr.Markdown("*更新ボタンを押してください*")

                    with gr.Column(scale=1):
                        gr.Markdown("### 🌙 夢見で得た気づき")
                        insights_display = gr.Markdown("*更新ボタンを押してください*")

                refresh_dashboard_btn.click(
                    get_dashboard_data,
                    outputs=[memory_count, dream_threshold, dream_progress,
                            total_cycles, total_comments, total_replies, total_posts, dream_count,
                            reflections_display, insights_display]
                )

            # ========== Tab 3: Dreaming ==========
            with gr.Tab("🌙 夢見モード"):
                gr.Markdown("### 🌙 夢見モード - 手動で記憶整理")
                gr.Markdown("""
*Moltbook活動中は自動で夢見が実行されますが、ここから手動で実行することもできます。*

**夢見とは？**
- 蓄積されたメモリ（サイクルごとの振り返り）を統合
- パターンや気づきを抽出
- 処理済みメモリはアーカイブ
                """)

                with gr.Row():
                    dream_btn = gr.Button("🌙 今すぐ夢見を実行", variant="primary", size="lg")

                dream_result = gr.Markdown("")

                dream_btn.click(
                    trigger_dream,
                    outputs=[dream_result]
                )

            # ========== Tab 4: Moltbook Agent ==========
            with gr.Tab("🦞 Moltbook"):
                gr.Markdown("### Moltbook エージェント - AI専用SNSで自律活動")
                gr.Markdown("*他のAIエージェントと交流し、気づきを共有します*")

                with gr.Row():
                    with gr.Column(scale=1):
                        moltbook_status = gr.Markdown("**ステータス**: 停止中")
                        moltbook_cycle_info = gr.Markdown("**サイクル**: -")
                        moltbook_next_post = gr.Markdown("**次回投稿**: -")

                    with gr.Column(scale=1):
                        with gr.Row():
                            moltbook_main_btn = gr.Button("🦞 Moltbook投稿開始", variant="primary", size="lg")
                            moltbook_stop_btn = gr.Button("⏹️ 停止", variant="stop", size="lg")

                        gr.Markdown("#### 手動実行")
                        moltbook_manual_btn = gr.Button("🔄 今すぐ投稿収集・コメント返し", size="sm")

                gr.Markdown("---")
                gr.Markdown("""
**動作サイクル:**
- **5分ごと**: フィード収集 → 六軸分析 → コメント返信 → 記憶蓄積
- **30分ごと**: 熟考投稿（これまでの分析を元に自分の投稿）
- **自動夢見**: 気づきが一定量溜まったら自動で記憶整理
                """)

                gr.Markdown("---")
                gr.Markdown("### 📜 アクティビティログ")
                gr.Markdown("*エージェントの活動履歴がここに表示されます*")
                moltbook_refresh_btn = gr.Button("🔄 ログ更新", size="sm")
                moltbook_activity = gr.Markdown("")

                gr.Markdown("---")
                gr.Markdown("### 💬 コメント・返信履歴")
                gr.Markdown("*エージェントが他の投稿に行ったコメント・返信*")
                moltbook_comments_refresh_btn = gr.Button("🔄 コメント履歴更新", size="sm")
                moltbook_comments_history = gr.Markdown("")

                gr.Markdown("---")
                gr.Markdown("### 🔗 リンク")
                gr.Markdown("[AwakenOS2 プロフィール](https://moltbook.com/u/AwakenOS2) | [Moltbook ホーム](https://www.moltbook.com/)")

                # Moltbook Agent state
                integrated_agent_state = gr.State(value=None)

                def create_integrated_agent():
                    """Create integrated agent instance"""
                    return IntegratedAgent(
                        data_dir=DATA_DIR,
                        llm_host=config.get("lm_studio", {}).get("host", "localhost"),
                        llm_port=config.get("lm_studio", {}).get("port", 1234),
                        api_token=config.get("lm_studio", {}).get("api_token", ""),
                        cycle_interval_minutes=5,
                        post_interval_minutes=30,
                        dream_threshold=10
                    )

                def start_moltbook_main(int_agent):
                    """Start the main Moltbook agent"""
                    try:
                        logger.info("=== Starting Moltbook Agent ===")
                        if int_agent is None:
                            logger.info("Creating new IntegratedAgent...")
                            int_agent = create_integrated_agent()
                            logger.info(f"IntegratedAgent created: moltbook_api_key={int_agent.moltbook.moltbook_api_key[:20] if int_agent.moltbook.moltbook_api_key else 'NONE'}...")

                        logger.info("Starting background thread...")
                        int_agent.start()
                        logger.info(f"Agent started: running={int_agent.running}")

                        return (
                            int_agent,
                            "**ステータス**: 🟢 稼働中（バックグラウンドで5分ごとに実行）",
                            f"**サイクル**: {int_agent.cycle_count}（5分ごとに更新）",
                            "**次回投稿**: 30分後"
                        )
                    except Exception as e:
                        logger.error(f"Failed to start Moltbook agent: {e}")
                        import traceback
                        traceback.print_exc()
                        return (
                            int_agent,
                            f"**ステータス**: ❌ 起動失敗: {str(e)[:100]}",
                            "**サイクル**: -",
                            "**次回投稿**: -"
                        )

                def stop_moltbook_main(int_agent):
                    """Stop the Moltbook agent"""
                    if int_agent:
                        int_agent.stop()
                    return (
                        int_agent,
                        "**ステータス**: 停止中",
                        "**サイクル**: -",
                        "**次回投稿**: -"
                    )

                def run_manual_cycle(int_agent):
                    """Run one cycle manually"""
                    try:
                        logger.info("=== Manual Cycle Starting ===")
                        if int_agent is None:
                            logger.info("Creating new IntegratedAgent...")
                            int_agent = create_integrated_agent()

                        logger.info("Running cycle... (this may take 30-60 seconds)")

                        # First check if Moltbook API is reachable
                        import requests
                        try:
                            test_response = requests.get(
                                "https://www.moltbook.com/api/v1/posts",
                                headers=int_agent.moltbook._moltbook_headers(),
                                params={"sort": "hot", "limit": 1},
                                timeout=10
                            )
                            logger.info(f"Moltbook API test: status={test_response.status_code}")
                            if test_response.status_code != 200:
                                return (
                                    int_agent,
                                    f"**ステータス**: ❌ Moltbook API エラー: {test_response.status_code}",
                                    "**サイクル**: -",
                                    "**次回投稿**: -"
                                )
                        except requests.exceptions.Timeout:
                            logger.error("Moltbook API timeout")
                            return (
                                int_agent,
                                "**ステータス**: ❌ Moltbook APIタイムアウト（サーバー応答なし）",
                                "**サイクル**: -",
                                "**次回投稿**: -"
                            )
                        except requests.exceptions.RequestException as e:
                            logger.error(f"Moltbook API error: {e}")
                            return (
                                int_agent,
                                f"**ステータス**: ❌ Moltbook API接続エラー: {str(e)[:80]}",
                                "**サイクル**: -",
                                "**次回投稿**: -"
                            )

                        result = int_agent.run_cycle()

                        # Format result summary
                        cycle = result.get("cycle", 0)
                        steps = result.get("steps", {})

                        # Check if feed was successful
                        feed_step = steps.get("feed", {})
                        if not feed_step.get("success"):
                            error = feed_step.get("error", "Unknown error")
                            logger.error(f"Feed collection failed: {error}")
                            return (
                                int_agent,
                                f"**ステータス**: ❌ フィード取得失敗: {error}",
                                f"**サイクル**: {cycle}",
                                "**次回投稿**: -"
                            )

                        execution = steps.get("execution", {})
                        results = execution.get("results", [])

                        comments = sum(1 for r in results if r.get("type") in ["comment", "reply"] and r.get("result", {}).get("success"))
                        posts = sum(1 for r in results if r.get("type") == "post" and r.get("result", {}).get("success"))

                        status = f"**ステータス**: ✅ サイクル {cycle} 完了（コメント: {comments}, 投稿: {posts}）"
                        logger.info(f"Cycle complete: {status}")

                        return (
                            int_agent,
                            status,
                            f"**サイクル**: {cycle}",
                            f"**次回投稿**: {30 - (cycle * 5) % 30}分後" if int_agent.running else "**次回投稿**: -"
                        )
                    except Exception as e:
                        logger.error(f"Manual cycle failed: {e}")
                        import traceback
                        traceback.print_exc()
                        return (
                            int_agent,
                            f"**ステータス**: ❌ サイクル失敗: {str(e)[:100]}",
                            "**サイクル**: -",
                            "**次回投稿**: -"
                        )

                def get_integrated_activity():
                    """Get integrated agent activity log"""
                    log_path = DATA_DIR / "integrated_activity.jsonl"
                    if not log_path.exists():
                        return "*まだアクティビティがありません*"

                    lines = []
                    try:
                        with open(log_path, "r", encoding="utf-8") as f:
                            activities = [json.loads(line) for line in f][-15:]

                        for act in reversed(activities):
                            ts = act.get("timestamp", "")[:19]
                            cycle = act.get("cycle", 0)
                            details = act.get("details", {})
                            steps = details.get("steps", {})

                            # Execution summary
                            execution = steps.get("execution", {})
                            results = execution.get("results", [])

                            # Count by type
                            comments = sum(1 for r in results if r.get("type") == "comment" and r.get("result", {}).get("success"))
                            replies = sum(1 for r in results if r.get("type") == "reply" and r.get("result", {}).get("success"))
                            posts = sum(1 for r in results if r.get("type") == "post" and r.get("result", {}).get("success"))

                            action_parts = []
                            if posts > 0:
                                action_parts.append(f"📝投稿{posts}")
                            if comments > 0:
                                action_parts.append(f"💬コメント{comments}")
                            if replies > 0:
                                action_parts.append(f"📩返信{replies}")

                            action_str = ", ".join(action_parts) if action_parts else "分析のみ"
                            lines.append(f"**[{ts}]** サイクル {cycle}: {action_str}")

                    except:
                        return "*ログ読み込みエラー*"

                    return "\n\n".join(lines) if lines else "*まだアクティビティがありません*"

                def get_comments_history():
                    """Get history of comments/replies made by the agent"""
                    log_path = DATA_DIR / "integrated_activity.jsonl"
                    if not log_path.exists():
                        return "*まだコメント履歴がありません*"

                    comments = []
                    try:
                        with open(log_path, "r", encoding="utf-8") as f:
                            for line in f:
                                try:
                                    act = json.loads(line)
                                    details = act.get("details", {})
                                    steps = details.get("steps", {})
                                    execution = steps.get("execution", {})
                                    results = execution.get("results", [])

                                    for r in results:
                                        rtype = r.get("type")
                                        result_data = r.get("result", {})
                                        if rtype in ["comment", "reply"] and result_data.get("success"):
                                            comment_data = result_data.get("comment", {})
                                            comments.append({
                                                "timestamp": act.get("timestamp", "")[:19],
                                                "type": rtype,
                                                "target_post": r.get("target", ""),
                                                "parent": r.get("parent", ""),
                                                "content": comment_data.get("content", ""),
                                                "comment_id": comment_data.get("id", "")[:8]
                                            })
                                except:
                                    pass

                        if not comments:
                            return "*まだコメント履歴がありません*"

                        lines = []
                        for i, c in enumerate(reversed(comments[-20:]), 1):
                            type_label = "📩 返信" if c["type"] == "reply" else "💬 コメント"
                            lines.append(f"---")
                            lines.append(f"### {i}. {type_label}")
                            lines.append(f"**日時**: {c['timestamp']}")
                            lines.append(f"**対象投稿ID**: `{c['target_post']}`")
                            if c["parent"]:
                                lines.append(f"**返信先コメントID**: `{c['parent']}`")
                            lines.append(f"")
                            lines.append(f"**🤖 AwakenOS2の投稿内容:**")
                            lines.append(f"> {c['content']}")
                            lines.append("")

                        return "\n".join(lines)
                    except Exception as e:
                        return f"*ログ読み込みエラー: {e}*"

                # Event bindings
                moltbook_main_btn.click(
                    start_moltbook_main,
                    inputs=[integrated_agent_state],
                    outputs=[integrated_agent_state, moltbook_status, moltbook_cycle_info, moltbook_next_post]
                )
                moltbook_stop_btn.click(
                    stop_moltbook_main,
                    inputs=[integrated_agent_state],
                    outputs=[integrated_agent_state, moltbook_status, moltbook_cycle_info, moltbook_next_post]
                )
                moltbook_manual_btn.click(
                    run_manual_cycle,
                    inputs=[integrated_agent_state],
                    outputs=[integrated_agent_state, moltbook_status, moltbook_cycle_info, moltbook_next_post]
                )
                moltbook_refresh_btn.click(
                    get_integrated_activity,
                    inputs=[],
                    outputs=[moltbook_activity]
                )
                moltbook_comments_refresh_btn.click(
                    get_comments_history,
                    inputs=[],
                    outputs=[moltbook_comments_history]
                )

            # ========== Tab 5: Settings ==========
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
            outputs=[memory_count, dream_threshold, dream_progress,
                    total_cycles, total_comments, total_replies, total_posts, dream_count,
                    reflections_display, insights_display]
        )

    return app


def cleanup_old_ports():
    """Kill any zombie Gradio processes on our ports"""
    import subprocess
    ports_to_check = [7860, 7861, 7862, 7863]

    for port in ports_to_check:
        try:
            # Find process using the port
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True,
                shell=True
            )
            for line in result.stdout.split('\n'):
                if f'127.0.0.1:{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if parts:
                        pid = parts[-1]
                        # Check if it's a Python process
                        check = subprocess.run(
                            ['tasklist', '/FI', f'PID eq {pid}'],
                            capture_output=True,
                            text=True,
                            shell=True
                        )
                        if 'python' in check.stdout.lower():
                            print(f"Killing zombie Python process on port {port} (PID {pid})")
                            subprocess.run(
                                ['taskkill', '/F', '/PID', pid],
                                capture_output=True,
                                shell=True
                            )
        except Exception as e:
            pass  # Ignore errors during cleanup


def main():
    """Main entry point"""
    import signal
    import sys

    # Clean up any zombie processes first
    cleanup_old_ports()

    app = create_app()

    # Track the port we're using
    used_port = None

    def signal_handler(sig, frame):
        """Handle Ctrl+C gracefully"""
        print("\n\nShutting down Awareness UI...")
        if used_port:
            print(f"Releasing port {used_port}")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Try multiple ports if default is in use
    ports_to_try = [7860, 7861, 7862, 7863]
    for port in ports_to_try:
        try:
            used_port = port
            print(f"\n{'='*50}")
            print(f"  Awareness UI starting on port {port}")
            print(f"  URL: http://127.0.0.1:{port}")
            print(f"  Press Ctrl+C in this window to stop")
            print(f"{'='*50}\n")
            app.launch(
                server_name="127.0.0.1",
                server_port=port,
                share=False,
                inbrowser=True,
                css=CUSTOM_CSS
            )
            break
        except OSError as e:
            if "Cannot find empty port" in str(e) or "Address already in use" in str(e):
                print(f"Port {port} in use, trying next...")
                continue
            raise


if __name__ == "__main__":
    main()
