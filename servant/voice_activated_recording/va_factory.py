import os

def VoiceActivatedRecordingFactory():
    provider_name=os.getenv('WAKEWORD_PROVIDER', 'speech-recognition')
    match provider_name:
        case 'speech-recognition':
            from servant.voice_activated_recording.va_speech_recognition import SpeechRecognitionActivated
            p = SpeechRecognitionActivated()
        case 'open-wakeword':
            from servant.voice_activated_recording.va_open_wake_word import  OpenWakewordActivated
            p = OpenWakewordActivated()
        case _:
            raise Exception(f"VoiceActivationFactory: unknown provider name {provider_name}")
    print(f"VoiceActivationFactory: start {provider_name} provider: {p.config_str()}")
    return p