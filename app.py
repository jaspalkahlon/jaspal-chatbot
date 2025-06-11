import os
import pickle
import re
import csv
import numpy as np
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ─── Load environment ───
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_KEY = os.getenv("ADMIN_KEY", "changeme")
CREDS_PATH = os.getenv("GSPREAD_CREDENTIALS")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# ─── Initialize OpenAI client ───
from openai import OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# ─── FastAPI setup ───
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://chat.prodifyteam.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── FAISS index & system prompt ───
INDEX_FILE = "index.faiss"
CHUNKS_FILE = "chunks.pkl"
EMBED_MODEL = "text-embedding-ada-002"
CHAT_MODEL = "gpt-4-turbo"

# Load editable system prompt (once)
with open("prompts/system_prompt.txt", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read().strip()

# Load Prompt Bank CSV with robust encoding
PROMPT_BANK = []
csv_path = os.path.join("data", "prompt_bank.csv")
if os.path.exists(csv_path):
    with open(csv_path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tmpl = row.get("template", "").strip()
            if tmpl:
                PROMPT_BANK.append(tmpl)
    if PROMPT_BANK:
        SYSTEM_PROMPT += "\n\n" + "### Prompt Bank Templates\n" + "\n".join(PROMPT_BANK)

# Load FAISS index + chunks
try:
    import faiss
    if os.path.exists(INDEX_FILE) and os.path.exists(CHUNKS_FILE):
        index = faiss.read_index(INDEX_FILE)
        with open(CHUNKS_FILE, "rb") as f:
            chunks = pickle.load(f)
    else:
        index, chunks = None, []
except ModuleNotFoundError:
    index, chunks = None, []
    print("Warning: FAISS not found. Context-based responses disabled.")

def get_context(query: str, k: int = 3) -> str:
    if not index:
        return ""
    resp = client.embeddings.create(model=EMBED_MODEL, input=query)
    vector = np.array([resp.data[0].embedding], dtype="float32")
    _, I = index.search(vector, k)
    return "\n\n".join(chunks[i] for i in I[0])

# ─── Google Sheets setup ───
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_PATH, scope)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID)

def get_worksheet(name: str):
    try:
        return sheet.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=name, rows="1000", cols="20")
        if name == "Leads":
            ws.append_row([
                "Session ID", "Timestamp", "Name", "Email", "Details", "Conversation"
            ])
        else:
            ws.append_row([
                "Session ID", "Timestamp", "Role", "Message", "Intent", "Quality", "Notes"
            ])
        return ws

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/chat")
async def chat_endpoint(request: dict):
    user_msg = request.get("message", "")
    session_id = request.get("session_id", "unknown")
    ts = datetime.utcnow().isoformat()

    ws_chat = get_worksheet("Chats")
    ws_chat.append_row([session_id, ts, "user", user_msg, "", "", ""])

    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    if index:
        ctx = get_context(user_msg)
        msgs.insert(1, {"role": "system", "content": f"Context:\n{ctx}"})

    resp = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=msgs,
        max_tokens=200,
        temperature=0.2,
    )
    answer = resp.choices[0].message.content.strip()

    def format_response(text: str) -> str:
        text = text.strip()
        text = re.sub(r'\*{1,2}', '', text)
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)

        def number_bullets(t: str) -> str:
            lines = t.splitlines()
            numbered = []
            count = 1
            for line in lines:
                if re.match(r'^\s*[-•]\s*(.*)', line):
                    content = re.sub(r'^\s*[-•]\s*', '', line).strip()
                    numbered.append(f"{count}. {content}")
                    count += 1
                else:
                    numbered.append(line)
            return "\n".join(numbered)

        text = number_bullets(text)
        text = text.replace(
            '🔎 What we’re solving:',
            '<p><strong>🔎 What we’re solving:</strong><br/>'
        )
        text = text.replace(
            '✅ What to focus on:',
            '</p><p><strong>✅ What to focus on:</strong><br/>'
        )
        text = text.replace(
            '❓ What next:',
            '</p><p><strong>❓ What next:</strong><br/>'
        )
        if not text.endswith('</p>'):
            text += '</p>'
        return text

    formatted_reply = format_response(answer)
    ws_chat.append_row([session_id, ts, "assistant", answer, "", "", ""])
    return {"reply": formatted_reply}

@app.post("/lead")
async def receive_lead(data: dict):
    session_id = data.get("session_id", "unknown")
    ts = datetime.utcnow().isoformat()
    name = data.get("name", "")
    email = data.get("email", "")
    details = data.get("details", "")

    ws_chat = sheet.worksheet("Chats")
    rows = ws_chat.get_all_values()[1:]
    conv_rows = [f"{r[2]}: {r[3]}" for r in rows if r[0] == session_id]
    conversation = "\n".join(conv_rows)

    ws_lead = get_worksheet("Leads")
    ws_lead.append_row([
        session_id,
        ts,
        name,
        email,
        details,
        conversation
    ])

    return {"status": "received"}

@app.post("/admin/reindex")
async def admin_reindex(x_admin_key: str = Header(...)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(403, "Forbidden")
    import subprocess, sys
    subprocess.run([sys.executable, "ingest.py"], cwd=os.path.dirname(__file__))
    try:
        import faiss
        global index, chunks
        index = faiss.read_index(INDEX_FILE)
        with open(CHUNKS_FILE, "rb") as f:
            chunks = pickle.load(f)
    except ModuleNotFoundError:
        index, chunks = None, []
    return {"status": "reindexed", "chunks": len(chunks)}

@app.post("/admin/reload_prompts")
async def reload_prompts(x_admin_key: str = Header(...)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(403, "Forbidden")
    global SYSTEM_PROMPT
    with open("prompts/system_prompt.txt", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read().strip()
    return {"status": "prompts reloaded"}
