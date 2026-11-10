"""Language detector: en | hi | hinglish."""
import re

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
HINDI_WORDS = set(
    "kya hai hain mera meri mere mujhe milegi milega milti milta kitna kitni kitne chahiye nahi nahin haan "
    "liye saal chutti kaise kab kaun kahan kyun karna karu kare karo kar sakta sakti hoon hu tha thi aur bhi "
    "mein mai main ka ki ke ko se wala wali batao bataiye samjhao paisa din mahine hafte abhi agar lekin "
    "kyunki matlab accha theek yaar".split()
)


def detect(text: str) -> str:
    if _DEVANAGARI.search(text):
        return "hi"
    words = re.findall(r"[a-z]+", text.lower())
    return "hinglish" if sum(w in HINDI_WORDS for w in words) >= 2 else "en"
