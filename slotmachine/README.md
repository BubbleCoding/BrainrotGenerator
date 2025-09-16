# Slot-Machine Brainrot UI (Laptop Edition)

A lightweight, kiosk-style **slot machine UI** that lets users stop three reels (Style / Character / Mood) and then generates an image with OpenAI.
This is designed to run on a **laptop** (no GPIO), but the backend is structured so you can later swap the on-screen buttons for **GPIO** inputs on a Raspberry Pi 5.

> You mentioned a "brainrot generator" — this repo integrates a simplified prompt builder similar in spirit (using OpenAI's Images API). It does not depend on Gradio and is optimized for the slot UX.

## Features
- Frontend: HTML/CSS/JS with buttery reel animations.
- Backend: FastAPI + WebSocket for real-time updates.
- Illusion of control: timing of button presses is used to seed the randomness.
- Image generation: calls OpenAI Images (DALL·E 3) and serves the result.

## Folder structure
```
slot-machine-ui/
├─ backend/
│  └─ main.py
├─ frontend/
│  ├─ index.html
│  ├─ assets/
│  └─ generated/     # images saved here
├─ .env.example
├─ requirements.txt
└─ README.md
```

## Quickstart
1. **Install deps** (Python 3.10+ recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Set your OpenAI key**:
   - Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY`  
   OR export it directly in your shell:
   ```bash
   export OPENAI_API_KEY=sk-...
   ```

3. **Run the backend**:
   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. **Open the frontend**:
   - Navigate to `http://localhost:8000` — the backend serves the `/frontend` folder.

## In-show flow
- Press **Stop A/B/C** to stop reels immediately; the press time seeds the pick.
- After all three reels stop, the backend composes a prompt and calls OpenAI.
- The final image appears full-screen when ready.

## Adapting to Raspberry Pi 5 later
- Replace on-screen buttons with GPIO events; the `main.py` already isolates the state machine and can accept GPIO triggers with minimal changes.
- Boot Chromium in kiosk mode pointing to `http://localhost:8000` and run the backend as a systemd service.

## Notes
- This project intentionally **does not** depend on Gradio; it mirrors the image-generation approach of your `brainrot_generator_gradio.py` but in a simple web UI.
- If you want to reuse your own prompt logic, swap out `compose_prompt` in `backend/main.py`.

