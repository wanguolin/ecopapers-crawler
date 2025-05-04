import json
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_OFFICIAL_API_KEY = os.getenv("DEEPSEEK_OFFICIAL_API_KEY")
SILICONFLOW_APIKEY = os.getenv("SILICONFLOW_APIKEY")

print(SILICONFLOW_APIKEY)


def prompts(abstract: str) -> str:
    return f"""
    You are evaluating whether the provided paper abstract describes a quantifiable, implementable, or conceptually backtestable trading strategy. Respond strictly in the structured JSON format below:

    {{
        \"strategy\": true/false,
        \"reason\": \"<Brief explanation of your decision>\"
    }}

    Evaluate using these more inclusive criteria:

    1. **Tradable Strategy Concept**:
       - Accept abstracts that discuss allocation strategies, portfolio construction approaches, or asset relationships that could inform trading decisions.
       - Includes papers on portfolio optimization, dynamic asset allocation, hedging strategies, factor investing concepts, or cross-asset relationships with trading implications.
       - Be inclusive of papers discussing high-level strategies without implementation details.

    2. **Implicit Trading Signals**:
       - Accept abstracts that suggest or imply potential trading actions, even if specific rules aren't detailed.
       - Recognize that academic papers often describe strategies conceptually without explicit entry/exit points.
       - Consider papers discussing portfolio tilts, rebalancing approaches, or asset selection methodologies as having implicit signals.

    3. **Broad Data Acceptance**:
       - Accept papers using or implying standard market data without requiring explicit data specifications.
       - If the strategy could reasonably be implemented with publicly available data, consider this criterion met.

    4. **Conceptual Testability**:
       - Accept papers that present ideas that could theoretically be tested, even without explicit mentions of backtesting.
       - Papers discussing historical relationships or empirical findings should qualify.

    **Decision Rule:**
    - Mark as \"true\" for any abstract that presents ideas that could reasonably inform trading decisions or portfolio construction.
    - Only mark \"false\" for abstracts that are purely theoretical with no practical application, or that focus exclusively on economic/market analysis without any implications for portfolio management.

    ---

    **Example True Cases:**
    - Papers discussing asset allocation strategies (like 60/40), even if only conceptually
    - Papers examining factor performance or market anomalies that could inform security selection
    - Papers on dynamic hedging or correlation structures that could guide portfolio construction
    - Papers discussing optimal portfolio construction methodologies
    - Papers exploring cross-asset relationships with trading implications

    ---
    Abstract:
    {abstract}
    """


def query_siliconflow(prompt, api_key=SILICONFLOW_APIKEY, model="deepseek-chat"):
    """
    Query the SiliconFlow API with a prompt and return the response.
    """
    url = "https://api.siliconflow.com/v1/chat/completions"

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 500,
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()

        # Check if content is wrapped in markdown code block and extract the JSON
        if content.startswith("```json") and content.endswith("```"):
            # Extract the JSON part from the markdown code block
            json_content = content.replace("```json", "", 1)
            json_content = json_content.replace("```", "", 1).strip()
            content = json_content

        try:
            # Try to parse the JSON response
            json_response = json.loads(content)
            # Add model information to the response
            json_response["model"] = model
            return json_response
        except json.JSONDecodeError as e:
            # Handle case where the response isn't valid JSON
            print(f"Error parsing JSON response: {e}")
            print(f"Raw response: {content}")
            # Return a structured error object instead of None
            return {
                "strategy": False,
                "reason": "Failed to parse model response as JSON",
                "model": model,
                "error": "json_decode_error",
                "raw_response": content,
            }

    except Exception as e:
        # Handle any API errors with a structured response
        print(f"Error querying SiliconFlow API: {e}")
        return {
            "strategy": False,
            "reason": f"API error: {str(e)}",
            "model": model,
            "error": "api_error",
        }


def main():
    """
    Process all papers and classify abstracts as strategy papers or not.
    """
    # Load paper details
    paper_details = {}
    with open("paper_details.json", "r") as f:
        paper_details = json.load(f)

    # Set up storage for strategy reviews
    strategy_reviews = {}
    try:
        with open("strategy_reviews.json", "r") as f:
            strategy_reviews = json.load(f)
    except FileNotFoundError:
        print("strategy_reviews.json not found, creating new file.")
    reviewed_papers = set(strategy_reviews.keys())

    print(f"Processing {len(paper_details)} papers...")

    # Process papers
    current_paper = 0
    total_papers = len(paper_details)
    for paper_id, paper_info in paper_details.items():
        # Skip already reviewed papers
        if paper_id in reviewed_papers:
            print(f"Skipping paper {paper_id}: already reviewed")
            current_paper += 1
            continue

        # Get abstract and handle empty/short abstracts
        abstract = paper_info.get("abstract", "")
        if not abstract or len(abstract.strip()) < 50:
            print(f"Skipping paper {paper_id}: abstract too short or empty")
            strategy_reviews[paper_id] = {
                "strategy": False,
                "reason": "Abstract too short or empty",
                "model": "none",
                "error": "empty_abstract",
            }
            continue

        # Process the paper
        print(
            f"Processing paper {current_paper} of {total_papers}: Abstract:{abstract[:150]}... ..."
        )

        # Query the model
        response = query_siliconflow(
            prompts(abstract), model="Pro/deepseek-ai/DeepSeek-V3"
        )

        print(f"\n\nResponse: {response}\n\n")
        current_paper += 1

        # Store the result (response is already a parsed object)
        strategy_reviews[paper_id] = response

        # Periodically save results
        if current_paper % 5 == 0:
            with open("strategy_reviews.json", "w") as f:
                json.dump(strategy_reviews, f, indent=2)

    # Save final results
    with open("strategy_reviews.json", "w") as f:
        json.dump(strategy_reviews, f, indent=2)

    # Show summary statistics
    strategy_count = sum(
        1 for result in strategy_reviews.values() if result.get("strategy", False)
    )
    print(
        f"Found {strategy_count} strategy papers out of {len(strategy_reviews)} processed papers."
    )


if __name__ == "__main__":
    main()
