// Direct C# port of rehab_vr/web/src/exposure_levels.js — same five levels,
// same asymmetric escalate/retreat thresholds, verified live in the WebXR
// build before this port existed. Keep this file's data and this engine's
// behavior in sync with the JS original if either changes; don't let the
// two tracks drift into different clinical logic.
//
// This is a designed prototype ladder, not a validated clinical exposure
// protocol — see PIVOT_PLAN.md §3a/§9. State it that way to judges.
using System;
using System.Collections.Generic;

namespace Aria
{
    [Serializable]
    public class ExposureLevel
    {
        public int Id;
        public string Name;
        public string Description;
        public float CrowdVolume;      // 0..1
        public bool CatcherPresent;
        public bool BatterPresent;
        public bool BatterSwinging;
        public float LightingIntensity; // 0..1

        public ExposureLevel(int id, string name, string description, float crowdVolume,
            bool catcherPresent, bool batterPresent, bool batterSwinging, float lightingIntensity)
        {
            Id = id;
            Name = name;
            Description = description;
            CrowdVolume = crowdVolume;
            CatcherPresent = catcherPresent;
            BatterPresent = batterPresent;
            BatterSwinging = batterSwinging;
            LightingIntensity = lightingIntensity;
        }
    }

    public enum AdaptationAction { Advance, Retreat }

    public struct AdaptationEvent
    {
        public AdaptationAction Action;
        public float Score;
        public float Threshold;
        public float HoldSeconds; // only meaningful for Advance

        public AdaptationEvent(AdaptationAction action, float score, float threshold, float holdSeconds)
        {
            Action = action;
            Score = score;
            Threshold = threshold;
            HoldSeconds = holdSeconds;
        }
    }

    public static class ExposureLevels
    {
        // Documented, prototype-stage thresholds — deliberately conservative
        // and asymmetric: escalation requires sustained calm; retreat is
        // immediate. The system should never escalate faster than it
        // retreats — that's the actual clinical principle being encoded.
        public const float EscalateBelow = 0.35f;
        public const float EscalateHoldSeconds = 8f;
        public const float RetreatAbove = 0.75f;

        public static readonly List<ExposureLevel> Levels = new List<ExposureLevel>
        {
            new ExposureLevel(0, "Solo toss",
                "Empty field. No batter, no catcher — reacquainting with a ball in hand.",
                0f, false, false, false, 0.55f),
            new ExposureLevel(1, "Bullpen, catcher only",
                "A catcher's target is present. Quiet bullpen, no batter.",
                0f, true, false, false, 0.7f),
            new ExposureLevel(2, "Batter stands in, no swing",
                "A batter is in the box but not swinging — reintroduces a person near the release point without live-swing risk.",
                0.15f, true, true, false, 0.8f),
            new ExposureLevel(3, "Live batting practice",
                "The batter takes live swings. Light ambient crowd presence.",
                0.45f, true, true, true, 0.9f),
            new ExposureLevel(4, "Full game simulation",
                "Full stadium ambience, count/scoreboard pressure, live batter.",
                1.0f, true, true, true, 1.0f),
        };
    }

    public class AdaptiveExposureEngine
    {
        private int _levelIndex;
        private float _calmSecondsAtLevel;

        public ExposureLevel CurrentLevel => ExposureLevels.Levels[_levelIndex];
        public float CalmSeconds => _calmSecondsAtLevel;

        public event Action<ExposureLevel, AdaptationEvent> OnChange;

        // Call once per fused sensor reading (~1Hz); dt in seconds since the
        // last call.
        public void Update(float arousalScore, float dt)
        {
            if (arousalScore >= ExposureLevels.RetreatAbove && _levelIndex > 0)
            {
                _levelIndex -= 1;
                _calmSecondsAtLevel = 0f;
                OnChange?.Invoke(CurrentLevel,
                    new AdaptationEvent(AdaptationAction.Retreat, arousalScore, ExposureLevels.RetreatAbove, 0f));
                return;
            }

            if (arousalScore < ExposureLevels.EscalateBelow)
            {
                _calmSecondsAtLevel += dt;
                if (_calmSecondsAtLevel >= ExposureLevels.EscalateHoldSeconds &&
                    _levelIndex < ExposureLevels.Levels.Count - 1)
                {
                    _levelIndex += 1;
                    _calmSecondsAtLevel = 0f;
                    OnChange?.Invoke(CurrentLevel, new AdaptationEvent(
                        AdaptationAction.Advance, arousalScore, ExposureLevels.EscalateBelow, ExposureLevels.EscalateHoldSeconds));
                }
            }
            else
            {
                _calmSecondsAtLevel = 0f;
            }
        }
    }
}
