# BrainrotGenerator

Turn ordinary names, animals, and fruits/objects into whimsical Italian brain‑style characters, complete with AI‑generated artwork. The app uses OpenAI GPT‑4o (for prompt crafting) and DALL·E 3 (for image generation), wrapped in a simple Gradio web UI with a Timeline view of all generated images.


1) Features
-----------
- Italian-style naming: Converts an input name into a fun, Italian-sounding character name.
- Fusion prompts: Blends an animal + fruit/object into a vivid, detailed visual description.
- DALL·E 3 integration: Generates artwork at 256x256, 512x512, or 1024x1024.
- Automatic saving: Stores images in ./images/ with timestamped filenames.
- Timeline view: Browse previously generated characters with name, timestamp, and full DALL·E prompt.


2) Example
----------
Input:
- Name: Melissa Rossi
- Animal: Shark
- Object: Watermelon

Output:
- Character: Melissia Rossini
- Image: A fierce yet playful shark made of watermelon (glossy green rind, seed-eyes, etc.)


3) Installation
---------------
a) Clone and enter the project directory:
   git clone https://github.com/BubbleCoding/BrainrotGenerator
   cd brainrot-generator

b) (Optional) Create a virtual environment:
   python -m venv env
   macOS/Linux:
   source env/bin/activate
   Windows (PowerShell):
   env\Scripts\Activate.ps1

c) Install dependencies:
   pip install -r requirements.txt

d) Set your OpenAI API key:
   macOS/Linux (bash/zsh):
   export OPENAI_API_KEY="sk-..."
   Windows (PowerShell):
   $env:OPENAI_API_KEY="sk-..."


4) Usage
--------
Run the app:
   python brainrot_generator_gradio.py

Open the local URL printed in the terminal (usually http://127.0.0.1:7860/).

Tabs:
- Generate:
  • Enter a name, animal, and fruit/object.
  • Click "Generate" to create a character.
  • Preview the image and see all details.
- Timeline:
  • Browse all previously generated characters.
  • Click any item to view full metadata (name, timestamp, file path, full prompt).


5) Project Structure
--------------------
.
├── brainrot_generator_gradio.py   (Main Gradio app)
├── images/                        (All generated images)
│   └── manifest.jsonl             (Metadata log of generations)
├── requirements.txt
└── readme.txt


6) Configuration
----------------
- Image size: 256x256, 512x512, 1024x1024
- Quality: standard, hd
- Style: vivid, natural
(These are selectable in the UI.)


7) Requirements (Python packages)
---------------------------------
- openai
- gradio
- requests
- pillow


8) Built With
-------------
- OpenAI GPT‑4o (prompt crafting)
- OpenAI DALL·E 3 (image generation)
- Gradio (web UI)
- Pillow (image handling)


9) License
----------
MIT License. You are free to remix and extend; please credit this repo if you share it.


10) Ideas for Next Steps
------------------------
- Search & filters in the timeline (by name or prompt text).
- Batch generation from a CSV file.
- Export timeline as a PDF/ZIP portfolio.
- Deploy on Hugging Face Spaces for quick sharing.


11) Troubleshooting
-------------------
- Gradio 4.x removed the .style() method on components. If you see errors like
  "AttributeError: 'Gallery' object has no attribute 'style'",
  pass layout options directly to the component, e.g.:
    gr.Gallery(preview=True, columns=[4], height=600)
  instead of:
    gr.Gallery(...).style(grid=[4], height=600)

- Ensure OPENAI_API_KEY is set in your environment before running.
- The app writes images and a manifest to the ./images/ folder; make sure the process has write permissions.
