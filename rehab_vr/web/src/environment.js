// Builds the objects the exposure ladder toggles (catcher, batter, onlookers,
// backstop, sky) and a small procedural crowd-noise generator. This is a
// generic park/sandlot, not an MLB stadium — no grandstand, no floodlight
// towers, no electronic scoreboard. A live test session (2026-09-27, see
// PROJECT_LOG.md) called the old version out for looking like "a bunch of
// orange balls in the background," which was literally correct: the earlier
// crowd was 240 tiny instanced spheres in front of a dark box. The social
// gradient the exposure ladder is actually about (fear of throwing badly in
// front of *someone*) is now a handful of simple standing figures at the
// fence line, growing in number with the level's crowdVolume, not a filled
// stadium — see onlookers below.
//
// The catcher and batter load real rigged glTF models (free, CC0/Khronos-
// licensed sample models, fetched at runtime from a public CDN — no binary
// assets checked into this repo, same pattern already used for Three.js and
// MediaPipe). Everything else stays primitives + canvas textures. If the
// model CDN is unreachable, each figure falls back to the old primitive-built
// silhouette rather than rendering nothing — the demo should never go blank
// because a CDN fetch failed.
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js";
// Dynamic, not static: GLTFLoader.js imports Three.js internally via the
// bare specifier "three" (resolved by the <script type="importmap"> in
// index.html). A statically-imported dependency chain can race ahead of
// importmap registration in some browsers; loading it lazily on first use
// runs only after the page (and its importmap) has already fully parsed,
// sidestepping that entirely — same fix as main.js's VRButton import.
let gltfLoaderPromise = null;
function getGltfLoader() {
  if (!gltfLoaderPromise) {
    gltfLoaderPromise = import("https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/loaders/GLTFLoader.js").then(
      (m) => new m.GLTFLoader()
    );
  }
  return gltfLoaderPromise;
}

// Free, CC0-licensed Khronos glTF sample models — generic rigged humanoids,
// not baseball-specific (none exist freely), used as honest stand-ins.
const CATCHER_MODEL_URL =
  "https://cdn.jsdelivr.net/gh/KhronosGroup/glTF-Sample-Models@main/2.0/RiggedFigure/glTF-Binary/RiggedFigure.glb";
const BATTER_MODEL_URL =
  "https://cdn.jsdelivr.net/gh/KhronosGroup/glTF-Sample-Models@main/2.0/CesiumMan/glTF-Binary/CesiumMan.glb";

const CATCHER_COLOR = 0x2a333a;
const BATTER_COLOR = 0x8c3a1d;
const BAT_COLOR = 0xc9a87c;
const FENCE_COLOR = 0x5c5347;
const TREE_TRUNK_COLOR = 0x4a3a2a;
const TREE_LEAF_COLOR = 0x3a5a34;
// A few different shirt colors so a park onlooker reads as "a person," not
// as a repeated colored dot — the complaint the single-color crowd spheres
// drew.
const ONLOOKER_COLORS = [0x3a4a5c, 0x5c4a3a, 0x4a5c3a, 0x5c3a4a];

function buildFigure(bodyColor, { headY, torsoHeight, torsoRadius, legHeight, hasArms }) {
  const group = new THREE.Group();

  const head = new THREE.Mesh(
    new THREE.SphereGeometry(0.16, 12, 10),
    new THREE.MeshStandardMaterial({ color: bodyColor })
  );
  head.position.set(0, headY, 0);
  group.add(head);

  const torso = new THREE.Mesh(
    new THREE.CapsuleGeometry(torsoRadius, torsoHeight, 4, 8),
    new THREE.MeshStandardMaterial({ color: bodyColor })
  );
  torso.position.set(0, headY - 0.16 - torsoHeight / 2 - torsoRadius, 0);
  group.add(torso);

  const legY = torso.position.y - torsoHeight / 2 - torsoRadius - legHeight / 2;
  for (const side of [-1, 1]) {
    const leg = new THREE.Mesh(
      new THREE.CylinderGeometry(0.07, 0.07, legHeight, 8),
      new THREE.MeshStandardMaterial({ color: bodyColor })
    );
    leg.position.set(side * torsoRadius * 0.6, legY, 0);
    group.add(leg);
  }

  let arms = null;
  if (hasArms) {
    arms = [];
    for (const side of [-1, 1]) {
      const arm = new THREE.Mesh(
        new THREE.CylinderGeometry(0.05, 0.05, torsoHeight * 0.8, 8),
        new THREE.MeshStandardMaterial({ color: bodyColor })
      );
      arm.position.set(side * (torsoRadius + 0.08), torso.position.y + torsoHeight * 0.15, 0);
      arm.rotation.z = side * 0.35;
      group.add(arm);
      arms.push(arm);
    }
  }

  return { group, head, torso, arms };
}

