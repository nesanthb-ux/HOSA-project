// Orchestrator: wires SensorFeedClient -> AdaptiveExposureEngine ->
// ExposureEnvironmentController, and drives the athlete/trainer HUD text —
// the C# equivalent of what rehab_vr/web/src/main.js does in the browser.
//
// NOT ported yet from the WebXR build: the trainer-view arousal sparkline
// (main.js's drawSparkline/canvas). Said explicitly here rather than
// silently dropped — add a Unity UI LineRenderer or uGUI RawImage-based
// version later if the trainer view needs it for the demo.
//
// Assign every field in the Inspector; this script has no scene of its own.
using TMPro;
using UnityEngine;

namespace Aria
{
    public class ExplainabilityHud : MonoBehaviour
    {
        [Header("Wiring")]
        public SensorFeedClient SensorFeed;
        public ExposureEnvironmentController Environment;

        [Header("HUD — shared")]
        public TMP_Text StatusText;
        public TMP_Text LevelNameText;
        public TMP_Text LevelDescText;
        public TMP_Text WhyText;
        public TMP_Text WhyTechnicalText;   // hidden in athlete view
        public GameObject[] TrainerOnlyPanels; // raw numbers, log panel — hidden in athlete view

        [Header("HUD — trainer-only numbers")]
        public TMP_Text EdaText;
        public TMP_Text HeartRateText;
        public TMP_Text SkinTempText;
        public TMP_Text ScoreText;

        private readonly AdaptiveExposureEngine _engine = new AdaptiveExposureEngine();
        private bool _athleteView;
        private float _reasonHoldUntil;
        private float _lastReadingTime;

        private void Start()
        {
            _engine.OnChange += HandleAdaptation;
            SensorFeed.OnStatusChanged += (s) => { if (StatusText) StatusText.text = s; };
            SensorFeed.OnReading += HandleReading;

            ApplyLevel(_engine.CurrentLevel);
            RenderIdle();
        }

        public void ToggleView()
        {
            _athleteView = !_athleteView;
            foreach (var panel in TrainerOnlyPanels)
                if (panel) panel.SetActive(!_athleteView);
            _reasonHoldUntil = 0f; // an explicit view switch should update immediately, not wait out the hold
            RenderIdle();
        }

        private void HandleReading(SensorReading reading)
        {
            if (EdaText) EdaText.text = $"{reading.eda_us:F2} µS";
            if (HeartRateText) HeartRateText.text = $"{reading.heart_rate_bpm:F0} bpm";
            if (SkinTempText) SkinTempText.text = $"{reading.skin_temp_c:F1} °C";
            if (ScoreText) ScoreText.text = $"{reading.arousal_score:F2}";

            float now = Time.time;
            float dt = _lastReadingTime > 0f ? now - _lastReadingTime : 0f;
            _lastReadingTime = now;

            _engine.Update(reading.arousal_score, dt);
            RenderIdle();
        }

        private void HandleAdaptation(ExposureLevel level, AdaptationEvent evt)
        {
            ApplyLevel(level);
            if (WhyText) WhyText.text = _athleteView ? Explainability.AthleteReason(evt) : Explainability.TechnicalReason(evt);
            if (WhyTechnicalText) WhyTechnicalText.text = "";
            _reasonHoldUntil = Time.time + 4f;
            // TODO: append to a trainer-facing log panel, same as main.js's
            // logAdaptation() — not wired to a UI list here yet.
        }

        private void ApplyLevel(ExposureLevel level)
        {
            if (LevelNameText) LevelNameText.text = $"Level {level.Id} — {level.Name}";
            if (LevelDescText) LevelDescText.text = level.Description;
            Environment.Apply(level);
        }

        private void RenderIdle()
        {
            if (Time.time < _reasonHoldUntil) return;
            bool isMaxLevel = _engine.CurrentLevel.Id == ExposureLevels.Levels[ExposureLevels.Levels.Count - 1].Id;
            string idle = Explainability.AthleteIdleStatus(_engine.CalmSeconds, ExposureLevels.EscalateHoldSeconds, isMaxLevel);

            if (_athleteView)
            {
                if (WhyText) WhyText.text = idle;
                if (WhyTechnicalText) WhyTechnicalText.text = "";
            }
            else
            {
                if (WhyText) WhyText.text = $"Holding at Level {_engine.CurrentLevel.Id}.";
                if (WhyTechnicalText) WhyTechnicalText.text = idle;
            }
        }
    }
}
