from openai import OpenAI
import os, requests

# Initialize client with your API key (or set it as environment variable OPENAI_API_KEY)
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

prompt = """
Name: Melissa Rossi
Fruit: Watermelon
Animal: Shark
"""

role_prompt = """
You are a creator of artistic prompts for dalle-3 image generation.
You will receive a persons name, an animal and a fruit or object.
The name needs to be converted into an italian sounding name which will be the name of the character.
The animal and fruit or object are what the character is made of.
The two elements need to be fused into one character, which you will describe in detail.
"""


# Send a chat completion request to GPT-4
response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": role_prompt},
        {"role": "user", "content": prompt}
    ]
)

# Print the response
print(response.choices[0].message.content)