// Scales a loaded glTF scene to a target height and sits it on the group's
// local floor (y=0) — avoids hardcoding a scale factor guessed from a model
// file's contents, which differ per source and would silently look wrong
// (too big/small) if guessed instead of measured.
function fitHeightToFloor(object3d, targetHeight) {
  // Force world matrices (and, for a skinned mesh, its bind-pose bone
  // transforms) to be current before measuring — Box3().setFromObject()
  // reads whatever matrices are already computed, and a just-loaded object
  // that's never been part of a render pass yet can still be carrying
  // stale/identity matrices at this point.
  object3d.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(object3d);
  const size = new THREE.Vector3();
  box.getSize(size);

  // A skinned mesh's bounding box can come back wrong before its first
  // render/pose update, making size.y tiny — targetHeight/size.y then
  // blows the scale up huge and the camera ends up rendering the *inside*
  // of a giant mesh (exactly the dark full-screen shapes seen in testing).
  // Clamp to a sane range and log loudly if it ever triggers, rather than
  // silently letting a bad bounding box wreck the scene again.
  let scale = size.y > 0.001 ? targetHeight / size.y : 1;
  if (scale > 8 || scale < 0.05) {
    console.warn(
      `fitHeightToFloor: rejected an unreasonable scale (${scale.toFixed(2)}x, measured size.y=${size.y.toFixed(4)}) — using 1x instead.`
    );
    scale = 1;
  }
  object3d.scale.multiplyScalar(scale);

  const rescaledBox = new THREE.Box3().setFromObject(object3d);
  object3d.position.y -= rescaledBox.min.y;
}

const modelCache = new Map(); // avoid re-downloading the same model for catcher vs. spares

function loadFigureModel(url) {
  if (!modelCache.has(url)) {
    modelCache.set(
      url,
      getGltfLoader().then(
        (loader) =>
          new Promise((resolve, reject) => {
            // GLTFLoader keeps animation clips separate from the scene graph
            // (gltf.animations, not gltf.scene.animations) — pass both through
            // explicitly rather than assuming the clips ride along with the scene.
            loader.load(url, (gltf) => resolve({ scene: gltf.scene, animations: gltf.animations }), undefined, reject);
          })
      )
    );
  }
  return modelCache.get(url);
}

// Builds a group holding the old primitive silhouette (visible immediately,
// so the scene is never empty), then swaps in the real glTF model once it
// loads — or just keeps the primitive if the fetch fails.
function buildLoadableFigure(bodyColor, primitiveOpts, modelUrl, targetHeight, animate) {
  const fallback = buildFigure(bodyColor, primitiveOpts);
  const group = new THREE.Group();
  group.add(fallback.group);

  // Not cloned: each model URL here is only ever requested by one figure,
  // so there's no shared-instance risk — and Three.js's default clone()
  // does not correctly re-bind skeletons on rigged meshes (that needs
  // SkeletonUtils.clone), so skipping it entirely sidesteps that pitfall.
  let mixer = null;
  loadFigureModel(modelUrl)
    .then(({ scene: model, animations }) => {
      fitHeightToFloor(model, targetHeight);
      group.add(model);
      fallback.group.visible = false;

      if (animate && animations?.length) {
        // CesiumMan's clip is a literal walk cycle with real forward
        // translation baked into its root bone's position track — playing
        // it unmodified visibly walks the model away from its assigned
        // spot over time. Stripping .position tracks keeps only the
        // in-place limb rotation, so it reads as idle life, not locomotion.
        const clip = animations[0].clone();
        clip.tracks = clip.tracks.filter((track) => !track.name.endsWith(".position"));
        mixer = new THREE.AnimationMixer(model);
        mixer.clipAction(clip).play();
      }
      console.log(`figure model loaded: ${modelUrl}`);
    })
    .catch((err) => {
      console.warn(`figure model failed to load (${modelUrl}), keeping the primitive stand-in:`, err);
    });

  return { group, fallback, getMixer: () => mixer };
}

function makeCanvasTexture(draw, width = 512, height = 512) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  draw(canvas.getContext("2d"), width, height);
  const texture = new THREE.CanvasTexture(canvas);
  return texture;
}

function buildSky() {
  // A vertical gradient, redrawn per exposure level: overcast/quiet at low
  // intensity, bright midday at high intensity — a park sky, not a stadium.
  const canvas = document.createElement("canvas");
  canvas.width = 2;
  canvas.height = 512;
  const texture = new THREE.CanvasTexture(canvas);
  return { canvas, texture };
}

function paintSky(sky, t) {
  // t: 0 (calm, overcast) -> 1 (bright midday). Interpolates two 3-stop
  // gradients, both daylight — a park, not a stadium at night under lights.
  const cool = ["#7c8b95", "#9aa6a0", "#a9b39a"];
  const warm = ["#5f9ee0", "#a9d0e8", "#cfe4c2"];
  const lerpHex = (a, b, f) => {
    const ah = parseInt(a.slice(1), 16);
    const bh = parseInt(b.slice(1), 16);
    const ar = (ah >> 16) & 255, ag = (ah >> 8) & 255, ab = ah & 255;
    const br = (bh >> 16) & 255, bg = (bh >> 8) & 255, bb = bh & 255;
    const r = Math.round(ar + (br - ar) * f);
    const g = Math.round(ag + (bg - ag) * f);
    const b2 = Math.round(ab + (bb - ab) * f);
    return `rgb(${r},${g},${b2})`;
  };
  const ctx = sky.canvas.getContext("2d");
  const grad = ctx.createLinearGradient(0, 0, 0, sky.canvas.height);
  grad.addColorStop(0, lerpHex(cool[0], warm[0], t));
  grad.addColorStop(0.55, lerpHex(cool[1], warm[1], t));
  grad.addColorStop(1, lerpHex(cool[2], warm[2], t));
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, sky.canvas.width, sky.canvas.height);
  sky.texture.needsUpdate = true;
}

// A flat pad on the ground, spun to a heading (radians, world Y axis) after
// being laid flat — see buildBasePath below for why rotation.y, not .z, is
// the correct axis once a plane has been laid flat with rotation.x.
function buildGroundPad(width, depth, color, headingRad = 0) {
  const pad = new THREE.Mesh(new THREE.PlaneGeometry(width, depth), new THREE.MeshStandardMaterial({ color }));
  pad.rotation.x = -Math.PI / 2;
  pad.rotation.y = headingRad;
  return pad;
}

