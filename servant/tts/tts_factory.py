import os

def TtsFactory():
    provider_name=os.getenv('TTS_PROVIDER', 'pyttsx')
    match provider_name:
        case 'openedai':
            from servant.tts.tts_openedai_speech import TextToSpeechOpenedaiSpeech
            p = TextToSpeechOpenedaiSpeech()
        case 'pyttsx':
            from servant.tts.tts_pyttsx import TextToSpeechPyTtsx, TextToSpeechEspeakCli
            #p = TextToSpeechPyTtsx()
            p = TextToSpeechEspeakCli()
        case 'transformers':
            from servant.tts.tts_transformer import TextToSpeechTransformer
            p = TextToSpeechTransformer()
        case _:
            raise Exception(f"TtsFactory: unknown provider name {provider_name}")
    print(f"TtsFactory: start {provider_name} provider. {p.config_str()}")
    return p