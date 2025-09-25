import asyncio, json
from fastapi import FastAPI, WebSocket
from gpiozero import Button, Device
from gpiozero.pins.pigpio import PiGPIOFactory

# Force pigpio backend
Device.pin_factory = PiGPIOFactory()

app = FastAPI()
clients = set()

# Grab one global loop to reuse everywhere
loop = asyncio.get_event_loop()

async def broadcast(payload: dict):
    dead = set()
    for ws in list(clients):
        try:
            await ws.send_text(json.dumps(payload))
        except Exception:
            dead.add(ws)
    clients.difference_update(dead)

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    print("[WS] Client connected")
    try:
        while True:
            await ws.receive_text()  # ignore incoming, just keep alive
    except Exception:
        pass
    finally:
        clients.discard(ws)
        print("[WS] Client disconnected")

# GPIO callbacks
def schedule(msg: str):
    print("[GPIO]", msg)
    asyncio.run_coroutine_threadsafe(
        broadcast({"type": "debug", "msg": msg}), loop
    )

btn23 = Button(23, pull_up=True, bounce_time=0.1)
btn27 = Button(27, pull_up=True, bounce_time=0.1)
btn22 = Button(22, pull_up=True, bounce_time=0.1)

btn23.when_pressed = lambda: schedule("LEFT (GPIO23)")
btn27.when_pressed = lambda: schedule("MIDDLE (GPIO27)")
btn22.when_pressed = lambda: schedule("RIGHT (GPIO22)")

print("[GPIO] Buttons active on BCM 23, 27, 22 (press to send debug messages)")
