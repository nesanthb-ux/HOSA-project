// Builds the JSON body the Python service's /ingest endpoint expects. A
// channel that is NAN (unavailable) is simply left out; the service treats an
// omitted channel as "no reading", never as zero. An all-NAN payload is the
// valid empty object {} and doubles as a heartbeat: it tells the service the
// node is alive but has nothing trustworthy to report this second.
// Portable C++ (unit tested on a PC).
#pragma once

#include <math.h>
#include <stddef.h>
#include <stdio.h>

namespace aria {

// Returns true and NUL-terminates buf on success. Returns false (and leaves a
// valid empty string in buf) if it would not fit; never overflows.
inline bool buildPayload(char* buf, size_t bufLen, float edaUs, float heartRateBpm, float skinTempC) {
  if (buf == nullptr || bufLen == 0) return false;
  buf[0] = '\0';

  size_t used = 0;
  auto append = [&](const char* fmt, float value, bool& first) -> bool {
    if (!isfinite(value)) return true;  // omitted on purpose
    const int n = snprintf(buf + used, bufLen - used, fmt, first ? "" : ",", value);
    if (n < 0 || static_cast<size_t>(n) >= bufLen - used) return false;
    used += static_cast<size_t>(n);
    first = false;
    return true;
  };

  if (bufLen < 3) return false;
  buf[used++] = '{';
  buf[used] = '\0';

  bool first = true;
  if (!append("%s\"eda_us\":%.3f", edaUs, first)) { buf[0] = '\0'; return false; }
  if (!append("%s\"heart_rate_bpm\":%.1f", heartRateBpm, first)) { buf[0] = '\0'; return false; }
  if (!append("%s\"skin_temp_c\":%.2f", skinTempC, first)) { buf[0] = '\0'; return false; }

  if (used + 2 > bufLen) { buf[0] = '\0'; return false; }
  buf[used++] = '}';
  buf[used] = '\0';
  return true;
}

}  // namespace aria
