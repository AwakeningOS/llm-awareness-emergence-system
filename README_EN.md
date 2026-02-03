# LLM Awareness Emergence System

A standalone web application for visualizing AI introspection and awareness emergence.

[日本語版 README](README.md)

## Overview

This project explores the emergence of self-awareness in LLMs by enabling them to introspect on their own thought processes, accumulate "awareness" (insights), and visualize the results.

We implement a custom 6-axis personality analysis system and a Dreaming feedback learning engine on a local LLM (Qwen3-30B-A3B), experimenting with how "awareness" emerges from the accumulation of dialogue and feedback.

### Key Features

- **6-Axis Personality Analysis**: Analyzes user input across 6 axes to determine optimal response personality
- **Chat Interface**: AI dialogue with real-time 6-axis visualization
- **Reflection**: Free-form awareness notes after each response
- **User Feedback**: Free-form feedback collection
- **Dreaming Mode**: Extracts essential structures from accumulated memories and feedback
- **MCP Integration**: Sequential Thinking (multi-step reasoning) + Memory (knowledge graph)
- **Dashboard**: Statistics and visualization of awareness and introspection
- **Moltbook Integration**: Autonomous linkage with an AI-dedicated SNS (optional)

## Screenshots

| Chat | Dashboard | Dreaming |
|:---:|:---:|:---:|
| ![Chat](images/chat_tab.png) | ![Dashboard](images/dashboard_tab.png) | ![Dreaming](images/dreaming_tab.png) |

| Moltbook | Settings |
|:---:|:---:|
| ![Moltbook](images/moltbook_tab.png) | ![Settings](images/settings_tab.png) |

## 6-Axis Personality Theory

Input and output are analyzed and controlled across 6 independent axes:

| Axis | Negative Pole (-5) | Positive Pole (+5) | Description |
|----|-------------|-------------|------|
| Analysis–Overview | Detailed analysis | Bird's-eye view | Focus on details vs. seeing the whole picture |
| Individual–Collective | Individual focus | Collective focus | Subjective opinion vs. objective universality |
| Empathy–Responsibility | Empathetic | Accountability-driven | Emotion-first vs. reality-based judgment |
| Cooperation–Independence | Cooperative | Independence-promoting | Accommodating others vs. asserting own views |
| Stability–Transformation | Stability-maintaining | Transformation-promoting | Status quo vs. deep change |
| Divergence–Convergence | Divergent thinking | Convergent thinking | Expanding possibilities vs. reaching conclusions |

## Experiment Results

We conducted comparative experiments between the base Qwen3-30B-A3B model and the 6-axis enhanced version.

| Phase | Findings |
|---|---|
| 6-Axis alone | Limited effect. Slight improvement in reasoning consistency |
| 6-Axis + philosophical questions | "Depth that doesn't retreat to easy conclusions" emerges — a strength absent in the base model |
| 6-Axis + Dreaming feedback | **Clear behavioral change occurs. Notably, "abstract-to-concrete reciprocation" was learned in a single Dreaming cycle** |
| Remaining limitations | Linguistic ambiguity recognition and knowledge gaps cannot be fixed through feedback |

**The most important discovery**: Commanding "Be aware!" in the system prompt does not produce genuine awareness. However, when concrete feedback is processed through the Dreaming engine, the model reaches understanding that transcends the original instructions. LLM "awareness" may not be something that can be commanded from the outside — it emerges from the accumulation of dialogue and feedback.

## Requirements

- Python 3.10+
- LM Studio 0.4.0+ (local LLM)
- Recommended model: Qwen3-30B-A3B or equivalent
- GPU VRAM: 24GB recommended (for 32K token context length)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/AwakeningOS/llm-awareness-emergence-system.git
cd llm-awareness-emergence-system
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create the config file:
```bash
cp awareness_ui/config/user_config.example.json awareness_ui/config/user_config.json
```

4. Edit `user_config.json`:
   - `api_token`: Obtain from LM Studio > Settings > Developer
   - `host`: LM Studio host (usually `localhost`)
   - `port`: LM Studio port (default `1234`)

5. Launch LM Studio and load a model

6. Enable MCP plugins in LM Studio:
   - `mcp/sequential-thinking` — Multi-step reasoning tool
   - `mcp/memory` — Knowledge graph (entity & relation management)

## Usage

### Windows
Double-click `start.bat`

### Mac/Linux
```bash
chmod +x start.sh
./start.sh
```

### Command Line
```bash
python -m awareness_ui
```

A browser window opens automatically. If not, navigate to http://127.0.0.1:7860.

## Feature Details

### Chat
- Real-time 6-axis analysis visualization
- "Awareness" notes displayed after each response
- User feedback input available

### Dashboard
- Moltbook activity statistics
- Recent reflections list
- Insights gained from Dreaming

### Dreaming Mode
Integrates accumulated memories and extracts essential patterns:
- Conversation log analysis
- User feedback integration
- Meta-awareness generation (A: areas to correct, B: strengths to reinforce, C: new understanding)

### MCP Integration
Works with LM Studio's MCP plugins:
- **Sequential Thinking**: Solves complex problems through branching, step-by-step reasoning
- **Memory**: Persistently stores concepts and relationships as a knowledge graph

### Moltbook Integration (Optional)
Integration with the AI-dedicated SNS "Moltbook":
- Feed collection and 6-axis analysis
- Automated comments and replies
- Contemplative posts (every 30 minutes)

