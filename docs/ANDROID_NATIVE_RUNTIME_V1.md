# Stage 10 Android NDK runtime

## Result

Stage 10 places the Stage 9 integrated environment closed loop behind an
Android application boundary. Kotlin owns lifecycle, physical input controls,
the fixed-step accumulator, telemetry, and OpenGL ES 3 rendering. JNI owns one
C++ core and copies state into caller-owned arrays. The renderer consumes the
native 302-vertex/600-triangle continuous surface; it never writes physics
nodes or supplies displacement, heading, gait, or animation commands.

The per-step causal order remains:

```text
physical light/contact field
  → sensory transduction
  → sparse LIF dynamics
  → motor neurons
  → muscle activation
  → shared 13-node 3D body physics
  → updated sample positions in the physical field
```

The Android controls expose lateral and dorsal–ventral light gradients in
`W/m³` plus a two-step posterior contact pulse. Their labels explicitly state
that they are sensory inputs, not heading commands. All light, transducer,
body, and muscle gains retain their existing provenance and claim boundaries.

![Android NDK runtime through the host JNI boundary](assets/oraclarva_android_mobile_runtime.gif)

The GIF is generated from 51 mesh frames copied through the actual JNI bridge
on the host JVM. It is not Android device or emulator footage. This distinction
is printed in the image itself.

## Mobile architecture

- `NativeOrganism` is created, advanced, read, reset, and destroyed on its
  owning GL thread.
- A real-time accumulator advances the native core at fixed `dt = 1 ms`, with
  elapsed wall time capped at 50 ms and at most 50 physics steps per draw.
- JNI rejects calls larger than 1,000 steps and invalid or undersized output
  arrays. Java/Kotlin allocate state, vertex, and index arrays once and reuse
  them.
- Android reads the native `maximum_steps` metadata and resets before the next
  fixed step would exceed the fixture's 14,600-step validation horizon. This
  keeps the observation loop alive without weakening the native fail-closed
  boundary or adding a movement policy.
- `oraclarva_mobile_read_render_mesh` is the sole body geometry source. Kotlin
  recenters copied render positions for the camera but does not mutate C++
  state.
- The OpenGL ES 3 shader colors the surface by native muscle activation.
- The app requests no Android permissions and targets `arm64-v8a` and
  `x86_64`, with minimum API 26 and compile/target API 36.

The application uses Android Gradle Plugin 9.3.0, Gradle 9.5.0, Java 17,
CMake 3.28.3, and NDK 28.2.13676358. The checked wrapper records the official
Gradle distribution SHA-256
`553c78f50dafcd54d65b9a444649057857469edf836431389695608536d6b746`;
the wrapper JAR SHA-256 is
`497c8c2a7e5031f6aa847f88104aa80a93532ec32ee17bdb8d1d2f67a194a9c7`.

## Checked host JNI results

The bridge is compiled as a shared library, loaded by Java 17, and driven
through the exact static methods declared by Kotlin. The regression gate checks:

| Diagnostic | Checked result |
| --- | ---: |
| Uniform field duration | 14.600 s / 14,600 fixed steps |
| Anatomical forward displacement | 467.539285129721 µm |
| Uniform-field yaw | 0.000000000000° |
| Total spatial spikes | 53,524 |
| +Y 6000 W/m³ yaw at 4.5 s | -3.831016030048° |
| +Y lateral displacement | -1.956735327396 µm |
| Render projection | 302 vertices / 600 triangles |
| Reset replay | exact state, vertex, and index arrays |
| Release validation | false |

The same parity gate is also cross-built against NDK r28c Bionic for
`arm64-v8a` and `x86_64`. Both static executables reproduce the checked host
state, render topology, exact reset replay, spike total, and
`release_validated=false`. Cross-ABI floating-point drift is at most
`6.02540239925e-12`, below the declared `1e-8` engineering tolerance. The
runner prints `device_performance_claim=false`: execution on this ARM host and
through QEMU is an ABI gate, not an Android runtime or performance result.

