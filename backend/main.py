import os, time, json, hashlib, datetime, requests
from functools import partial
from fastapi import FastAPI, WebSocket, Depends, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse
from dotenv import load_dotenv
from openai import OpenAI
from .auth import authenticate, verify_ws_token, create_token, verify_password, USERNAME, PASSWORD_HASH, SECRET_KEY
from fastapi import Request
from jose import JWTError, jwt


load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY is not set. Image generation will fail.")
cli = OpenAI(api_key=OPENAI_API_KEY)

ROLE_PROMPT = """You are a creator of artistic prompts for DALL·E 3 image generation.
You are generating a prompt to generate brainrot art.
You will receive: (1) an animal, (2) a fruit, and (3) an object.
Tasks:
1) Generate an Italian-sounding name (no real people) based on the animal, fruit and object. Keep it tasteful, 2-4 words max.
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
    "session_seed": 0,
    "generating": False,
}

app = FastAPI()

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    protected = ["/"]
    if request.url.path in protected:
        token = request.cookies.get("access_token")
        if not token:
            return RedirectResponse(url="/login")
        try:
            jwt.decode(token.replace("Bearer ", ""), SECRET_KEY, algorithms=["HS256"])
        except JWTError:
            return RedirectResponse(url="/login")
    return await call_next(request)


@app.get("/login", include_in_schema=False)
def login_page():
    return FileResponse("frontend/login.html")
    
@app.post("/login", include_in_schema=False)
def login(username: str = Form(...), password: str = Form(...)):
    if username != USERNAME or not verify_password(password, PASSWORD_HASH):
        return RedirectResponse(url="/login?error=1", status_code=303)
    token = create_token(username)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("access_token", f"Bearer {token}", httponly=True, max_age=86400)
    return response

@app.get("/logout", include_in_schema=False)
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response

@app.get("/", include_in_schema=False)
def index():
    return FileResponse("frontend/index.html")

@app.get("/gallery", include_in_schema=False)
@app.get("/gallery.html", include_in_schema=False)
def gallery():
    return FileResponse("frontend/gallery.html")

@app.get("/gallery_manifest")
def gallery_manifest():
    path = os.path.join("frontend", "generated", "manifest.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

app.mount("/static", StaticFiles(directory="frontend", html=False), name="static")

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

    def gpio_emit(index: int, action: str):
        asyncio.run_coroutine_threadsafe(
            broadcast({"type":"gpio_press","reel": index, "action": action}),
            loop
        )

    btn_gpio_map = { 23:0, 27:1, 22:2 }
    buttons = []
    for pin, idx in btn_gpio_map.items():
        try:
            b = Button(pin, pull_up=True, bounce_time=0.1)
            # Handle both press and release for switches
            b.when_pressed = lambda idx=idx: gpio_emit(idx, "pressed")
            b.when_released = lambda idx=idx: gpio_emit(idx, "released")
            buttons.append(b)
        except Exception as e:
            print(f"[GPIO] Failed to initialize Button on GPIO {pin}: {e}")

except ImportError:
    print("[GPIO] gpiozero or pigpio not available; GPIO buttons disabled.")

def generate_prompt_and_name(animal: str, fruit: str, object: str, retries: int = 3):
    user_block = f"Animal: {animal}\\Fruit: {fruit}\\Object: {object}\\n"
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
    state["generating"] = False

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
                        await asyncio.sleep(0.1)
                        await broadcast({"type":"all_stopped","result":state["result"]})
                        
            elif data.get("type") == "start_generation":
                if state["generating"]:
                    await ws.send_text(json.dumps({"type":"error","message":"Generation already in progress. Please wait."}))
                    continue
                if all(not s for s in state["spinning"]) and all(r is not None for r in state["result"]):
                    try:
                        animal, fruit, obj = state["result"]
                        state["generating"] = True
                        await broadcast({"type":"generation_started"})
                        
                        # Generate prompt with retry logic
                        try:
                            loop = asyncio.get_running_loop()
                            italian_name, dalle_prompt = await loop.run_in_executor(
                                None,
                                partial(generate_prompt_and_name, animal, fruit, obj)
                            )
                        except Exception as e:
                            print(f"[ERROR] Prompt generation failed: {e}")
                            await broadcast({"type":"error","message":f"Failed to generate prompt: {str(e)}"})
                            # Reset state to allow retry
                            state["spinning"] = [True, True, True]
                            state["result"] = [None, None, None]
                            state["generating"] = False
                            continue
                        
                        # Generate image with better error handling
                        try:
                            img_path = await loop.run_in_executor(
                                None,
                                partial(generate_image, dalle_prompt)
                            )
                        except Exception as e:
                            print(f"[ERROR] Image generation failed: {e}")
                            await broadcast({"type":"error","message":f"Failed to generate image: {str(e)}"})
                            # Reset state to allow retry
                            state["spinning"] = [True, True, True]
                            state["result"] = [None, None, None]
                            state["generating"] = False
                            continue
                        
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
                        state["generating"] = False
                    except Exception as e:
                        print(f"[ERROR] Unexpected error: {e}")
                        await broadcast({"type":"error","message":f"Unexpected error: {str(e)}"})
                        # Reset state to allow retry
                        state["spinning"] = [True, True, True]
                        state["result"] = [None, None, None]
                        state["generating"] = False
                else:
                    await broadcast({"type":"error","message":"Invalid state. Please reset and try again."})

            elif data.get("type") == "reset":
                if state["generating"]:
                    await ws.send_text(json.dumps({"type":"error","message":"Cannot reset while generation is running."}))
                    continue
                state["spinning"] = [True, True, True]
                state["result"] = [None, None, None]
                state["session_seed"] = 0
                state["generating"] = False
                await broadcast({"type":"reset_ok"})
    finally:
        clients.discard(ws)