// A straight ground strip from (fromX,fromZ) to (toX,toZ) — used for base
// paths, the cricket pitch, etc. Once a PlaneGeometry is laid flat with
// rotation.x = -PI/2, its face normal ends up pointing along world +Y, so a
// further rotation.y (the fixed, real vertical axis) is what spins it
// in-plane to point any direction on the ground — rotation.z at that point
// would spin it around a horizontal axis instead, tipping it up on edge.
function buildGroundStrip(fromX, fromZ, toX, toZ, width, color) {
  const dx = toX - fromX;
  const dz = toZ - fromZ;
  const length = Math.hypot(dx, dz);
  const heading = Math.atan2(-dx / length, -dz / length);
  const strip = buildGroundPad(width, length, color, heading);
  strip.position.set((fromX + toX) / 2, 0, (fromZ + toZ) / 2);
  return strip;
}

// A repeating mowed-stripe grass texture — alternating light/dark bands,
// the pattern real groomed turf gets from mowing one pass in each direction.
// One small tile, repeated across the ground via RepeatWrapping, so this
// doesn't need a giant canvas to cover the whole 80x80 plane.
function buildGrassTexture() {
  const texture = makeCanvasTexture((ctx, w, h) => {
    const stripes = 8;
    const stripeHeight = h / stripes;
    for (let i = 0; i < stripes; i++) {
      ctx.fillStyle = i % 2 === 0 ? "#4a7a3d" : "#437030";
      ctx.fillRect(0, i * stripeHeight, w, stripeHeight);
    }
  }, 32, 256);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(12, 12);
  return texture;
}

// --- Baseball diamond: sized and placed from a real photo (2026-09-27
// session) — a groomed dirt skin bounded by a diamond of base paths, an
// inset infield-grass diamond, foul lines, and batter's boxes, all baked
// onto one overlay texture so it can have soft edges and painted lines
// without dozens of separate meshes. Compressed toward the camera side so
// every corner stays in view from this fixed camera position — real base
// distances (90 ft apart) would put second base and the mound well behind
// where this scene's camera actually sits. Not a survey drawing.
const DIAMOND_HOME = { x: 0, z: -13 };
const DIAMOND_FIRST = { x: 4.2, z: -7.8 };
const DIAMOND_SECOND = { x: 0, z: -2.2 }; // stylized: sits just short of the real mound (built in main.js, z=0)
const DIAMOND_THIRD = { x: -4.2, z: -7.8 };
const DIAMOND_WIDTH = 15;
const DIAMOND_DEPTH = 18;
const DIAMOND_CENTER_Z = -7.6;

function buildDiamondTexture() {
  const points = [DIAMOND_HOME, DIAMOND_FIRST, DIAMOND_SECOND, DIAMOND_THIRD];
  const cx = points.reduce((s, p) => s + p.x, 0) / points.length;
  const cz = points.reduce((s, p) => s + p.z, 0) / points.length;
  const scaled = (factor) => points.map((p) => ({ x: cx + (p.x - cx) * factor, z: cz + (p.z - cz) * factor }));

  return makeCanvasTexture((ctx, w, h) => {
    const toX = (x) => ((x + DIAMOND_WIDTH / 2) / DIAMOND_WIDTH) * w;
    const toY = (z) => (1 - (z - (DIAMOND_CENTER_Z - DIAMOND_DEPTH / 2)) / DIAMOND_DEPTH) * h;
    const fillPoly = (pts, style) => {
      ctx.fillStyle = style;
      ctx.beginPath();
      pts.forEach((p, i) => (i === 0 ? ctx.moveTo(toX(p.x), toY(p.z)) : ctx.lineTo(toX(p.x), toY(p.z))));
      ctx.closePath();
      ctx.fill();
    };

    ctx.clearRect(0, 0, w, h); // transparent outside the field, so the grass ground shows through
    fillPoly(scaled(1.55), "#8a5a34"); // dirt skin
    fillPoly(scaled(0.55), "#4f7a3c"); // infield grass, a touch darker than the outfield stripes

    ctx.strokeStyle = "#e7ece0";
    ctx.lineWidth = 4;
    for (const base of [DIAMOND_FIRST, DIAMOND_THIRD]) {
      const extended = { x: base.x * 1.6, z: DIAMOND_HOME.z + (base.z - DIAMOND_HOME.z) * 1.6 };
      ctx.beginPath();
      ctx.moveTo(toX(DIAMOND_HOME.x), toY(DIAMOND_HOME.z));
      ctx.lineTo(toX(extended.x), toY(extended.z));
      ctx.stroke();
    }

    ctx.strokeStyle = "rgba(231,236,224,0.85)";
    ctx.lineWidth = 3;
    const boxW = toX(1.1) - toX(0);
    const boxH = toY(DIAMOND_HOME.z - 1.0) - toY(DIAMOND_HOME.z + 1.0);
    ctx.strokeRect(toX(0.6), toY(DIAMOND_HOME.z + 1.0), boxW, boxH);
    ctx.strokeRect(toX(-1.7), toY(DIAMOND_HOME.z + 1.0), boxW, boxH);
  }, 512, 512);
}

