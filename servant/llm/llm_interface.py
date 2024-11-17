from fuzzywuzzy import process
from abc import ABC, abstractmethod

class LmmInterface(ABC):

    @abstractmethod
    def chat(self, text: str, stream: bool = False):
        pass

    def is_conversation_ending(self, sentence):
        # Define phrases that indicate the end of a conversation in both English and German
        end_phrases = [
            "stop chat", "end chat", "goodbye", "exit", "bye", "finish",
            "halt stoppen", "chat beenden", "auf wiedersehen", "tschüss", "ende", "schluss"
        ]
        # Use fuzzy matching to find the closest match to the input sentence and get the match score
        highest_match = process.extractOne(sentence.lower(), end_phrases)
        # Define a threshold for deciding if the sentence means to end the conversation
        threshold = 80  # You can adjust the threshold based on testing
        # Check if the highest match score is above the threshold
        if highest_match[1] >= threshold:
            return True
        else:
            return False