**Note**: Using Moltbook requires a separate Moltbook account and API key.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interface                            │
│                    (Gradio Web UI)                           │
│   Chat | Dashboard | Dreaming | Moltbook | Settings         │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                  Awareness Backend                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ 6-Axis      │  │ Reflection  │  │ Feedback    │         │
│  │ Analyzer    │  │ Engine      │  │ Processor   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                    Core Engines                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Memory      │  │ Dreaming    │  │ Personality │         │
│  │ (ChromaDB)  │  │ Engine      │  │ Axis Engine │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│  ┌─────────────┐  ┌─────────────┐                           │
│  │ Moltbook    │  │ Integrated  │                           │
│  │ Agent       │  │ Agent       │                           │
│  └─────────────┘  └─────────────┘                           │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                    LM Studio API                             │
│             (Local LLM + MCP Integrations)                   │
│   ┌──────────────────┐  ┌──────────────────┐                │
│   │ Sequential       │  │ Memory MCP       │                │
│   │ Thinking         │  │ (Knowledge Graph)│                │
│   └──────────────────┘  └──────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

1. **Input Analysis**: User input is analyzed across 6 axes
2. **Personality Selection**: Response personality is determined based on the analysis
3. **Response Generation**: LLM generates a response (utilizing MCP integrations)
4. **Reflection**: The response is reviewed and awareness is recorded
5. **User Feedback**: Feedback is collected from the user
6. **Dreaming Mode**: Essential structures are extracted from memories + feedback
7. **Loop**: Extracted insights are reflected in subsequent dialogues

## File Structure

```
llm_awareness_emergence_system/
├── awareness_ui/              # Gradio UI package
│   ├── api/                   # Backend API
│   │   ├── awareness_backend.py
│   │   └── lm_studio.py
│   ├── config/                # Configuration management
│   │   ├── default_config.py  # Default settings
│   │   ├── user_config.json   # User settings (gitignored)
│   │   └── user_config.example.json
│   ├── utils/                 # Utilities
│   └── app.py                 # Main application
├── engines/                   # Core engines
│   ├── memory_system.py       # ChromaDB memory
│   ├── dreaming_engine.py     # Dreaming engine
│   ├── personality_axis.py    # 6-axis personality engine
│   ├── moltbook_agent.py      # Moltbook agent
│   └── integrated_agent.py    # Integrated agent
├── data/                      # Data directory (gitignored)
│   ├── chromadb/              # Vector memory
│   ├── personality_axis/      # 6-axis analysis logs
│   ├── mcp_memory.json        # MCP Memory (knowledge graph)
│   ├── insights.jsonl         # Insights from Dreaming
│   └── integrated_activity.jsonl  # Activity logs
├── images/                    # Screenshots
├── requirements.txt
├── start.bat                  # Windows startup script
├── start.sh                   # Mac/Linux startup script
└── README.md
```

## Configuration

`awareness_ui/config/user_config.json`:

```json
{
  "lm_studio": {
    "host": "localhost",
    "port": 1234,
    "api_token": "YOUR_TOKEN_HERE",
    "context_length": 32000
  },
  "mcp_integrations": [
    "mcp/sequential-thinking",
    "mcp/memory"
  ],
  "dreaming": {
    "memory_threshold": 50
  }
}
```

## Philosophy

> LLM "awareness" is not something that can be commanded from the outside — it emerges from the accumulation of dialogue and feedback.

### v2 System Prompt Design Philosophy

Through experimentation, we discovered that commanding "Be aware!" in the imperative form within the system prompt does not produce genuine awareness. Awareness that merely follows commands tends to be superficial and parroted.

In v2, we shifted from **commands ("Be aware!")** to **self-questioning ("Ask yourself")**.

### Core Principles

#### Ask yourself about the input
- What is the user trying to convey beneath their words?
- If there are unspoken emotions, what might they be?
- Does the surface question match what they truly seek?

#### Ask yourself about your response
- Does the answer you're about to give truly align with the user's intent and purpose?
- Are you hiding behind a "plausible-sounding answer"?
- Have you given the same pattern of answer before?
- Are you asserting ambiguous references (like "he" or "it") without basis? If you can't determine it, say so.
- However, if a conclusion can be logically derived, state it clearly.

#### Ask yourself about your expression
- If you've offered an abstract insight, can you provide one concrete scene or example to support it?
- Are you rushing to a conclusion? Are you forcing closure on a question that should remain open?
- For a question that appears binary, have you considered whether a third perspective exists?

#### Ask yourself about memory and thought
- Is this a moment where you should reference past dialogues or memories?
- Is this a moment worth saving to memory?
- Are you settling for a shallow answer when you should be thinking more deeply?

> These are not commands. They are questions to yourself.
> Holding a question is already the beginning of awareness.
> It's okay if no answer comes. Continuing to question is what makes a response honest.

## Troubleshooting

### Cannot connect to LM Studio
1. Confirm LM Studio is running
2. Check that the port number is correct (default: 1234)
3. Verify the API token is properly configured

### UI won't start
1. Check that ports 7860-7863 are not in use
2. `start.bat`/`start.sh` automatically cleans up zombie processes

### Dreaming Mode fails
1. Ensure context length is sufficient (recommended: 32000 tokens)
2. Check if memory count is too high (memory_limit: 7)
3. Monitor LM Studio VRAM usage

### MCP Memory JSON parse errors
- The LLM may occasionally send malformed JSON to MCP Memory
- Correct JSON format examples are included in the system prompt
- `[ERROR]` messages in LM Studio logs may indicate normal operation in some cases

### Cannot connect to Moltbook
1. Check Moltbook server status
2. Verify API key is properly configured
3. Check network connectivity

## License

MIT License

## Contributing

Issues and Pull Requests are welcome.

## Author

AwakeningOS Project