function buildDiamond(groundY) {
  const group = new THREE.Group();

  const overlay = new THREE.Mesh(
    new THREE.PlaneGeometry(DIAMOND_WIDTH, DIAMOND_DEPTH),
    new THREE.MeshBasicMaterial({ map: buildDiamondTexture(), transparent: true })
  );
  overlay.rotation.x = -Math.PI / 2;
  overlay.position.set(0, groundY + 0.004, DIAMOND_CENTER_Z);
  group.add(overlay);

  // A little physical relief at the three visible bases (second base is
  // stylized right up against the mound, so it's left out here rather than
  // drawn as a separate raised pad that would visually collide with it).
  for (const base of [DIAMOND_HOME, DIAMOND_FIRST, DIAMOND_THIRD]) {
    const pad = buildGroundPad(0.4, 0.4, 0xdedcc8, Math.PI / 4);
    pad.position.set(base.x, groundY + 0.008, base.z);
    group.add(pad);
  }
  return group;
}

// --- Cricket: dimensions are the real ones (20.12m between popping
// creases, 3.05m pitch width, 71.1cm stumps 22.86cm apart with bails) —
// unlike the throw/arm thresholds elsewhere in this project, a cricket
// pitch's measurements are a published constant, not a biomechanical guess,
// so there's no reason to compress or approximate them. Bowling-motion
// detection reuses the generic overhead-release model (see
// activity_profiles.js) as an approximation, not a validated bowling
// classifier — it doesn't check a legal (straight-arm) delivery or model
// the run-up.
const CRICKET_PITCH_LENGTH = 20.12;
const CRICKET_PITCH_WIDTH = 3.05;
const CRICKET_CENTER_Z = -11.5;

function buildCricketPitchTexture() {
  return makeCanvasTexture((ctx, w, h) => {
    ctx.fillStyle = "#c2a878";
    ctx.fillRect(0, 0, w, h);
    // Subtle worn/patchy variation so it doesn't read as a flat color fill.
    for (let i = 0; i < 130; i++) {
      ctx.fillStyle = `rgba(140,110,72,${0.03 + Math.random() * 0.06})`;
      ctx.fillRect(Math.random() * w, Math.random() * h, 8 + Math.random() * 26, 5 + Math.random() * 12);
    }

    ctx.strokeStyle = "rgba(255,255,255,0.9)";
    ctx.lineWidth = 4;
    // Bowling creases, right at each end.
    ctx.beginPath();
    ctx.moveTo(0, 3);
    ctx.lineTo(w, 3);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(0, h - 3);
    ctx.lineTo(w, h - 3);
    ctx.stroke();

    // Popping creases, 1.22m in front of each set of stumps, with short
    // return-crease ticks at each edge.
    const poppingFrac = 1.22 / CRICKET_PITCH_LENGTH;
    for (const f of [poppingFrac, 1 - poppingFrac]) {
      ctx.beginPath();
      ctx.moveTo(0, f * h);
      ctx.lineTo(w, f * h);
      ctx.stroke();
      const dir = f < 0.5 ? 1 : -1;
      for (const x of [w * 0.18, w * 0.82]) {
        ctx.beginPath();
        ctx.moveTo(x, f * h);
        ctx.lineTo(x, f * h + dir * h * 0.045);
        ctx.stroke();
      }
    }
  }, 96, 1024);
}

function buildStumps(groundY, z) {
  const group = new THREE.Group();
  const stumpMaterial = new THREE.MeshStandardMaterial({ color: 0xd9c9a0 });
  const stumpTopY = groundY + 0.711;
  const xs = [-0.1143, 0, 0.1143];
  for (const x of xs) {
    const stump = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.711, 8), stumpMaterial);
    stump.position.set(x, groundY + 0.3555, z);
    group.add(stump);
  }
  for (let i = 0; i < xs.length - 1; i++) {
    const bail = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.145, 6), stumpMaterial);
    bail.rotation.z = Math.PI / 2;
    bail.position.set((xs[i] + xs[i + 1]) / 2, stumpTopY + 0.012, z);
    group.add(bail);
  }
  return group;
}

// A simple, generic pavilion-style building behind the far end of the
// pitch — evoking "a ground has a stand," not a reproduction of any real,
// identifiable venue's architecture.
function buildPavilion(groundY, z) {
  const group = new THREE.Group();
  const body = new THREE.Mesh(
    new THREE.BoxGeometry(10, 3.2, 3),
    new THREE.MeshStandardMaterial({ color: 0x6b4a3a })
  );
  body.position.set(0, groundY + 1.6, z);
  group.add(body);
  const roof = new THREE.Mesh(
    new THREE.BoxGeometry(10.6, 0.3, 3.6),
    new THREE.MeshStandardMaterial({ color: 0x2f2a28 })
  );
  roof.position.set(0, groundY + 3.35, z);
  group.add(roof);
  const stand = new THREE.Mesh(
    new THREE.BoxGeometry(10, 1.4, 1.8),
    new THREE.MeshStandardMaterial({ color: 0xe7ece7 })
  );
  stand.position.set(0, groundY + 0.7, z + 2.1);
  group.add(stand);
  return group;
}

function buildCricketPitch(groundY) {
  const group = new THREE.Group();
  const pitch = new THREE.Mesh(
    new THREE.PlaneGeometry(CRICKET_PITCH_WIDTH, CRICKET_PITCH_LENGTH),
    new THREE.MeshBasicMaterial({ map: buildCricketPitchTexture() })
  );
  pitch.rotation.x = -Math.PI / 2;
  pitch.position.set(0, groundY + 0.004, CRICKET_CENTER_Z);
  group.add(pitch);

  const nearZ = CRICKET_CENTER_Z + CRICKET_PITCH_LENGTH / 2;
  const farZ = CRICKET_CENTER_Z - CRICKET_PITCH_LENGTH / 2;
  group.add(buildStumps(groundY, nearZ));
  group.add(buildStumps(groundY, farZ));
  group.add(buildPavilion(groundY, farZ - 4));
  return group;
}

