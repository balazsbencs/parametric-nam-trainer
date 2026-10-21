# Release review — 2026-10-21

Reviewed PRs #2, #4, #5, #6 and #7 as two dependency stacks, then tested their combined tree at `d9205a76d0cec0f740d7b1d608dc84d258ba3d8a`. Existing GitHub review submissions, comments and CI checks were empty. The original working directory's uncommitted playback changes were preserved; review and release work used separate worktrees.

## Findings and fixes

- **Console/training integration:** the Console rewrite replaced the old GUI where the input-reference, warm-start and measured-performance controls had been added. Ported those actions into Train → Expert settings, kept subprocess jobs wired to the correct source checkout, disabled all job settings while busy, reset per-project settings, and restored baseline settings on CPU retry.
- **Playback save policy:** Console's synthetic run fixtures still represented the previous qualification format. Updated fixtures to require policy version 3 and passing transient checks, retaining hash verification and rejection of old reports. The synthetic screenshot run uses the same report shape; it is not evidence of audio qualification.
- **Input-reference replacement:** a reference could be written even when dataset input gain made its effective mapping unsupported. Validate the complete mapping before replacing the existing reference. The regression test failed before the fix and passed afterward.
- **Find cancellation:** cancelling during the last scan or after worker completion could publish a successful result. Check cancellation after audio and before returning; discard queued Qt success results after a cancellation request. Four regression cases failed before the fixes; the fixes preserve channels and prior level proof.
- **Stack conflicts:** apply connection features on top of the latest Console changes, preserving clipped-take recovery, calibrated levels and qualified model saving. Preserve those fixes again when combining split-interface support.
- **Source packaging:** include cloud tool sources referenced by the README, the changelog and version 0.2.0. Environments, the upstream checkout and datasets stay outside the source archive.

## Validation

- Transient-training branch: **75 passed**, including the input-reference regression.
- Route/scan tests: **131 passed**. Find GUI tests: **3 passed**, including queued cancellation.
- Targeted Console/training integration: **12 passed**, including a real subprocess benchmark followed by training, Save model gating and project-state resets.
- Combined full suite: **339 passed, 1 skipped**, with 13 upstream Lightning deprecation warnings (541 seconds). The skip is the macOS-only CoreAudio smoke test.
- Train expert controls inspected in dark/light at 1140×840 and 800×680 using offscreen Qt.
- Installer and launcher shell syntax checked. Built the Python wheel and checked its version, CRC, fonts, UI, connection and training modules. Checked the source ZIP's CRC, every file's bytes, version, executable launcher permissions and inclusion of cloud tool sources.

Tests ran on Linux with Python 3.13, PySide6 and the pinned upstream trainer. The host lacked Tkinter; Debian Tk libraries were extracted into a temporary test directory, without changing application code or the pinned upstream. `QT_QPA_PLATFORM=offscreen` and one OpenMP thread were used. Upstream Lightning emits deprecation warnings.

## Remaining target-hardware checks

The macOS CoreAudio smoke test is skipped on Linux. Physical Mac/UMC22 recording, native menus and device behavior, complete MPS/CUDA training and listening were not performed. Offscreen tests and synthetic screenshots do not establish those results. FiLM protected saving remains unavailable, and reserved transient recordings are required for new protected playback exports.
