# app.py
import os
import re
import json
import time
import datetime
import argparse
from typing import Tuple
import requests
from openai import OpenAI, APIError, RateLimitError, APIConnectionError

ROLE_PROMPT = """You are a creator of artistic prompts for DALL·E 3 image generation.
You will receive: (1) a person's name, (2) an animal, and (3) a fruit or object.
Tasks:
1) Convert the person's name into a fun, Italian-sounding name (no real people). Keep it tasteful, 2–4 words max.
2) Write a vivid, specific prompt for DALL·E 3 that fuses the animal and fruit/object into a single coherent character with clear materials, textures, shapes, and composition. Avoid story; focus on visual description and style.
3) Do NOT include camera brands or copyrighted style names. Keep it PG-13.

Return ONLY valid JSON with keys:
- italian_name: string
- prompt: string
"""

JSON_INSTRUCTION = """Return ONLY a compact JSON object. No backticks, no explanations, no extra keys.
Example:
{"italian_name":"Luigi Pescecocomero","prompt":"A charming character that fuses a shark with watermelon ..."}
"""

def parse_args():
    p = argparse.ArgumentParser(
        description="Generate an image by fusing an animal and a fruit/object, saving as the Italian-style character name."
    )
    p.add_argument("name", help="Original person name, e.g., 'Melissa Rossi'")
    p.add_argument("animal", help="Animal, e.g., 'Shark'")
    p.add_argument("thing", help="Fruit or object, e.g., 'Watermelon'")
    p.add_argument("--size", default="1024x1024", choices=["256x256","512x512","1024x1024"], help="Image size")
    p.add_argument("--quality", default="standard", choices=["standard","hd"], help="DALL·E 3 quality")
    p.add_argument("--style", default="vivid", choices=["vivid","natural"], help="DALL·E 3 style")
    p.add_argument("--retries", type=int, default=3, help="Max retries on API/network errors")
    p.add_argument("--timeout", type=float, default=30.0, help="HTTP request timeout (seconds) for image download")
    return p.parse_args()

def get_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
    return OpenAI(api_key=api_key)

def backoff_sleep(attempt: int):
    # simple exponential backoff with jitter
    delay = min(2 ** attempt, 10) + (0.1 * attempt)
    time.sleep(delay)

def sanitize_filename(name: str) -> str:
    # Replace non-filename-safe chars; collapse spaces/underscores
    cleaned = re.sub(r"[^\w\s.-]", "", name, flags=re.UNICODE).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned or "character"

def build_input_block(name: str, animal: str, thing: str) -> str:
    return f"""Name: {name}
Animal: {animal}
Fruit_or_Object: {thing}
"""

def generate_prompt_and_name(client: OpenAI, name: str, animal: str, thing: str, retries: int) -> Tuple[str, str]:
    user_block = build_input_block(name, animal, thing)
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": ROLE_PROMPT},
                    {"role": "user", "content": user_block},
                    {"role": "system", "content": JSON_INSTRUCTION},
                ],
                temperature=0.7,
            )
            content = resp.choices[0].message.content.strip()
            # Ensure pure JSON
            # In case the model adds extra text, try to extract a JSON object
            if not content.startswith("{"):
                first_brace = content.find("{")
                last_brace = content.rfind("}")
                if first_brace != -1 and last_brace != -1:
                    content = content[first_brace:last_brace+1]
            data = json.loads(content)
            italian_name = data["italian_name"].strip()
            prompt = data["prompt"].strip()
            if not italian_name or not prompt:
                raise ValueError("Missing 'italian_name' or 'prompt' in model output.")
            return italian_name, prompt
        except (APIError, RateLimitError, APIConnectionError, requests.RequestException, json.JSONDecodeError, KeyError, ValueError) as e:
            last_err = e
            if attempt < retries:
                backoff_sleep(attempt)
            else:
                raise RuntimeError(f"Failed to produce prompt/name after {retries} attempts: {e}") from e
    # unreachable
    raise RuntimeError(f"Unexpected failure: {last_err}")

def generate_image(client: OpenAI, prompt: str, size: str, quality: str, style: str, retries: int) -> bytes:
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            # Request URL-based response, then download
            img_resp = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality=quality,
                style=style,
                n=1,
            )
            url = img_resp.data[0].url
            if not url:
                raise RuntimeError("Image URL missing in response.")
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            return r.content
        except (APIError, RateLimitError, APIConnectionError, requests.RequestException) as e:
            last_err = e
            if attempt < retries:
                backoff_sleep(attempt)
            else:
                raise RuntimeError(f"Failed to generate/download image after {retries} attempts: {e}") from e
    # unreachable
    raise RuntimeError(f"Unexpected failure: {last_err}")

def main():
    args = parse_args()
    client = get_client()

    italian_name, dalle_prompt = generate_prompt_and_name(
        client, args.name, args.animal, args.thing, retries=args.retries
    )

    print(f"[INFO] Character name: {italian_name}")
    print(f"[INFO] Generating image with DALL·E 3...")
    img_bytes = generate_image(
        client, dalle_prompt, size=args.size, quality=args.quality, style=args.style, retries=args.retries
    )

    # always save in "images/" folder
    output_dir = "images"
    os.makedirs(output_dir, exist_ok=True)

    # add timestamp to filename
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(output_dir, f"{sanitize_filename(italian_name)}_{timestamp}.png")

    with open(filename, "wb") as f:
        f.write(img_bytes)

    print(f"[SUCCESS] Saved image to: {filename}")


if __name__ == "__main__":
    main()
