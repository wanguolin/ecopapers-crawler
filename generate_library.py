import json
import os


def extract_keywords(keywords_data):
    """
    Extract keywords from various possible structures into a simple array of terms.
    """
    # Handle empty string case
    if keywords_data == "":
        return []

    # Handle dictionary-structured keywords where each item has a 'term' field
    if isinstance(keywords_data, list):
        terms = []
        for item in keywords_data:
            if isinstance(item, dict) and "term" in item:
                terms.append(item["term"])
            elif isinstance(item, str):
                terms.append(item)
        return terms

    # Handle other nested structures (not expected based on sample)
    if isinstance(keywords_data, dict) and "term" in keywords_data:
        term_data = keywords_data["term"]
        terms = []

        if isinstance(term_data, list):
            for item in term_data:
                if isinstance(item, str):
                    terms.append(item)
                elif isinstance(item, dict) and "content" in item:
                    terms.append(item["content"])
        elif isinstance(term_data, str):
            terms.append(term_data)
        elif isinstance(term_data, dict) and "content" in term_data:
            terms.append(term_data["content"])

        return terms

    # Default case: return as-is or empty list
    return keywords_data if isinstance(keywords_data, list) else []


library = []

with open("strategy_reviews.json", "r") as f:
    strategy_reviews = json.load(f)

with open("paper_details.json", "r") as f:
    paper_details = json.load(f)

for paper_id, details in paper_details.items():
    if paper_id in strategy_reviews and strategy_reviews[paper_id]["strategy"]:
        # Extract keywords from the top level of details
        keywords = extract_keywords(details.get("keywords", []))

        library.append(
            {
                "title": details.get("parsed_title", "n/a"),
                "abstract": details.get("abstract", "n/a"),
                "keywords": keywords,
                "eco_link": paper_id,
                "reviewed_by": strategy_reviews[paper_id]["model"],
            }
        )

with open("library.json", "w") as f:
    json.dump(library, f, indent=4)
