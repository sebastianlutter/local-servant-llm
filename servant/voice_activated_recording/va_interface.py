import time
import os
import numpy as np
from abc import ABC, abstractmethod
from servant.audio_device.soundcard import SoundCard


class VoiceActivationInterface(ABC):

    def __init__(self):
        super().__init__()
        self.wakeword = os.getenv('WAKEWORD', 'computer')
        self.wakeword_threshold = os.getenv('WAKEWORD_THRESHOLD', '250')
        # Configurable delay before counting silence
        self.silence_lead_time = 2
        self.soundcard = SoundCard()


    @abstractmethod
    def listen_for_wake_word(self, sentence: str):
        pass

    def start_recording(self):
        print("Recording...")
        stream = self.soundcard.get_record_stream()
        audio_frames = []
        silence_counter = 0
        record_start_time = time.time()
        while True:
            data = stream.read(self.soundcard.frames_per_buffer, exception_on_overflow=False)
            if time.time() - record_start_time < self.silence_lead_time:
                audio_frames.append(data)
            else:
                if self.is_silence(data):
                    silence_counter += 1
                else:
                    silence_counter = 0
                audio_frames.append(data)
            if silence_counter > 30:  # approx 2 seconds of silence detected
                break
        print("Stopping recording...")
        stream.stop_stream()
        stream.close()
        # Remove the last two seconds of audio corresponding to silence detection
        return self.soundcard.get_audio_buffer(audio_frames[:-30])


    def config_str(self):
        return f'wakeword: {self.wakeword}, threshold: {self.wakeword_threshold}'

    def is_silence(self, data):
        audio_data = np.frombuffer(data, dtype=np.int16)
        mean_volume = np.mean(np.abs(audio_data))
        return mean_volume < self.wakeword_threshold