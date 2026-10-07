# Earshot: call recorder

A single-page web app that records a call from your computer. It captures
your **microphone**, the **device audio** (the other people on the call, or
anything else playing), or both. You then download the result as a file.
Everything happens in the browser: there is no server, and audio never
leaves the computer until you download it.

All of it lives in [`index.html`](index.html): no build step, no dependencies.

## Opening it

Pick one:

- **Open the file directly.** Download `index.html` and open it in Chrome or
  Edge (double-click it, or drag it into a browser window).
- **Serve it locally.** From this folder, run `python3 -m http.server 8000`,
  then open <http://localhost:8000>.
- **Host it** on any static HTTPS host (GitHub Pages, Netlify, an intranet
  server…).

Browsers only allow the microphone and screen sharing on `https://`,
`http://localhost` or local files. On a plain `http://` address the page
explains this and records nothing.

## Recording a call

1. Switch on **Device audio**. The browser asks what to share:
   - **Teams in a browser** (teams.microsoft.com): pick its tab and keep
     **Share tab audio** on.
   - **Teams app, a softphone, or anything else on Windows**: pick
     **Entire screen** and turn on **Share system audio**.

   Only the sound is recorded, never the picture.
2. Switch on **Microphone** for your own voice. Pick the input if you have
   several, and keep **Voice cleanup** on for speech.
3. Check that both meters move, then press **Record**.
4. Press **Stop**. The recording appears under **Recordings**: play it back,
   rename it, then press **Download**.

During a recording you can switch either source off and on again (it's muted
in the file meanwhile), add a source you hadn't switched on, change
microphones, adjust each volume, and pause. Wear headphones: on speakers,
the microphone also picks up the other people and they end up in the file
twice.

## Options

| Option | Choices |
| --- | --- |
| File format | **Compressed**: WebM/Opus at 128 kbit/s, about 1 MB per minute (MP4/AAC or Ogg/Opus in browsers without WebM). **WAV**: 16-bit PCM, about 5–6 MB per minute in mono, which opens anywhere. |
| Channels | **Mixed**: everything together. **Split**: microphone on the left channel, device audio on the right. Useful for transcription (who said what) and for editing each side separately. |
| Volume | 0–200 % per source, to balance a quiet microphone against loud call audio. |
| Voice cleanup | The browser's echo cancellation, noise suppression and automatic gain on the microphone. Turn it off to record music. |

## What works where

| Where | Microphone | Call / device audio |
| --- | --- | --- |
| Windows · Chrome, Edge | Yes | Yes, from anything: **Entire screen** + **Share system audio**, or a single tab |
| macOS, Linux · Chrome, Edge | Yes | From a browser tab. Whole-system audio only if the share dialog offers **Share system audio** |
| Firefox, Safari | Yes | No (they share video without sound) |
| iPhone, iPad, Android | Yes | No: mobile browsers can't share audio, and phones don't let web pages hear calls |

For a phone call, the reliable option is to take the call on the computer
(Teams, a softphone). Otherwise, put the phone on speaker next to the
computer and record with the microphone only.

## Limits

- Recordings are kept in the tab's memory until you download them. Closing
  or reloading the tab discards them; the page asks for confirmation first.
- Teams does not show other participants that this page is recording. Tell
  them.

## How it works

- `getUserMedia` captures the microphone; `getDisplayMedia` captures tab or
  system audio (its video track is never recorded).
- Each source goes through its own Web Audio gain (volume, mute) and analyser
  (level meter), then into either a stereo mix bus (Mixed) or a channel
  merger (Split: mic → left, device → right). Because the mixing happens in
  the audio graph, sources can be added, muted or swapped without
  interrupting the recording.
- **Compressed** files come from `MediaRecorder`. Chrome writes WebM without
  a duration, so players can't show the length or seek. The page inserts the
  Duration element into the WebM header when the recording stops.
- **WAV** files come from an `AudioWorklet` that taps the raw samples. They
  are converted to 16-bit PCM as they arrive and stored in blob chunks to
  keep memory use low on long calls.
