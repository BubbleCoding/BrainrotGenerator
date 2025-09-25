import os
import time
import json
import datetime
import requests
import asyncio
from typing import Dict, Any, Set

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.websockets import WebSocketDisconnect
from dotenv import load_dotenv
from openai import OpenAI

# ---------------------------
# Optional GPIO (Pi only)
# ---------------------------
GPIO_AVAILABLE = False
try:
    from gpiozero import Button, Device  # type: ignore
    GPIO_AVAILABLE = True
except Exception:
    GPIO_AVAILABLE = False

# Try to import PiGPIOFactory to force a stable backend
try:
    from gpiozero.pins.pigpio import PiGPIOFactory  # type: ignore
except Exception:  # pragma: no cover
    PiGPIOFactory = None  # type: ignore

# ---------------------------
# Env & OpenAI
# ---------------------------
load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY is not set. Image generation will fail.")
cli = OpenAI(api_key=OPENAI_API_KEY)

ROLE_PROMPT = """You are a creator of artistic prompts for DALL·E 3 image generation.
You are generating a prompt to generate brainrot art.
You will receive: (1) an animal, (2) a fruit, and (3) an object.
Tasks:
1) Generate an Italian-sounding name (no real people) based on the animal, fruit and object. Keep it tasteful, 2–4 words max.
2) Write a vivid, specific prompt for DALL·E 3 that fuses the animal, fruit and object into a single coherent character with clear materials, textures, shapes, and composition. Describe how the animal and the fruit and object are merged. Avoid story; focus on visual description and style. Only include the character in the image. The background should be a simple color or gradient. The art style is oil painting.
3) Do NOT include brands or copyrighted style names. Keep it PG-13.
Return ONLY valid JSON with keys: italian_name, prompt.
"""
JSON_INSTRUCTION = 'Return ONLY JSON like: {"italian_name":"...", "prompt":"..."}'

REELS: Dict[int, list] = {
    0: ["Cat","Dog","Shark","Octopus","Dragon","Snake","Elephant","Lion","Bear","Horse",
        "Rabbit","Wolf","Tiger","Fox","Dolphin","Eagle","Owl","Frog","Penguin","Giraffe",
        "Zebra","Kangaroo","Crocodile","Parrot","Bat","Whale","Ant","Bee","Crab","Lizard"],
    1: ["Apple","Banana","Orange","Watermelon","Grapes","Pineapple","Mango","Lemon","Strawberry","Blueberry",
        "Raspberry","Peach","Pear","Kiwi","Cherry","Pomegranate","Coconut","Fig","Plum","Apricot",
        "Papaya","Melon","Lychee","Passionfruit","Guava","Dragonfruit","Blackcurrant","Mulberry","Cranberry","Gooseberry"],
    2: ["Sword","Shield","Lantern","Chair","Table","Clock","Mirror","Crown","Helmet","Book",
        "Scroll","Pen","Cup","Bottle","Key","Lock","Dice","Card","Bell","Violin",
        "Drum","Brush","Palette","Hammer","Anvil","Telescope","Compass","Anchor","Rope","Backpack"]
}

state: Dict[str, Any] = {
    "spinning": [True, True, True],
    "result":   [None, None, None],
    "session_seed": 0
}

app = FastAPI()

# ---------------------------
# Static & routes
# ---------------------------
@app.get("/", include_in_schema=False)
def index():
    return FileResponse("frontend/index.html")

@app.get("/gallery.html", include_in_schema=False)
def gallery():
    return FileResponse("frontend/gallery.html")

app.mount("/static", StaticFiles(directory="frontend", html=False), name="static")

@app.get("/gallery_manifest")
def gallery_manifest():
    path = os.path.join("frontend","generated","manifest.jsonl")
    if not os.path.exists(path):
        return []
    with open(path,"r",encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

# ---------------------------
# WS broadcast & clients
# ---------------------------
clients: Set[WebSocket] = set()
_clients_lock = asyncio.Lock()

async def broadcast(payload: dict):
    dead: Set[WebSocket] = set()
    async with _clients_lock:
        for ws in list(clients):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.add(ws)
        for ws in dead:
            clients.discard(ws)

# ---------------------------
# Prompt & image generation
# ---------------------------
def generate_prompt_and_name(animal: str, fruit: str, object: str, retries: int = 3):
    user_block = f"Animal: {animal}\\Fruit: {fruit}\\nObject: {object}\\n"
    last_err = None
    for attempt in range(1, retries+1):
        try:
            r = cli.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": ROLE_PROMPT},
                    {"role": "user", "content": user_block},
                    {"role": "system", "content": JSON_INSTRUCTION},
                ],
                temperature=0.7,
            )
            content = r.choices[0].message.content.strip()
            if not content.startswith("{"):
                i, j = content.find("{"), content.rfind("}")
                if i != -1 and j != -1:
                    content = content[i:j+1]
            data = json.loads(content)
            return data["italian_name"].strip(), data["prompt"].strip()
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(min(2 ** attempt, 10))
            else:
                raise RuntimeError(f"Prompt generation failed: {e}") from e
    raise RuntimeError(f"Unexpected: {last_err}")

