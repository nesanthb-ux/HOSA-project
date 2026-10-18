# ARIA — Unity/Quest Build (Future Work Track)

**Status: scaffolding only.** The logic in `Assets/Scripts/` is a faithful C#
port of the verified WebXR build (`rehab_vr/`) — same exposure ladder, same
escalate/retreat thresholds, same explainability phrasing. None of it has
been opened in the Unity Editor, built, or run. Everything past "write the
scripts" requires the actual Editor, which cannot be driven from this
environment — that part is on you (or whoever on the team has Unity
installed).

**Read this before starting:** `PIVOT_PLAN.md` §9 flagged this as deferred
future work specifically because a Unity + Quest native build-and-deploy
cycle is real, multi-day-to-multi-week effort even for an experienced Unity
developer — asset import, XR rig setup, Android/Quest build signing, and
actual testing on headset hardware. The WebXR build in `rehab_vr/` is
already working, already verified end-to-end, and needs zero rebuild for a
browser-based Quest demo (open the URL in the Quest's browser). Only keep
pushing this track if the team has real Unity experience and time to spare
beyond the WebXR build — otherwise this becomes two half-finished projects
instead of one working one.

---

## 1. What's already here

```
rehab_vr_unity/
  Packages/manifest.json      XR Interaction Toolkit, XR Management, OpenXR, TextMeshPro, Input System
  Assets/Scripts/
    ExposureLevels.cs          the 5-level ladder + AdaptiveExposureEngine (port of exposure_levels.js)
    Explainability.cs          athlete/trainer phrasing (port of explain.js)
    SensorFeedClient.cs        WebSocket client for the SAME Python sensor service
    ExposureEnvironmentController.cs   toggles scene objects per level (port of environment.js)
    ExplainabilityHud.cs        orchestrator wiring the above to UI text fields
```

Nothing here is a `.unity` scene, a prefab, or an imported 3D model —
those have to be built in the Editor.

## 2. What you need to do in Unity (I cannot do this part)

1. **Install Unity Hub + Unity 2022 LTS** (matches the package versions in
   `manifest.json`).
2. **Open this folder as a Unity project** (`File > Open Project`, point at
   `rehab_vr_unity/`). Unity will restore the packages from `manifest.json`
   automatically.
3. **Add NativeWebSocket** (Unity has no built-in WebSocket API that works
   on Quest/Android under IL2CPP): `Window > Package Manager > + > Add
   package from git URL` →
   `https://github.com/endel/NativeWebSocket.git#upm`
4. **Install the Meta XR SDK** (formerly Oculus Integration) from the Unity
   Asset Store, or use plain OpenXR with the Meta Quest feature group
   (`Project Settings > XR Plug-in Management > OpenXR`, enable "Meta Quest
   Support" under Android tab). Either path works; Meta's SDK has more
   Quest-specific niceties, OpenXR is more portable.
5. **Switch build platform to Android** (`File > Build Settings > Android >
   Switch Platform`) — required for any Quest build.
6. **Source or build the 3D assets.** Nothing here provides actual models:
   - Rigged humanoid characters (catcher, batter) — Mixamo
     (mixamo.com, free, Adobe account) is the standard free source for
     rigged, animated humanoid characters compatible with Unity's Mecanim
     system. The `Swing` animation trigger in
     `ExposureEnvironmentController.cs` expects an Animator with a state
     matching `SwingTriggerName`.
   - Stadium/crowd/props (bleachers, lights, scoreboard) — Kenney.nl or
     Quaternius both publish free CC0 low-poly asset packs well suited to
     a stylized (non-photoreal) look, which also renders cheaper on
     standalone Quest hardware than realistic models would.
   - Crowd: the controller assumes a single `ParticleSystem` standing in
     for "many people" (cheap, standard Unity trick) rather than hundreds
     of individual character instances — swap for GPU-instanced meshes
     later if you want individually distinct crowd figures.
7. **Build the scene**, matching the concept storyboard
   (`aria_storyboard` artifact) and the WebXR build's layout: mound in the
   foreground, home plate/catcher/batter downrange, backstop, stands
   behind, two stadium light rigs, a scoreboard.
8. **Add an empty GameObject** with `ExplainabilityHud`,
   `ExposureEnvironmentController`, and `SensorFeedClient` components
   attached, and wire every public field in the Inspector to the scene
   objects and TextMeshPro UI elements you just built. Set
   `SensorFeedClient.HostOverride` to your laptop's LAN IP before building
   for the headset — leaving it blank resolves to `localhost`, which on a
   Quest means the headset itself, not your laptop running the Python
   service (same gotcha the WebXR build's `location.hostname` fix
   addressed).
9. **Run the same Python sensor service** as the WebXR build needs — no
   changes required there:
   ```bash
   cd rehab_vr/sensor_service
   python -m rehab_vr.sensor_service.server
   ```
10. **Build & deploy to Quest**: `File > Build Settings > Build` (or `Build
    And Run` with the headset connected via USB and Developer Mode
    enabled on the device).

## 3. Known gaps vs. the WebXR build

- No trainer-view sparkline yet (flagged in `ExplainabilityHud.cs`).
- No adaptation log panel wired up yet (flagged in `ExplainabilityHud.cs`)
  — the event fires, nothing renders it to a list yet.
- No throwing-motion tracking — the WebXR build uses MediaPipe in the
  browser; Quest's own hand/controller tracking would replace that here,
  and isn't wired up.
- No audio — the WebXR build's procedural crowd noise isn't ported;
  Unity's own `AudioSource` + a real crowd-noise clip would be simpler
  here than the browser's Web Audio workaround (no autoplay-unlock
  gesture needed), just not done yet.
