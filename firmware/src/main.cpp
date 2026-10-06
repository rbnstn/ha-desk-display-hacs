#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <TFT_eSPI.h>
#include <TJpg_Decoder.h>
#include <Preferences.h>
#include <Update.h>
#include <memory>
#include <new>
#include <esp_system.h>
#include <freertos/task.h>
#if __has_include("secrets.h")
#include "secrets.h"
#else
#define DESK_WIFI_SSID ""
#define DESK_WIFI_PASSWORD ""
#define DESK_DEVICE_KEY ""
#endif
#include "runtime_controls.h"
#include "frame_receiver.h"
#include "region_receiver.h"

TFT_eSPI screen;
WebServer server(80);
String configuredSsid,configuredPassword,deviceKey,discoveryHost;
SleepController sleepControl;
bool mdnsActive=false,needsNetworkSetup=false;
int bootResetReason=0;
uint32_t reconnectAt=0;

String randomHex(size_t bytes) {
  String value;char pair[3];
  for(size_t i=0;i<bytes;++i){snprintf(pair,sizeof(pair),"%02x",static_cast<unsigned>(esp_random()&255));value+=pair;}
  return value;
}
bool validKey(const String& value) {
  if(value.length()<24 || value.length()>80 || value.startsWith("REPLACE"))return false;
  for(size_t i=0;i<value.length();++i)if(value[i]<33 || value[i]>126)return false;
  return true;
}
String htmlEscape(String value) {
  value.replace("&","&amp;");value.replace("<","&lt;");value.replace(">","&gt;");value.replace("\"","&quot;");value.replace("'","&#39;");return value;
}
void loadNetwork() {
  Preferences prefs;prefs.begin("desk-network",true);
  configuredSsid=prefs.getString("ssid",DESK_WIFI_SSID);
  configuredPassword=prefs.getString("password",DESK_WIFI_PASSWORD);
  deviceKey=prefs.getString("key",DESK_DEVICE_KEY);prefs.end();
  if(configuredSsid.startsWith("YOUR_"))configuredSsid="";
  if(!validKey(deviceKey)){deviceKey=randomHex(24);needsNetworkSetup=true;}
}
void configureNetwork() {
  server.stop();MDNS.end();mdnsActive=false;
  WiFi.mode(WIFI_AP_STA);
  String apName="DeskDisplay-"+WiFi.macAddress().substring(12);apName.replace(":","");
  const String apPassword=randomHex(6),token=randomHex(16);
  WiFi.softAP(apName.c_str(),apPassword.c_str());
  screen.fillScreen(TFT_BLACK);screen.setTextColor(TFT_WHITE,TFT_BLACK);
  screen.drawString("WLAN einrichten",16,20,2);screen.drawString(apName,16,55,2);
  screen.drawString("Passwort: "+apPassword,16,85,2);
  screen.drawString("Browser: http://192.168.4.1",16,120,2);
  WebServer portal(80);bool done=false;
  auto page=[&](const String& message){
    String html="<!doctype html><html lang='de'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Desk Display</title><body><h1>WLAN einrichten</h1><p>"+htmlEscape(message)+"</p><form method='post' action='/save'><input type='hidden' name='token' value='"+token+"'><p><label>WLAN Name <input name='ssid' maxlength='32' required value='"+htmlEscape(configuredSsid)+"'></label></p><p><label>WLAN Passwort <input name='password' type='password' maxlength='63' autocomplete='new-password'></label></p><p><label>Geräteschlüssel für Home Assistant <input name='key' minlength='24' maxlength='80' required value='"+htmlEscape(deviceKey)+"'></label></p><p>Den Geräteschlüssel kopieren und später in Home Assistant eingeben.</p><button>Speichern und verbinden</button></form></body></html>";
    portal.sendHeader("Cache-Control","no-store");portal.sendHeader("Content-Security-Policy","default-src 'none'; form-action 'self'; frame-ancestors 'none'");
    portal.send(200,"text/html; charset=utf-8",html);
  };
  portal.on("/",HTTP_GET,[&](){
    if(portal.client().localIP()!=WiFi.softAPIP()){portal.send(403,"text/plain","Nur über das Einrichtungs-WLAN");return;}page("");
  });
  portal.on("/save",HTTP_POST,[&](){
    if(portal.client().localIP()!=WiFi.softAPIP() || portal.arg("token")!=token){portal.send(403,"text/plain","Ungültige Einrichtung");return;}
    String ssid=portal.arg("ssid"),password=portal.arg("password"),key=portal.arg("key");
    if(!ssid.length() || ssid.length()>32 || (password.length() && (password.length()<8 || password.length()>63)) || !validKey(key)){page("Bitte WLAN Daten und Schlüssel prüfen.");return;}
    screen.drawString("Verbindung wird geprueft ...",16,155,2);
    WiFi.disconnect();WiFi.begin(ssid.c_str(),password.c_str());uint32_t started=millis();
    while(WiFi.status()!=WL_CONNECTED && millis()-started<20000)delay(100);
    if(WiFi.status()!=WL_CONNECTED){page("Verbindung fehlgeschlagen. Bitte WLAN Name und Passwort prüfen. Nur 2,4 GHz wird unterstützt.");return;}
    Preferences prefs;prefs.begin("desk-network",false);prefs.putString("ssid",ssid);prefs.putString("password",password);prefs.putString("key",key);prefs.end();
    configuredSsid=ssid;configuredPassword=password;deviceKey=key;needsNetworkSetup=false;
    portal.sendHeader("Cache-Control","no-store");portal.send(200,"text/html; charset=utf-8","<h1>Verbunden</h1><p>Display kann jetzt in Home Assistant eingerichtet werden.</p><p>IP: "+WiFi.localIP().toString()+"</p>");done=true;
  });
  portal.begin();while(!done){portal.handleClient();delay(2);}delay(500);portal.stop();WiFi.softAPdisconnect(true);WiFi.mode(WIFI_STA);
}
void advertiseDisplay() {
  MDNS.end();mdnsActive=MDNS.begin(discoveryHost.c_str());
  if(mdnsActive){MDNS.addService("desk-display","tcp",80);String id=WiFi.macAddress();id.replace(":","");id.toLowerCase();MDNS.addServiceTxt("desk-display","tcp","id",id);MDNS.addServiceTxt("desk-display","tcp","model","E32R35T");}
}
FrameReceiver receiver;
RegionReceiver regionReceiver;
bool regionReceiving=false, regionStarted=false, regionReady=false, regionFailed=false;
bool jpegReceiving=false, jpegStarted=false, jpegReady=false, jpegFailed=false;
int jpegX=0,jpegY=0,jpegWidth=0,jpegHeight=0;
int regionX=0, regionY=0, regionWidth=0, regionHeight=0;
size_t frameCursor=0;
bool debugEnabled=false;
bool hasFrame = false;
constexpr char kFirmwareMarker[]="desk_display:E32R35T:1";
constexpr char kFirmwareVersion[]="desk_display_version:0.9.0";
int backlightPercent=100;
bool otaReceiving=false,otaReady=false,otaFailed=false;
size_t otaBytes=0;
void setBrightness(int value) {
  backlightPercent=constrain(value,0,100);
  ledcWrite(2,(sleepControl.sleeping?sleepControl.brightness:backlightPercent)*255/100);
}
constexpr int kDebugX=256, kDebugY=300, kDebugWidth=224, kDebugHeight=20;
std::unique_ptr<uint16_t[]> debugUnderlay;
TaskHandle_t idleTasks[2];
hw_timer_t* cpuTimer=nullptr;
portMUX_TYPE sampleMux=portMUX_INITIALIZER_UNLOCKED;
volatile uint32_t cpuSamples=0, busySamples=0;
uint32_t completedFrames=0, metricsAt=0;
float cpuPercent=0, framesPerSecond=0;
uint32_t jpegReceiveAt=0, jpegReceiveUs=0, jpegSpiUs=0;
uint32_t jpegMeasuredFrames=0;
uint64_t jpegBytesTotal=0, jpegReceiveTotal=0, jpegRenderTotal=0, jpegSpiTotal=0;
float jpegBytesAverage=0, jpegReceiveMs=0, jpegDecodeMs=0, jpegDisplayMs=0;

