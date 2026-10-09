# Native companion interface

The visual authority is the pinned capture app's existing Qt widget interface. This work extends its task tabs with **Train on Mac** and **Pedal setup**; it does not introduce a new visual identity or web application.

Use standard platform widgets and system typography. Preserve the incumbent tab hierarchy and native focus/disabled states. The training page is a title and explanation, a labeled execution-settings form, one row of actions, a job-status message and a growing read-only log. The setup page keeps concrete wiring and level instructions together. Body labels wrap in compact windows. Read-only logs cap retained blocks for long runs.

Training and checking run in separate Python processes, keeping the window responsive. Disable project/capture tabs during a job so its source paths cannot be changed through this window. Stop remains visible; closing during a job tells the user to stop and wait. Empty/no-project, missing outputs, failed launch, training failure and stopped-job states have explicit messages.

Screenshots in docs/screenshots are Linux offscreen verification of the native layout. Platform-specific fonts, spacing and rendering require a Mac pass. No macOS styling fidelity claim is made from these images.