// --- Tennis: a basic court rectangle with painted lines, and a net. Serve
// detection is NOT implemented — scenery only, same reasoning as cricket.
function buildTennisCourt(groundY) {
  const group = new THREE.Group();
  const lineTexture = makeCanvasTexture((ctx, w, h) => {
    ctx.fillStyle = "#2e6b4f";
    ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = "rgba(255,255,255,0.85)";
    ctx.lineWidth = 6;
    ctx.strokeRect(20, 20, w - 40, h - 40);
    ctx.beginPath();
    ctx.moveTo(w / 2, 20);
    ctx.lineTo(w / 2, h - 20);
    ctx.stroke();
  }, 256, 512);
  const court = new THREE.Mesh(
    new THREE.PlaneGeometry(8, 16),
    new THREE.MeshBasicMaterial({ map: lineTexture })
  );
  court.rotation.x = -Math.PI / 2;
  court.position.set(0, groundY + 0.004, -10);
  group.add(court);

  const net = new THREE.Mesh(
    new THREE.PlaneGeometry(8, 0.9),
    new THREE.MeshBasicMaterial({ map: buildNetTexture(), transparent: true, opacity: 0.7, side: THREE.DoubleSide })
  );
  net.position.set(0, groundY + 0.45, -10);
  group.add(net);
  for (const x of [-4, 4]) {
    const post = new THREE.Mesh(
      new THREE.CylinderGeometry(0.04, 0.04, 0.95, 6),
      new THREE.MeshStandardMaterial({ color: 0x2a333a })
    );
    post.position.set(x, groundY + 0.475, -10);
    group.add(post);
  }
  return group;
}

// --- Basketball: a basic court patch, backboard and hoop. Shot detection is
// NOT implemented — scenery only, same reasoning as cricket/tennis.
function buildBasketballCourt(groundY) {
  const group = new THREE.Group();
  const courtTexture = makeCanvasTexture((ctx, w, h) => {
    ctx.fillStyle = "#a97a4b"; // wood tone
    ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = "rgba(255,255,255,0.85)";
    ctx.lineWidth = 5;
    ctx.strokeRect(20, 20, w - 40, h - 40);
    ctx.beginPath();
    ctx.arc(w / 2, h * 0.78, 60, 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeRect(w / 2 - 90, h - 40, 180, -220);
  }, 512, 512);
  const court = new THREE.Mesh(
    new THREE.PlaneGeometry(10, 10),
    new THREE.MeshBasicMaterial({ map: courtTexture })
  );
  court.rotation.x = -Math.PI / 2;
  court.position.set(0, groundY + 0.004, -10);
  group.add(court);

  const pole = new THREE.Mesh(
    new THREE.CylinderGeometry(0.06, 0.06, 3.0, 8),
    new THREE.MeshStandardMaterial({ color: 0x2a333a })
  );
  pole.position.set(0, groundY + 1.5, -13.6);
  group.add(pole);
  const backboard = new THREE.Mesh(
    new THREE.PlaneGeometry(1.1, 0.7),
    new THREE.MeshStandardMaterial({ color: 0xe7ece7 })
  );
  backboard.position.set(0, groundY + 2.4, -13.4);
  group.add(backboard);
  const hoop = new THREE.Mesh(
    new THREE.TorusGeometry(0.23, 0.02, 8, 16),
    new THREE.MeshStandardMaterial({ color: 0xd9822b })
  );
  hoop.rotation.x = Math.PI / 2;
  hoop.position.set(0, groundY + 2.1, -13.15);
  group.add(hoop);
  return group;
}

// Every basic venue a trainer can preview, and the group builder for each.
// Cricket/tennis/basketball are scenery only — see activity_profiles.js for
// why their motion detection is not implemented, and note that clearly to
// anyone reading this alongside the "Activity" dropdown, which stays
// disabled for them.
export const VENUES = [
  { id: "baseball", label: "Baseball diamond" },
  { id: "cricket", label: "Cricket pitch (basic)" },
  { id: "tennis", label: "Tennis court (basic)" },
  { id: "basketball", label: "Basketball court (basic)" },
];

// Cross-hatch net pattern with an alpha channel — used for the backstop.
function buildNetTexture() {
  return makeCanvasTexture((ctx, w, h) => {
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = "rgba(255,255,255,0.35)";
    ctx.lineWidth = 1;
    const step = 14;
    for (let x = -h; x < w + h; x += step) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x + h, h);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(x, h);
      ctx.lineTo(x + h, 0);
      ctx.stroke();
    }
  }, 256, 256);
}