void resetVideoTimings() {
  jpegMeasuredFrames=0;
  jpegBytesTotal=jpegReceiveTotal=jpegRenderTotal=jpegSpiTotal=0;
}

// Statistical scheduler sampling, not a loop-duration proxy. Compare both cores
// with their idle tasks. The standard Arduino SDK has no runtime task counters.
void sampleCpu() {
  const uint32_t busy=(xTaskGetCurrentTaskHandleForCPU(0)!=idleTasks[0])+
                      (xTaskGetCurrentTaskHandleForCPU(1)!=idleTasks[1]);
  portENTER_CRITICAL_ISR(&sampleMux);
  cpuSamples+=2; busySamples+=busy;
  portEXIT_CRITICAL_ISR(&sampleMux);
}

void drawDebug() {
  if (!debugEnabled || !hasFrame) return;
  char text[48];
  snprintf(text,sizeof(text),"CPU~ %.0f%%  FPS %.1f",cpuPercent,framesPerSecond);
  screen.fillRect(kDebugX,kDebugY,kDebugWidth,kDebugHeight,TFT_BLACK);
  screen.setTextColor(TFT_CYAN,TFT_BLACK);
  screen.drawRightString(text,476,302,2);
  screen.setTextColor(TFT_WHITE,TFT_BLACK);
}

