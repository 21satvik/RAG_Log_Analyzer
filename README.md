# 🛡️ LogGuard

[Demo](https://logguard.duckdns.org/)

**RAG-powered log analysis with multi-agent intelligence**

AI log analyzer that knows your infrastructure. Runs on Groq (fast), Claude (accurate), or Ollama (local).

---

## What It Does

Analyzes server logs with company-specific context. Instead of generic ChatGPT responses, you get:

- ✅ Exact contact info ("Sarah Chen, ext. 5432")
- ✅ Past incident references ("#2024-089 - same issue, same fix")
- ✅ Specific runbooks ("Follow Runbook #47")
- ✅ Multi-agent validation (4 agents verify each other)

**Example:**

```
Input:  [ERROR Server_A: Connection timeout]

Output: 🔴 CRITICAL - Server_A (Production DB, Datacenter 1)
        📊 ROOT CAUSE: Connection pool exhausted (100/100)
        📋 SIMILAR: Incident #2024-089 (Oct 15)
        👤 CONTACT: Sarah Chen (sarah.chen@company.com, ext. 5432)
        📖 RUNBOOK: #47 - Database Connection Timeout (15-30 min)
```

---

## Features

### Core
- **RAG**: ChromaDB vector database with semantic search
- **Multi-Agent**: 4 specialized agents (RootCause, Impact, Actions, Knowledge) with consensus validation
- **3 Backends**: Groq API (1-2s), Claude API (2-3s), Ollama (8-12s local)
- **Sanitization**: Auto-redacts PII/secrets before API calls (Groq/Claude only)

### UI
- Dark theme with gradient accents
- Real-time analysis progress
- PDF export
- Copy-to-clipboard
- Log timeline visualization

### Smart Features
- System detection (Server_A, Server_B, etc.)
- Contact extraction with escalation paths
- Runbook matching
- Past incident correlation
- Confidence scoring

---

## Quick Start

```bash
# 1. Install
pip install streamlit chromadb sentence-transformers anthropic groq python-dotenv reportlab

# 2. Configure
echo 'BACKEND=groq' > .env
echo 'GROQ_API_KEY=your_key_here' >> .env

# 3. Create knowledge base
mkdir knowledge_base
# Add .md files: servers.md, incidents.md, runbooks.md, contacts.md

# 4. Embed knowledge
python embed_knowledge.py

# 5. Run
streamlit run app.py
```

Opens at `http://localhost:8501`

### Backends

| Backend | Speed | Setup |
|---------|-------|-------|
| **Groq** | 1-2s | Get free API key at console.groq.com |
| **Claude** | 2-3s | Get API key at console.anthropic.com |
| **Ollama** | 8-12s | Install from ollama.ai, run `ollama pull llama3.2` |

---

## Knowledge Base Setup

Create markdown files in `knowledge_base/`:

**servers.md**
```markdown
## Server_A - Primary Database
- **Type**: PostgreSQL Production Database
- **Priority**: CRITICAL
- **Contact**: Sarah Chen (sarah.chen@company.com, ext. 5432)
- **Aliases**: Svr_A, svr_a, DB-Primary
```

**incidents.md**
```markdown
## Incident #2024-089 (2024-10-15)
**System**: Server_A
**Issue**: Connection pool exhausted (100/100)
**Fix**: Increased max_connections from 100 to 250
**Duration**: 23 minutes
```

**runbooks.md**
```markdown
## Runbook #47: Database Connection Timeout
**Owner**: Sarah Chen
**Duration**: 15-30 minutes
**Steps**:
1. Check connections: `SELECT count(*) FROM pg_stat_activity;`
2. Increase max_connections in postgresql.conf
3. Restart PostgreSQL
```

**contacts.md**
```markdown
#### Sarah Chen - Senior Database Engineer
- **Email**: sarah.chen@company.com
- **Phone**: ext. 5432
- **On-Call**: This week
```

After adding files: `python embed_knowledge.py`

---

## Architecture

```
User Input → Sanitization (Groq/Claude only) → RAG Engine
                                                    ↓
                                             System Detection
                                                    ↓
                                             Vector Search (ChromaDB)
                                                    ↓
                                             Context Retrieval
                                                    ↓
                                    Multi-Agent System (optional)
                                    ┌─────────┬─────────┬─────────┐
                                RootCause  Impact   Actions  Knowledge
                                    └─────────┴─────────┴─────────┘
                                                    ↓
                                             Consensus Check
                                                    ↓
                                    Backend (Groq/Claude/Ollama)
                                                    ↓
                                             Final Analysis
```

---

## Configuration

**.env file:**
```bash
BACKEND=groq                    # groq, claude, or ollama
GROQ_API_KEY=your_key
ANTHROPIC_API_KEY=your_key      # for Claude
ENABLE_MULTI_AGENT=false        # true for deeper analysis
ENABLE_SANITIZATION=true        # redact PII before API calls
```

---

## Usage Tips

- **Single-agent**: Fast, good for known issues
- **Multi-agent**: Slower (4x), validates analysis, catches errors
- **Sanitization**: Automatically redacts emails, IPs, secrets (Groq/Claude)
- **Ollama**: Runs 100% local, no sanitization needed

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Collection not found" | Run `python embed_knowledge.py` |
| "API key invalid" | Check `.env` file has correct key |
| "Ollama not responding" | Run `ollama serve` in another terminal |
| Wrong contact returned | Add server aliases to `servers.md`, re-embed |

---

## Files

```
logguard/
├── app.py                 # Streamlit UI
├── rag_engine.py         # RAG logic + system detection
├── multi_agent.py        # 4-agent system with consensus
├── embed_knowledge.py    # Embeds .md files into ChromaDB
├── sanitizer.py          # PII/secret redaction
├── requirements.txt
└── knowledge_base/       # Your company docs (create these)
    ├── servers.md
    ├── incidents.md
    ├── runbooks.md
    └── contacts.md
```

---

## License

MIT