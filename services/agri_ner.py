
import spacy
import re

from spacy.pipeline import EntityRuler

# 1. INITIALIZE NLP MODEL

nlp = spacy.blank("en")

ruler = nlp.add_pipe(
    "entity_ruler",
    config={"phrase_matcher_attr": "LOWER"}
)

# 2. AGRICULTURAL ENTITY DICTIONARY

AGRI_TERMS = {

    "CROP": [
        "wheat", "mustard", "rice", "paddy",
        "maize", "cotton", "sugarcane",
        "barley", "gram", "chickpea",
        "soybean", "potato", "tomato",
        "bajra", "millet", "groundnut"
    ],

    "DISEASE": [
        "yellow rust", "brown rust", "black rust",
        "powdery mildew", "root rot",
        "alternaria blight", "white rust",
        "downy mildew", "late blight",
        "leaf spot", "fusarium wilt"
    ],

    "PEST": [
        "aphids", "termites", "whitefly",
        "bollworm", "armyworm", "thrips",
        "cutworm", "leaf miner"
    ],

    "FERTILIZER": [
        "urea", "dap", "mop", "npk",
        "zinc sulphate", "zinc sulfate",
        "potash", "compost", "farmyard manure",
        "single super phosphate", "ssp"
    ],

    "SOIL_TYPE": [
        "sandy soil", "clay soil", "loamy soil",
        "sandy loam", "clay loam",
        "alluvial soil", "black soil",
        "saline soil", "alkaline soil"
    ],

    "IRRIGATION": [
        "drip irrigation", "sprinkler irrigation",
        "surface irrigation", "furrow irrigation",
        "flood irrigation", "canal irrigation"
    ],

    "GROWTH_STAGE": [
        "germination", "seedling stage",
        "tillering", "jointing",
        "flowering", "heading",
        "grain filling", "maturity",
        "ripening"
    ],

    "LOCATION": [
        "haryana", "punjab", "uttar pradesh",
        "rajasthan", "madhya pradesh",
        "hisar", "hansi", "karnal",
        "ambala", "rohtak", "sirsa",
        "kurukshetra", "ludhiana"
    ],

    "SOIL_PROPERTY": [
        "soil ph", "ph", "nitrogen",
        "phosphorus", "potassium",
        "organic carbon", "soil moisture",
        "electrical conductivity", "salinity"
    ]
}

# 3. REGISTER AGRICULTURAL ENTITIES

patterns = []

for label, terms in AGRI_TERMS.items():

    for term in terms:

        patterns.append({
            "label": label,
            "pattern": term
        })

ruler.add_patterns(patterns)

# 4. AGRICULTURAL INTENT CLASSIFICATION

INTENT_KEYWORDS = {

    "DISEASE_DIAGNOSIS": [
        "disease", "symptoms", "infection",
        "yellow leaves", "spots", "rust",
        "fungus", "wilting"
    ],

    "IRRIGATION_ADVICE": [
        "irrigation", "watering",
        "water requirement", "water management"
    ],

    "SOIL_ANALYSIS": [
        "soil", "ph", "nutrient",
        "soil health", "soil fertility"
    ],

    "FERTILIZER_ADVICE": [
        "fertilizer", "fertiliser", "urea",
        "npk", "nutrient deficiency"
    ],

    "CROP_MANAGEMENT": [
        "cultivation", "sowing", "planting",
        "harvesting", "yield", "growth"
    ],

    "PEST_MANAGEMENT": [
        "pest", "insects", "aphids",
        "whitefly", "bollworm"
    ]
}



def classify_intent(text):

    text_lower = text.lower()

    # Memory recall should have priority
    memory_keywords = [
        "what do i grow",
        "what crop do i grow",
        "where is my farm",
        "where is my farm located",
        "what is my recorded",
        "what do you remember",
        "what do you know about my farm",
        "my stored information",
        "my saved information",
        "based on my memories",
        "what information do you have about me"
    ]

    if any(keyword in text_lower for keyword in memory_keywords):
        return "MEMORY_RECALL"

    scores = {}

    for intent, keywords in INTENT_KEYWORDS.items():

        scores[intent] = sum(
            1 for keyword in keywords
            if keyword in text_lower
        )

    best_intent = max(scores, key=scores.get)

    if scores[best_intent] == 0:
        return "GENERAL_AGRICULTURAL_QUERY"

    return best_intent


# 5. EXTRACT NUMERICAL AGRICULTURAL VALUES

def extract_measurements(text):

    measurements = []

    patterns = [
        (
            r"\bph\s*(?:is|of|=|:)?\s*(\d+(?:\.\d+)?)",
            "SOIL_PH"
        ),
        (
            r"\b(\d+(?:\.\d+)?)\s*(kg/ha|kg per hectare)",
            "FERTILIZER_QUANTITY"
        ),
        (
            r"\b(\d+(?:\.\d+)?)\s*(mm|cm|inches?)\b",
            "LENGTH_OR_RAINFALL"
        ),
        (
            r"\b(\d+(?:\.\d+)?)\s*(celsius|°c|percent|%)",
            "MEASUREMENT"
        )
    ]

    for pattern, label in patterns:

        for match in re.finditer(
            pattern,
            text,
            re.IGNORECASE
        ):

            measurements.append({
                "type": label,
                "value": match.group(1),
                "unit": (
                    match.group(2)
                    if match.lastindex >= 2
                    else None
                )
            })

    return measurements


# 6. MAIN ENTITY EXTRACTION FUNCTION

def extract_agricultural_entities(text):

    doc = nlp(text)

    entities = {}

    for ent in doc.ents:

        entities.setdefault(ent.label_, [])

        if ent.text not in entities[ent.label_]:

            entities[ent.label_].append(ent.text)

    intent = classify_intent(text)

    measurements = extract_measurements(text)

    return {

        "original_query": text,

        "entities": entities,

        "intent": intent,

        "measurements": measurements

    }


# 7. TESTING

if __name__ == "__main__":

    query = (
        "My wheat crop in Haryana has yellow rust "
        "symptoms and soil pH is 8.2. "
        "What should I do?"
    )

    result = extract_agricultural_entities(query)

    import json

    print(json.dumps(result, indent=4))