void setDebug(bool enabled) {
  if (debugEnabled == enabled) return;
  debugEnabled=enabled;
  portENTER_CRITICAL(&sampleMux);
  cpuSamples=busySamples=0;
  portEXIT_CRITICAL(&sampleMux);
  completedFrames=0; metricsAt=millis(); cpuPercent=framesPerSecond=0;
  resetVideoTimings();
  jpegBytesAverage=jpegReceiveMs=jpegDecodeMs=jpegDisplayMs=0;
  if (enabled) {
    timerAlarmEnable(cpuTimer);
    drawDebug();
  } else {
    timerAlarmDisable(cpuTimer);
    if (hasFrame) {
      screen.startWrite();
      screen.setAddrWindow(kDebugX,kDebugY,kDebugWidth,kDebugHeight);
      screen.pushColors(debugUnderlay.get(),kDebugWidth*kDebugHeight,true);
      screen.endWrite();
    }
  }
}

void writePixels(uint16_t* pixels,size_t count,int x,int y,int width,size_t& cursor) {
  // Keep only the small area underneath the debug overlay, so turning it off
  // restores the real layout without another network frame or a full framebuffer.
  if (count && x+width>kDebugX && y+(cursor+count-1)/width>=kDebugY) for (size_t i=0;i<count;++i) {
    const int px=x+(cursor+i)%width, py=y+(cursor+i)/width;
    if (px>=kDebugX && px<480 && py>=kDebugY && py<320)
      debugUnderlay[(py-kDebugY)*kDebugWidth+px-kDebugX]=pixels[i];
  }
  cursor+=count;
  screen.pushColors(pixels,count,true);
}
bool uploading = false;
bool uploadStarted = false;
bool uploadFinished = false;
bool uploadFailed = false;
uint32_t lastContactAt = 0;
String frameRevision;
String touchId;
String touchRevision;
String bootId;
uint32_t touchSequence = 0;
uint32_t touchAt = 0;
uint32_t lastTouchAt = 0;
uint16_t touchX = 0, touchY = 0;
bool touchPending = false;
bool touchDown = false;
uint32_t gestureStartedAt=0;
uint16_t gestureValueX=0,gestureValueY=0;
String touchGesture="tap";
bool gestureArmed=false;

void calibrateTouch(bool force = false) {
  hasFrame = false;
  touchPending = false;
  frameRevision = "";
  uint16_t calibration[5];
  Preferences preferences;
  preferences.begin("desk-touch", false);
  if (force || preferences.getBytesLength("calibration") != sizeof(calibration)) {
    screen.fillScreen(TFT_BLACK);
    screen.drawString("Touch each corner as indicated", 20, 120);
    screen.calibrateTouch(calibration, TFT_CYAN, TFT_BLACK, 15);
    preferences.putBytes("calibration", calibration, sizeof(calibration));
  } else {
    preferences.getBytes("calibration", calibration, sizeof(calibration));
  }
  preferences.end();
  screen.setTouch(calibration);
  touchDown = true; // Wait for release after calibration before accepting a tap.
}

bool authenticated() {
  return server.header("X-Desk-Key") == deviceKey;
}

void closeUpload() {
  if (uploading) screen.endWrite();
  uploading = false;
}

void handleUpload() {
  HTTPUpload& upload = server.upload();
  if (upload.status == UPLOAD_FILE_START) {
    closeUpload();
    // Only one frame part per request is accepted.
    if (uploadStarted) { uploadFailed = true; return; }
    uploadStarted = true;
    uploadFailed = false;
    uploadFinished = false;
    receiver.reset();
    frameCursor=0;
    if (!authenticated() || upload.name != "frame") { uploadFailed = true; return; }
    hasFrame = false;
    screen.startWrite();
    screen.setAddrWindow(0, 0, 480, 320);
    uploading = true;
  } else if (upload.status == UPLOAD_FILE_WRITE && uploading) {
    if (!receiver.feed(upload.buf, upload.currentSize, [](uint16_t* pixels, size_t count) {
      writePixels(pixels,count,0,0,480,frameCursor);
    })) { uploadFailed = true; closeUpload(); }
  } else if (upload.status == UPLOAD_FILE_END) {
    uploadFinished = uploading && receiver.complete() && !uploadFailed;
    closeUpload();
  } else if (upload.status == UPLOAD_FILE_ABORTED) {
    uploadFailed = true;
    closeUpload();
    uploadStarted = false;
  }
}

