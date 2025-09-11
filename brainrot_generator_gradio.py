import os, re, json, time, datetime, requests, glob
from typing import Tuple, List, Dict, Any
from openai import OpenAI, APIError, RateLimitError, APIConnectionError
from PIL import Image
from io import BytesIO
import gradio as gr

# ---------- Core (same as before) ----------
ROLE_PROMPT = """You are a creator of artistic prompts for DALL·E 3 image generation.
You will receive: (1) a person's name, (2) an animal, and (3) a fruit or object.
Tasks:
1) Convert the person's name into a fun, Italian-sounding name (no real people). Keep it tasteful, 2–4 words max.
2) Write a vivid, specific prompt for DALL·E 3 that fuses the animal and fruit/object into a single coherent character with clear materials, textures, shapes, and composition. Avoid story; focus on visual description and style.
3) Do NOT include camera brands or copyrighted style names. Keep it PG-13.
Return ONLY valid JSON with keys: italian_name, prompt.
"""
JSON_INSTRUCTION = 'Return ONLY JSON like: {"italian_name":"...", "prompt":"..."}'

IMAGES_DIR = "images"
MANIFEST = os.path.join(IMAGES_DIR, "manifest.jsonl")

def client():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    return OpenAI(api_key=key)

def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w\s.-]", "", name).strip()
    return re.sub(r"\s+", "_", cleaned) or "character"

def backoff(attempt: int):
    time.sleep(min(2 ** attempt, 10) + 0.1 * attempt)

def ensure_dirs():
    os.makedirs(IMAGES_DIR, exist_ok=True)

