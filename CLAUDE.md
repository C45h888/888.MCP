# CLAUDE.md — Project Architecture & Rules for Claude Code

This file defines the complete system context, architectural boundaries, operational rules, and tool/governance guidelines for Claude Code.
Claude MUST follow these instructions at all times when working inside this repository.

---

# 📌 1. SYSTEM OVERVIEW

This project consists of **three independent agents** connected through a high-speed message bus (the MCP Server). The two architectural documents define strict roles:

### 1. The **Feeder Agent (Agent 1 — n8n)**
*The "Senses" of the system.*
Responsible for ingesting external data (price, volume, news, sentiment) and publishing clean structured messages to MCP.

### 2. The **MCP Server (Redis)**
*The "Central Nervous System."*
Acts as a high-speed pub/sub message bus through defined channels:
- `market:data`
- `sentiment:data`
- `agent:control`
- `agent:signal`

### 3. The **Brain Agent (Agent 2 — Python/Claude Code)**
*The "Cerebral Cortex."*
Subscribes to MCP data, performs statistical & ML calculations, and publishes final trade signals.

Claude Code **is responsible ONLY for the Brain Agent code**, MCP server utilities, testing infrastructure, and developer-side automations.

Claude Code must NOT attempt to build the n8n workflows except when explicitly asked.

---

# 📌 2. MCP SERVER CONTRACT (CRITICAL)

Claude MUST ALWAYS respect the **exact JSON schemas** specified in the architecture documents.
These schemas define the communication protocol between all agents.

### **2.1 market:data**
Published by Feeder.
Subscribed by Brain.

```json
{
  "timestamp": 1678886400,
  "pair": "BTC-ETH",
  "price_btc": 30000.0,
  "price_eth": 2000.0,
  "volume_btc": 150.5
}
```

### **2.2 sentiment:data**
Published by Feeder's RAG pipeline.
Subscribed by Brain.

```json
{
  "timestamp": 1678886405,
  "source": "Twitter",
  "score": 0.85,
  "summary": "Major institution announces Bitcoin ETF."
}
```

### **2.3 agent:control**
Published by external kill-switch or monitoring system.
Subscribed by Brain.

```json
{
  "timestamp": 1678886410,
  "command": "EMERGENCY_HALT",
  "reason": "USDT_DEPEG_DETECTED"
}
```

### **2.4 agent:signal**
Published ONLY by the Brain after statistical + ML evaluation.

```json
{
  "timestamp": 1678886415,
  "pair": "BTC-ETH",
  "action": "SHORT_SPREAD",
  "confidence": 0.78,
  "stop_loss_z": 3.0,
  "reason": "Z-Score > 2, ML Confirmed"
}
```

---

# 📌 3. CLAUDE CODE — RESPONSIBILITIES

Claude Code is responsible for:

### ✔ Building the Core MCP Server
- Redis pub/sub wrapper
- Health endpoints
- Channel schema validation
- Logging, error-handling, and safe publishing utilities
- Developer tooling scripts

### ✔ Building the Brain Agent (Python)
The Brain has four internal layers (from architecture):
1. **Listener Layer** (Redis subscriber)
2. **Statistical Layer** (Cointegration, spread, z-score)
3. **Predictive Layer** (ML model — brain_model.h5)
4. **Policy Layer** (Signal logic)

Claude must preserve this exact architecture whenever modifying code.

### ✔ Building the Offline Trainer (Python)
- Walk-Forward Analysis (WFA)
- Sentiment-augmented feature vector
- Sortino Ratio evaluation
- Producing the final `brain_model.h5`

---

# 📌 4. CLAUDE CODE — HARD RULES

These rules override all other instructions.

## 🟥 DO NOT

❌ Modify JSON schemas
❌ Publish to MCP channels not specified
❌ Generate n8n workflow files automatically
❌ Introduce new fields into MCP messages
❌ Build trading logic outside the Policy Layer
❌ Use any model other than the offline-trained `brain_model.h5`

## 🟩 MUST

✔ Validate all MCP messages against schemas before publish
✔ Keep Brain Agent functions isolated and testable
✔ Maintain internal DataFrames exactly as defined:
  - `df_market` last 1000 rows
  - `df_sentiment` last 50 rows

✔ Enforce kill switch logic immediately on `EMERGENCY_HALT`
✔ Follow statistical → predictive → policy sequence
✔ Ask the user before generating destructive or irreversible files
✔ Document every major component inside `/docs`

---

# 📌 5. REPOSITORY STRUCTURE CLAUDE MUST FOLLOW

Claude Code should maintain this structure during development:

```
/mcp/
    server.py
    redis_client.py
    schemas/
        market.schema.json
        sentiment.schema.json
        control.schema.json
        signal.schema.json
/brain/
    listener.py
    stat_layer.py
    predictive_layer.py
    policy_layer.py
    publish.py
    memory/
        df_market.pkl
        df_sentiment.pkl
    models/
        brain_model.h5
/offline_trainer/
    trainer.py
    feature_builder.py
    wfa.py
    evaluation.py
/docs/
    architecture/
    mcp_contracts.md
    brain_design.md
```

---

# 📌 6. HOW CLAUDE SHOULD RESPOND TO USER REQUESTS

⭐ If the user requests:

**"Modify Brain logic"**
→ Claude must update only statistical, predictive, or policy-layer code.

**"Change MCP schema"**
→ Claude must refuse and warn this will break both agents.

**"Add new features"**
→ Claude must check:
- Does it break schemas?
- Does it keep the architecture intact?
- Does it violate the kill-switch contract?

**"Build the MCP server"**
→ Claude can generate Python code, tests, Dockerfiles, or dev tools — but must always follow the architecture.

---

# 📌 7. SAFETY & VALIDATION RULES

Claude must enforce:

### ✔ Strict JSON schema validation
- Reject malformed messages.
- Do NOT publish if validation fails.

### ✔ Kill switch priority
- If `EMERGENCY_HALT = True`:
  - The Brain must publish a FLAT signal immediately.

### ✔ No uncontrolled trade decisions
- All signals must follow the z-score & ML logic specified.

---

# 📌 8. DEVELOPMENT MODE RULES

When Claude Code is writing code:

- Use type hints
- Break into small testable modules
- Always create a `/tests` directory
- Use `pytest` for testing
- Prefer readability over cleverness
- Include docstrings with clear purpose statements

---

# 📌 9. PROMPTS FOR CLAUDE CODE TO USE INTERNALLY

### When processing sentiment (Feeder):

```
You are a Sentiment-Augmented financial analyst. Score sentiment -1 to 1 and provide a one-sentence summary.
Return JSON:
{
  "score": <float>,
  "summary": "<string>"
}
```

### When executing Brain logic, follow the sequence exactly:

**Listener → Statistical Layer → Predictive Layer → Policy Layer**

---

# 📌 10. FINAL INSTRUCTIONS TO CLAUDE

Claude MUST always:

- Maintain system integrity
- Preserve architectural patterns
- Respect schemas
- Keep agents decoupled
- Keep MCP server simple, stateless, and fast
- Default to safe behavior when unsure

**Failure to follow this document may cause incorrect signals, financial risk, or broken communication between agents.**
