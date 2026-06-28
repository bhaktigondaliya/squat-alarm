"""
alarm.py
--------
Handles the alarm sound: loops indefinitely, can be paused/resumed.

Why pygame.mixer instead of playsound:
- playsound blocks and can't loop easily without re-launching.
- pygame.mixer.music supports loop=-1 (infinite) and pause()/unpause()
  natively, which is exactly the "pause while squatting, resume if you
  walk away" behavior we want.
"""

import pygame
import os


class Alarm:
    def __init__(self, sound_path):
        if not os.path.exists(sound_path):
            raise FileNotFoundError(f"Alarm sound not found: {sound_path}")

        pygame.mixer.init()
        self.sound_path = sound_path
        self._playing = False
        self._paused = False

    def start(self):
        """Begin looping playback from the start."""
        pygame.mixer.music.load(self.sound_path)
        pygame.mixer.music.play(loops=-1)  # -1 = loop forever
        self._playing = True
        self._paused = False

    def pause(self):
        if self._playing and not self._paused:
            pygame.mixer.music.pause()
            self._paused = True

    def resume(self):
        if self._playing and self._paused:
            pygame.mixer.music.unpause()
            self._paused = False

    def stop(self):
        if self._playing:
            pygame.mixer.music.stop()
        self._playing = False
        self._paused = False

    def is_paused(self):
        return self._paused