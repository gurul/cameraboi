// cameraboi-af — enable continuous autofocus on attached cameras (macOS).
//
// UVC cameras like the IPEVO V4K power up with whatever focus state they were
// left in; ffmpeg/avfoundation cannot touch focus at all. This helper flips
// every camera that supports it into .continuousAutoFocus via AVCaptureDevice,
// then holds the device briefly so the lens starts settling. The mode persists
// on the device after exit, so a following ffmpeg capture inherits it.
//
// Exit 0 if at least one device was set (or none needed it); prints one line
// per device to stderr. Never used in a failing path — callers treat any
// non-zero exit as "AF unavailable, capture anyway".

import AVFoundation
import Foundation

let settleSeconds = ProcessInfo.processInfo.environment["CAMERABOI_AF_SETTLE"]
    .flatMap(Double.init) ?? 1.0

func note(_ s: String) { FileHandle.standardError.write((s + "\n").data(using: .utf8)!) }

let ds = AVCaptureDevice.DiscoverySession(
    deviceTypes: [.external, .builtInWideAngleCamera],
    mediaType: .video, position: .unspecified)

var touched = false
for dev in ds.devices {
    guard dev.isFocusModeSupported(.continuousAutoFocus) else {
        note("af: \(dev.localizedName): continuous AF not supported, skipped")
        continue
    }
    do {
        try dev.lockForConfiguration()
        dev.focusMode = .continuousAutoFocus
        dev.unlockForConfiguration()
        note("af: \(dev.localizedName): continuous autofocus enabled")
        touched = true
    } catch {
        note("af: \(dev.localizedName): \(error.localizedDescription)")
    }
}

if touched && settleSeconds > 0 {
    Thread.sleep(forTimeInterval: settleSeconds)
}
exit(0)