void finishUpload() {
  closeUpload();
  if (!authenticated()) server.send(401, "text/plain", "Unauthorized");
  else if (!uploadFinished || uploadFailed) server.send(400, "text/plain", "Expected one 307200-byte RGB565 frame");
  else {
    hasFrame = true;
    frameRevision = server.arg("revision");
    if (frameRevision.length() != 32) frameRevision = "";
    touchPending = false;
    lastContactAt = millis();
    ++completedFrames;
    drawDebug();
    server.send(200, "text/plain", "OK");
  }
  uploadStarted = false;
  uploadFinished = false;
  uploadFailed = false;
}

bool validRevision(const String& revision) {
  if (revision.length()!=32) return false;
  for (unsigned int i=0;i<revision.length();++i)
    if (!isxdigit(revision[i])) return false;
  return true;
}

int coordinate(const char* name) {
  const String value=server.arg(name);
  if (!value.length() || value.length()>3) return -1;
  for (unsigned int i=0;i<value.length();++i) if (!isDigit(value[i])) return -1;
  return value.toInt();
}

void handleRegion() {
  HTTPUpload& upload=server.upload();
  if (upload.status==UPLOAD_FILE_START) {
    if (regionStarted) { regionFailed=true; regionReceiving=false; return; }
    regionStarted=true; regionFailed=false; regionReady=false;
    regionX=coordinate("x"); regionY=coordinate("y");
    regionWidth=coordinate("width"); regionHeight=coordinate("height");
    const String format=server.arg("format");
    regionReceiving=authenticated() && upload.name=="region" &&
      (format=="raw" || format=="rle") && validRevision(server.arg("revision")) &&
      (server.arg("final")=="0" || server.arg("final")=="1") &&
      regionReceiver.begin(regionX,regionY,regionWidth,regionHeight,format=="rle");
    if (!regionReceiving) { regionFailed=true; return; }
    hasFrame=false; touchPending=false; frameRevision="";
  } else if (upload.status==UPLOAD_FILE_WRITE && regionReceiving) {
    if (!regionReceiver.feed(upload.buf,upload.currentSize)) {
      regionFailed=true; regionReceiving=false;
    }
  } else if (upload.status==UPLOAD_FILE_END) {
    regionReady=regionReceiving && regionReceiver.complete() && !regionFailed;
    regionReceiving=false;
  } else if (upload.status==UPLOAD_FILE_ABORTED) {
    regionReceiving=false; regionStarted=false; regionReady=false; regionFailed=true;
  }
}

void finishRegion() {
  if (!authenticated()) server.send(401,"text/plain","Unauthorized");
  else if (!regionReady || regionFailed) server.send(400,"text/plain","Invalid region");
  else {
    // WLAN reception is finished. Paint the validated region in one SPI burst.
    size_t cursor=0;
    screen.startWrite();
    screen.setAddrWindow(regionX,regionY,regionWidth,regionHeight);
    regionReceiver.draw([&cursor](uint16_t* pixels,size_t count) {
      writePixels(pixels,count,regionX,regionY,regionWidth,cursor);
    });
    screen.endWrite();
    lastContactAt=millis();
    if (server.arg("final")=="1") {
      hasFrame=true; frameRevision=server.arg("revision");
      ++completedFrames;
      drawDebug();
    }
    server.send(200,"text/plain","OK");
  }
  regionReceiving=regionStarted=regionReady=regionFailed=false;
}

bool drawJpegBlock(int16_t x,int16_t y,uint16_t width,uint16_t height,uint16_t* pixels) {
  if (x<jpegX || y<jpegY || x+width>jpegX+jpegWidth || y+height>jpegY+jpegHeight) return false;
  const uint32_t started=debugEnabled ? micros() : 0;
  size_t cursor=0;
  screen.setAddrWindow(x,y,width,height);
  writePixels(pixels,static_cast<size_t>(width)*height,x,y,width,cursor);
  if (debugEnabled) jpegSpiUs+=micros()-started;
  return true;
}

