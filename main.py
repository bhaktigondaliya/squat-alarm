"""
main.py
-------
Glue script: waits for alarm time -> starts blaring sound -> opens camera
-> counts squats -> pauses sound while you're in frame and squatting
-> resumes sound if you walk away -> stops everything once 10 reps are done.

Usage:
    python main.py --time 07:00 --sound alarm.wav --reps 10

If --time is omitted, the alarm starts immediately (good for testing the
squat-counting logic without waiting for a real alarm time).
"""

import argparse
import time
import datetime
import cv2

from alarm import Alarm
from squat_counter import SquatSession


def wait_until(target_time_str):
    """Block until the next occurrence of HH:MM (24hr) local time."""
    now = datetime.datetime.now()
    target = datetime.datetime.strptime(target_time_str, "%H:%M").time()
    target_dt = datetime.datetime.combine(now.date(), target)

    if target_dt <= now:
        target_dt += datetime.timedelta(days=1)  # roll over to tomorrow

    print(f"Waiting until {target_dt} ...")
    while datetime.datetime.now() < target_dt:
        time.sleep(1)


def run_squat_alarm(sound_path, reps, camera_index):
    alarm = Alarm(sound_path)
    alarm.start()
    print("ALARM! Do your squats to turn it off.")

    session = SquatSession(target_reps=reps, camera_index=camera_index)
    session.start_camera()

    window_name = "Squat Alarm - press Q only after finishing reps"

    try:
        while not session.done:
            frame = session.process_frame()
            if frame is None:
                print("Camera read failed, retrying...")
                continue

            # --- Pause/resume logic ---
            # We pause the alarm only while you're making real progress on
            # squats. "Progress" = your rep count went up recently, OR
            # you're currently mid-squat (DOWN state). Just standing in
            # frame doing nothing does NOT pause it.
            making_progress = (
                session.state == "DOWN"
                or (time.time() - session.last_rep_time) < 1.5
            )
            if session.person_visible and making_progress:
                alarm.pause()
            else:
                alarm.resume()

            cv2.imshow(window_name, frame)

            # 'q' is only a safety/debug exit, not meant to be the normal
            # way to silence the alarm -- the point is you actually do
            # the squats. Remove this if you want zero escape hatches.
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Manual exit requested (debug).")
                break

    finally:
        session.close()
        cv2.destroyAllWindows()

    if session.done:
        print(f"Nice work! {session.count} squats completed. Alarm off.")
    alarm.stop()


def main():
    parser = argparse.ArgumentParser(description="Squat-to-dismiss alarm")
    parser.add_argument("--time", type=str, default=None,
                         help="Alarm time in 24hr HH:MM format, e.g. 07:00. "
                              "Omit to start immediately (testing mode).")
    parser.add_argument("--sound", type=str, default="alarm.wav",
                         help="Path to the alarm sound file (wav/mp3).")
    parser.add_argument("--reps", type=int, default=10,
                         help="Number of squats required to dismiss alarm.")
    parser.add_argument("--camera", type=int, default=0,
                         help="Webcam index.")
    args = parser.parse_args()

    if args.time:
        wait_until(args.time)

    run_squat_alarm(args.sound, args.reps, args.camera)


if __name__ == "__main__":
    main()