export function buildEnvironment(scene) {
  // --- Sky ---
  const sky = buildSky();
  paintSky(sky, 0);
  scene.background = sky.texture;

  // --- Ground: was missing entirely — without it, the scene.background
  // texture (a flat 2D backdrop, not a skydome) fills the *entire*
  // viewport uniformly, including where a ground should be, which is why
  // it read as "fully gray" with nothing underfoot. A real grass plane
  // fixes that.
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(80, 80),
    new THREE.MeshStandardMaterial({ map: buildGrassTexture() })
  );
  ground.rotation.x = -Math.PI / 2;
  // The mound cylinder in main.js sits at y=-0.85 with height 0.3, so its
  // base is at -1.0 — ground goes there, not at the mound's own y, or the
  // plane would slice through the mound's middle instead of sitting under it.
  ground.position.y = -1.0;
  scene.add(ground);

  const GROUND_Y = -1.0;
  const venueGroups = {
    baseball: buildDiamond(GROUND_Y),
    cricket: buildCricketPitch(GROUND_Y),
    tennis: buildTennisCourt(GROUND_Y),
    basketball: buildBasketballCourt(GROUND_Y),
  };
  for (const [id, group] of Object.entries(venueGroups)) {
    group.visible = id === "baseball"; // baseball is the default venue
    scene.add(group);
  }

  // --- Catcher: real rigged model (RiggedFigure), primitive fallback ---
  const catcherLoadable = buildLoadableFigure(
    CATCHER_COLOR,
    { headY: 0.55, torsoHeight: 0.35, torsoRadius: 0.24, legHeight: 0.3, hasArms: false },
    CATCHER_MODEL_URL,
    1.0, // crouched-height stand-in — the source model's own pose isn't a real crouch
    false
  );
  catcherLoadable.group.position.set(0, 0.2, -14);
  catcherLoadable.group.visible = false;
  scene.add(catcherLoadable.group);

  // --- Batter: real rigged + animated model (CesiumMan), primitive fallback ---
  const batterLoadable = buildLoadableFigure(
    BATTER_COLOR,
    { headY: 1.15, torsoHeight: 0.55, torsoRadius: 0.22, legHeight: 0.55, hasArms: true },
    BATTER_MODEL_URL,
    1.75,
    true // play the model's own animation clip as ambient life, not a real swing motion
  );
  batterLoadable.group.position.set(1.1, 0.35, -12.5);
  batterLoadable.group.visible = false;
  scene.add(batterLoadable.group);

  const bat = new THREE.Mesh(
    new THREE.CylinderGeometry(0.03, 0.055, 0.85, 8),
    new THREE.MeshStandardMaterial({ color: BAT_COLOR })
  );
  bat.position.set(0.35, 0.55, 0);
  bat.rotation.z = Math.PI / 3.2;
  bat.visible = false;
  batterLoadable.fallback.group.add(bat); // only meaningful on the primitive stand-in; CesiumMan has no bat

  // --- Backstop net ---
  const backstop = new THREE.Mesh(
    new THREE.PlaneGeometry(6, 3.5),
    new THREE.MeshBasicMaterial({ map: buildNetTexture(), transparent: true, opacity: 0.45, side: THREE.DoubleSide })
  );
  backstop.position.set(0, 1.6, -15.5);
  backstop.visible = false;
  scene.add(backstop);

  // --- Park fence: a low chain-link backstop line behind the field, not a
  // grandstand. Always present (a park has a fence whether or not anyone's
  // watching) — only the onlookers standing at it come and go with the level.
  const FENCE_WIDTH = 22;
  const FENCE_HEIGHT = 1.4;
  const fence = new THREE.Mesh(
    new THREE.PlaneGeometry(FENCE_WIDTH, FENCE_HEIGHT),
    new THREE.MeshBasicMaterial({ map: buildNetTexture(), color: FENCE_COLOR, transparent: true, opacity: 0.55, side: THREE.DoubleSide })
  );
  fence.position.set(0, -1.0 + FENCE_HEIGHT / 2, -19);
  scene.add(fence);

  // --- Trees: static park scenery, always visible, level-independent — a
  // few low-poly trees so an empty level still reads as a park and not a
  // void, without needing a real crowd to look like anywhere at all.
  const TREE_SPOTS = [
    [-11, -21], [-7.5, -22.5], [8, -21.5], [11.5, -20], [-14, -18], [14, -19],
  ];
  for (const [x, z] of TREE_SPOTS) {
    const tree = new THREE.Group();
    const trunk = new THREE.Mesh(
      new THREE.CylinderGeometry(0.14, 0.18, 1.6, 6),
      new THREE.MeshStandardMaterial({ color: TREE_TRUNK_COLOR })
    );
    trunk.position.y = -1.0 + 0.8;
    tree.add(trunk);
    const leaves = new THREE.Mesh(
      new THREE.SphereGeometry(1.1 + Math.random() * 0.3, 8, 6),
      new THREE.MeshStandardMaterial({ color: TREE_LEAF_COLOR })
    );
    leaves.position.y = -1.0 + 1.9;
    tree.add(leaves);
    tree.position.set(x, 0, z);
    scene.add(tree);
  }

  // --- Light towers + a distant building silhouette: static background
  // structure so the far side of the field reads as a real facility, not
  // empty air past the trees (photo reference, 2026-09-27 session). Not
  // tied to any exposure level or venue — always there, like the trees.
  for (const [x, z] of [[-13, -22], [13, -22]]) {
    const tower = new THREE.Group();
    const pole = new THREE.Mesh(
      new THREE.CylinderGeometry(0.12, 0.16, 7.5, 8),
      new THREE.MeshStandardMaterial({ color: 0x3a3f45 })
    );
    pole.position.y = -1.0 + 3.75;
    tower.add(pole);
    const fixture = new THREE.Mesh(
      new THREE.BoxGeometry(1.6, 0.9, 0.3),
      new THREE.MeshStandardMaterial({ color: 0x2a2f35 })
    );
    fixture.position.y = -1.0 + 7.6;
    tower.add(fixture);
    tower.position.set(x, 0, z);
    scene.add(tower);
  }
  const building = new THREE.Group();
  const buildingBody = new THREE.Mesh(
    new THREE.BoxGeometry(9, 3, 3),
    new THREE.MeshStandardMaterial({ color: 0x4a4038 })
  );
  buildingBody.position.set(0, -1.0 + 1.5, -24);
  building.add(buildingBody);
  const buildingRoof = new THREE.Mesh(
    new THREE.BoxGeometry(9.4, 0.3, 3.4),
    new THREE.MeshStandardMaterial({ color: 0x2a262a })
  );
  buildingRoof.position.set(0, -1.0 + 3.15, -24);
  building.add(buildingRoof);
  scene.add(building);

  // --- Onlookers: a handful of simple standing figures at the fence, not a
  // filled stadium. A fixed pool is built once; applyExposureLevel shows
  // only as many as the current level's crowdVolume calls for, so this is a
  // visibility toggle, not a rebuild, same pattern as the rest of the scene.
  const MAX_ONLOOKERS = 10;
  const onlookers = new THREE.Group();
  for (let i = 0; i < MAX_ONLOOKERS; i++) {
    const person = buildFigure(ONLOOKER_COLORS[i % ONLOOKER_COLORS.length], {
      headY: 1.0,
      torsoHeight: 0.45,
      torsoRadius: 0.16,
      legHeight: 0.45,
      hasArms: false,
    }).group;
    // Spread along the fence line, just behind it, with a little depth/spacing
    // jitter so they don't read as a mechanically even row.
    const x = (i / (MAX_ONLOOKERS - 1) - 0.5) * (FENCE_WIDTH - 2) + (Math.random() - 0.5) * 0.6;
    const z = -19.6 - Math.random() * 0.6;
    person.position.set(x, -1.0, z);
    person.visible = false;
    onlookers.add(person);
  }
  scene.add(onlookers);

  const daylight = new THREE.HemisphereLight(0xffffff, 0x3a4a2a, 0.9);
  scene.add(daylight);
  const sun = new THREE.DirectionalLight(0xfff4e0, 0.6);
  sun.position.set(-6, 10, 4);
  scene.add(sun);

  // --- Pitch ball: the actual throw, previously entirely missing — the
  // scene reacted to the sensor score, but a real throwing motion in front
  // of the webcam did nothing visible in the world. `throwPitch()` below
  // fires this on a detected release.
  const ball = new THREE.Mesh(
    new THREE.SphereGeometry(0.07, 12, 12),
    new THREE.MeshStandardMaterial({ color: 0xf3f1e8, emissive: 0xf3f1e8, emissiveIntensity: 0.15 })
  );
  ball.visible = false;
  scene.add(ball);
  const pitchState = { ball, active: null };

  return {
    catcher: catcherLoadable.group,
    batter: batterLoadable.group,
    batterLoadable,
    bat,
    backstop,
    onlookers,
    daylight,
    sky,
    pitchState,
    venueGroups,
    venue: "baseball",
    currentLevel: null,
  };
}

