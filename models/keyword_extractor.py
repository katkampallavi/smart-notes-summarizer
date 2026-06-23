import re
import math
from collections import Counter


class KeywordExtractor:
    """
    Keyword extractor using TF-IDF and frequency ranking.
    No external dependencies — pure Python implementation.
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
        'throughout', 'despite', 'towards', 'upon', 'whether', 'use',
        'used', 'using', 'one', 'two', 'three', 'four', 'five', 'six',
        'seven', 'eight', 'nine', 'ten', 'said', 'say', 'says', 'like',
        'get', 'got', 'make', 'made', 'know', 'see', 'come', 'go',
        'take', 'give', 'new', 'way', 'even', 'well', 'back', 'any',
        'good', 'much', 'need', 'want', 'look', 'first', 'last', 'long',
        'great', 'little', 'own', 'right', 'big', 'high', 'different',
        'small', 'large', 'next', 'early', 'young', 'important', 'public',
        'private', 'real', 'best', 'free', 'however', 'therefore',
        'thus', 'hence', 'since', 'because', 'although', 'though',
        'whereas', 'while', 'unless', 'rather', 'quite', 'still',
        'already', 'then', 'now', 'here', 'there', 'again', 'once',
        'per', 're', 'eg', 'ie', 'etc', 'vs', 'via', 'fig'
    }

    def __init__(self, max_keywords=10, min_word_length=4):
        self.max_keywords = max_keywords
        self.min_word_length = min_word_length

    def _clean_text(self, text):
        """Normalize and clean the input text."""
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\d+', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.lower().strip()

    def _tokenize(self, text):
        """Extract meaningful words from text."""
        cleaned = self._clean_text(text)
        words = re.findall(r'\b[a-zA-Z]{' + str(self.min_word_length) + r',}\b', cleaned)
        return [w for w in words if w not in self.STOP_WORDS]

    def _get_sentences(self, text):
        """Split text into sentences for IDF calculation."""
        return re.split(r'[.!?]+', text)

    def _compute_tfidf(self, words, all_sentences):
        """Compute TF-IDF scores for words."""
        if not words:
            return {}

        # Term frequency
        word_freq = Counter(words)
        total_words = len(words)
        tf = {word: count / total_words for word, count in word_freq.items()}

        # Inverse document frequency
        num_sentences = len(all_sentences)
        word_doc_count = Counter()
        for sentence in all_sentences:
            sentence_words = set(self._tokenize(sentence))
            for word in sentence_words:
                word_doc_count[word] += 1

        idf = {}
        for word in tf:
            doc_count = word_doc_count.get(word, 0)
            idf[word] = math.log((num_sentences + 1) / (doc_count + 1)) + 1

        tfidf = {word: tf[word] * idf[word] for word in tf}
        return tfidf

    def _extract_bigrams(self, words, top_unigrams):
        """Extract meaningful bigrams from top unigrams."""
        top_set = set(top_unigrams)
        bigrams = []
        for i in range(len(words) - 1):
            if words[i] in top_set and words[i + 1] in top_set:
                bigrams.append(f"{words[i]} {words[i + 1]}")
        bigram_freq = Counter(bigrams)
        return [bg for bg, count in bigram_freq.most_common(3) if count > 1]

    def extract(self, text):
        """
        Extract top keywords from the text.
        Returns a list of keyword strings.
        """
        if not text or len(text.strip()) < 50:
            return []

        words = self._tokenize(text)
        if not words:
            return []

        sentences = self._get_sentences(text)
        tfidf_scores = self._compute_tfidf(words, sentences)

        # Sort by TF-IDF score
        sorted_keywords = sorted(tfidf_scores.items(), key=lambda x: x[1], reverse=True)
        top_unigrams = [kw for kw, _ in sorted_keywords[:self.max_keywords]]

        # Try to include some bigrams
        bigrams = self._extract_bigrams(words, set(top_unigrams[:5]))

        # Combine: prefer bigrams, fill rest with unigrams
        final_keywords = []
        for bg in bigrams[:3]:
            final_keywords.append(bg)

        for uw in top_unigrams:
            if len(final_keywords) >= self.max_keywords:
                break
            # Skip if already represented in a bigram
            already_in_bigram = any(uw in bg for bg in final_keywords)
            if not already_in_bigram:
                final_keywords.append(uw)

        return final_keywords[:self.max_keywords]

    def extract_as_string(self, text):
        """Return keywords as a comma-separated string."""
        keywords = self.extract(text)
        return ', '.join(keywords)