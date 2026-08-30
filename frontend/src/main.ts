import {
  DrawingUtils,
  FilesetResolver,
  PoseLandmarker,
  type NormalizedLandmark,
} from "@mediapipe/tasks-vision";

import "./style.css";
import { SquatAnalyzer, type SquatAnalysis } from "./squat-analyzer";

const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/" +
  "pose_landmarker_lite/float16/1/pose_landmarker_lite.task";
const WASM_URL =
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm";
const FRAME_INTERVAL_MS = 66;
const inferenceCanvas = document.createElement("canvas");

interface SpeechRecognitionResultLike {
  readonly length: number;
  readonly isFinal: boolean;
  readonly [index: number]: { readonly transcript: string };
}

interface SpeechRecognitionEventLike {
  readonly resultIndex: number;
  readonly results: {
    readonly length: number;
    readonly [index: number]: SpeechRecognitionResultLike;
  };
}

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start(): void;
  stop(): void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

function requiredElement<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing required element #${id}`);
  }
  return element as T;
}

function requiredCanvasContext(
  canvasElement: HTMLCanvasElement,
): CanvasRenderingContext2D {
  const canvasContext = canvasElement.getContext("2d");
  if (!canvasContext) {
    throw new Error("Canvas is unavailable");
  }
  return canvasContext;
}

const video = requiredElement<HTMLVideoElement>("camera");
const canvas = requiredElement<HTMLCanvasElement>("overlay");
const startButton = requiredElement<HTMLButtonElement>("start-camera");
const stopButton = requiredElement<HTMLButtonElement>("stop-camera");
const resetButton = requiredElement<HTMLButtonElement>("reset-session");
const voiceButton = requiredElement<HTMLButtonElement>("voice-control");
const soundToggle = requiredElement<HTMLInputElement>("sound-enabled");
const statusText = requiredElement<HTMLElement>("status");
const feedbackText = requiredElement<HTMLElement>("feedback");
const repCount = requiredElement<HTMLElement>("rep-count");
const kneeAngleText = requiredElement<HTMLElement>("knee-angle");
const torsoLeanText = requiredElement<HTMLElement>("torso-lean");
const phaseText = requiredElement<HTMLElement>("phase");
const context = requiredCanvasContext(canvas);

const analyzer = new SquatAnalyzer();
let landmarker: PoseLandmarker | null = null;
let drawingUtils: DrawingUtils | null = null;
let stream: MediaStream | null = null;
let animationFrame: number | null = null;
let lastInferenceAt = 0;
let lastVideoTime = -1;
let lastSpokenFeedback = "";
let lastSpokenAt = 0;
let recognition: SpeechRecognitionLike | null = null;
let voiceControlEnabled = false;

async function createLandmarker(): Promise<PoseLandmarker> {
  const fileset = await FilesetResolver.forVisionTasks(WASM_URL);
  const options = {
    baseOptions: {
      modelAssetPath: MODEL_URL,
      delegate: "GPU" as const,
    },
    canvas: inferenceCanvas,
    runningMode: "VIDEO" as const,
    numPoses: 1,
    minPoseDetectionConfidence: 0.6,
    minPosePresenceConfidence: 0.6,
    minTrackingConfidence: 0.6,
  };

  try {
    return await PoseLandmarker.createFromOptions(fileset, options);
  } catch (error) {
    console.warn("GPU initialization failed; using CPU", error);
    return PoseLandmarker.createFromOptions(fileset, {
      ...options,
      baseOptions: {
        ...options.baseOptions,
        delegate: "CPU",
      },
    });
  }
}

async function startCamera(): Promise<void> {
  if (stream) {
    return;
  }
  startButton.disabled = true;
  statusText.textContent = "Loading pose model…";

  try {
    landmarker ??= await createLandmarker();
    stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        facingMode: "user",
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
    });
    video.srcObject = stream;
    await video.play();
    drawingUtils = new DrawingUtils(context);
    statusText.textContent = "Camera active · analysis stays on this device";
    stopButton.disabled = false;
    analyzeFrame();
  } catch (error) {
    console.error(error);
    statusText.textContent =
      "Camera unavailable. Allow permission and use HTTPS or localhost.";
    startButton.disabled = false;
    stream?.getTracks().forEach((track) => track.stop());
    stream = null;
  }
}

function stopCamera(): void {
  if (animationFrame !== null) {
    cancelAnimationFrame(animationFrame);
    animationFrame = null;
  }
  stream?.getTracks().forEach((track) => track.stop());
  stream = null;
  video.srcObject = null;
  context.clearRect(0, 0, canvas.width, canvas.height);
  statusText.textContent = "Camera stopped";
  startButton.disabled = false;
  stopButton.disabled = true;
}

