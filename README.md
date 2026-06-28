# Squat Alarm 🏋️⏰

An alarm clock that **won't turn off until you do 10 squats.**

Built with OpenCV and MediaPipe Pose to track your body in real time, count squat reps, and keep the alarm sound blaring until you actually finish your reps — not just stand in front of the camera pretending.

## How it works

1. At your set alarm time, a loud sound starts playing on repeat.
2. Your webcam turns on and MediaPipe Pose tracks your body landmarks (hips, knees, etc.).
3. A simple state machine watches the distance between your hips and knees:
   - Hips drop close to knees → you're squatting (`DOWN`)
   - Hips rise back up → rep counted (`UP`)
4. The alarm sound **pauses only while you're actively squatting** — just standing there does nothing.
5. Once you hit your target rep count, the alarm shuts off for good.

## Tech Stack

- **OpenCV** – webcam capture and video display
- **MediaPipe Pose** – body landmark detection
- **Pygame** – looping alarm sound playback with pause/resume

## Project Structure

```
squat_alarm/
├── main.py            # Entry point — scheduling, main loop, ties everything together
├── squat_counter.py   # MediaPipe pose tracking + squat rep counting logic
├── alarm.py           # Alarm sound playback (play/pause/resume/stop)
└── alarm.wav          # Your alarm sound file (add your own)
```

## Setup

1. Clone/download this project.
2. Install dependencies:
   ```bash
   pip install opencv-python mediapipe pygame
   ```
3. Add an alarm sound file named `alarm.wav` to the project folder (or point to your own with `--sound`).

## Usage

Run with a real alarm time:
```bash
python main.py --time 07:00 --sound alarm.wav --reps 10
```

Test immediately without waiting for an alarm time:
```bash
python main.py --sound alarm.wav --reps 5
```

### Arguments

| Flag | Description | Default |
|------|-------------|---------|
| `--time` | Alarm time in 24hr `HH:MM` format. Omit to start immediately. | none |
| `--sound` | Path to alarm sound file (`.wav`/`.mp3`) | `alarm.wav` |
| `--reps` | Number of squats required to dismiss the alarm | `10` |
| `--camera` | Webcam index | `0` |

## Notes

- Press `q` to force-quit the camera window (debug/safety exit only — not meant to be your normal way of dismissing the alarm).
- If squat detection feels off, watch the `gap` value shown on screen and tune `DOWN_THRESH` / `UP_THRESH` in `squat_counter.py` to match your camera distance and angle.
- This is a desktop-only project for now — no mobile support yet.

## Status

Desktop prototype, in progress. Possible next steps: stricter form checking, mobile port, sound customization.