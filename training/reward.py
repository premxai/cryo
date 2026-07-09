"""Reward computation utilities for RLAIF training."""

from dataclasses import dataclass

REWARD_WEIGHTS = {
    "authenticity": 0.40,
    "relevance": 0.30,
    "quality": 0.20,
    "provenance": 0.10,
}


@dataclass
class Trajectory:
    query: str
    doc_id: str
    doc_text: str
    authenticity: float
    relevance: float
    quality: float
    provenance: float
    total: float


def compute_total_reward(
    authenticity: float,
    relevance: float,
    quality: float,
    provenance: float,
) -> float:
    """Weighted sum of 4 reward dimensions."""
    return (
        REWARD_WEIGHTS["authenticity"] * authenticity
        + REWARD_WEIGHTS["relevance"] * relevance
        + REWARD_WEIGHTS["quality"] * quality
        + REWARD_WEIGHTS["provenance"] * provenance
    )


def trajectory_to_pair(traj: Trajectory) -> tuple[str, str, float]:
    """Convert a trajectory to (query_text, doc_text, reward) for PPO."""
    return traj.query, traj.doc_text, traj.total
