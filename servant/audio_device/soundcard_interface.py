import os
from abc import ABC, abstractmethod
from typing import BinaryIO, List

class AudioInterface(ABC):

    def __init__(self):
        # Read environment variables
        self.audio_microphone_device = int(os.getenv('AUDIO_MICROPHONE_DEVICE', '0'))
        self.audio_playback_device = int(os.getenv('AUDIO_PLAYBACK_DEVICE', '0'))
        # Validate microphone device index
        if not self.is_valid_device_index(self.audio_microphone_device, input_device=True):
            print("Available devices:")
            self.list_devices()
            raise Exception(f"Error: The microphone device index '{self.audio_microphone_device}' is invalid or not available.")

        # Validate playback device index
        if not self.is_valid_device_index(self.audio_playback_device, input_device=False):
            print("Available devices:")
            self.list_devices()
            raise Exception(f"Error: The playback device index '{self.audio_playback_device}' is invalid or not available.")


    @abstractmethod
    def list_devices(self) -> None:
        """
        List all available audio devices. This should display separate lists for input and output devices,
        along with relevant details such as device index, name, supported channels, and sample rates.
        """
        pass

    @abstractmethod
    def is_valid_device_index(self, index: int, input_device: bool = True) -> bool:
        """
        Check if the given device index is valid and can be used as an input or output device.

        :param index: The device index to validate.
        :param input_device: If True, checks for input capability; if False, checks for output capability.
        :return: True if the device index is valid for the requested direction, False otherwise.
        """
        pass

    @abstractmethod
    def get_record_stream(self):
        """
        Open a recording stream (or equivalent object) for capturing audio from the currently selected microphone device.

        :return: A stream or device handle suitable for reading raw audio data frames.
        :raises RuntimeError: If no valid microphone device is configured.
        """
        pass

    @abstractmethod
    def get_audio_buffer(self, frames: List[bytes]) -> BinaryIO:
        """
        Convert raw audio frames into an audio buffer (e.g., a WAV file in memory).

        :param frames: A list of raw audio data frames.
        :return: A file-like object (BinaryIO) containing the audio data (e.g. WAV) ready to be read or written.
        """
        pass

    def config_str(self):
        return f'Soundcard device: microphone={self.audio_microphone_device}, playback: {self.audio_playback_device}'