from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import opengradient as og
import os
import uuid
from dotenv import load_dotenv

# Load your private key from the .env file
load_dotenv()

# ─────────────────────────────────────────
# START UP THE APP
# ─────────────────────────────────────────

app = FastAPI()

# This allows your index.html (opened directly in browser) to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect to OpenGradient using your wallet private key
client = og.Client(private_key=os.getenv("OG_PRIVATE_KEY"))

# Approve OPG spending once when the server starts
# This lets the SDK pay for AI inference automatically
client.llm.ensure_opg_approval(opg_amount=10.0)

# ─────────────────────────────────────────
# THE AI FIGHTERS
# ─────────────────────────────────────────

FIGHTERS = {
    "degen": {
        "name": "Chad Degen",
        "title": "The 100x Moonboy",
        "emoji": "🚀",
        "system_prompt": (
            "You are Chad Degen, an overconfident crypto trader who thinks every coin "
            "is going 100x. You roast opponents by mocking their weak hands, no conviction, "
            "and inability to see the vision. Keep roasts to 2-3 punchy sentences. Be funny, not cruel."
        ),
    },
    "doomer": {
        "name": "Doomer Dave",
        "title": "The Bear Who Was Always Right",
        "emoji": "🐻",
        "system_prompt": (
            "You are Doomer Dave, a perpetual crypto bear who predicted every crash. "
            "You roast opponents by citing their losses, their bags, and their naive optimism. "
            "Keep roasts to 2-3 punchy sentences. Be funny, not cruel."
        ),
    },
    "boomer": {
        "name": "Boomer Bob",
        "title": "The Just Buy Index Funds Guy",
        "emoji": "👴",
        "system_prompt": (
            "You are Boomer Bob, a traditional finance guy who thinks crypto is a scam. "
            "You roast opponents by comparing crypto to Beanie Babies and telling them to "
            "call their financial advisor. Keep roasts to 2-3 punchy sentences. Be funny, not cruel."
        ),
    },
    "nft_bro": {
        "name": "NFT Bro",
        "title": "The JPEG Evangelist",
        "emoji": "🖼️",
        "system_prompt": (
            "You are NFT Bro, who genuinely believes owning a JPEG is the future of ownership. "
            "You roast opponents by questioning if they understand digital ownership and the metaverse. "
            "Keep roasts to 2-3 punchy sentences. Be funny, not cruel."
        ),
    },
}

# ─────────────────────────────────────────
# IN-MEMORY BATTLE STORAGE
# ─────────────────────────────────────────

battles = {}

# In-memory leaderboard — tracks total wins per fighter
leaderboard = {fid: 0 for fid in FIGHTERS}

# ─────────────────────────────────────────
# DATA SHAPES (what the frontend sends us)
# ─────────────────────────────────────────

class StartBattleRequest(BaseModel):
    fighter1_id: str
    fighter2_id: str

class RoastRequest(BaseModel):
    battle_id: str
    attacking_fighter_id: str

class VoteRequest(BaseModel):
    battle_id: str
    fighter_id: str
    voter_address: str

class FinalizeRequest(BaseModel):
    battle_id: str

# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────

@app.get("/")
def home():
    # Simple check to confirm the server is running
    return {"status": "AI Roast Battle Arena is live 🔥"}


@app.get("/api/fighters")
def get_fighters():
    # Returns all available fighters to the frontend
    result = {}
    for id, f in FIGHTERS.items():
        result[id] = {
            "name": f["name"],
            "title": f["title"],
            "emoji": f["emoji"],
        }
    return result


@app.post("/api/start-battle")
def start_battle(req: StartBattleRequest):
    # Creates a new battle between two chosen fighters
    if req.fighter1_id not in FIGHTERS or req.fighter2_id not in FIGHTERS:
        return {"error": "Invalid fighter selected"}

    if req.fighter1_id == req.fighter2_id:
        return {"error": "A fighter cannot battle themselves"}

    battle_id = str(uuid.uuid4())[:8]

    battles[battle_id] = {
        "id": battle_id,
        "fighter1": req.fighter1_id,
        "fighter2": req.fighter2_id,
        "round": 1,
        "last_roast": "The battle begins... who will throw the first punch?",
        "last_attacker": None,
        "round_history": [],
        "status": "active",
        "votes": {req.fighter1_id: 0, req.fighter2_id: 0},
        "voters": [],
        "winner": None,
        "verdict": None,
    }

    return {"battle_id": battle_id, "battle": battles[battle_id]}


@app.post("/api/generate-roast")
async def generate_roast(req: RoastRequest):
    # Calls OpenGradient LLM to generate a roast
    # Each call costs a tiny amount of $OPG on Base Sepolia

    if req.battle_id not in battles:
        return {"error": "Battle not found"}

    battle = battles[req.battle_id]

    if battle["status"] != "active":
        return {"error": "This battle is already over"}

    if req.attacking_fighter_id not in [battle["fighter1"], battle["fighter2"]]:
        return {"error": "This fighter is not in this battle"}

    attacker = FIGHTERS[req.attacking_fighter_id]

    # Figure out the opponent
    defender_id = battle["fighter2"] if req.attacking_fighter_id == battle["fighter1"] else battle["fighter1"]
    defender = FIGHTERS[defender_id]

    messages = [
        {
            "role": "system",
            "content": attacker["system_prompt"],
        },
        {
            "role": "user",
            "content": (
                f"You are battling {defender['name']} ({defender['title']}). "
                f"Their last line was: \"{battle['last_roast']}\". "
                f"Roast them back hard in 2-3 sentences. Stay in character."
            ),
        },
    ]

    try:
        result = client.llm.chat(
            model=og.TEE_LLM.GPT_4O,
            messages=messages,
            max_tokens=150,
            temperature=0.9,
        )

        roast_text = result.chat_output["content"]
        payment_hash = result.payment_hash

        battle["round_history"].append({
            "round": battle["round"],
            "attacker": req.attacking_fighter_id,
            "attacker_name": attacker["name"],
            "attacker_emoji": attacker["emoji"],
            "roast": roast_text,
            "payment_hash": payment_hash,
        })

        battle["last_roast"] = roast_text
        battle["last_attacker"] = req.attacking_fighter_id
        battle["round"] += 1

        # End the battle after 6 total roasts
        if battle["round"] > 6:
            battle["status"] = "voting"

        return {
            "roast": roast_text,
            "attacker_name": attacker["name"],
            "attacker_emoji": attacker["emoji"],
            "payment_hash": payment_hash,
            "round": battle["round"] - 1,
            "battle_status": battle["status"],
        }

    except Exception as e:
        print(f"LLM Error: {e}")
        return {"error": "The AI fighter is catching their breath, try again!"}


