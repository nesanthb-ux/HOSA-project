// Direct C# port of rehab_vr/web/src/explain.js — two audiences, one set of
// facts, both built from the same AdaptationEvent so they can't drift out
// of sync with each other or with what the engine actually did.
using System;

namespace Aria
{
    public static class Explainability
    {
        public static string TechnicalReason(AdaptationEvent e)
        {
            int pct = Mathf_RoundToInt(e.Score * 100f);
            if (e.Action == AdaptationAction.Retreat)
            {
                return $"Retreated one level — arousal reading {e.Score:F2} crossed the retreat threshold ({e.Threshold:0.##}).";
            }
            return $"Advanced one level — arousal stayed below {e.Threshold:0.##} for {e.HoldSeconds:0}s straight (last reading {e.Score:F2}, {pct}%).";
        }

        public static string AthleteReason(AdaptationEvent e)
        {
            return e.Action == AdaptationAction.Retreat
                ? "We eased back a step — your body showed some stress there. Totally normal, let's reset and try again."
                : "Nice and steady. Since you held calm for a while, we're stepping it up a notch.";
        }

        // A short, level-agnostic status line shown even between adaptation
        // events, so the panel never looks frozen while waiting for the next one.
        public static string AthleteIdleStatus(float secondsCalm, float holdTarget, bool isMaxLevel)
        {
            if (isMaxLevel) return "Full game intensity — holding here.";
            if (secondsCalm <= 0f) return "Reading your response to this level.";
            int remaining = Mathf_Max(0, Mathf_CeilToInt(holdTarget - secondsCalm));
            return remaining > 0
                ? $"Staying steady — {remaining}s more at this level before we step it up."
                : "Holding here.";
        }

        // Local rounding helpers so this file has zero UnityEngine dependency
        // and can be unit-tested outside Unity if that's ever useful.
        private static int Mathf_RoundToInt(float v) => (int)Math.Round(v, MidpointRounding.AwayFromZero);
        private static int Mathf_CeilToInt(float v) => (int)Math.Ceiling(v);
        private static int Mathf_Max(int a, int b) => a > b ? a : b;
    }
}
