"""Seed a small LangSmith eval dataset of representative questions.
Run once: uv run python evals/dataset.py"""
from langsmith import Client

DATASET = "fantasy-gm-hero-questions"
EXAMPLES = [
    {"question": "Who should I pick up this week?", "type": "waiver"},
    {"question": "Should I trade my Haliburton for their Sabonis?", "type": "trade"},
    {"question": "Any buy-low candidates on the wire?", "type": "waiver"},
    {"question": "Who's streaming well against this week's schedule?", "type": "waiver"},
    {"question": "Is it worth dropping my bench big for a two-game guard?", "type": "waiver"},
    {"question": "Should I start my rookie over my vet tonight?", "type": "start-sit"},
    {"question": "Who has the tougher back-to-back this week?", "type": "start-sit"},
    {"question": "Would you offer my Porzingis for their Sabonis and a bench piece?",
     "type": "trade"},
    {"question": "Is my star's season trending up or down?", "type": "trends"},
    {"question": "Which of my players is heating up the most lately?", "type": "trends"},
    {"question": "Should I sell high on a player who's been on a hot streak?", "type": "trade"},
    {"question": "Who on the wire has the most games this week?", "type": "waiver"},
    {"question": "Is my point guard in a slump worth benching?", "type": "start-sit"},
    {"question": "What's the value gap in this three-team trade?", "type": "trade"},
    {"question": "Which of my injured players is trending back to form?", "type": "trends"},
    {"question": "Who should I stream at center this week?", "type": "waiver"},
    {"question": "Should I bench my studs during their team's back-to-back?", "type": "start-sit"},
    {"question": "Does this trade help my category weaknesses long-term?", "type": "trade"},
    {"question": "Which free agent has the best recent form?", "type": "trends"},
    {"question": "How many games does my team play this week overall?", "type": "waiver"},
]

if __name__ == "__main__":
    client = Client()
    ds = client.create_dataset(DATASET)
    for ex in EXAMPLES:
        client.create_example(inputs={"question": ex["question"]},
                              metadata={"type": ex["type"]}, dataset_id=ds.id)
    print(f"seeded {len(EXAMPLES)} examples into {DATASET}")