// Baseball's actors (catcher/batter/backstop/bat) should only show when
// BOTH the exposure level calls for them AND the venue is actually baseball
// — switching to cricket/tennis/basketball shouldn't leave a catcher
// standing in the middle of a tennis court. applyExposureLevel and
// applyVenue can run in either order, so both call this afterward using
// whichever of {level, venue} was set most recently.
function refreshBaseballActors(handles) {
  const level = handles.currentLevel;
  const isBaseball = handles.venue === "baseball";
  handles.catcher.visible = isBaseball && !!level?.catcherPresent;
  handles.batter.visible = isBaseball && !!level?.batterPresent;
  handles.bat.visible = isBaseball && !!level?.batterSwinging;
  handles.backstop.visible = isBaseball && !!level?.catcherPresent;
}

// Switches which basic venue is shown. See VENUES for the full list; falls
// back to baseball for an unrecognized id rather than leaving the scene with
// nothing visible.
export function applyVenue(handles, venueId) {
  const id = handles.venueGroups[venueId] ? venueId : "baseball";
  handles.venue = id;
  for (const [groupId, group] of Object.entries(handles.venueGroups)) {
    group.visible = groupId === id;
  }
  refreshBaseballActors(handles);
}

// Advances the batter model's ambient animation clip, if/once it's loaded.
// Call once per rendered frame with the seconds elapsed since the last call.
export function updateAnimations(handles, deltaSeconds) {
  handles.batterLoadable.getMixer()?.update(deltaSeconds);
}

const PITCH_DURATION = 0.42; // seconds, release to plate — fast but readable, used when there's no tracked release to react to
const PITCH_ARC_HEIGHT = 0.35; // same idea — the default when there's no release data
const PITCH_RELEASE = new THREE.Vector3(0.25, 1.25, 1.2); // roughly where a real release point would be, this close to the camera
const PITCH_TARGET_DEFAULT = new THREE.Vector3(0, 1.0, -13); // used when no catcher/backstop is present to aim at

const MIN_PITCH_DURATION = 0.2; // never let a fast release make the flight unreadably short
const MAX_PITCH_DURATION = 0.7; // never let a slow/noisy release make it drag
// How far the release point can shift from PITCH_RELEASE based on where in
// the camera frame the wrist actually was — a stylistic mapping from image
// position to scene position (the wrist's normalized 0-1 frame coordinate
// isn't a measured 3D position), not a calibrated projection.
const RELEASE_X_RANGE = 0.45;
const RELEASE_Y_RANGE = 0.3;

// Turns the tracked release speed (see ReleaseDetector's own comment on why
// this is a relative image-space quantity, not mph) into a flight duration:
// a faster tracked release plays a shorter, snappier flight. The 0.18
// scaling constant and the min/max clamps are visual-feel choices, tuned by
// eye, not derived from any real speed-to-time relationship.
function pitchDurationFor(speed) {
  if (!(speed > 0)) return PITCH_DURATION;
  return Math.max(MIN_PITCH_DURATION, Math.min(MAX_PITCH_DURATION, PITCH_DURATION / (1 + speed * 0.18)));
}

