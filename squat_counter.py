"""
squat_counter.py
-----------------
Uses MediaPipe Pose to detect squats via hip/knee y-coordinate tracking.

Logic:
- Track average hip-y and average knee-y (normalized 0-1, image coords).
- "Squat ratio" = hip_y - knee_y  (gets SMALLER/more negative... actually
  in image coords, y increases DOWNWARD. So when you squat, your hip
  drops -> hip_y increases and gets CLOSER to knee_y.)
- We track the vertical distance between hip and knee.
    - Standing: hip is well above knee -> large gap
    - Squatting: hip drops toward knee -> small gap
- State machine:
    UP   -> DOWN  when gap shrinks below DOWN_THRESH
    DOWN -> UP    when gap grows back above UP_THRESH  => count += 1
  (Two different thresholds = hysteresis, prevents flickering/double counts)

This module exposes a SquatSession class so main.py can poll it frame by frame.
"""

import cv2
import mediapipe as mp
import time
import os
import urllib.request


_HAS_OLD_API = hasattr(mp, "solutions")

POSE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)
POSE_MODEL_PATH = os.path.join(os.path.dirname(__file__), "pose_landmarker_lite.task")


def _ensure_new_model_downloaded():
    if not os.path.exists(POSE_MODEL_PATH):
        print("Downloading pose landmarker model (one-time, ~5MB)...")
        urllib.request.urlretrieve(POSE_MODEL_URL, POSE_MODEL_PATH)
        print("Model downloaded.")


# Landmark indices are identical across both MediaPipe APIs (BlazePose 33-point
# topology), so we can hardcode them and read raw (x, y, z, visibility) tuples
# regardless of which API produced them.
LEFT_HIP, RIGHT_HIP = 23, 24
LEFT_KNEE, RIGHT_KNEE = 25, 26


class SquatSession:
    def __init__(self, target_reps=10, camera_index=0):
        self.target_reps = target_reps
        self.camera_index = camera_index
        self.using_old_api = _HAS_OLD_API

        if self.using_old_api:
            self.mp_pose = mp.solutions.pose
            self.mp_draw = mp.solutions.drawing_utils
            self.pose = self.mp_pose.Pose(
                model_complexity=1,
                min_detection_confidence=0.6,
                min_tracking_confidence=0.6,
            )
        else:
            from mediapipe.tasks.python import vision
            from mediapipe.tasks.python.core import base_options as bo
            _ensure_new_model_downloaded()
            options = vision.PoseLandmarkerOptions(
                base_options=bo.BaseOptions(model_asset_path=POSE_MODEL_PATH),
                running_mode=vision.RunningMode.VIDEO,
                num_poses=1,
                min_pose_detection_confidence=0.6,
                min_tracking_confidence=0.6,
            )
            self._vision = vision
            self.landmarker = vision.PoseLandmarker.create_from_options(options)
            self._frame_timestamp_ms = 0

        self.cap = None
        self.count = 0
        self.state = "UP"  # UP or DOWN
        self.person_visible = False
        self.last_visible_time = 0
        self.last_rep_time = 0  # timestamp of the most recent completed rep
        self.done = False

        # Hysteresis thresholds for normalized hip-knee gap.
        # Tune these by watching the printed gap value if detection feels off.
        self.DOWN_THRESH = 0.10
        self.UP_THRESH = 0.16

        # If person is missing from frame for this many seconds,
        # we consider them "away" (used by main.py to resume the alarm sound).
        self.ABSENCE_TIMEOUT = 2.0

    def start_camera(self):
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            raise RuntimeError("Could not open webcam. Check camera index / permissions.")

    def stop_camera(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def is_person_present(self):
        """True if a person was seen within ABSENCE_TIMEOUT seconds."""
        return (time.time() - self.last_visible_time) < self.ABSENCE_TIMEOUT

    def process_frame(self):
        """
        Reads one frame, runs pose detection, updates squat count.
        Returns the annotated BGR frame for display (or None if camera read failed).
        """
        if self.cap is None:
            self.start_camera()

        ret, frame = self.cap.read()
        if not ret:
            return None

        frame = cv2.flip(frame, 1)  # mirror, feels natural
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        landmarks = self._get_landmarks(rgb, frame)

        if landmarks is not None:
            self.person_visible = True
            self.last_visible_time = time.time()

            hip_y = (landmarks[LEFT_HIP][1] + landmarks[RIGHT_HIP][1]) / 2
            knee_y = (landmarks[LEFT_KNEE][1] + landmarks[RIGHT_KNEE][1]) / 2

            gap = knee_y - hip_y  # large when standing, small when squatting
            self._update_state(gap)

            self._draw_skeleton(frame, landmarks)

            # Debug overlay of the raw gap value (handy for tuning thresholds)
            cv2.putText(frame, f"gap: {gap:.3f}", (10, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 0), 2)
        else:
            self.person_visible = False

        self._draw_hud(frame)
        return frame

    def _get_landmarks(self, rgb_frame, bgr_frame_for_size):
        """
        Returns a list of (x, y) normalized landmark coords, or None if no
        person detected. Abstracts away the old/new MediaPipe API difference.
        """
        if self.using_old_api:
            results = self.pose.process(rgb_frame)
            if not results.pose_landmarks:
                return None
            lm = results.pose_landmarks.landmark
            return [(p.x, p.y) for p in lm]
        else:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            self._frame_timestamp_ms += 33  # ~30fps step; doesn't need to be exact
            result = self.landmarker.detect_for_video(mp_image, self._frame_timestamp_ms)
            if not result.pose_landmarks:
                return None
            lm = result.pose_landmarks[0]  # first detected person
            return [(p.x, p.y) for p in lm]

    def _draw_skeleton(self, frame, landmarks):
        """Draw simple dots + hip/knee connector lines (works for both APIs
        since we already reduced everything to plain (x, y) tuples)."""
        h, w = frame.shape[:2]
        for (x, y) in landmarks:
            cv2.circle(frame, (int(x * w), int(y * h)), 3, (0, 255, 0), -1)

        for a_idx, b_idx in [(LEFT_HIP, LEFT_KNEE), (RIGHT_HIP, RIGHT_KNEE)]:
            ax, ay = landmarks[a_idx]
            bx, by = landmarks[b_idx]
            cv2.line(frame, (int(ax * w), int(ay * h)), (int(bx * w), int(by * h)),
                      (0, 200, 255), 2)

    def _update_state(self, gap):
        if self.state == "UP" and gap < self.DOWN_THRESH:
            self.state = "DOWN"
        elif self.state == "DOWN" and gap > self.UP_THRESH:
            self.state = "UP"
            self.count += 1
            self.last_rep_time = time.time()
            if self.count >= self.target_reps:
                self.done = True

    def _draw_hud(self, frame):
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (0, 0), (w, 70), (0, 0, 0), -1)
        cv2.putText(frame, f"Squats: {self.count}/{self.target_reps}",
                    (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 0), 3)
        status_color = (0, 255, 255) if self.state == "DOWN" else (255, 255, 255)
        cv2.putText(frame, self.state, (w - 150, 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, status_color, 2)

        if not self.person_visible:
            cv2.putText(frame, "Get back in frame!", (10, 95),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    def close(self):
        self.stop_camera()
        if self.using_old_api:
            self.pose.close()
        else:
            self.landmarker.close()