function dispose(): void {
  stopCamera();
  recognition?.stop();
  landmarker?.close();
  landmarker = null;
}

function analyzeFrame(now = performance.now()): void {
  if (!landmarker || !stream) {
    return;
  }

  if (
    video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA &&
    now - lastInferenceAt >= FRAME_INTERVAL_MS &&
    video.currentTime !== lastVideoTime
  ) {
    lastInferenceAt = now;
    lastVideoTime = video.currentTime;
    resizeCanvas();
    const result = landmarker.detectForVideo(video, now);
    const landmarks = result.landmarks[0];
    drawPose(landmarks);
    const analysis = analyzer.update(
      landmarks ?? [],
      video.videoWidth,
      video.videoHeight,
    );
    renderAnalysis(analysis);
  }

  animationFrame = requestAnimationFrame(analyzeFrame);
}

function resizeCanvas(): void {
  if (
    canvas.width !== video.videoWidth ||
    canvas.height !== video.videoHeight
  ) {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
  }
}

function drawPose(landmarks: NormalizedLandmark[] | undefined): void {
  context.clearRect(0, 0, canvas.width, canvas.height);
  if (!landmarks || !drawingUtils) {
    return;
  }
  drawingUtils.drawConnectors(landmarks, PoseLandmarker.POSE_CONNECTIONS, {
    color: "#b8ff5a",
    lineWidth: 4,
  });
  drawingUtils.drawLandmarks(landmarks, {
    color: "#ffffff",
    fillColor: "#10151f",
    lineWidth: 2,
    radius: 3,
  });
}

function renderAnalysis(analysis: SquatAnalysis): void {
  repCount.textContent = String(analysis.reps);
  phaseText.textContent = analysis.phase;
  kneeAngleText.textContent =
    analysis.kneeAngle === null ? "—" : `${Math.round(analysis.kneeAngle)}°`;
  torsoLeanText.textContent =
    analysis.torsoLean === null ? "—" : `${Math.round(analysis.torsoLean)}°`;
  feedbackText.textContent = analysis.feedback;
  feedbackText.dataset.tracked = String(analysis.tracked);
  speakFeedback(analysis.feedback);
}

function speakFeedback(message: string): void {
  const now = Date.now();
  if (
    !soundToggle.checked ||
    message === lastSpokenFeedback ||
    now - lastSpokenAt < 2500
  ) {
    return;
  }
  speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(message);
  utterance.rate = 1.05;
  speechSynthesis.speak(utterance);
  lastSpokenFeedback = message;
  lastSpokenAt = now;
}

function resetSession(): void {
  analyzer.reset();
  lastSpokenFeedback = "";
  renderAnalysis(analyzer.update([], 1, 1));
  statusText.textContent = stream
    ? "Session reset · camera active"
    : "Session reset · camera stopped";
}

function configureVoiceControl(): void {
  const Recognition =
    window.SpeechRecognition ?? window.webkitSpeechRecognition;
  if (!Recognition) {
    voiceButton.disabled = true;
    voiceButton.textContent = "Voice commands unavailable";
    return;
  }

  recognition = new Recognition();
  recognition.continuous = true;
  recognition.interimResults = false;
  recognition.lang = "en-US";
  recognition.onresult = (event) => {
    const result = event.results[event.resultIndex];
    const command = result?.[0]?.transcript.trim().toLowerCase() ?? "";
    if (command.includes("start")) {
      void startCamera();
    } else if (command.includes("stop")) {
      stopCamera();
    } else if (command.includes("reset")) {
      resetSession();
    } else if (command.includes("mute")) {
      soundToggle.checked = false;
    } else if (command.includes("sound") || command.includes("unmute")) {
      soundToggle.checked = true;
    }
  };
  recognition.onerror = () => {
    statusText.textContent =
      "Voice control stopped. Camera analysis is still available.";
    voiceControlEnabled = false;
    voiceButton.textContent = "Enable voice commands";
  };
  recognition.onend = () => {
    if (voiceControlEnabled) {
      recognition?.start();
    }
  };
}

function toggleVoiceControl(): void {
  if (!recognition) {
    return;
  }
  voiceControlEnabled = !voiceControlEnabled;
  if (voiceControlEnabled) {
    recognition.start();
    voiceButton.textContent = "Disable voice commands";
    statusText.textContent =
      'Listening for “start”, “stop”, “reset”, “mute” and “sound”';
  } else {
    recognition.stop();
    voiceButton.textContent = "Enable voice commands";
  }
}

startButton.addEventListener("click", () => void startCamera());
stopButton.addEventListener("click", stopCamera);
resetButton.addEventListener("click", resetSession);
voiceButton.addEventListener("click", toggleVoiceControl);
window.addEventListener("beforeunload", dispose);

configureVoiceControl();
renderAnalysis(analyzer.update([], 1, 1));
