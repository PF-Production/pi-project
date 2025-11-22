# TODO

## Completed

- [x] Run locally on macOS using `pygame` (single output)
- [x] Run on Raspberry Pi using `aplay` subprocesses for multiple outputs

## In Progress

## Backlog

- [ ] Confirm playback through multiple outputs.
- [ ] 3 files required to playback on devices. 2 files are mono and should be played through left and right channels. 1 file is stereo and should be played through both channels.
- [ ] Figure out what the default playback outputs are for Raspberry Pi OS and update code accordingly. Or find a way to set the outputs manually.
- [ ] Optional: per-device volume controls (use `amixer`)
- [ ] Write setup scripts for easy installation using `justinstall`
- [ ] Check if on device bootup the application starts automatically
- [ ] Test if start times for script can be set using system clock
- [ ] Add --force flag to bypass time checks for testing purposes
- [ ] Figure out how to remote into device via WiFi for onsite debugging and EQ
- [ ] Onsite controls should only be to force playback, adjust volume or change EQ settings.
- [ ] Test devices locally first to ensure they all playback correctly when powered on.
- [ ] Use streamlit or similar to create a web interface for controlling playback and settings remotely
- [ ] Figure out how to remote into device via WiFi for onsite debugging and EQ
