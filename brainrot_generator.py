from openai import OpenAI
import os, requests

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

prompt = """
Introduce a charming and unique character — Melissia Rossini. Melissia is a splendid fusion of a fierce shark and a refreshing watermelon, eliciting a whimsical imagination.

Her body, primarily a shark's anatomy, is comprised of vibrant watermelon textures. Her skin shares the sleek and glossy pattern of a ripe watermelon, complete with contrasting green stripes running the entire length of her body. She carries a massive, powerful, yet gracefully streamlined watermelon torso that tapers into a strong, muscular tail, reminding one of a shark.

Her fintastic arms boast the firmness of a shark fin but are beautifully etched with watermelon-esque patterns. Embellishing her compelling appearance are her watermelon seed-shaped eyes that glisten with curiosity and adventure, set on her shark-like face that is softened by the fruit-inspired hue.

Rossini's teeth, though reminiscent of a shark's, are not made of bone but mirror the glistening white inner rind of a watermelon. Her dorsal fin, an essential part of her shark identity, mirrors the curvature of a watermelon slice, maintaining the iconic shark silhouette, yet bringing an unexpected softness to her overall persona.

In essence, Melissia Rossini is an unforgettable blend of the aquatic predator's natural fierceness and the juicy, sweet delight of a summer watermelon, crafting a character both mesmerizing and intriguing."""

result = client.images.generate(
    model="dall-e-3",
    prompt=prompt,
    size="1024x1024"  # you can also use 512x512 or 256x256
)

# Get the image URL from the response
image_url = result.data[0].url

# Download the image
img_bytes = requests.get(image_url).content
with open("otter.png", "wb") as f:
    f.write(img_bytes)

print("Image saved to otter.png")
