// Connects to the Python sensor-fusion WebSocket service and streams parsed
// readings to a callback. Auto-reconnects — the demo shouldn't die because a
// socket dropped for a second.
//
// Returns { send(text) -> boolean }. send() is false when the socket is not
// open, so a caller can tell the user the request did not go through.
export function connectSensorFeed(url, onReading) {
  const status = document.getElementById("status");
  let current = null;

  function connect() {
    const socket = new WebSocket(url);
    current = socket;
    socket.onopen = () => {
      status.textContent = "sensor service connected";
    };
    socket.onmessage = (event) => {
      try {
        onReading(JSON.parse(event.data));
      } catch (err) {
        console.error("bad sensor payload", err);
      }
    };
    socket.onclose = () => {
      status.textContent = "sensor service disconnected — retrying…";
      setTimeout(connect, 2000);
    };
    socket.onerror = () => socket.close();
  }

  connect();

  return {
    send(text) {
      if (current && current.readyState === WebSocket.OPEN) {
        current.send(text);
        return true;
      }
      return false;
    },
  };
}