void handleJpeg() {
  HTTPUpload& upload=server.upload();
  if (upload.status==UPLOAD_FILE_START) {
    if (jpegStarted) { jpegFailed=true; jpegReceiving=false; return; }
    jpegStarted=true; jpegFailed=false; jpegReady=false;
    jpegX=coordinate("x"); jpegY=coordinate("y");
    jpegWidth=coordinate("width"); jpegHeight=coordinate("height");
    const bool replace=server.arg("replace")=="1";
    jpegReceiving=authenticated() && upload.name=="jpeg" && validRevision(server.arg("revision")) &&
      jpegX>=0 && jpegY>=0 && jpegWidth>0 && jpegHeight>0 && jpegWidth<=480 && jpegHeight<=320 &&
      jpegX<=480-jpegWidth && jpegY<=320-jpegHeight &&
      ((replace && jpegX==0 && jpegY==0 && jpegWidth==480 && jpegHeight==320) ||
       (server.arg("replace")=="0" && hasFrame && frameRevision==server.arg("revision")));
    if (!jpegReceiving) { jpegFailed=true; return; }
    jpegReceiveAt=micros();
    regionReceiver.beginPayload();
  } else if (upload.status==UPLOAD_FILE_WRITE && jpegReceiving) {
    if (!regionReceiver.feed(upload.buf,upload.currentSize)) { jpegFailed=true; jpegReceiving=false; }
  } else if (upload.status==UPLOAD_FILE_END) {
    jpegReceiveUs=micros()-jpegReceiveAt;
    const auto bytes=regionReceiver.data(); const size_t length=regionReceiver.size();
    uint16_t width=0,height=0;
    jpegReady=jpegReceiving && !jpegFailed && length>=4 && bytes[0]==0xff && bytes[1]==0xd8 &&
      bytes[length-2]==0xff && bytes[length-1]==0xd9 &&
      TJpgDec.getJpgSize(&width,&height,bytes,length)==JDR_OK && width==jpegWidth && height==jpegHeight;
    jpegReceiving=false;
  } else if (upload.status==UPLOAD_FILE_ABORTED) {
    jpegReceiving=false; jpegStarted=false; jpegReady=false; jpegFailed=true;
  }
}

void finishJpeg() {
  if (!authenticated()) server.send(401,"text/plain","Unauthorized");
  else if (!jpegReady || jpegFailed) server.send(400,"text/plain","Invalid JPEG or stale revision");
    else {
      jpegSpiUs=0;
      const uint32_t renderAt=micros();
      screen.startWrite();
    const JRESULT result=TJpgDec.drawJpg(jpegX,jpegY,regionReceiver.data(),regionReceiver.size());
      screen.endWrite();
      const uint32_t renderUs=micros()-renderAt;
    if (result!=JDR_OK) {
      hasFrame=false; touchPending=false; frameRevision="";
      server.send(400,"text/plain","JPEG decode failed");
      } else {
        if (debugEnabled) {
          ++jpegMeasuredFrames;
          jpegBytesTotal+=regionReceiver.size();
          jpegReceiveTotal+=jpegReceiveUs;
          jpegRenderTotal+=renderUs;
          jpegSpiTotal+=jpegSpiUs;
        }
      if (frameRevision!=server.arg("revision")) touchPending=false;
      hasFrame=true; frameRevision=server.arg("revision"); lastContactAt=millis();
      ++completedFrames;
      if (jpegX+jpegWidth>kDebugX && jpegY+jpegHeight>kDebugY) drawDebug();
      server.send(200,"text/plain","OK");
    }
  }
  jpegReceiving=jpegStarted=jpegReady=jpegFailed=false;
}