def append_manifest(entry: Dict[str, Any]):
    ensure_dirs()
    with open(MANIFEST, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def abbrev(text: str, max_len: int = 120) -> str:
    text = (text or "").strip().replace("\n", " ")
    return (text[:max_len] + "…") if len(text) > max_len else text


def read_manifest() -> List[Dict[str, Any]]:
    if not os.path.exists(MANIFEST):
        return []
    rows = []
    with open(MANIFEST, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows

def generate_prompt_and_name(cli: OpenAI, name: str, animal: str, thing: str, retries: int = 3) -> Tuple[str, str]:
    user_block = f"Name: {name}\nAnimal: {animal}\nFruit_or_Object: {thing}\n"
    last_err = None
    for attempt in range(1, retries + 1):
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
                backoff(attempt)
            else:
                raise RuntimeError(f"Prompt generation failed: {e}") from e
    raise RuntimeError(f"Unexpected: {last_err}")

def generate_image_bytes(cli: OpenAI, prompt: str, size="1024x1024", quality="standard", style="vivid", retries: int = 3) -> bytes:
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = cli.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality=quality,
                style=style,
                n=1,
            )
            url = resp.data[0].url
            if not url:
                raise RuntimeError("No image URL returned.")
            img = requests.get(url, timeout=30)
            img.raise_for_status()
            return img.content
        except (APIError, RateLimitError, APIConnectionError, requests.RequestException) as e:
            last_err = e
            if attempt < retries:
                backoff(attempt)
            else:
                raise RuntimeError(f"Image generation failed: {e}") from e
    raise RuntimeError(f"Unexpected: {last_err}")

# ---------- Timeline helpers ----------
def parse_ts_from_filename(path: str) -> str:
    # expects *_YYYYMMDD_HHMMSS.png
    base = os.path.basename(path)
    m = re.search(r"_(\d{8}_\d{6})\.", base)
    return m.group(1) if m else ""

def human_ts(ts_compact: str) -> str:
    # 20250911_121530 -> 2025-09-11 12:15:30
    try:
        dt = datetime.datetime.strptime(ts_compact, "%Y%m%d_%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts_compact

def build_gallery_items() -> List[List[str]]:
    """
    Returns [[image_path, caption], ...] newest-first.
    Caption includes: ItalianName — YYYY-MM-DD HH:MM:SS\nShort prompt
    Falls back to scanning files if no manifest.
    """
    ensure_dirs()
    items = []
    manifest = read_manifest()
    if manifest:
        for row in manifest:
            fpath = row.get("filepath")
            if not fpath or not os.path.exists(fpath):
                continue
            italian = row.get("italian_name", "Unknown")
            ts = row.get("timestamp") or parse_ts_from_filename(fpath)
            prompt = row.get("prompt", "")
            cap = f"{italian} — {human_ts(ts)}\n{abbrev(prompt)}"
            items.append([fpath, cap, ts])
    else:
        # Fallback: filename + parsed timestamp, no prompt
        for fpath in glob.glob(os.path.join(IMAGES_DIR, "*.png")):
            ts = parse_ts_from_filename(fpath)
            cap = f"{os.path.basename(fpath)} — {human_ts(ts)}"
            items.append([fpath, cap, ts])
    # Newest first; unknown timestamps go last
    items.sort(key=lambda x: x[2], reverse=True)
    return [[x[0], x[1]] for x in items]

def details_for_image(selected_index: int):
    items = build_gallery_items()
    if not items or selected_index is None or selected_index < 0 or selected_index >= len(items):
        return "", ""
    # find manifest row by path
    path = items[selected_index][0]
    data = None
    for row in read_manifest():
        if row.get("filepath") == path or row.get("filename") == path:
            data = row
            break
    if not data:
        # fallback minimal
        ts = parse_ts_from_filename(path)
        info = f"File: {path}\nTimestamp: {human_ts(ts)}"
        return path, info
    info = (
        f"🧾 Name: {data.get('italian_name','Unknown')}\n"
        f"🕒 Created: {human_ts(data.get('timestamp',''))}\n"
        f"📁 File: {path}\n"
        f"🎨 Size/Quality/Style: {data.get('size','?')} • {data.get('quality','?')} • {data.get('style','?')}\n\n"
        f"🧠 Prompt:\n{data.get('prompt','')}"
    )
    return path, info

# ---------- Gradio callbacks ----------
def make_character(name, animal, thing, size, quality, style):
    cli = client()
    italian_name, dalle_prompt = generate_prompt_and_name(cli, name, animal, thing)
    img_bytes = generate_image_bytes(cli, dalle_prompt, size=size, quality=quality, style=style)

    ensure_dirs()
    ts_compact = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{sanitize_filename(italian_name)}_{ts_compact}.png"
    fpath = os.path.join(IMAGES_DIR, fname)
    with open(fpath, "wb") as f:
        f.write(img_bytes)

    # log metadata to manifest
    append_manifest({
        "filepath": fpath,
        "italian_name": italian_name,
        "timestamp": ts_compact,
        "size": size,
        "quality": quality,
        "style": style,
        "prompt": dalle_prompt
    })


    # return preview and info
    info = f"✅ Saved: {fpath}\n🧾 Name: {italian_name}\n🕒 {human_ts(ts_compact)}\n🎨 {size} • {quality} • {style}\n\n🧠 Prompt:\n{dalle_prompt}"
    pil_img = Image.open(BytesIO(img_bytes))
    # also update timeline gallery immediately
    gallery = build_gallery_items()
    return pil_img, info, gallery

def load_timeline():
    return build_gallery_items()

def on_select(evt: gr.SelectData):
    # evt.index gives the item index clicked in the Gallery
    return details_for_image(evt.index)

# ---------- Build Gradio App ----------
with gr.Blocks(title="Brainrot Character Maker") as demo:
    gr.Markdown("# Brainrot Character Maker")

    with gr.Tab("Generate"):
        with gr.Row():
            name = gr.Textbox(label="Original Name", value="Melissa Rossi")
            animal = gr.Textbox(label="Animal", value="Shark")
            thing = gr.Textbox(label="Fruit/Object", value="Watermelon")
        with gr.Row():
            size = gr.Radio(choices=["256x256","512x512","1024x1024"], value="1024x1024", label="Image Size")
            quality = gr.Radio(choices=["standard","hd"], value="standard", label="Quality")
            style = gr.Radio(choices=["vivid","natural"], value="vivid", label="Style")

        generate_btn = gr.Button("Generate", variant="primary")
        out_image = gr.Image(label="Preview", interactive=False)
        out_info = gr.Textbox(label="Details", lines=10)

        # timeline preview gets updated after generation
        timeline_gallery_live = gr.Gallery(
            label="Latest (auto-updated)",
            show_label=True,
            preview=True,          # instead of allow_preview
            columns=[3],           # instead of .style(grid=[3], ...)
            height=300
        )

        generate_btn.click(
            fn=make_character,
            inputs=[name, animal, thing, size, quality, style],
            outputs=[out_image, out_info, timeline_gallery_live]
        )

    with gr.Tab("Timeline"):
        refresh = gr.Button("Refresh")
        timeline_gallery = gr.Gallery(
            label="All Characters",
            preview=True,          # instead of allow_preview
            columns=[4],           # instead of .style(grid=[4], ...)
            height=600
        )
        selected_image = gr.Image(label="Selected Image", interactive=False)
        selected_info = gr.Textbox(label="Selected Details", lines=12)

        # load on open + via refresh
        demo.load(load_timeline, inputs=None, outputs=timeline_gallery)
        refresh.click(load_timeline, inputs=None, outputs=timeline_gallery)

        # click handler to show details
        timeline_gallery.select(on_select, outputs=[selected_image, selected_info])

if __name__ == "__main__":
    demo.launch()