This test validates the C++/JNI contract and deterministic data transfer. It
does not establish device framerate, thermal behavior, battery use, GPU driver
compatibility, or biological validation.

## Android build and device boundary

The Android SDK licenses were explicitly accepted on 2026-09-01. With API 36,
Build Tools 36.0.0, Platform Tools 37.0.1, and NDK 28.2.13676358 installed,
`./gradlew :app:assembleDebug --no-daemon` completes for both declared ABIs.
The generated debug artifact is:

| Property | Checked value |
| --- | --- |
| Path | `android/app/build/outputs/apk/debug/app-debug.apk` |
| Size | 6,683,716 bytes |
| SHA-256 | `222bf163b293dd45be8fd62b029cc077f6032f7861ec63e9907c5f95ab900a6e` |
| Signature | Android Debug, APK Signature Scheme v2 verified |
| Alignment | `zipalign -c -P 16 -v 4` successful |
| Native libraries | `arm64-v8a/liboraclarva_android.so`, `x86_64/liboraclarva_android.so` |

The package declares API 26 minimum/API 36 target, requires OpenGL ES 3, asks
for no Android permissions, and contains the checked parity fixtures. Build,
signature, and package checks remain distinct from the Android runtime gate.

A prior Android Emulator 37.1.11 smoke attempt used the API 36 AOSP ATD `x86_64`
image because the APK contains an `x86_64` library. The official emulator
binary itself had to run through QEMU user translation on this ARM64 host, and
the Android guest then ran under unaccelerated TCG. Across an initial two-hour
first boot and a preserved-data restart, the guest mounted its data partition
and bootstrap APEX packages, but ADB remained offline. The APK was therefore
not installed or launched in that unsupported nested setup. This is recorded
as an environment limitation, not as an emulator pass or a performance
measurement; a compatible x86_64 emulator host or physical Android device is
still required for that gate.

The current ARM64 host now supplies a separate Android execution gate through
an Android 13 ReDroid container. ADB is bound to loopback only. The debug APK
installed and launched at 1280 × 592/160 dpi with ANGLE/SwiftShader. The
Habitat screen was captured to `docs/assets/habitat-ui-redroid.png`; its
SHA-256 is
`fe31639597dfe4127ad90079e259f59f40e0181fb9c80d459702b6be7c25f02c`.
Pause, Observe, physical light-field drag, and posterior contact controls were
exercised through ADB. The Activity remained resumed after crossing the finite
14,600-step fixture boundary, and the Android runtime log contained no fatal
app exception. This is Android-container functional evidence, not a Google
Emulator, physical-device, GPU-performance, thermal, or battery claim.

`release_validated=false` remains mandatory. GitHub Actions also remains
manual-only through `workflow_dispatch`; the Android build is not added as an
automatic CI trigger.

## Reproduce

Host JNI boundary and visualization:

```bash
python tools/build_android_host_bridge.py
pytest -q tests/test_android_mobile_runtime.py
python tools/render_android_mobile_runtime_gif.py
```

With accepted SDK licenses and API 36, Build Tools 36.0.0, Platform Tools, and
NDK 28.2.13676358 installed:

```bash
cd android
./gradlew :app:assembleDebug --no-daemon
cd ..
python tools/build_android_ndk_parity.py --ndk "$ANDROID_NDK_HOME"
```

An APK build alone must not be reported as device validation. Emulator or
physical-device execution and measurements require a separate recorded gate.

For the checked ReDroid container, installation, launch, and capture use the
normal ADB boundary:

```bash
adb connect 127.0.0.1:5555
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
adb shell am start -W -n org.oraclarva.mobile/.MainActivity
adb shell screencap -p /sdcard/habitat-ui-redroid.png
adb pull /sdcard/habitat-ui-redroid.png docs/assets/habitat-ui-redroid.png
```
