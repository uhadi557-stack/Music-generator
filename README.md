#  AI Music Generator (Suroor AI)

🎧 Create complete multi-variant songs from prompts with synchronized lyrics playback, voice cloning, and Google Colab GPU integration.An end-to-end AI music generation studio that produces complete, multi-variant songs from themes and lyrics, featuring custom voice cloning and conversion powered by ACE-Step and FastAPI.

---

## ✨ Features

- **Multilingual Lyric Generation**: Automatic lyric synthesis (Urdu Ghazals, English, Hindi, and more) with custom themes and rhyme structures.
- **Voice Conversion & Cloning**: Upload a short voice sample (>= 5s) to convert singing vocals into your own voice.
- **Multi-Variant Generation**: Generate multiple diverse musical renditions (seeds, arrangement variants) for each song request.
- **Synchronized Lyrics Viewer**: Modern React frontend with playback controls, synchronized lyric highlights, and downloadable audio tracks.
- **Cloud GPU Accelerated**: ACE-Step model integration running on Google Colab with public Gradio bridge.
- **Offline / Local Demo Mode**: Synthesized multi-track fallback when no Cloud GPU is connected.

---

## 🏗️ Architecture

```
music-generator/
├── backend/                  # FastAPI backend
│   ├── app/                 # API routes, lyrics generator, voice converter, audio utils
│   ├── media/               # Audio uploads, processed vocals, generated variants
│   ├── tests/               # Test suites
│   ├── run_backend.py       # Server entrypoint (Uvicorn)
│   └── requirements.txt
├── frontend/                 # React 19 + TypeScript + Vite
│   ├── src/                 # UI components, audio player, lyrics viewer
│   └── package.json
├── cloud_colab/              # Colab GPU runner & notebooks (ACE-Step backend)
│   ├── colab_ace_step_runner.py
│   └── suroor_ai_colab_runner.ipynb
└── start_servers.bat         # Single-click launch script for Windows
```

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python 3.10+**
- **Node.js 18+** & npm

### 2. Backend Setup
```bash
cd backend
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
python run_backend.py
```
Backend runs at `http://localhost:8000`.

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Frontend runs at `http://localhost:5173`.

### 4. Or Run Everything (Windows)
Double-click `start_servers.bat` in the root directory.

---

## ☁️ Cloud GPU Integration (Optional)

1. Open `cloud_colab/suroor_ai_colab_runner.ipynb` in [Google Colab](https://colab.research.google.com).
2. Select a GPU runtime (T4 or A100).
3. Run the notebook to start the Gradio public tunnel.
4. Copy the resulting `https://xxxx.gradio.live` URL.
5. Paste into `backend/.env`:
   ```env
   CLOUD_GPU_URL=https://xxxx.gradio.live
   ```

---

## 📄 License

MIT License.
