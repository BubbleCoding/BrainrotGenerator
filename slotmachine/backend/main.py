import os, time, json, hashlib, datetime, requests
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from openai import OpenAI

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

REELS = {
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

state = {
    "spinning": [True, True, True],
    "result":   [None, None, None],
    "session_seed": 0
}

app = FastAPI()

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

clients = set()

async def broadcast(payload: dict):
    dead = set()
    for ws in list(clients):
        try:
            await ws.send_text(json.dumps(payload))
        except Exception:
            dead.add(ws)
    clients.difference_update(dead)

# -----------------------------------------------------------------------------
# GPIO integration: physical buttons send gpio_press to clients
try:
    import asyncio
    from gpiozero import Button, Device       # type: ignore
    from gpiozero.pins.pigpio import PiGPIOFactory  # type: ignore

    try:
        Device.pin_factory = PiGPIOFactory()
    except Exception:
        pass

    loop = asyncio.get_event_loop()

    def gpio_emit(index: int):
        print(f"[GPIO] Physical button pressed for reel {index}")
        asyncio.run_coroutine_threadsafe(
            broadcast({"type":"gpio_press","reel": index}),
            loop
        )

    btn_gpio_map = { 23:0, 27:1, 22:2 }
    buttons = []
    for pin, idx in btn_gpio_map.items():
        try:
            b = Button(pin, pull_up=True, bounce_time=0.05)
            b.when_pressed = lambda idx=idx: gpio_emit(idx)
            buttons.append(b)
        except Exception as e:
            print(f"[GPIO] Failed to initialize Button on GPIO {pin}: {e}")

except ImportError:
    print("[GPIO] gpiozero or pigpio not available; GPIO buttons disabled.")

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

from starlette.websockets import WebSocketDisconnect

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)

    state["spinning"] = [True, True, True]
    state["result"] = [None, None, None]
    state["session_seed"] = int(time.time() * 1000) % 1000000

    try:
        await ws.send_text(json.dumps({"type":"init","reels":REELS}))
        while True:
            try:
                msg = await ws.receive_text()
            except WebSocketDisconnect:
                break
            data = json.loads(msg)

            if data.get("type") == "stop_reel":
                idx = int(data["reel"])
                if 0 <= idx < 3 and state["spinning"][idx]:
                    sym = data.get("symbol")
                    items = REELS[idx]
                    if sym in items:
                        symbol = sym
                    else:
                        t = time.time_ns()
                        symbol = items[(t ^ (idx*7919)) % len(items)]
                    state["spinning"][idx] = False
                    state["result"][idx] = symbol
                    await broadcast({"type":"reel_stopped","reel":idx,"symbol":symbol})
                    if all(not s for s in state["spinning"]):
                        await broadcast({"type":"all_stopped","result":state["result"]})
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
                                mf.write(json.dumps(entry)+"\n")
                            await broadcast({"type":"image_ready","url":url,"prompt":dalle_prompt,"italian_name":italian_name})
                        except Exception as e:
                            await broadcast({"type":"error","message":str(e)})

            elif data.get("type") == "reset":
                state["spinning"] = [True, True, True]
                state["result"] = [None, None, None]
                state["session_seed"] = 0
                await broadcast({"type":"reset_ok"})
    finally:
        clients.discard(ws)
