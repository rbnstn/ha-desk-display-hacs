#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

// A complete region is validated before any pixel is drawn. No full framebuffer.
class RegionReceiver {
 public:
  static constexpr size_t kCapacity = 65536;
  // WebServer handles one upload at a time; JPEG reuses this same storage.
  void beginPayload() { size_=0; pixels_=0; valid_=true; rle_=false; }
  const uint8_t* data() const { return data_; }
  size_t size() const { return size_; }
  bool begin(int x, int y, int width, int height, bool rle) {
    size_ = 0; rle_ = rle;
    valid_ = x >= 0 && y >= 0 && width > 0 && height > 0 &&
             width <= 480 && height <= 320 && x <= 480-width && y <= 320-height;
    pixels_ = valid_ ? static_cast<size_t>(width)*height : 0;
    if (!rle && pixels_*2 > kCapacity) valid_ = false;
    return valid_;
  }
  bool feed(const uint8_t* bytes, size_t length) {
    if (!valid_ || length > kCapacity-size_) { valid_ = false; return false; }
    memcpy(data_+size_, bytes, length); size_ += length;
    return true;
  }
  bool complete() const {
    if (!valid_) return false;
    if (!rle_) return size_ == pixels_*2;
    if (!size_ || size_%4) return false;
    size_t total = 0;
    for (size_t i=0; i<size_; i+=4) {
      const uint16_t count = word(i);
      if (!count || count > pixels_-total) return false;
      total += count;
    }
    return total == pixels_;
  }
  template<typename Writer> bool draw(Writer write) const {
    if (!complete()) return false;
    uint16_t block[256]; size_t used = 0;
    for (size_t i=0; i<size_; i+=rle_ ? 4 : 2) {
      const uint16_t value = word(i+(rle_ ? 2 : 0));
      const size_t count = rle_ ? word(i) : 1;
      for (size_t j=0; j<count; ++j) {
        block[used++] = value;
        if (used == 256) { write(block,used); used=0; }
      }
    }
    if (used) write(block,used);
    return true;
  }
 private:
  uint16_t word(size_t i) const { return data_[i] | (static_cast<uint16_t>(data_[i+1])<<8); }
  uint8_t data_[kCapacity];
  size_t size_=0, pixels_=0;
  bool valid_=false, rle_=false;
};

