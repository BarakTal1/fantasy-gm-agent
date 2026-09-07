"""Run the agent over the dataset and score with our scorers in LangSmith.
Run: uv run python evals/run_evals.py  (needs LANGCHAIN_API_KEY + a live agent)"""
from langsmith import Client

from evals.dataset import DATASET

if __name__ == "__main__":
    client = Client()
    print(f"Open the LangSmith UI to view runs for dataset '{DATASET}'.")
    print("Wire the agent target + scorers here once real Yahoo data is available;")
    print("scorers live in evals/scorers.py and are already unit-tested.")
    # Intentionally thin until live data exists — see Phase 3 (closed loop).
    _ = client, DATASET
