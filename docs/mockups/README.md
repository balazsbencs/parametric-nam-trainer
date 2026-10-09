# Parametric UX mockups

Open **overview.html** for the whole journey, or **index.html** for the clickable prototype. Both work directly from a local folder without installing or serving anything.

Five stages: Connect → Plan → Capture → Train → Review. All device state, measurements, capture results and training runs are examples. No physical audio or actual training is accessed. The A/B panel previews an interaction and does not play audio. Handoff download creates a labeled `.example.json`, never a fake trained model.

Try:

1. Connect: choose **Use example rig**, then **Check audio route** and continue. Expand the advanced section to try permission and sample-rate failures.
2. Plan: leave **Good** selected and choose **Start capturing**, or move the single quality slider. It updates recording count, spacing for both knobs, sound-check count and estimated recording effort. Physical ranges and manual controls stay under **Advanced**.
3. Capture: confirm the physical knob targets, then record an example take. Try a clipped take or the complete-session state.
4. Train: start a one-epoch test or full example run. Navigate while the simulated job runs. Try the GPU-memory recovery state.
5. Review: inspect unseen settings, switch A/B targets, complete the listening checklist and download the example handoff.

The prototype retains the native utility's light surfaces and familiar control patterns. These HTML screens are review artifacts for the macOS desktop design; they are not a decision to replace the native app with a website.

At compact widths, the stage navigation becomes a top row and content stacks. This permits inspecting the mockups on smaller displays; desktop is still the application target.

The audit, full-resolution captures and interaction verification are under `../ui-audit/` and `screenshots/`. Final verification covers 20 screen/viewport combinations and 19 interactions, including local file access, all five quality levels and pointer/keyboard slider use. The real application code was not changed by this design task.

Quality is a capture-coverage preset, not a measured sound rating. The example counts are for Drive + Tone and need validation with real pedal captures. A session's plan locks after the first accepted take; **Start a separate plan** keeps earlier example take metadata separate. See [the quality-control brief](plan-quality.md).

Choices persist while navigating this open prototype; reloading resets the example. Saved-session language describes proposed native behavior rather than browser storage. Screenshots include their local-render origin metadata. The included Inter font and license are in `assets/`.
