// Webcam arm tracking. MediaPipe Pose finds the shoulder/elbow/wrist of the
// chosen arm in the browser; the sport-specific logic (phase labels and what
// counts as a release) lives in activity_profiles.js so it can be tested
// without a camera and extended per sport.
//
// getSettings() is read every frame and returns { arm: "right"|"left",
// profileId: string }, so changing the dropdowns takes effect immediately.
import { PoseLandmarker, FilesetResolver } from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14";
import { PROFILES, ReleaseDetector, pointsForTorso, pointsFromLandmarks } from "./activity_profiles.js";

const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task";
const WASM_URL = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm";

export async function startThrowingMotionTracking(videoEl, overlayCanvas, onState, getSettings) {
  const vision = await FilesetResolver.forVisionTasks(WASM_URL);
  const landmarker = await PoseLandmarker.createFromOptions(vision, {
    baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
    runningMode: "VIDEO",
    numPoses: 1,
  });

  const stream = await navigator.mediaDevices.getUserMedia({
    video: { width: 320, height: 240 },
  });
  videoEl.srcObject = stream;
  await videoEl.play();

  overlayCanvas.width = videoEl.videoWidth || 320;
  overlayCanvas.height = videoEl.videoHeight || 240;
  const ctx = overlayCanvas.getContext("2d");

  let detector = null;
  let detectorProfileId = null;

  function frame() {
    const nowMs = performance.now();
    const { arm, profileId } = getSettings();

    if (!detector || detectorProfileId !== profileId) {
      detector = new ReleaseDetector(PROFILES[profileId] ?? PROFILES.overhead_throw);
      detectorProfileId = profileId;
    }

    const result = landmarker.detectForVideo(videoEl, nowMs);
    ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

    const landmarks = result.landmarks && result.landmarks[0];
    const points = pointsFromLandmarks(landmarks, arm);
    // Hips/shoulders for the hip-shoulder separation estimate — optional:
    // pointsForTorso() returns null if either hip is out of frame, and
    // ReleaseDetector already treats a null hip reading as "no hip signal
    // this frame," falling back to the arm-only test.
    const torso = pointsForTorso(landmarks);
    if (!points) {
      detector.reset();
      onState({ phase: "no pose detected", elbowAngleDeg: null, hipShoulderSeparationDeg: null, justReleased: false, releaseVelocity: null });
    } else {
      onState(detector.update(points, nowMs / 1000, torso));

      ctx.strokeStyle = "#4fc7b0";
      ctx.lineWidth = 3;
      ctx.beginPath();
      [points.shoulder, points.elbow, points.wrist].forEach((p, i) => {
        const x = p.x * overlayCanvas.width;
        const y = p.y * overlayCanvas.height;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      // Hip and shoulder lines, drawn only when both are tracked — visual
      // confirmation that the hip-shoulder separation signal is actually
      // seeing something, not just a number in the HUD to take on faith.
      if (torso) {
        ctx.strokeStyle = "#e0b855";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(torso.leftShoulder.x * overlayCanvas.width, torso.leftShoulder.y * overlayCanvas.height);
        ctx.lineTo(torso.rightShoulder.x * overlayCanvas.width, torso.rightShoulder.y * overlayCanvas.height);
        ctx.stroke();
        ctx.strokeStyle = "#e08655";
        ctx.beginPath();
        ctx.moveTo(torso.leftHip.x * overlayCanvas.width, torso.leftHip.y * overlayCanvas.height);
        ctx.lineTo(torso.rightHip.x * overlayCanvas.width, torso.rightHip.y * overlayCanvas.height);
        ctx.stroke();
      }
    }
    requestAnimationFrame(frame);
  }
  frame();
}