def generate_image(prompt: str) -> str:
    resp = cli.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size=os.getenv("IMAGE_SIZE","1024x1024"),
        quality=os.getenv("IMAGE_QUALITY","standard"),
        style=os.getenv("IMAGE_STYLE","vivid"),
        n=1,
    )
    url = resp.data[0].url
    if not url:
        raise RuntimeError("No image URL from Images API.")
    r = requests.get(url, timeout=60); r.raise_for_status()
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"slot_{ts}.png"
    out_dir = os.path.join("frontend","generated"); os.makedirs(out_dir, exist_ok=True)
    fpath = os.path.join(out_dir, fname)
    with open(fpath,"wb") as f: f.write(r.content)
    return fpath

# ---------------------------
# Shared input handler
# ---------------------------
async def handle_input(data: Dict[str, Any]):
    msg_type = data.get("type")

    if msg_type == "stop_reel":
        idx = int(data["reel"])
        if 0 <= idx < 3 and state["spinning"][idx]:
            sym = data.get("symbol")
            items = REELS[idx]
            if sym in items:
                symbol = sym
            else:
                t = time.time_ns()
                seed = (state.get("session_seed", 0) or 0) ^ (idx * 7919) ^ (t & 0xFFFFFFFF)
                symbol = items[seed % len(items)]
            state["spinning"][idx] = False
            state["result"][idx] = symbol
            await broadcast({"type": "reel_stopped", "reel": idx, "symbol": symbol})

            if all(not s for s in state["spinning"]):
                await broadcast({"type": "all_stopped", "result": state["result"]})
                try:
                    animal, fruit, obj = state["result"]
                    italian_name, dalle_prompt = generate_prompt_and_name(
                        "Player", animal, fruit or obj
                    )
                    img_path = generate_image(dalle_prompt)
                    url = "/static/generated/" + os.path.basename(img_path)
                    entry = {
                        "url": url,
                        "italian_name": italian_name,
                        "prompt": dalle_prompt,
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    manifest_path = os.path.join("frontend","generated","manifest.jsonl")
                    with open(manifest_path,"a",encoding="utf-8") as mf:
                        mf.write(json.dumps(entry) + "\n")
                    await broadcast({"type": "image_ready","url":url,"prompt":dalle_prompt,"italian_name":italian_name})
                except Exception as e:
                    await broadcast({"type":"error","message":str(e)})
    elif msg_type == "reset":
        state["spinning"] = [True, True, True]
        state["result"] = [None, None, None]
        state["session_seed"] = 0
        await broadcast({"type": "reset_ok"})

# ---------------------------
# WebSocket endpoint
# ---------------------------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    async with _clients_lock:
        clients.add(ws)

    state["spinning"] = [True, True, True]
    state["result"] = [None, None, None]
    state["session_seed"] = int(time.time() * 1000) % 1_000_000

    try:
        await ws.send_text(json.dumps({"type":"init","reels":REELS}))
        while True:
            try:
                msg = await ws.receive_text()
            except WebSocketDisconnect:
                break
            data = json.loads(msg)
            await handle_input(data)
    finally:
        async with _clients_lock:
            clients.discard(ws)

# ---------------------------
# GPIO buttons -> same handler
# ---------------------------
@app.on_event("startup")
async def gpio_startup():
    if not GPIO_AVAILABLE:
        print("[GPIO] gpiozero not available; skipping GPIO setup.")
        return

    if PiGPIOFactory is not None:
        try:
            Device.pin_factory = PiGPIOFactory()
            print("[GPIO] Using pin factory:", type(Device.pin_factory).__name__)
        except Exception as e:
            print("[GPIO] Failed to set PiGPIOFactory:", e)
    else:
        print("[GPIO] PiGPIOFactory not importable; using default pin factory.")

    loop = asyncio.get_running_loop()

    left_btn   = Button(23, pull_up=True, bounce_time=0.1)
    middle_btn = Button(27, pull_up=True, bounce_time=0.1)
    right_btn  = Button(22, pull_up=True, bounce_time=0.1)

    def schedule(payload):
        asyncio.run_coroutine_threadsafe(broadcast({"type":"debug","msg":payload}), loop)
        asyncio.run_coroutine_threadsafe(handle_input(payload), loop)

    def on_left():
        print("[GPIO] LEFT pressed (GPIO23)")
        schedule({"type":"stop_reel","reel":0})
    def on_middle():
        print("[GPIO] MIDDLE pressed (GPIO27)")
        schedule({"type":"stop_reel","reel":1})
    def on_right():
        print("[GPIO] RIGHT pressed (GPIO22)")
        schedule({"type":"stop_reel","reel":2})

    left_btn.when_pressed = on_left
    middle_btn.when_pressed = on_middle
    right_btn.when_pressed = on_right

    print("[GPIO] Buttons active on BCM 23, 27, 22 (other leg to any GND).")
