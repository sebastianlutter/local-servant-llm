import random
import threading
import time
import os
import io
import hashlib
import logging
from pydub import AudioSegment
from typing import AsyncGenerator, Tuple
from servant.audio_device.soundcard_factory import SoundcardFactory
from servant.interrupt_speech_thread import InterruptSpeechThread
from servant.stt.stt_factory import SttFactory
from servant.tts.tts_factory import TtsFactory
from servant.voice_activated_recording.va_factory import VoiceActivatedRecordingFactory
from tqdm import tqdm
import soundfile as sf

format_string = (
    "%(asctime)s - [Logger: %(name)s] - %(levelname)s - %(filename)s:%(lineno)d in %(funcName)s() - %(message)s"
)
logging.basicConfig(format=format_string, level=logging.INFO)
logging.getLogger('httpx').setLevel(logging.ERROR)
logging.getLogger('websocket').setLevel(logging.ERROR)

class HumanSpeechAgent:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    # Create new instance
                    cls._instance = super(HumanSpeechAgent, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        # Ensure __init__ only runs once per singleton instance
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.interrupt_speech_thread = None
        self.soundcard = SoundcardFactory()
        self.voice_activator = VoiceActivatedRecordingFactory()
        self.tts_provider = TtsFactory()
        self.silence_lead_time = 2
        self.max_recording_time = 15
        self.stt_provider = SttFactory()
        self.stop_signal = threading.Event()
        self.hi_choices = [
            'ja, hi', 'schiess los!',
            'was gibts?', 'hi, was geht?',
            'leg los!', 'was willst du?',
            'sprechen Sie', 'jo bro',
        ]
        self.bye_choices = [
            "Auf Wiedersehen!", "Mach’s gut!", "Bis zum nächsten Mal!", "Tschüss!", "Ciao!", "Adieu!",
            "Schönen Tag noch!",
            "Bis bald!", "Pass auf dich auf!", "Bleib gesund!", "Man sieht sich!", "Bis später!", "Bis dann!",
            "Gute Reise!",
            "Viel Erfolg noch!", "Danke und tschüss!", "Alles Gute!", "Bis zum nächsten Treffen!",
            "Leb wohl!"
        ]
        init_greetings_identity = "Ich freue mich dein Assistent zu sein! "
        self.init_greetings = [
            "Guten Tag!", "Hi, wie geht's?", "Schön dich zu sehen!", "Hallo und willkommen!",
            "Freut mich, dich zu treffen!", "Hallo zusammen!", "Hallo, mein Freund!",
            "Guten Tag, wie kann ich helfen?", "Willkommen!", "Hallo an alle!",
            "Herzlich willkommen!", "Hallo, schön dich hier zu haben!", "Hey, alles klar?",
            "Hallo, schön dich kennenzulernen!", "Hallo, wie läuft's?", "Einen schönen Tag!", "Schön, dass du da bist!"
        ]
        self.init_greetings = list(map(lambda g: g + init_greetings_identity, self.init_greetings))
        self.did_not_understand = [
            "Das war unverständlich, noch mal bitte"
        ]
        self.explain_sentence = "Sag das wort computer um zu starten."
        self._warmup_cache()

    def engage_input_beep(self):
        sample_rate, audio_buffer = self._load_mp3_to_wav_bytesio("sounds/deskviewerbeep.mp3")
        self.soundcard.play_audio(sample_rate, audio_buffer)

    def beep_positive(self):
        sample_rate, audio_buffer = self._load_mp3_to_wav_bytesio("sounds/computerbeep_26.mp3")
        self.soundcard.play_audio(sample_rate, audio_buffer)

    def beep_error(self):
        sample_rate, audio_buffer = self._load_mp3_to_wav_bytesio("sounds/denybeep1.mp3")
        self.soundcard.play_audio(sample_rate, audio_buffer)

    def processing_sound(self):
        sample_rate, audio_buffer = self._load_mp3_to_wav_bytesio("sounds/processing.mp3")
        self.soundcard.play_audio(sample_rate, audio_buffer)

    def say_init_greeting(self):
        hi_phrase = random.choice(self.init_greetings)
        mp3_path = self._get_cache_file_name(hi_phrase)
        sample_rate, audio_buffer = self._load_mp3_to_wav_bytesio(mp3_path)
        self.soundcard.play_audio(sample_rate, audio_buffer)
        self.tts_provider.speak(f"Ich höre auf den Namen {self.voice_activator.wakeword}")
        self.soundcard.wait_until_playback_finished()

    def say_hi(self):
        hi_phrase = random.choice(self.hi_choices)
        mp3_path = self._get_cache_file_name(hi_phrase)
        sample_rate, audio_buffer = self._load_mp3_to_wav_bytesio(mp3_path)
        self.logger.info(f"say_hi: {hi_phrase}")
        self.soundcard.play_audio(sample_rate, audio_buffer)

    def say_bye(self, message: str = ''):
        bye_phrase = random.choice(self.bye_choices)
        mp3_path = self._get_cache_file_name(bye_phrase)
        sample_rate, audio_buffer = self._load_mp3_to_wav_bytesio(mp3_path)
        self.logger.info(f"say_bye: {message}{bye_phrase}")
        if message != '':
            self.tts_provider.speak(message)
        self.tts_provider.wait_until_done()
        self.soundcard.play_audio(sample_rate, audio_buffer)

    def say_did_not_understand(self):
        did_not_understand_phrase = random.choice(self.did_not_understand)
        mp3_path = self._get_cache_file_name(did_not_understand_phrase)
        sample_rate, audio_buffer = self._load_mp3_to_wav_bytesio(mp3_path)
        self.logger.info(f"say_did_not_understand: {did_not_understand_phrase}")
        self.soundcard.play_audio(sample_rate, audio_buffer)

    def say(self, message: str):
        self.logger.info(f"SAY: {message}")
        self.tts_provider.speak(message)

    def skip_all_and_say(self, message: str):
        self.logger.info(f"Skip all and say: {message}")
        # first skip all speaking tasks
        self.tts_provider.set_stop_signal()
        self.tts_provider.wait_until_done()
        time.sleep(0.2)
        self.tts_provider.clear_stop_signal()
        self.tts_provider.speak(message)

    def block_until_talking_finished(self):
        self.tts_provider.wait_until_done()

    async def get_human_input(self, ext_stop_signal: threading.Event, wait_for_wakeword: bool = True) -> AsyncGenerator[str, None]:
        #self.soundcard.wait_until_playback_finished()
        if wait_for_wakeword:
            await self.voice_activator.listen_for_wake_word()
            self.beep_positive()

        def on_close_ws_callback():
            #self.logger.info("get_human_input.on_close_ws_callback: set stop")
            ext_stop_signal.set()

        def on_ws_open():
            #self.logger.info("on_ws_open: Should say_hi now ws is opened:")
            pass

        async for text in self.stt_provider.transcribe_stream(
            audio_stream=self.start_recording(),
            websocket_on_close=on_close_ws_callback,
            websocket_on_open=on_ws_open
        ):
            yield text
        self.logger.debug("get_human_input: finished")

    async def start_recording(self) -> AsyncGenerator[bytes, None]:
        self.logger.info("start_recording: Recording...")
        silence_counter = 0
        record_start_time = time.time()

        async for wav_chunk in self.soundcard.get_record_stream():
            if self.stop_signal.is_set():
                self.logger.info("start_recording: Stop signal is set. Abort reading record stream")
                self.soundcard.stop_recording()
                break
            yield wav_chunk

    def _warmup_cache(self):
        # Ensure the tts_cache directory exists
        os.makedirs("tts_cache", exist_ok=True)
        # Pre-render all hi and bye choices to mp3
        all_choices = self.hi_choices + self.bye_choices + self.init_greetings + [self.explain_sentence] + self.did_not_understand
        for sentence in tqdm(all_choices, desc="Warmup cache with hi and bye phrases"):
            file_name = self._get_cache_file_name(sentence)
            if not os.path.exists(file_name):
                # Render the sentence to the specified file in mp3 format
                self.tts_provider.render_sentence(sentence=sentence, store_file_name=file_name, output_format='mp3')

    def _get_cache_file_name(self, sentence: str):
        # Create a short hash based on the sentence content
        hash_obj = hashlib.md5(sentence.encode('utf-8'))
        # Truncate the hash for a shorter filename if desired
        hash_str = hash_obj.hexdigest()[:8]
        return os.path.join("tts_cache/", f"{hash_str}.mp3")

    def _load_mp3_to_wav_bytesio(self, mp3_path: str) -> Tuple[int, io.BytesIO]:
        # Load the MP3 file into an AudioSegment
        audio_segment = AudioSegment.from_mp3(mp3_path)
        # Create a BytesIO buffer to hold WAV data
        wav_bytes = io.BytesIO()
        # Export the audio segment as WAV into the BytesIO buffer
        audio_segment.export(wav_bytes, format="wav")
        # Reset the buffer's position to the beginning
        wav_bytes.seek(0)
        # convert to ndarray
        data, sample_rate = sf.read(wav_bytes, dtype='float32')
        return sample_rate, data

    def start_speech_interrupt_thread(self, ext_stop_signal: threading.Event):
        self.interrupt_speech_thread = InterruptSpeechThread(stop_event=ext_stop_signal, va_provider=self.voice_activator)
