# TODO

- [x] Run locally on macOS using `pygame` (single output)
- [x] Run on Raspberry Pi using `aplay` subprocesses for multiple outputs
- [x] Confirm playback through multiple outputs.
- [x] 3 files required to playback on devices. 2 files are mono and should be played through left and right channels. 1 file is stereo and should be played through both channels.
- [x] Figure out what the default playback outputs are for Raspberry Pi OS and update code accordingly. Or find a way to set the outputs manually.
- [x] Optional: per-device volume controls (use `amixer`)
- [x] Write setup scripts for easy installation using `justinstall`
- [x] Check if on device bootup the application starts automatically
- [x] Test if start times for script can be set using system clock
- [x] Add --force flag to bypass time checks for testing purposes
- [x] Test devices locally first to ensure they all playback correctly when powered on.

- [ ] Figure out how to remote into device via WiFi for onsite debugging and EQ
- [ ] Onsite controls should only be to force playback, adjust volume or change EQ settings.
- [ ] Figure out how to do EQ and change it remotely
- [ ] Review remote commands to control playback and volume without needing SSH access
