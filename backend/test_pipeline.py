import urllib.request
import json
import time
import io
import sys
import numpy as np
from scipy.io import wavfile

# 1. Create a 6-second test voice sample WAV (satisfies >= 5.0s requirement)
sr = 44100
t = np.linspace(0, 6.0, int(sr * 6.0), endpoint=False)
voice_data = (0.3 * np.sin(2 * np.pi * 330.0 * t) * np.exp(-t * 0.2)).astype(np.float32)
wav_buffer = io.BytesIO()
wavfile.write(wav_buffer, sr, (voice_data * 32767).astype(np.int16))
wav_bytes = wav_buffer.getvalue()

# 2. Form multipart request
boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
body = io.BytesIO()
def add_field(name, val):
    body.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{val}\r\n'.encode())

add_field('language', 'urdu')
add_field('theme', 'Autumn rain in Lahore and longing')
add_field('genre', 'ghazal')
add_field('variants', '2')

body.write(f'--{boundary}\r\nContent-Disposition: form-data; name="voice_sample"; filename="my_voice.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode())
body.write(wav_bytes)
body.write(f'\r\n--{boundary}--\r\n'.encode())

req = urllib.request.Request(
    'http://127.0.0.1:8000/api/song/start',
    data=body.getvalue(),
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
)
res = json.loads(urllib.request.urlopen(req).read().decode())
job_id = res['job_id']
print(f'Started Job ID: {job_id}')

# 3. Poll variants until complete
for i in range(25):
    time.sleep(1.0)
    v_res = json.loads(urllib.request.urlopen(f'http://127.0.0.1:8000/api/song/{job_id}/variants').read().decode())
    print(f'Step {v_res["current_step"]}: Status = {v_res["status"]}, Variants ready = {len(v_res["variants"])}')
    if v_res['status'] == 'completed':
        print('\n=== PIPELINE SUCCESS! 8 STEPS COMPLETE ===')
        for v in v_res['variants']:
            print(f' - Variant {v["variant_number"]}: {v["title"]}, Seed: {v["seed"]}, Audio: {v["audio_url"]}')
        break
    elif v_res['status'] == 'failed':
        print(f"FAILED (expected when cloud GPU offline): {v_res.get('error')}")
        break
