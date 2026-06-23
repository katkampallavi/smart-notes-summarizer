import re
import math
from collections import Counter


class Summarizer:
    """
    Extractive text summarizer using TF-IDF scoring.
    No external NLP models required — works offline with pure Python.
    """

    STOP_WORDS = {
        'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
        'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were',
        'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'shall',
        'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she',
        'it', 'we', 'they', 'what', 'which', 'who', 'whom', 'when',
        'where', 'why', 'how', 'all', 'each', 'every', 'both', 'few',
        'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
        'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
        'as', 'if', 'its', 'their', 'our', 'your', 'my', 'his', 'her',
        'also', 'about', 'above', 'after', 'before', 'between', 'into',
        'through', 'during', 'including', 'until', 'while', 'among',
        'throughout', 'despite', 'towards', 'upon', 'whether'
    }

    def __init__(self, max_sentences=10, min_sentence_length=20):
        self.max_sentences = max_sentences
        self.min_sentence_length = min_sentence_length

    def _tokenize_sentences(self, text):
        """Split text into sentences."""
        text = re.sub(r'\s+', ' ', text.strip())
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) >= self.min_sentence_length]
        return sentences

    def _tokenize_words(self, text):
        """Tokenize and clean words."""
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        return [w for w in words if w not in self.STOP_WORDS]

    def _compute_tf(self, words):
        """Compute term frequency."""
        if not words:
            return {}
        freq = Counter(words)
        total = len(words)
        return {word: count / total for word, count in freq.items()}

    def _compute_idf(self, sentences):
        """Compute inverse document frequency across sentences."""
        num_sentences = len(sentences)
        if num_sentences == 0:
            return {}
        word_doc_count = Counter()
        for sentence in sentences:
            words_in_sentence = set(self._tokenize_words(sentence))
            for word in words_in_sentence:
                word_doc_count[word] += 1
        idf = {}
        for word, count in word_doc_count.items():
            idf[word] = math.log((num_sentences + 1) / (count + 1)) + 1
        return idf

    def _score_sentences(self, sentences, idf):
        """Score each sentence using TF-IDF."""
        scores = {}
        for i, sentence in enumerate(sentences):
            words = self._tokenize_words(sentence)
            if not words:
                scores[i] = 0
                continue
            tf = self._compute_tf(words)
            score = sum(tf.get(w, 0) * idf.get(w, 0) for w in words)
            # Slight position bonus for early sentences
            position_bonus = 1.0 if i == 0 else (0.9 if i == 1 else 1.0)
            scores[i] = score * position_bonus
        return scores

    def summarize(self, text):
        """
        Generate an extractive summary from the given text.
        Returns a string summary.
        """
        if not text or len(text.strip()) < 100:
            return text.strip() if text else "No content to summarize."

        sentences = self._tokenize_sentences(text)
        if not sentences:
            return "Could not extract meaningful sentences from the document."

        if len(sentences) <= self.max_sentences:
            return ' '.join(sentences)

        idf = self._compute_idf(sentences)
        scores = self._score_sentences(sentences, idf)

        # Select top-N sentences, preserving original order
        top_indices = sorted(
            sorted(scores, key=scores.get, reverse=True)[:self.max_sentences]
        )

        summary_sentences = [sentences[i] for i in top_indices]
        summary = ' '.join(summary_sentences)

        # Ensure minimum length — fallback to first N sentences
        if len(summary) < 100:
            summary = ' '.join(sentences[:self.max_sentences])

        return summary

    def get_word_count(self, text):
        """Return the word count of text."""
        if not text:
            return 0
        return len(text.split())

    def get_reading_time(self, text, wpm=200):
        """Estimate reading time in minutes."""
        wc = self.get_word_count(text)
        return max(1, round(wc / wpm))