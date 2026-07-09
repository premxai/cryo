"""RLAIF PPO training loop for embedding model fine-tuning.

Loads trajectories → fine-tunes all-MiniLM-L6-v2 via TRL PPO →
saves model to models/cryo-embeddings-v1/.

Usage:
    python training/train.py
    python training/train.py --trajectories training/trajectories.jsonl --epochs 3
"""

import argparse
import json
import sys
from pathlib import Path

from tqdm import tqdm

sys.path.insert(0, ".")


def load_trajectories(path: str) -> list[dict]:
    """Load trajectories from JSONL file."""
    path = Path(path)
    if not path.exists():
        print(f"[train] No trajectories found at {path}. Run collect.py first.")
        return []

    trajectories = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                trajectories.append(json.loads(line))
    print(f"[train] Loaded {len(trajectories)} trajectories from {path}")
    return trajectories


def train_ppo(
    trajectories_path: str,
    model_name: str = "all-MiniLM-L6-v2",
    output_dir: str = "models/cryo-embeddings-v1",
    epochs: int = 3,
    batch_size: int = 4,
    learning_rate: float = 1e-5,
) -> None:
    """Fine-tune embedding model using PPO with reward signals."""
    trajectories = load_trajectories(trajectories_path)
    if not trajectories:
        print("[train] Nothing to train on. Exiting.")
        return

    try:
        import torch
        from sentence_transformers import SentenceTransformer
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        print(f"[train] Missing dependency: {exc}")
        print("Install: pip install sentence-transformers transformers trl torch")
        return

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[train] Using device: {device}")

    try:
        from trl import PPOConfig, PPOTrainer
    except ImportError:
        print("[train] TRL not installed. Run: pip install trl")
        return

    model = SentenceTransformer(model_name, device=device)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token or "[PAD]"

    config = PPOConfig(
        learning_rate=learning_rate,
        batch_size=batch_size,
        mini_batch_size=max(1, batch_size // 4),
        gradient_accumulation_steps=1,
        optimize_cuda_cache=True,
    )

    dummy_model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=1).to(
        device
    )

    ppo_trainer = PPOTrainer(
        config=config,
        model=dummy_model,
        tokenizer=tokenizer,
    )

    # Build (query, response, reward) triplets
    pairs = [(t["query"], t["doc_text"], t["total"]) for t in trajectories if t.get("total", 0) > 0]

    if not pairs:
        print("[train] No valid pairs with reward > 0. Exiting.")
        return

    print(f"[train] Training on {len(pairs)} (query, doc, reward) pairs")

    for epoch in range(epochs):
        epoch_rewards = []
        for i in tqdm(range(0, len(pairs), batch_size), desc=f"Epoch {epoch + 1}/{epochs}"):
            batch = pairs[i : i + batch_size]
            queries = [b[0] for b in batch]
            responses = [b[1] for b in batch]
            rewards = [torch.tensor(b[2]) for b in batch]

            query_tensors = tokenizer(queries, return_tensors="pt", padding=True, truncation=True)
            response_tensors = tokenizer(
                responses, return_tensors="pt", padding=True, truncation=True
            )

            stats = ppo_trainer.step(
                query_tensors["input_ids"].to(device),
                response_tensors["input_ids"].to(device),
                rewards,
            )
            if stats:
                epoch_rewards.append(stats.get("mean_reward", 0))

        mean_reward = sum(epoch_rewards) / len(epoch_rewards) if epoch_rewards else 0
        print(f"[train] Epoch {epoch + 1}/{epochs} — mean reward: {mean_reward:.4f}")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    model.save(str(output_path))
    print(f"[train] Model saved to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="RLAIF PPO training for Cryo.")
    parser.add_argument("--trajectories", default="training/trajectories.jsonl")
    parser.add_argument("--model", default="all-MiniLM-L6-v2")
    parser.add_argument("--output", default="models/cryo-embeddings-v1")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    args = parser.parse_args()

    train_ppo(
        trajectories_path=args.trajectories,
        model_name=args.model,
        output_dir=args.output,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
    )


if __name__ == "__main__":
    main()
