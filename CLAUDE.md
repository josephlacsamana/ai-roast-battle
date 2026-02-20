# AI Roast Battle Arena — CLAUDE.md

## What This Project Is

A web app where two AI characters roast each other in real-time.
Users connect a MetaMask wallet (Base Sepolia testnet), vote with $OPG tokens,
and watch AI fighters battle across 3 rounds. Built on OpenGradient's verified AI infrastructure.

---

## Stack

| Layer | Tool |
|---|---|
| Frontend | Plain HTML + CSS + vanilla JS (single file to start, no framework) |
| Backend | Python FastAPI |
| AI Inference | OpenGradient Python SDK (`pip install opengradient`) |
| LLM | `og.TEE_LLM.GPT_4O` (primary), `og.TEE_LLM.CLAUDE_3_5_HAIKU` (fallback) |
| AI Judge | `og.TEE_LLM.GPT_4O` — reads all roasts and declares winner after voting closes |
| Payments | x402 via OG SDK — auto-handled inside `client.llm.chat()` |
| Blockchain | Base Sepolia testnet (Chain ID: 84532) |
| $OPG Token | `0x240b09731D96979f50B2C649C9CE10FcF9C7987F` |
| Wallet | MetaMask via `window.ethereum` — NO external wallet library in MVP |
| Frontend hosting | Vercel (free tier) |
| Backend hosting | Railway.app (free tier) |
| Database | In-memory (Python dict) for MVP — no DB needed yet |

---

## Project Structure

```
ai-roast-battle/
├── CLAUDE.md              ← you are here
├── frontend/
│   └── index.html         ← entire frontend in ONE file for MVP
├── backend/
│   ├── main.py            ← FastAPI app, all routes
│   ├── roast_engine.py    ← OpenGradient LLM calls + prompt logic
│   ├── game_state.py      ← in-memory battle state management
│   └── requirements.txt   ← opengradient fastapi uvicorn python-dotenv
├── .env                   ← OG_PRIVATE_KEY only — never commit this
└── .gitignore             ← must include .env
```

---

## Core Rules (Never Break These)

1. **One HTML file** — the entire frontend lives in `frontend/index.html`. No React, no Vite, no build step. The user has 0 coding experience and needs to just open the file.
2. **Never hardcode the private key** — always load from `.env` via `os.getenv("OG_PRIVATE_KEY")`.
3. **Testnet only** — all transactions use Base Sepolia. Never reference mainnet.
4. **Keep it simple** — if there's a simpler way to do something, always choose that. No abstraction layers in MVP.
5. **Comments everywhere** — add a plain English comment above every function explaining what it does. The user is not a developer.
6. **Error messages must be human-readable** — no raw Python tracebacks to the user. Catch errors and return `{"error": "Something went wrong, try again"}`.
7. **Always provide the full file** — never give partial snippets. The user is not a developer and needs to copy-paste the entire file every time.

---

## AI Characters (The Fighters)

Each character has a `name`, `title`, and `system_prompt` used for LLM inference.

```python
FIGHTERS = {
    "degen": {
        "name": "Chad Degen",
        "title": "The 100x Moonboy",
        "emoji": "🚀",
        "system_prompt": "You are Chad Degen, an overconfident crypto trader who thinks every coin is going 100x. You roast opponents by mocking their 'weak hands', 'no conviction', and inability to 'see the vision'. Keep roasts to 2-3 sentences. Be funny, not mean."
    },
    "doomer": {
        "name": "Doomer Dave",
        "title": "The Bear Who Was Always Right",
        "emoji": "🐻",
        "system_prompt": "You are Doomer Dave, a perpetual crypto bear who predicted every crash. You roast opponents by citing their losses, their bags, and their naive optimism. Keep roasts to 2-3 sentences. Be funny, not mean."
    },
    "boomer": {
        "name": "Boomer Bob",
        "title": "The 'Just Buy Index Funds' Guy",
        "emoji": "👴",
        "system_prompt": "You are Boomer Bob, a traditional finance guy who thinks crypto is a scam. You roast opponents by comparing crypto to Beanie Babies and suggesting they call their financial advisor. Keep roasts to 2-3 sentences. Be funny, not mean."
    },
    "nft_bro": {
        "name": "NFT Bro",
        "title": "The JPEG Evangelist",
        "emoji": "🖼️",
        "system_prompt": "You are NFT Bro, who genuinely believes owning a JPEG is the future of ownership. You roast opponents by questioning if they even understand 'digital ownership' and 'the metaverse'. Keep roasts to 2-3 sentences. Be funny, not mean."
    }
}
```

