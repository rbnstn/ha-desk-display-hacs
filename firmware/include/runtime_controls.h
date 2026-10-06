#pragma once
#include <stdint.h>

// Unsigned subtraction also works across the millis() rollover.
struct SleepController {
  uint32_t after=0,lastActivity=0;
  int brightness=0;
  bool sleeping=false;
  void wake(uint32_t now){sleeping=false;lastActivity=now;}
  bool touch(uint32_t now){bool consumed=sleeping;wake(now);return consumed;}
  bool tick(uint32_t now){
    if(after && !sleeping && static_cast<uint32_t>(now-lastActivity)>=after){sleeping=true;return true;}
    return false;
  }
};
