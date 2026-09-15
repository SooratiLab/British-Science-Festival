#!/usr/bin/env python3
"""
Runs on the Raspberry Pi 5, connects over
Tailscale to rosbridge on the Jetson, subscribes to /nav_state, and
speaks each message aloud using Text-to-Speech.

Requires JETSON_IP to be set to the Jetson's Tailscale IP:
JETSON_IP=100.x.x.x python3 narrator.py

See scripts/requirements.txt for dependencies.
"""

import json
import os
import threading
import subprocess
import time

import websocket

JETSON_TAILSCALE_IP = os.environ.get('JETSON_IP')
WS_URL = f"ws://{JETSON_TAILSCALE_IP}:9090"
SPEECH_RATE = 150

speak_queue = []
is_speaking = False
queue_lock = threading.Lock()

"""Add text to the speech queue."""
def speak(text: str):
    global is_speaking
    with queue_lock:
        speak_queue.append(text)
        if is_speaking:
            return
        is_speaking = True
    threading.Thread(target=_process_queue, daemon=True).start()

"""Process the speech queue one message at a time."""
def _process_queue():
    global is_speaking
    is_speaking = True
    while True:
        with queue_lock:
            if not speak_queue:
                is_speaking = False
                break
            text = speak_queue.pop(0)
        print(f'Narrating: {text}')
        try:
            subprocess.run(['espeak', '-s', str(SPEECH_RATE), text], check=True)
        except FileNotFoundError:
            print('espeak not found.')
        except subprocess.CalledProcessError as e:
            print(f'espeak failed: {e}')
        time.sleep(0.5)

"""Handle incoming WebSocket messages from ROSbridge."""
def on_message(ws, message):
    try:
        data = json.loads(message)
        if data.get('op') == 'publish' and data.get('topic') == '/nav_state':
            text = data['msg']['data']
            speak(text)
    except json.JSONDecodeError:
        pass

def on_error(ws, error):
    print(f'WebSocket error: {error}')

def on_close(ws, close_status_code, close_msg):
    print('Disconnected from Jetson. Reconnecting in 5 seconds...')
    time.sleep(5)

def on_open(ws):
    print(f'Connected to Jetson rosbridge')
    subscribe_msg = {
        'op': 'subscribe',
        'topic': '/nav_state',
        'type': 'std_msgs/String'
    }
    ws.send(json.dumps(subscribe_msg))
    speak('Ready for mission.')

if __name__ == '__main__':
    print(f'Connecting to {WS_URL} ...')
    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    ws.run_forever(reconnect=5)