// Mirrors rehab_vr/web/src/environment.js's applyExposureLevel() — same
// per-level fields (CatcherPresent, BatterPresent, BatterSwinging,
// CrowdVolume, LightingIntensity) drive the same kind of state changes,
// just against real Inspector-wired scene objects instead of Three.js
// primitives built in code.
//
// Every field below must be assigned in the Unity Editor Inspector — this
// script has no scene to attach to on its own. See rehab_vr_unity/README.md
// for what to build and wire up.
using UnityEngine;

namespace Aria
{
    public class ExposureEnvironmentController : MonoBehaviour
    {
        [Header("Figures")]
        public GameObject Catcher;
        public GameObject Batter;
        public Animator BatterAnimator;      // trigger a "Swing" animation state when BatterSwinging is true
        public const string SwingTriggerName = "Swing";

        [Header("Crowd")]
        public ParticleSystem Crowd;         // simplest way to fake "hundreds of people" cheaply in Unity
        public GameObject Stands;

        [Header("Lighting")]
        public Light[] StadiumLights;        // intensity scales with CrowdVolume above a threshold, matching the WebXR build
        public float StadiumLightThreshold = 0.3f;
        public float StadiumLightMaxIntensity = 3f;
        public Light AmbientLight;           // stands in for the WebXR build's HemisphereLight

        [Header("Sky")]
        public Material SkyboxMaterial;      // expects a shader exposing a "_Tint" or gradient color property
        public Color SkyColorCalm = new Color32(0x1B, 0x23, 0x2B, 0xFF);
        public Color SkyColorFullGame = new Color32(0x5C, 0x4A, 0x37, 0xFF);

        [Header("Scoreboard")]
        public GameObject Scoreboard;        // visible only at max level (CrowdVolume >= 1.0)

        public void Apply(ExposureLevel level)
        {
            if (Catcher) Catcher.SetActive(level.CatcherPresent);
            if (Batter) Batter.SetActive(level.BatterPresent);
            if (BatterAnimator && level.BatterSwinging) BatterAnimator.SetTrigger(SwingTriggerName);

            if (Stands) Stands.SetActive(level.CrowdVolume > 0f);
            if (Crowd)
            {
                var emission = Crowd.emission;
                emission.rateOverTime = level.CrowdVolume * 40f;
                var main = Crowd.main;
                var c = main.startColor.color;
                c.a = 0.2f + level.CrowdVolume * 0.8f;
                main.startColor = c;
            }

            if (AmbientLight) AmbientLight.intensity = level.LightingIntensity;

            foreach (var light in StadiumLights)
            {
                if (!light) continue;
                bool on = level.CrowdVolume > StadiumLightThreshold;
                light.intensity = on ? Mathf.Lerp(0.5f, StadiumLightMaxIntensity, level.CrowdVolume) : 0f;
            }

            if (SkyboxMaterial && SkyboxMaterial.HasProperty("_Tint"))
            {
                float t = Mathf.InverseLerp(0.55f, 1.0f, level.LightingIntensity);
                SkyboxMaterial.SetColor("_Tint", Color.Lerp(SkyColorCalm, SkyColorFullGame, t));
            }

            if (Scoreboard) Scoreboard.SetActive(level.CrowdVolume >= 1.0f);
        }
    }
}