void setup() {
  Serial.begin(115200);
  ledcSetup(2,5000,8);
  ledcAttachPin(27,2);
  setBrightness(100);
  // TFT and XPT2046 share SPI; TFT_eSPI selects only one chip at a time.
  pinMode(33, OUTPUT);
  digitalWrite(33, HIGH);
    screen.init();
    screen.setRotation(1);
    // ESP32 has a smaller linker window for static DRAM than its available heap.
    // Allocate the existing 8.75 KiB underlay once, leaving static space for JPEG tables.
    debugUnderlay.reset(new (std::nothrow) uint16_t[kDebugWidth*kDebugHeight]());
    if (!debugUnderlay) {
      Serial.println("Display startup failed: debug underlay allocation");
      screen.fillScreen(TFT_BLACK);
      screen.drawString("Not enough memory - restart display",12,20);
      while (true) delay(1000);
    }
  TJpgDec.setJpgScale(1);
  TJpgDec.setSwapBytes(false);
  TJpgDec.setCallback(drawJpegBlock);
  screen.fillScreen(TFT_BLACK);
  screen.setTextColor(TFT_WHITE, TFT_BLACK);
  screen.setTextFont(2);
  pinMode(0, INPUT_PULLUP);
  calibrateTouch();
  screen.fillScreen(TFT_BLACK);
  char boot[9];
  snprintf(boot, sizeof(boot), "%08lx", static_cast<unsigned long>(esp_random()));
  bootId = boot;
  idleTasks[0]=xTaskGetIdleTaskHandleForCPU(0);
  idleTasks[1]=xTaskGetIdleTaskHandleForCPU(1);
  cpuTimer=timerBegin(0,80,true);
  timerAttachInterrupt(cpuTimer,sampleCpu,false);
  // 997 Hz avoids locking the samples to the RTOS's regular 1 ms tick.
  timerAlarmWrite(cpuTimer,1003,true);
  timerAlarmDisable(cpuTimer);
  screen.drawString("Desk Display - connecting to Wi-Fi", 20, 20);
  bootResetReason=static_cast<int>(esp_reset_reason());loadNetwork();
  discoveryHost="desk-display-"+String(static_cast<uint32_t>(ESP.getEfuseMac()),HEX)+String(static_cast<uint32_t>(ESP.getEfuseMac()>>32),HEX);discoveryHost.replace(":","");discoveryHost.toLowerCase();
  WiFi.setHostname(discoveryHost.c_str());WiFi.mode(WIFI_STA);WiFi.setSleep(false);WiFi.setAutoReconnect(true);
  if(configuredSsid.length())WiFi.begin(configuredSsid.c_str(),configuredPassword.c_str());
  uint32_t wifiStarted=millis();
  while(configuredSsid.length() && WiFi.status()!=WL_CONNECTED && millis()-wifiStarted<20000)delay(100);
  if(WiFi.status()!=WL_CONNECTED || needsNetworkSetup){screen.drawString("WLAN Einrichtung startet.",16,155,2);configureNetwork();}
  sleepControl.wake(millis());advertiseDisplay();
  String deviceId = WiFi.macAddress();
  deviceId.replace(":", "");
  deviceId.toLowerCase();
  const char* headers[] = {"X-Desk-Key"};
  server.collectHeaders(headers, 1);
  server.on("/api/info", HTTP_GET, [deviceId]() {
    if (!authenticated()) { server.send(401, "text/plain", "Unauthorized"); return; }
    String info = "{\"product\":\"desk_display\",\"protocol\":1,\"model\":\"E32R35T\","
                  "\"width\":480,\"height\":320,\"version\":\""+String(kFirmwareVersion+21)+"\",\"touch\":true,\"jpeg_regions\":true,"
                  "\"buffered_regions\":true,\"debug_overlay\":true,\"id\":\"";
    info += deviceId + "\",\"has_frame\":" + (hasFrame ? "true" : "false") + "}";
    info.remove(info.length()-1);
    info += ",\"debug_enabled\":" + String(debugEnabled ? "true" : "false") +
            ",\"cpu_percent\":" + String(cpuPercent,1) + ",\"fps\":" + String(framesPerSecond,2) +
            ",\"jpeg_bytes\":" + String(jpegBytesAverage,0) + ",\"receive_ms\":" + String(jpegReceiveMs,2) +
            ",\"decode_ms\":" + String(jpegDecodeMs,2) + ",\"display_ms\":" + String(jpegDisplayMs,2) +
            ",\"brightness_control\":true,\"ota_update\":true,\"status_heartbeat\":true,\"brightness\":"+String(backlightPercent)+
            ",\"firmware_marker\":\""+String(kFirmwareMarker)+"\"}";
    info.remove(info.length()-1);
    info+=",\"rssi\":"+String(WiFi.RSSI())+",\"free_heap\":"+String(ESP.getFreeHeap())+",\"min_free_heap\":"+String(ESP.getMinFreeHeap())+",\"uptime\":"+String(millis()/1000)+",\"reset_reason\":"+String(bootResetReason)+",\"boot_id\":\""+bootId+"\",\"sleep_control\":true,\"sleeping\":"+String(sleepControl.sleeping?"true":"false")+"}";
    server.send(200, "application/json", info);
  });
  server.on("/api/frame", HTTP_POST, finishUpload, handleUpload);
  server.on("/api/region",HTTP_POST,finishRegion,handleRegion);
  server.on("/api/jpeg",HTTP_POST,finishJpeg,handleJpeg);
  server.on("/api/heartbeat",HTTP_POST,[]() {
    if(!authenticated()){server.send(401,"text/plain","Unauthorized");return;}
    if(!hasFrame || server.arg("revision")!=frameRevision){server.send(409,"text/plain","Stale revision");return;}
    lastContactAt=millis();server.send(200,"text/plain","OK");
  });
  server.on("/api/brightness",HTTP_POST,[]() {
    if(!authenticated()){server.send(401,"text/plain","Unauthorized");return;}
    const String value=server.arg("value");
    if(!value.length() || value.length()>3){server.send(400,"text/plain","Expected 0..100");return;}
    for(size_t i=0;i<value.length();++i)if(!isDigit(value[i])){server.send(400,"text/plain","Expected 0..100");return;}
    if(value.toInt()>100){server.send(400,"text/plain","Expected 0..100");return;}
    setBrightness(value.toInt());server.send(200,"text/plain","OK");
  });
  server.on("/api/sleep",HTTP_POST,[](){
    if(!authenticated()){server.send(401,"text/plain","Unauthorized");return;}
    String after=server.arg("after"),level=server.arg("brightness"),wake=server.arg("wake");
    bool valid=after.length()>0 && after.length()<=4 && level.length()>0 && level.length()<=3;
    for(size_t i=0;i<after.length();++i)valid=valid && isDigit(after[i]);
    for(size_t i=0;i<level.length();++i)valid=valid && isDigit(level[i]);
    int seconds=after.toInt(),brightness=level.toInt();
    if(!valid || (seconds!=0 && (seconds<15 || seconds>3600)) || brightness>100 || (wake!="0" && wake!="1")){server.send(400,"text/plain","Invalid sleep settings");return;}
    bool changed=sleepControl.after!=static_cast<uint32_t>(seconds)*1000 || sleepControl.brightness!=brightness;
    sleepControl.after=seconds*1000;sleepControl.brightness=brightness;
    if(changed || wake=="1")sleepControl.wake(millis());
    setBrightness(backlightPercent);server.send(200,"text/plain","OK");
  });
  server.on("/api/update",HTTP_POST,[]() {
    if(!authenticated()){server.send(401,"text/plain","Unauthorized");return;}
    if(!otaReady || otaFailed || otaBytes<65536 || !Update.end(true)) {
      Update.abort();otaReceiving=false;otaReady=false;
      server.send(400,"text/plain","Firmware rejected");return;
    }
    server.send(200,"text/plain","Firmware accepted; rebooting");
    delay(300);ESP.restart();
  },[]() {
    HTTPUpload& upload=server.upload();
    if(upload.status==UPLOAD_FILE_START) {
      otaFailed=!authenticated();otaReady=false;otaBytes=0;
      otaReceiving=!otaFailed;
      if(otaReceiving && !Update.begin(UPDATE_SIZE_UNKNOWN,U_FLASH))otaFailed=true;
    } else if(upload.status==UPLOAD_FILE_WRITE && otaReceiving && !otaFailed) {
      if(!otaBytes && (upload.currentSize<24 || upload.buf[0]!=0xe9 || upload.buf[12]!=0 || upload.buf[13]!=0))otaFailed=true;
      otaBytes+=upload.currentSize;
      if(otaBytes>1310720 || otaFailed || Update.write(upload.buf,upload.currentSize)!=upload.currentSize){otaFailed=true;Update.abort();}
    } else if(upload.status==UPLOAD_FILE_END) {
      otaReady=otaReceiving && !otaFailed;otaReceiving=false;
    } else if(upload.status==UPLOAD_FILE_ABORTED) {
      Update.abort();otaReceiving=false;otaFailed=true;otaReady=false;
    }
  });
  server.on("/api/debug",HTTP_POST,[]() {
    if (!authenticated()) { server.send(401,"text/plain","Unauthorized"); return; }
    if (server.arg("enabled")!="0" && server.arg("enabled")!="1") {
      server.send(400,"text/plain","Expected enabled=0 or 1"); return;
    }
    setDebug(server.arg("enabled")=="1");
    server.send(200,"text/plain","OK");
  });
  server.on("/api/touch", HTTP_GET, []() {
    if (!authenticated()) { server.send(401, "text/plain", "Unauthorized"); return; }
    if (!hasFrame || millis() - touchAt > 5000) touchPending = false;
    if (!touchPending) { server.send(200, "application/json", "{\"event\":null}"); return; }
    String event = "{\"event\":{\"id\":\"" + touchId + "\",\"revision\":\"" + touchRevision;
    event += "\",\"x\":" + String(touchX) + ",\"y\":" + String(touchY) + ",\"gesture\":\"" + touchGesture + "\",\"value_x\":" + String(gestureValueX) + "}}";
    server.send(200, "application/json", event);
  });
  server.on("/api/touch/ack", HTTP_POST, []() {
    if (!authenticated()) { server.send(401, "text/plain", "Unauthorized"); return; }
    if (!touchPending || server.arg("id") != touchId) {
      server.send(409, "text/plain", "Touch expired"); return;
    }
    touchPending = false;
    server.send(200, "text/plain", "OK");
  });
  server.onNotFound([]() { server.send(404, "text/plain", "Not found"); });
  server.begin();
  screen.drawString("Add this IP in Home Assistant:", 20, 60);
  screen.drawString(WiFi.localIP().toString(), 20, 90);
  Serial.print("Desk Display IP: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  server.handleClient();
  // Release BOOT after 3 seconds for calibration, after 8 for Wi-Fi setup.
  static uint32_t bootPressedAt=0;
  if(digitalRead(0)==LOW){if(!bootPressedAt)bootPressedAt=millis();}
  else if(bootPressedAt){
    uint32_t held=millis()-bootPressedAt;bootPressedAt=0;
    if(held>=8000){hasFrame=false;touchPending=false;frameRevision="";configureNetwork();server.begin();advertiseDisplay();sleepControl.wake(millis());}
    else if(held>=3000)calibrateTouch(true);
  }
  if(WiFi.status()!=WL_CONNECTED){
    if(mdnsActive){MDNS.end();mdnsActive=false;}
    if(millis()-reconnectAt>15000){reconnectAt=millis();WiFi.reconnect();}
  }else if(!mdnsActive)advertiseDisplay();
  if(sleepControl.tick(millis()))setBrightness(backlightPercent);
  static uint32_t touchCheckedAt=0;
  if (!uploading && !regionReceiving && !jpegReceiving && millis()-touchCheckedAt>=33) {
    touchCheckedAt=millis();
    uint16_t x = 0, y = 0;
    const bool pressed = screen.getTouch(&x, &y);
    static bool wakeTouch=false;
    if(pressed && !touchDown){wakeTouch=sleepControl.touch(millis());if(wakeTouch)setBrightness(backlightPercent);}
    if(!pressed && wakeTouch){wakeTouch=false;touchDown=false;gestureArmed=false;return;}
    if(wakeTouch){touchDown=pressed;return;}
    if (pressed && !touchDown && hasFrame && frameRevision.length() == 32 &&
        !touchPending && millis() - lastTouchAt > 500 && x < 480 && y < 320) {
      touchX = x; touchY = y;
      gestureStartedAt=millis();gestureArmed=true;gestureValueX=x;gestureValueY=y;
      screen.fillRect(380,300,100,20,TFT_BLACK);screen.setTextColor(TFT_CYAN,TFT_BLACK);screen.drawRightString("Beruehrt",476,302,2);
      touchId = bootId + "-" + String(++touchSequence);
      touchRevision = frameRevision;
      touchAt = lastTouchAt = millis();
    }
    if(pressed && gestureArmed && x<480 && y<320){gestureValueX=x;gestureValueY=y;}
    if (!pressed && touchDown && gestureArmed) {
      gestureArmed=false;
      screen.startWrite();screen.setAddrWindow(kDebugX,kDebugY,kDebugWidth,kDebugHeight);screen.pushColors(debugUnderlay.get(),kDebugWidth*kDebugHeight,true);screen.endWrite();drawDebug();
      if(hasFrame && touchRevision==frameRevision && millis()-gestureStartedAt<10000) {
        int dx=int(gestureValueX)-int(touchX),dy=int(gestureValueY)-int(touchY);
        touchGesture=abs(dx)>=60 && abs(dx)>2*abs(dy)?(dx<0?"left":"right"):(millis()-gestureStartedAt>=700?"hold":"tap");touchAt=lastTouchAt=millis();touchPending=true;
      }
    }
    touchDown = pressed;
  }
  if (debugEnabled && !uploading && !regionReceiving && !jpegReceiving && millis()-metricsAt>=5000) {
    uint32_t samples,busy;
    portENTER_CRITICAL(&sampleMux);
    samples=cpuSamples; busy=busySamples; cpuSamples=busySamples=0;
    portEXIT_CRITICAL(&sampleMux);
    cpuPercent=samples ? 100.0f*busy/samples : 0;
    framesPerSecond=1000.0f*completedFrames/(millis()-metricsAt);
    if (jpegMeasuredFrames) {
      jpegBytesAverage=static_cast<float>(jpegBytesTotal)/jpegMeasuredFrames;
      jpegReceiveMs=static_cast<float>(jpegReceiveTotal)/jpegMeasuredFrames/1000;
      jpegDisplayMs=static_cast<float>(jpegSpiTotal)/jpegMeasuredFrames/1000;
      jpegDecodeMs=static_cast<float>(jpegRenderTotal-jpegSpiTotal)/jpegMeasuredFrames/1000;
      Serial.printf("Video %dx%d: FPS %.1f, CPU %.0f%%, JPEG %.0f bytes, receive %.1f ms, decode %.1f ms, display %.1f ms\n",
                    jpegWidth,jpegHeight,framesPerSecond,cpuPercent,jpegBytesAverage,jpegReceiveMs,jpegDecodeMs,jpegDisplayMs);
    } else {
      jpegBytesAverage=jpegReceiveMs=jpegDecodeMs=jpegDisplayMs=0;
    }
    resetVideoTimings();
    completedFrames=0; metricsAt=millis();
    drawDebug();
  }
  // Retain the last image but visibly mark it stale and disable all touch actions.
  static bool staleVisible=false;
  static uint32_t stalePaintAt=0;
  if (hasFrame && (WiFi.status() != WL_CONNECTED || millis() - lastContactAt > 45000)) {
    hasFrame = false;
    touchPending = false;
    frameRevision = "";
    staleVisible=true;
  }
  if(hasFrame)staleVisible=false;
  if(staleVisible && millis()-stalePaintAt>1000) {
    stalePaintAt=millis();
    screen.fillRect(0,300,480,20,TFT_RED);screen.setTextColor(TFT_WHITE,TFT_RED);
    screen.drawString("Offline - last data "+String((millis()-lastContactAt)/1000)+"s ago",4,301,2);
    screen.setTextColor(TFT_WHITE,TFT_BLACK);
  }
  delay(2);
}

