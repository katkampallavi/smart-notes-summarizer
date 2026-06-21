from collections import Counter
import re

def generate_summary(text):

    sentences = re.split(r'(?<=[.!?]) +', text)

    if len(sentences) <= 3:
        return text

    words = re.findall(r'\w+', text.lower())

    word_freq = Counter(words)

    sentence_scores = {}

    for sentence in sentences:
        for word in re.findall(r'\w+', sentence.lower()):
            if word in word_freq:
                sentence_scores[sentence] = sentence_scores.get(sentence, 0) + word_freq[word]

    summary_sentences = sorted(
        sentence_scores,
        key=sentence_scores.get,
        reverse=True
    )[:3]

    summary = " ".join(summary_sentences)

    return summary