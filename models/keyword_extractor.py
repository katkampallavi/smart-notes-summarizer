from keybert import KeyBERT

kw_model = KeyBERT()

def extract_keywords(text):

    results = kw_model.extract_keywords(
        text,
        keyphrase_ngram_range=(1, 2),
        stop_words="english",
        top_n=20,
        use_mmr=True,
        diversity=0.8
    )

    unique_keywords = []

    for keyword, score in results:
        if keyword not in unique_keywords:
            unique_keywords.append(keyword)

    return unique_keywords[:10]