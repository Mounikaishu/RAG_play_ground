from typing import TypedDict, List

class ChatState(TypedDict):
    question: str
    context: str
    answer: str
    history: List[str]