// Turns the tracked release angle into how high the pitch's arc peaks: a
// more upward release plays a higher arc, a flatter or downward-trending
// release plays a flatter one. Clamped hard so a noisy angle reading can
// never send the arc negative (the ball diving through the ground) or
// absurdly high.
function pitchArcHeightFor(angleDeg) {
  if (!Number.isFinite(angleDeg)) return PITCH_ARC_HEIGHT;
  const clamped = Math.max(-30, Math.min(60, angleDeg));
  return Math.max(0.08, PITCH_ARC_HEIGHT * (0.4 + clamped / 60));
}

// Where the ball starts from, nudged from the fixed release point toward
// wherever in the camera frame the hand actually released — see
// RELEASE_X_RANGE/RELEASE_Y_RANGE above.
function pitchReleasePointFor(releaseVelocity) {
  if (!releaseVelocity || !Number.isFinite(releaseVelocity.x) || !Number.isFinite(releaseVelocity.y)) {
    return PITCH_RELEASE.clone();
  }
  const dx = (0.5 - releaseVelocity.x) * 2 * RELEASE_X_RANGE;
  const dy = (0.5 - releaseVelocity.y) * 2 * RELEASE_Y_RANGE;
  return PITCH_RELEASE.clone().add(new THREE.Vector3(dx, dy, 0));
}

// Starts a new pitch animation toward the catcher (or a default downrange
// point if no catcher is present at the current level). No-ops if a pitch
// is already in flight, so rapid-fire throw detections can't spawn
// overlapping balls. onArrive fires once, when the ball reaches the plate.
//
// releaseVelocity is the optional { speed, angleDeg, x, y } from
// ReleaseDetector's update() — when it's missing (or any field isn't a
// finite number), this falls back to the original fixed-feel pitch exactly
// as before, so a dropped tracking frame at the moment of release never
// breaks the animation.
export function throwPitch(handles, onArrive, releaseVelocity) {
  const { pitchState } = handles;
  if (pitchState.active) return;

  const target = handles.catcher.visible
    ? handles.catcher.position.clone().add(new THREE.Vector3(0, 0.9, 0))
    : PITCH_TARGET_DEFAULT.clone();
  const from = pitchReleasePointFor(releaseVelocity);
  const duration = releaseVelocity ? pitchDurationFor(releaseVelocity.speed) : PITCH_DURATION;
  const arcHeight = releaseVelocity ? pitchArcHeightFor(releaseVelocity.angleDeg) : PITCH_ARC_HEIGHT;

  pitchState.active = { elapsed: 0, from, to: target, onArrive, duration, arcHeight };
  pitchState.ball.visible = true;
  pitchState.ball.position.copy(from);
}

// Call once per rendered frame with the seconds elapsed since the last call.
export function updatePitch(handles, deltaSeconds) {
  const { pitchState } = handles;
  const active = pitchState.active;
  if (!active) return;

  active.elapsed += deltaSeconds;
  const t = Math.min(1, active.elapsed / active.duration);

  pitchState.ball.position.lerpVectors(active.from, active.to, t);
  // A simple upward arc (peaks mid-flight) rather than a flat straight-line
  // throw, purely for readability — real pitch trajectories are much
  // flatter than this, this is a visual clarity choice, not a physics model.
  pitchState.ball.position.y += Math.sin(t * Math.PI) * active.arcHeight;

  if (t >= 1) {
    pitchState.ball.visible = false;
    pitchState.active = null;
    active.onArrive?.();
  }
}

export function applyExposureLevel(handles, level) {
  handles.currentLevel = level;
  refreshBaseballActors(handles);

  // How many of the fixed onlooker pool are shown scales with crowdVolume —
  // a handful of people at the fence at the busiest level, not a stadium.
  const people = handles.onlookers.children;
  const shownCount = Math.round(level.crowdVolume * people.length);
  people.forEach((person, i) => {
    person.visible = i < shownCount;
  });

  handles.daylight.intensity = 0.5 + level.lightingIntensity * 0.5;

  // 0 at the calmest level's lightingIntensity, 1 at the brightest — reuses
  // the ladder's own documented intensity field rather than a second scale.
  const t = Math.max(0, Math.min(1, (level.lightingIntensity - 0.55) / (1.0 - 0.55)));
  paintSky(handles.sky, t);
}

// Procedural crowd noise (filtered white noise) — no external audio asset.
// Browsers block audio before a user gesture, so this is created lazily and
// wrapped defensively; a missing audio cue should never break the demo.
export function createCrowdNoise() {
  let ctx = null;
  let gain = null;

  function ensureStarted() {
    if (ctx) return;
    try {
      ctx = new (window.AudioContext || window.webkitAudioContext)();
      const bufferSize = 2 * ctx.sampleRate;
      const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
      const data = buffer.getChannelData(0);
      for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1;

      const noise = ctx.createBufferSource();
      noise.buffer = buffer;
      noise.loop = true;

      const filter = ctx.createBiquadFilter();
      filter.type = "bandpass";
      filter.frequency.value = 800;

      gain = ctx.createGain();
      gain.gain.value = 0;

      noise.connect(filter).connect(gain).connect(ctx.destination);
      noise.start();
    } catch (err) {
      console.warn("crowd noise unavailable:", err);
    }
  }

  return {
    setVolume(v) {
      ensureStarted();
      if (!gain) return;
      const clamped = Math.max(0, Math.min(1, v));
      gain.gain.linearRampToValueAtTime(clamped * 0.15, (ctx.currentTime || 0) + 0.5);
    },
  };
}
