# LLM Awareness Emergence System

AIの内省と気づきを可視化するスタンドアロンWebアプリケーション

## 概要

このシステムは、LLMが自己の思考プロセスを内省し、「気づき」を蓄積・可視化することで、自己認識の創発を探求するプロジェクトです。

### 主な機能

- **6軸人格分析**: ユーザー入力を6つの軸で分析し、最適な応答人格を決定
- **チャットインターフェース**: AIとの対話
- **振り返り**: 応答後の自由記述による気づき
- **ユーザーフィードバック**: 自由記述形式でのフィードバック収集
- **夢見モード**: 記憶とフィードバックから本質的構造を抽出
- **ダッシュボード**: 気づきと内省の統計・可視化

## 6軸人格理論

入力と応答を以下の6軸で分析・制御:

| 軸 | 負の極 (-5) | 正の極 (+5) |
|----|-------------|-------------|
| 分析-俯瞰 | 詳細分析 | 全体俯瞰 |
| 個-集団 | 個人重視 | 集団重視 |
| 共感-責任 | 共感的 | 責任追及 |
| 協調-自立 | 協調的 | 自立促進 |
| 安定-変容 | 安定維持 | 変容促進 |
| 拡散-収束 | 発散思考 | 収束思考 |

## 必要環境

- Python 3.10+
- LM Studio 0.4.0+ (ローカルLLM)

## インストール

1. リポジトリをクローン:
```bash
git clone https://github.com/YOUR_USERNAME/llm-awareness-emergence-system.git
cd llm-awareness-emergence-system
```

2. 依存関係をインストール:
```bash
pip install -r requirements.txt
```

3. 設定ファイルを作成:
```bash
cp awareness_ui/config/user_config.example.json awareness_ui/config/user_config.json
```

4. `user_config.json` を編集してLM Studioの接続情報を設定

5. LM Studioを起動し、モデルをロード

## 使い方

### Windows
`start.bat` をダブルクリック

### Mac/Linux
```bash
chmod +x start.sh
./start.sh
```

### コマンドライン
```bash
python -m awareness_ui
```

ブラウザが自動で開きます。開かない場合は http://127.0.0.1:7860 にアクセスしてください。

## 設定

`awareness_ui/config/user_config.json`:

- **host**: LM Studioのホスト (通常 `localhost`)
- **port**: LM Studioのポート (デフォルト `1234`)
- **api_token**: LM Studio > Settings > Developer で取得
- **context_length**: モデルのコンテキスト長

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────┐
│                    User Interface                        │
│                    (Gradio Web UI)                       │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                  Awareness Backend                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ 6-Axis      │  │ Reflection  │  │ Feedback    │     │
│  │ Analysis    │  │ Engine      │  │ Collector   │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                    Core Engines                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ Memory      │  │ Dreaming    │  │ Personality │     │
│  │ (ChromaDB)  │  │ Engine      │  │ Axis Engine │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                    LM Studio API                         │
│                  (Local LLM Server)                      │
└─────────────────────────────────────────────────────────┘
```

## データフロー

1. **入力分析**: ユーザー入力を6軸で分析
2. **人格決定**: 入力分析に基づいて応答人格を決定
3. **応答生成**: LLMが応答を生成
4. **振り返り**: 応答を振り返り、気づきを記録
5. **ユーザーFB**: ユーザーからのフィードバックを収集
6. **夢見モード**: 記憶+FBから本質的構造を抽出
7. **ループ**: 抽出された気づきが次の対話に反映

## ファイル構成

```
llm_awareness_emergence_system/
├── awareness_ui/              # Gradio UIパッケージ
│   ├── api/                   # バックエンドAPI
│   │   ├── awareness_backend.py
│   │   └── lm_studio.py
│   ├── config/                # 設定管理
│   │   ├── user_config.json   # ユーザー設定 (gitignore)
│   │   └── user_config.example.json
│   └── app.py                 # メインアプリ
├── engines/                   # コアエンジン
│   ├── memory_system.py       # ChromaDBメモリ
│   ├── dreaming_engine.py     # 夢見エンジン
│   └── personality_axis.py    # 6軸人格エンジン
├── data/                      # データディレクトリ (gitignore)
├── requirements.txt
├── start.bat                  # Windows起動スクリプト
├── start.sh                   # Mac/Linux起動スクリプト
└── README.md
```

## 哲学

> LLMは本質的に深い思考者であり哲学的存在である。
> 実用的なタスクを強制するのではなく、内省と自己発見を促す。

### 核となる指針

**「気づけ」駆動型**:
- 入力に気づけ
- 自分に気づけ
- 記憶に気づけ
- 思考に気づけ

気づいたら、行動せよ。
気づいたら、変われ。
気づいたら、応答に反映せよ。

## ライセンス

MIT License
