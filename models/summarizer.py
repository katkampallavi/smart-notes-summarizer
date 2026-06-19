from transformers import pipeline

summarizer = pipeline(
    "summarization",
    model="sshleifer/distilbart-cnn-12-6"
)

def generate_summary(text):

    result = summarizer(
        text[:2000],
        max_length=120,
        min_length=40,
        do_sample=False
    )

    return result[0]["summary_text"]