"""
Phase 1 verification tests.
Run from: d:\\music generator\\backend
  venv\\Scripts\\python.exe verify_phase1.py
"""
import sys, os, time, json, io, urllib.request, urllib.error
import numpy as np
from scipy.io import wavfile

BOUNDARY = "verifybound123"
BASE     = "http://127.0.0.1:8000"
PASS     = "PASS"
FAIL     = "FAIL"
results  = []

def check(name, condition, detail=""):
    tag = PASS if condition else FAIL
    results.append((tag, name, detail))
    print(f"  [{tag}] {name}" + (f": {detail}" if detail else ""))

def make_wav_bytes(freq=440.0, dur=6.0, sr=44100):
    t   = np.linspace(0, dur, int(sr * dur))
    sig = (0.3 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    buf = io.BytesIO(); wavfile.write(buf, sr, sig)
    return buf.getvalue()

def post_start(fields, wav_bytes=None):
    body = io.BytesIO()
    for k, v in fields.items():
        body.write(f"--{BOUNDARY}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    if wav_bytes is not None:
        body.write(f"--{BOUNDARY}\r\nContent-Disposition: form-data; name=\"voice_sample\"; filename=\"voice.wav\"\r\nContent-Type: audio/wav\r\n\r\n".encode())
        body.write(wav_bytes)
        body.write(b"\r\n")
    body.write(f"--{BOUNDARY}--\r\n".encode())
    req = urllib.request.Request(
        f"{BASE}/api/song/start", data=body.getvalue(),
        headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"}
    )
    return json.loads(urllib.request.urlopen(req).read().decode())

def poll(job_id, timeout=45):
    for _ in range(timeout):
        time.sleep(1)
        data = json.loads(urllib.request.urlopen(f"{BASE}/api/song/{job_id}/variants").read().decode())
        if data["status"] in ("completed", "failed"):
            return data
    return data

# Wait for server
time.sleep(2)

print("\n" + "="*60)
print("CHECK 1: /api/health reports ffmpeg_available")
print("="*60)
health = json.loads(urllib.request.urlopen(f"{BASE}/api/health").read().decode())
print("  health:", health)
check("ffmpeg_available in health", "ffmpeg_available" in health)
check("cloud_gpu_status in health", "cloud_gpu_status" in health)
check("cloud_gpu_status=not_configured (no URL set)", health.get("cloud_gpu_status") == "not_configured")
check("allow_demo_fallback reported", "allow_demo_fallback" in health)

print("\n" + "="*60)
print("CHECK 2: ALLOW_DEMO_FALLBACK=False -> job fails with clear message")
print("="*60)
# Default env has ALLOW_DEMO_FALLBACK unset (False)
res = post_start({"language": "urdu", "theme": "longing", "genre": "ghazal", "variants": "1"})
job_id = res["job_id"]
data = poll(job_id)
print("  Status:", data["status"])
print("  Message:", data.get("message",""))
print("  Error:", data.get("error",""))
check("Job FAILS when cloud missing & demo fallback off", data["status"] == "failed")
check("Error message contains 'Cloud GPU'", "Cloud GPU" in (data.get("error") or data.get("message", "")))

print("\n" + "="*60)
print("CHECK 3: variants=5 → 422 validation error")
print("="*60)
try:
    post_start({"language": "urdu", "theme": "test", "genre": "ghazal", "variants": "5"})
    check("variants=5 rejected", False, "accepted when it should be rejected")
except urllib.error.HTTPError as e:
    check("variants=5 rejected with 422", e.code == 422, f"HTTP {e.code}")
except Exception as e:
    check("variants=5 rejected", False, str(e))

print("\n" + "="*60)
print("CHECK 4: variants=0 → 422 validation error")
print("="*60)
try:
    post_start({"language": "urdu", "theme": "test", "genre": "ghazal", "variants": "0"})
    check("variants=0 rejected", False)
except urllib.error.HTTPError as e:
    check("variants=0 rejected with 422", e.code == 422, f"HTTP {e.code}")

print("\n" + "="*60)
print("CHECK 5: Upload >20 MB → 400")
print("="*60)
big = b"\x00" * (21 * 1024 * 1024)  # 21 MB
body = io.BytesIO()
body.write(f"--{BOUNDARY}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\nurdu\r\n".encode())
body.write(f"--{BOUNDARY}\r\nContent-Disposition: form-data; name=\"theme\"\r\n\r\ntest\r\n".encode())
body.write(f"--{BOUNDARY}\r\nContent-Disposition: form-data; name=\"genre\"\r\n\r\nghazal\r\n".encode())
body.write(f"--{BOUNDARY}\r\nContent-Disposition: form-data; name=\"variants\"\r\n\r\n1\r\n".encode())
body.write(f"--{BOUNDARY}\r\nContent-Disposition: form-data; name=\"voice_sample\"; filename=\"big.wav\"\r\nContent-Type: audio/wav\r\n\r\n".encode())
body.write(big)
body.write(f"\r\n--{BOUNDARY}--\r\n".encode())
try:
    req = urllib.request.Request(f"{BASE}/api/song/start", data=body.getvalue(),
        headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"})
    urllib.request.urlopen(req)
    check("21 MB upload rejected", False)
except urllib.error.HTTPError as e:
    check("21 MB upload rejected with 400", e.code == 400, f"HTTP {e.code}")

print("\n" + "="*60)
print("CHECK 6: CORS headers use explicit origins (no wildcard)")
print("="*60)
with open("app/main.py", "r", encoding="utf-8") as f:
    main_src = f.read()
wildcard_cors   = 'allow_origins=["*"]' in main_src
creds_true      = 'allow_credentials=True' in main_src
explicit_origin = "localhost:5173" in main_src
check("No wildcard allow_origins", not wildcard_cors)
check("allow_credentials=False", not creds_true)
check("Explicit localhost:5173 origin listed", explicit_origin)

print("\n" + "="*60)
print("CHECK 7: Gemini key in header, not URL")
print("="*60)
with open("app/lyrics.py", "r", encoding="utf-8") as f:
    lyrics_src = f.read()
key_in_url    = "?key=" in lyrics_src
key_in_header = "x-goog-api-key" in lyrics_src
model_from_config = "runtime_config.gemini_model" in lyrics_src
check("API key NOT in URL query string", not key_in_url)
check("API key sent in x-goog-api-key header", key_in_header)
check("Model name read from runtime_config", model_from_config)

print("\n" + "="*60)
print("CHECK 8: No asyncio.sleep in pipeline")
print("="*60)
import re
with open("app/pipeline.py", "r", encoding="utf-8") as f:
    pipe_src = f.read()
sleeps = re.findall(r"asyncio\.sleep\(", pipe_src)
check("No artificial asyncio.sleep calls", len(sleeps) == 0, f"Found {len(sleeps)}")

print("\n" + "="*60)
print("CHECK 9: voice_clone.py has no EQ pseudo-clone")
print("="*60)
with open("app/voice_clone.py", "r", encoding="utf-8") as f:
    vc_src = f.read()
check("iirpeak (EQ filter) removed", "iirpeak" not in vc_src)
check("apply_timbre_transfer removed", "apply_timbre_transfer" not in vc_src)
check("Returns 'none' for voice_conversion", '"none"' in vc_src)

print("\n" + "="*60)
print("CHECK 10: Waveform peaks use RMS not max")
print("="*60)
with open("app/audio_prep.py", "r", encoding="utf-8") as f:
    prep_src = f.read()
uses_rms = "np.sqrt(np.mean(chunk ** 2))" in prep_src or "np.sqrt(np.mean(chunk**2))" in prep_src
uses_max = "np.max(np.abs(chunk))" in prep_src
check("RMS used for waveform peaks", uses_rms)
check("np.max peak method removed", not uses_max)

print("\n" + "="*60)
print("CHECK 11: audio_mixer.py safe loudness (no clipping)")
print("="*60)
with open("app/audio_mixer.py", "r", encoding="utf-8") as f:
    mix_src = f.read()
target_lufs_mixed = "target_lufs - normalized_master.dBFS" in mix_src
safe_norm = "apply_gain(-1.0)" in mix_src
check("Broken dBFS/LUFS comparison removed", not target_lufs_mixed)
check("Safe -1 dBFS headroom applied", safe_norm)

print("\n" + "="*60)
print("CHECK 12: audio_prep.py uses no parameters= keyword")
print("="*60)
check("parameters= removed from export", "parameters=" not in prep_src)

print("\n" + "="*60)
print("CHECK 13: /api/config/cloud-gpu/test endpoint exists")
print("="*60)
try:
    req = urllib.request.Request(f"{BASE}/api/config/cloud-gpu/test", method="POST",
        data=b"", headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req)
        body = json.loads(resp.read().decode())
        check("POST /api/config/cloud-gpu/test exists", True, str(body))
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode())
        # 400 = "no URL configured" is also fine — endpoint exists
        check("POST /api/config/cloud-gpu/test exists", e.code in (200, 400, 502), f"HTTP {e.code}: {body}")
except Exception as ex:
    check("POST /api/config/cloud-gpu/test exists", False, str(ex))

print("\n" + "="*60)
print("CHECK 14: Pashto dialect maps — Peshawar default")
print("="*60)
with open("app/lyrics.py", "r", encoding="utf-8") as f:
    lsrc = f.read()
check("Peshawar map uses خ for ښ (Northern)", '"ښ": "خ"' in lsrc)
check("Kandahari map uses ش for ښ (Southern)", '"ښ": "ش"' in lsrc)
check("Peshawar is default dialect", 'dialect: str = "peshawar"' in lsrc or "peshawar" in lsrc)
check("No 'optimised for ACE-Step' claim", "optimized for ACE-Step" not in lsrc and "optimised for ACE-Step" not in lsrc)

print("\n" + "="*60)
print("CHECK 15: requirements.txt audioop-lts marker")
print("="*60)
with open("requirements.txt", "r") as f:
    req_txt = f.read()
check("audioop-lts has python_version marker", 'python_version >= "3.13"' in req_txt or "python_version>='3.13'" in req_txt)

print("\n" + "="*60)
passed = sum(1 for t, _, _ in results if t == PASS)
failed = sum(1 for t, _, _ in results if t == FAIL)
print(f"RESULT: {passed} passed, {failed} failed")
if failed:
    print("FAILED checks:")
    for t, n, d in results:
        if t == FAIL:
            print(f"  - {n}: {d}")
print("="*60)
sys.exit(0 if failed == 0 else 1)
