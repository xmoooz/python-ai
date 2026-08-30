# Python AI Service

## Formline gym MVP

Formline is a browser-based bodyweight squat coach. MediaPipe Pose Landmarker
runs on the user's device, draws a pose overlay, measures knee and torso angles,
counts completed repetitions, and provides optional spoken guidance.

The current rules are an MVP demonstration and are not medical advice or a
substitute for assessment by a qualified trainer or clinician.

### Run the web app

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173/gym/`. Camera access works on localhost and on
HTTPS deployments. The model and WebAssembly runtime are downloaded from
Google and jsDelivr when a session starts.

Voice output uses the browser Speech Synthesis API. Voice commands use the Web
Speech API where supported; camera analysis still works when speech recognition
is unavailable. Depending on the browser, speech recognition may use the
browser vendor's remote service and is therefore optional.

### Build and serve from FastAPI

```bash
cd frontend
npm run build
cd ..
uv run uvicorn app.main:app --reload
```

The build is generated under `app/static/gym/` and served at `/gym/`. Generated
assets are intentionally excluded from Git.

### Verification

```bash
cd frontend
npm test
npm run build
cd ..
uv run python -c "import app.main"
```