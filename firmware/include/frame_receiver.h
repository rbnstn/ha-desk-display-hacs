#pragma once
#include <stddef.h>
#include <stdint.h>

// Incremental decoder shared by the ESP32 and native protocol tests.
// Bounds are checked before drawing a chunk; an odd byte is kept for the next one.
class FrameReceiver {
 public:
  static constexpr size_t kBytes = 480 * 320 * 2;
  void reset() { received_ = 0; pending_ = false; valid_ = true; }
  template <typename Writer>
  bool feed(const uint8_t* data, size_t length, Writer write) {
    if (!valid_ || length > kBytes - received_) { valid_ = false; return false; }
    received_ += length;
    uint16_t pixels[256];
    size_t count = 0;
    for (size_t index = 0; index < length; ++index) {
      if (!pending_) { low_ = data[index]; pending_ = true; }
      else {
        pixels[count++] = static_cast<uint16_t>(low_) | (static_cast<uint16_t>(data[index]) << 8);
        pending_ = false;
        if (count == 256) { write(pixels, count); count = 0; }
      }
    }
    if (count) write(pixels, count);
    return true;
  }
  bool complete() const { return valid_ && received_ == kBytes && !pending_; }
 private:
  size_t received_ = 0;
  uint8_t low_ = 0;
  bool pending_ = false;
  bool valid_ = true;
};