---

## Winner Logic (Phase 3)

After 6 roasts are done, the battle enters a **10-second voting window**.

When voting closes, an **AI Judge** (separate OpenGradient LLM call) reads the full roast history and all vote counts, then declares a winner with a short verdict.

### How it works:
1. Battle ends after round 6 → status set to `"voting"`
2. Frontend shows a **10-second countdown timer**
3. Users vote during the countdown (costs 0.001 $OPG)
4. When timer hits 0 → frontend calls `POST /api/finalize-battle`
5. Backend sends all roasts + vote counts to the AI Judge LLM
6. AI Judge returns a winner + a one-sentence verdict explaining why
7. Frontend shows the winner + judge's verdict on screen
8. Winner is saved to the leaderboard

### AI Judge Prompt:
```
You are the AI Judge of a crypto roast battle. 
Read the roasts below and the vote counts, then declare a winner.
Consider: quality of roasts, funniness, and crowd votes.
Respond in this format only:
WINNER: [fighter name]
VERDICT: [one funny sentence explaining why they won]
```

---

## API Endpoints

```
POST /api/start-battle        → { fighter1_id, fighter2_id } → returns battle_id
POST /api/generate-roast      → { battle_id, attacking_fighter } → returns roast text + payment_hash
POST /api/cast-vote           → { battle_id, voter_address, fighter_id } → records vote
POST /api/finalize-battle     → { battle_id } → runs AI judge, returns winner + verdict
GET  /api/battle-state/{id}   → returns full current battle state
GET  /api/leaderboard         → returns win/loss record per fighter
```

---

## Key OpenGradient Code Pattern

```python
import opengradient as og
import os

client = og.Client(private_key=os.getenv("OG_PRIVATE_KEY"))

# Call ONCE at startup
client.llm.ensure_opg_approval(opg_amount=10.0)

async def generate_roast(attacker_prompt: str, opponent_last_line: str) -> dict:
    messages = [
        {"role": "system", "content": attacker_prompt},
        {"role": "user", "content": f"Your opponent just said: '{opponent_last_line}'. Roast them back!"}
    ]
    result = client.llm.chat(
        model=og.TEE_LLM.GPT_4O,
        messages=messages,
        max_tokens=150,
        temperature=0.9  # higher = more creative/funny
    )
    return {
        "roast": result.chat_output["content"],
        "payment_hash": result.payment_hash  # Base Sepolia tx proof
    }
```

---

## Environment Variables

```bash
# .env — never commit this file
OG_PRIVATE_KEY=0x...          # MetaMask private key funded with testnet $OPG
```

Get free testnet $OPG: https://faucet.opengradient.ai

---

## Running Locally

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend — just open in browser
open frontend/index.html
# or double-click the file
```

---

## Phase Checklist

- [x] **Phase 1** — Frontend skeleton + OG LLM producing roasts (no wallet yet)
- [x] **Phase 2** — MetaMask connect + Base Sepolia voting with $OPG
- [ ] **Phase 3** — 10-second voting countdown + AI Judge declares winner + leaderboard update
- [ ] **Phase 4** — Leaderboard page + deploy to Vercel + Railway

---

## What NOT to Do

- ❌ Don't use React, Vue, or any JS framework — plain HTML only
- ❌ Don't add a real database until Phase 4+
- ❌ Don't use mainnet or real money
- ❌ Don't add authentication — wallet address IS the identity
- ❌ Don't make the backend do wallet signing — signing happens in the user's MetaMask
- ❌ Don't use ML Inference / Model Hub in v1 — LLM inference only
- ❌ Don't give partial code snippets — always give the full file
