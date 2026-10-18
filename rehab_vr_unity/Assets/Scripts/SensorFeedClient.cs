// Connects to the SAME Python sensor-fusion WebSocket service the WebXR
// build uses (rehab_vr/sensor_service/server.py) — nothing on the Python
// side changes for Unity. Mirrors rehab_vr/web/src/sensor_client.js:
// auto-reconnects, never lets a dropped socket kill the session.
//
// REQUIRES the free NativeWebSocket package (Unity has no built-in
// cross-platform WebSocket API, and Quest/Android builds need one that
// works under IL2CPP). Add it in Package Manager -> Add package from git
// URL: https://github.com/endel/NativeWebSocket.git#upm
using System;
using UnityEngine;
using NativeWebSocket;

namespace Aria
{
    [Serializable]
    public class SensorReading
    {
        public double timestamp;
        public float eda_us;
        public float heart_rate_bpm;
        public float skin_temp_c;
        public float arousal_score;
    }

    public class SensorFeedClient : MonoBehaviour
    {
        [Tooltip("Leave blank to auto-derive from this device's connection to the host running the sensor service.")]
        public string HostOverride = "";
        public int Port = 8765;

        public event Action<SensorReading> OnReading;
        public event Action<string> OnStatusChanged;

        private WebSocket _socket;
        private bool _reconnecting;

        private async void Start()
        {
            await Connect();
        }

        private async System.Threading.Tasks.Task Connect()
        {
            string host = string.IsNullOrEmpty(HostOverride) ? "localhost" : HostOverride;
            // On a Quest, "localhost" means the headset itself — set
            // HostOverride to your laptop's LAN IP (the one running
            // sensor_service.server) before building for headset, the same
            // gotcha the WebXR build's location.hostname fix addressed.
            string url = $"ws://{host}:{Port}";

            _socket = new WebSocket(url);

            _socket.OnOpen += () => OnStatusChanged?.Invoke("sensor service connected");
            _socket.OnError += (e) => OnStatusChanged?.Invoke($"sensor service error: {e}");
            _socket.OnClose += (e) =>
            {
                OnStatusChanged?.Invoke("sensor service disconnected — retrying…");
                if (!_reconnecting) _ = Reconnect();
            };
            _socket.OnMessage += (bytes) =>
            {
                try
                {
                    var json = System.Text.Encoding.UTF8.GetString(bytes);
                    var reading = JsonUtility.FromJson<SensorReading>(json);
                    OnReading?.Invoke(reading);
                }
                catch (Exception ex)
                {
                    Debug.LogError($"bad sensor payload: {ex}");
                }
            };

            await _socket.Connect();
        }

        private async System.Threading.Tasks.Task Reconnect()
        {
            _reconnecting = true;
            await System.Threading.Tasks.Task.Delay(2000);
            _reconnecting = false;
            await Connect();
        }

        private void Update()
        {
#if !UNITY_WEBGL || UNITY_EDITOR
            // NativeWebSocket needs this pumped every frame on non-WebGL
            // platforms (standalone, Android/Quest) to dispatch queued
            // callbacks on the main thread.
            _socket?.DispatchMessageQueue();
#endif
        }

        private async void OnApplicationQuit()
        {
            if (_socket != null) await _socket.Close();
        }
    }
}