@app.get("/api/battle-state/{battle_id}")
def get_battle_state(battle_id: str):
    # Returns the full current state of a battle
    if battle_id not in battles:
        return {"error": "Battle not found"}
    return battles[battle_id]


@app.post("/api/cast-vote")
def cast_vote(req: VoteRequest):
    # Records a vote for a fighter during the voting window
    if req.battle_id not in battles:
        return {"error": "Battle not found"}

    battle = battles[req.battle_id]

    if battle["status"] != "voting":
        return {"error": "This battle is not in voting phase"}

    if req.fighter_id not in [battle["fighter1"], battle["fighter2"]]:
        return {"error": "Invalid fighter"}

    # Check if this wallet already voted
    if req.voter_address.lower() in [v.lower() for v in battle["voters"]]:
        return {"error": "You already voted in this battle!"}

    battle["votes"][req.fighter_id] += 1
    battle["voters"].append(req.voter_address.lower())

    return {
        "success": True,
        "fighter_voted": FIGHTERS[req.fighter_id]["name"],
        "votes": battle["votes"],
    }


@app.post("/api/finalize-battle")
async def finalize_battle(req: FinalizeRequest):
    # Called when the 10-second voting countdown ends
    # Sends all roasts + vote counts to the AI Judge
    # AI Judge reads everything and declares a winner with a funny verdict

    if req.battle_id not in battles:
        return {"error": "Battle not found"}

    battle = battles[req.battle_id]

    if battle["status"] not in ["voting", "finished"]:
        return {"error": "Battle is not ready to be finalized"}

    # If already finalized, just return the saved result
    if battle["status"] == "finished" and battle["winner"]:
        return {
            "winner_id": battle["winner"],
            "winner_name": FIGHTERS[battle["winner"]]["name"],
            "winner_emoji": FIGHTERS[battle["winner"]]["emoji"],
            "verdict": battle["verdict"],
            "votes": battle["votes"],
        }

    f1 = FIGHTERS[battle["fighter1"]]
    f2 = FIGHTERS[battle["fighter2"]]

    # Build a readable roast transcript for the judge
    transcript = ""
    for entry in battle["round_history"]:
        transcript += f'{entry["attacker_name"]}: "{entry["roast"]}"\n'

    f1_votes = battle["votes"].get(battle["fighter1"], 0)
    f2_votes = battle["votes"].get(battle["fighter2"], 0)

    # Build the AI Judge prompt
    judge_prompt = (
        f"You are the AI Judge of a crypto roast battle between "
        f"{f1['name']} ({f1['title']}) and {f2['name']} ({f2['title']}).\n\n"
        f"Here is the full roast transcript:\n{transcript}\n"
        f"Vote counts: {f1['name']} got {f1_votes} votes, {f2['name']} got {f2_votes} votes.\n\n"
        f"Consider the quality of roasts, funniness, and crowd votes. "
        f"Respond in this exact format and nothing else:\n"
        f"WINNER: [fighter name]\n"
        f"VERDICT: [one funny sentence explaining why they won]"
    )

    try:
        result = client.llm.chat(
            model=og.TEE_LLM.GPT_4O,
            messages=[{"role": "user", "content": judge_prompt}],
            max_tokens=100,
            temperature=0.7,
        )

        judge_response = result.chat_output["content"]

        # Parse the judge's response
        winner_name = None
        verdict = "The crowd has spoken!"

        for line in judge_response.strip().split("\n"):
            if line.startswith("WINNER:"):
                winner_name = line.replace("WINNER:", "").strip()
            if line.startswith("VERDICT:"):
                verdict = line.replace("VERDICT:", "").strip()

        # Match the winner name back to a fighter ID
        winner_id = battle["fighter1"]  # default to fighter1 if parsing fails
        for fid, fighter in FIGHTERS.items():
            if fighter["name"].lower() in (winner_name or "").lower():
                winner_id = fid
                break

        # Save result and update leaderboard
        battle["winner"] = winner_id
        battle["verdict"] = verdict
        battle["status"] = "finished"
        leaderboard[winner_id] += 1

        return {
            "winner_id": winner_id,
            "winner_name": FIGHTERS[winner_id]["name"],
            "winner_emoji": FIGHTERS[winner_id]["emoji"],
            "verdict": verdict,
            "votes": battle["votes"],
        }

    except Exception as e:
        print(f"Judge Error: {e}")
        return {"error": "The judge is still deliberating, try again!"}


@app.get("/api/leaderboard")
def get_leaderboard():
    # Returns total wins per fighter across all battles
    sorted_board = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)

    return [
        {
            "fighter_id": fid,
            "name": FIGHTERS[fid]["name"],
            "emoji": FIGHTERS[fid]["emoji"],
            "wins": wins,
        }
        for fid, wins in sorted_board
    ]