from transformers import pipeline

chatbot = pipeline(
    "text2text-generation",
    model="google/flan-t5-base"
)

def ask_question(question):

    result = chatbot(
        question,
        max_length=100
    )

    return result[0]["generated_text"]