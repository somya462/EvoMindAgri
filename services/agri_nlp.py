
from services.agri_ner import extract_agricultural_entities


def analyze_query(text):

    # Existing NER module already performs
    # entity extraction, intent classification
    # and measurement extraction.

    result = extract_agricultural_entities(text)

    return {
        "original_query": result["original_query"],
        "entities": result["entities"],
        "intent": result["intent"],
        "measurements": result["measurements"]
    }
