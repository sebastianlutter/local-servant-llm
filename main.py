import time

import nltk
import random
from nltk.tokenize import sent_tokenize
from typing import Tuple
from burr.core import ApplicationBuilder, State, action, when, expr
from servant.servant_factory import ServantFactory
from dotenv import load_dotenv

load_dotenv()

nltk.download('punkt_tab')

factory = ServantFactory()

def random_bye():
    choices = [
        "Auf Wiedersehen!", "Mach’s gut!", "Bis zum nächsten Mal!", "Tschüss!", "Ciao!", "Adieu!", "Schönen Tag noch!",
        "Bis bald!", "Pass auf dich auf!", "Bleib gesund!", "Man sieht sich!", "Bis später!", "Bis dann!", "Gute Reise!",
        "Viel Erfolg noch!", "Danke und tschüss!", "Alles Gute!", "Bis zum nächsten Treffen!",
        "Leb wohl!"
    ]
    return random.choice(choices)

def title(msg):
    print("###########################################################################################################")
    print(f"# {msg}")
    print("###########################################################################################################")

@action(reads=[], writes=["voice_buffer"])
def get_user_speak_input(state: State) -> Tuple[dict, State]:
    # block until wake word has been said
    audio_buffer = factory.va_provider.listen_for_wake_word()
    title(f"get_user_speak_input")
    return {"voice_buffer": audio_buffer}, state.update(voice_buffer=audio_buffer)

@action(reads=["voice_buffer"], writes=["prompt","prompt_len"])
def transcribe_voice_recording(state: State) -> Tuple[dict, State]:
    audio_buffer = state.get("voice_buffer")
    transcription = factory.stt_provider.transcribe(audio_buffer)
    title(f"transcribe_voice_recording: {transcription}")
    return {"prompt": transcription, "prompt_len": len(str(transcription).strip())}, state.update(prompt=transcription).update(prompt_len=len(str(transcription).strip()))

@action(reads=[], writes=["voice_buffer"])
def we_did_not_understand(state: State) -> Tuple[dict, State]:
    message = "Ich habe dich nicht verstanden. Sag es noch mal."
    title(message)
    factory.tts_provider.speak(message)
    voice_buffer = factory.va_provider.start_recording()
    return {"voice_buffer": voice_buffer}, state.update(voice_buffer=voice_buffer)

@action(reads=["chat_history"], writes=["prompt", "chat_history"])
def human_input(state: State) -> Tuple[dict, State]:
    # add the prompt to history
    prompt = state.get("prompt")
    print(f"User: {prompt}")
    chat_item = {"content": prompt, "role": "user"}
    title(f"human_input: {prompt}")
    return {"prompt": prompt}, state.update(prompt=prompt).append(chat_history=chat_item)

@action(reads=["prompt"], writes=["exit_chat"])
def exit_chat_check(state: State) -> Tuple[dict, State]:
    prompt = state.get("prompt")
    is_ending = factory.llm_provider.is_conversation_ending(prompt)
    title(f"exit_chat_check: {is_ending}")
    return {"exit_chat": is_ending}, state.update(exit_chat=is_ending)

@action(reads=[], writes=["chat_history"])
def exit_chat(state: State) -> Tuple[dict, State]:
    title("exit_chat")
    factory.tts_provider.speak(f"Ich beende das Programm, {random_bye()}")
    return {"chat_history": []}, state.update(chat_history=[])

@action(reads=["chat_history"], writes=["response", "chat_history"])
def ai_response(state: State) -> Tuple[dict, State]:
    # give the history including the last user input to the LLM to get its response
    response_stream = factory.llm_provider.chat_stream(state["chat_history"])
    response = ''
    print("KI: ", end='', flush=True)
    # consume the stream and collect response while printing to console
    buffer = ""
    response = ""
    sentences_all = []
    for chunk in response_stream:
        response += chunk
        buffer += chunk
        print(chunk, end='', flush=True)
        # Tokenize to sentences
        sentences = sent_tokenize(buffer)
        # process all full sentences (except incomplete)
        for sentence in sentences[:-1]:
            factory.tts_provider.speak(sentence)
            sentences_all.append(sentence)
        # store last (maybe incomplete) sentence in the buffer
        buffer = sentences[-1]
    if len(buffer) > 2:
        # add last fragment of response
        factory.tts_provider.speak(buffer)
        sentences_all.append(buffer)
    # add response to the history to show to the use
    chat_item = {"content": response, "role": "assistant"}
    print()
    title(f"ai_response finished, wait for speaking is done")
    # Stop if we do not speak for a second
    counter_not_speaking=0
    while True:
        if not factory.tts_provider.still_speaking:
            counter_not_speaking+=1
        if counter_not_speaking > 15:
            break
        time.sleep(0.1)
    title(f"ai_repsonse: speaking has finished")
    #for s in sentences_all:
    #    print(f"Sentence: {s}")
    return {"response": response}, state.update(response=response).append(chat_history=chat_item)

def application():
    return (
        ApplicationBuilder()
        .with_actions(
            get_user_speak_input=get_user_speak_input,
            transcribe_voice_recording=transcribe_voice_recording,
            we_did_not_understand=we_did_not_understand,
            human_input=human_input,
            ai_response=ai_response,
            exit_chat_check=exit_chat_check,
            exit_chat=exit_chat
        )
        .with_transitions(
            # get first user input with wakeup word "hey computer" and send to transcription
            ("get_user_speak_input", "transcribe_voice_recording"),
            # check if we have enough chars from the transcription, if not go to we_did_not_understand
            ("transcribe_voice_recording", "we_did_not_understand", expr("prompt_len < 10")),
            # if we_did_not_understand directly record again and transcribe again
            ("we_did_not_understand", "transcribe_voice_recording"),
            # if prompt_len is ok then send to human_input
            ("transcribe_voice_recording", "exit_chat_check", expr("prompt_len >= 10")),
            # if user wants to end the conversation we do so
            ("exit_chat_check", "exit_chat", when(exit_chat=True)),
            # else pass on to use this as human input
            ("exit_chat_check", "human_input", when(exit_chat=False)),
            # the human input is given to the LLM to get a response
            ("human_input", "ai_response"),
            # after AI has answered go back to wait for wakeup word to record again
            ("ai_response", "get_user_speak_input"),
        )
        # init the chat history with the system prompt
        .with_state(chat_history=[{"content": factory.llm_provider.system_prompt, "role": "assistant"}], exit_chat=False)
        .with_entrypoint("get_user_speak_input")
        .with_tracker("local", project="servant-llm")
        .build()
    )

if __name__ == "__main__":
    app = application()
    #app.visualize(include_conditions=True, output_file_path="graph.png", include_state=True)
    action_we_ran, result, state = app.run(halt_after=["exit_chat"])
    title("Application finished")
    for item in state['chat_history']:
        print(item['role'] + ':' + item['content'] + '\n')