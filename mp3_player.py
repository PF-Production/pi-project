import pygame
import threading
import time
from datetime import datetime
import os


class MP3Player:
    def __init__(self, mp3_path, second_path=None, volume=0.5, audio_device=None):
        # Set audio device if specified (e.g., "hw:1,0")
        if audio_device:
            os.environ["SDL_AUDIODRIVER"] = "alsa"
            os.environ["AUDIODEV"] = audio_device

        pygame.mixer.init()
        self.mp3_path = mp3_path
        self.second_path = second_path
        self.volume = volume
        self._playing = False
        self._thread = None
        pygame.mixer.music.set_volume(self.volume)

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, volume))
        pygame.mixer.music.set_volume(self.volume)

    def play_loop(self):
        pygame.mixer.music.load(self.mp3_path)
        pygame.mixer.music.play(loops=-1)
        self._playing = True
        # Play second track if provided
        if self.second_path:
            sound2 = pygame.mixer.Sound(self.second_path)
            channel2 = pygame.mixer.Channel(1)
            channel2.play(sound2, loops=-1)

    def stop(self):
        pygame.mixer.music.stop()
        if self.second_path:
            channel2 = pygame.mixer.Channel(1)
            channel2.stop()
        self._playing = False

    def play_between_times(self, start_time, end_time):
        """
        start_time and end_time should be datetime.time objects
        """

        def _run():
            while True:
                now = datetime.now().time()
                if start_time <= now <= end_time:
                    if not self._playing:
                        self.play_loop()
                else:
                    if self._playing:
                        self.stop()
                time.sleep(1)

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def is_playing(self):
        return self._playing
