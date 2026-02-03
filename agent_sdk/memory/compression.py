"""
Memory Compression: Summarize old messages to reduce context size.

Implements message summarization and compression strategies to keep conversation
context manageable while preserving important information.
"""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import asyncio


class CompressionStrategy(str, Enum):
    """Strategies for compressing messages."""
    SUMMARIZATION = "summarization"
    CLUSTERING = "clustering"
    IMPORTANCE_SAMPLING = "importance_sampling"
    TOKEN_BUDGET = "token_budget"


@dataclass
class Message:
    """Represents a message in conversation memory."""
    content: str
    role: str  # "user", "assistant", "system"
    message_id: str = ""
    timestamp: float = 0.0
    importance_score: float = 0.5  # 0-1
    token_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def estimate_tokens(self) -> int:
        """Estimate token count (rough approximation)."""
        self.token_count = max(1, len(self.content) // 4)
        return self.token_count


@dataclass
class SummarizedMessage:
    """Represents a summarized group of messages."""
    summary: str
    original_messages: List[str] = field(default_factory=list)
    summary_id: str = ""
    timestamp_start: float = 0.0
    timestamp_end: float = 0.0
    message_count: int = 0
    compression_ratio: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return {
            "type": "summary",
            "summary": self.summary,
            "message_count": self.message_count,
            "compression_ratio": self.compression_ratio,
        }


class CompressionEngine(ABC):
    """Abstract base for compression strategies."""

    @abstractmethod
    async def compress(
        self,
        messages: List[Message],
    ) -> List[Message | SummarizedMessage]:
        """Compress messages."""
        pass


class SummarizationEngine(CompressionEngine):
    """Summarizes messages by creating abstract summaries."""

    def __init__(self, window_size: int = 5):
        """
        Initialize summarization engine.

        Args:
            window_size: Number of messages to summarize together
        """
        self.window_size = window_size

    async def compress(
        self,
        messages: List[Message],
    ) -> List[Message | SummarizedMessage]:
        """Compress messages using summarization."""
        if len(messages) <= self.window_size:
            return messages

        # Keep recent messages, summarize old ones
        recent = messages[-self.window_size:]
        old = messages[:-self.window_size]

        # Group old messages into chunks
        compressed = []
        for i in range(0, len(old), self.window_size):
            chunk = old[i:i + self.window_size]
            summary = await self._create_summary(chunk)
            compressed.append(summary)

        return compressed + recent

    async def _create_summary(
        self,
        messages: List[Message],
    ) -> SummarizedMessage:
        """Create summary of messages."""
        # Simple heuristic summary
        content = " ".join(m.content for m in messages)
        summary_text = f"[Summarized {len(messages)} messages] "
        summary_text += content[:100] + "..."

        original_tokens = sum(m.estimate_tokens() for m in messages)
        summary_tokens = len(summary_text) // 4

        summary = SummarizedMessage(
            summary=summary_text,
            original_messages=[m.content for m in messages],
            message_count=len(messages),
            compression_ratio=(
                1.0 - (summary_tokens / original_tokens)
                if original_tokens > 0 else 0.0
            ),
            timestamp_start=messages[0].timestamp,
            timestamp_end=messages[-1].timestamp,
        )

        return summary


class ImportanceSamplingEngine(CompressionEngine):
    """Keeps only important messages, samples the rest."""

    def __init__(self, importance_threshold: float = 0.6):
        """
        Initialize importance sampling.

        Args:
            importance_threshold: Minimum importance to keep
        """
        self.importance_threshold = importance_threshold

    async def compress(
        self,
        messages: List[Message],
    ) -> List[Message]:
        """Keep important messages, sample others."""
        important = [
            m for m in messages
            if m.importance_score >= self.importance_threshold
        ]

        # Sample lower importance messages
        lower_importance = [
            m for m in messages
            if m.importance_score < self.importance_threshold
        ]

        # Keep 50% of lower importance
        sampled = lower_importance[::2]

        return important + sampled

    async def score_importance(
        self,
        message: Message,
    ) -> float:
        """Score importance of a message."""
        score = 0.5

        # Keywords that increase importance
        keywords = ["important", "critical", "error", "question", "answer"]
        for kw in keywords:
            if kw in message.content.lower():
                score += 0.1

        # User messages slightly more important
        if message.role == "user":
            score += 0.05

        return min(1.0, score)


class TokenBudgetEngine(CompressionEngine):
    """Compress to stay within token budget."""

    def __init__(self, token_budget: int = 4000):
        """
        Initialize token budget compression.

        Args:
            token_budget: Maximum tokens to retain
        """
        self.token_budget = token_budget

    async def compress(
        self,
        messages: List[Message],
    ) -> List[Message | SummarizedMessage]:
        """Compress to stay within token budget."""
        # Estimate total tokens
        total_tokens = sum(m.estimate_tokens() for m in messages)

        if total_tokens <= self.token_budget:
            return messages

        # Keep recent high-value messages
        messages_with_value = [
            (m, self._calculate_value(m))
            for m in messages
        ]

        # Sort by value (keeping recent messages high value)
        sorted_msgs = sorted(
            messages_with_value,
            key=lambda x: x[1],
            reverse=True,
        )

        # Select until budget reached
        selected = []
        current_tokens = 0

        for msg, value in sorted_msgs:
            msg_tokens = msg.estimate_tokens()
            if current_tokens + msg_tokens <= self.token_budget:
                selected.append(msg)
                current_tokens += msg_tokens

        return selected

    def _calculate_value(self, message: Message) -> float:
        """Calculate value of a message for retention."""
        # Recent messages have more value
        # Messages from user have more value
        # Shorter messages have more value (efficiency)

        value = 0.5

        if message.role == "user":
            value += 0.3

        # Shorter is better for token efficiency
        token_count = message.estimate_tokens()
        if token_count < 50:
            value += 0.2

        return min(1.0, value)


class ClusteringEngine(CompressionEngine):
    """Compress by clustering similar messages."""

    def __init__(self, cluster_size: int = 3):
        """
        Initialize clustering compression.

        Args:
            cluster_size: Target cluster size
        """
        self.cluster_size = cluster_size

    async def compress(
        self,
        messages: List[Message],
    ) -> List[Message | SummarizedMessage]:
        """Compress by clustering similar messages."""
        if len(messages) <= self.cluster_size * 2:
            return messages

        # Group messages into clusters
        compressed = []
        for i in range(0, len(messages), self.cluster_size):
            cluster = messages[i:i + self.cluster_size]

            if len(cluster) > 1:
                summary = await self._create_cluster_summary(cluster)
                compressed.append(summary)
            else:
                compressed.append(cluster[0])

        return compressed

    async def _create_cluster_summary(
        self,
        messages: List[Message],
    ) -> SummarizedMessage:
        """Create summary from cluster."""
        summary_text = " ".join(m.content for m in messages)[:100]

        return SummarizedMessage(
            summary=f"[Clustered: {summary_text}...]",
            original_messages=[m.content for m in messages],
            message_count=len(messages),
        )


class MemoryCompressionManager:
    """Manages memory compression with multiple strategies."""

    def __init__(self, strategy: CompressionStrategy = CompressionStrategy.SUMMARIZATION):
        """
        Initialize compression manager.

        Args:
            strategy: Compression strategy to use
        """
        self.strategy = strategy
        self.messages: List[Message] = []
        self.compressed_history: List[SummarizedMessage] = []

        # Create appropriate engine
        if strategy == CompressionStrategy.SUMMARIZATION:
            self.engine = SummarizationEngine()
        elif strategy == CompressionStrategy.IMPORTANCE_SAMPLING:
            self.engine = ImportanceSamplingEngine()
        elif strategy == CompressionStrategy.TOKEN_BUDGET:
            self.engine = TokenBudgetEngine()
        elif strategy == CompressionStrategy.CLUSTERING:
            self.engine = ClusteringEngine()

    async def add_message(self, message: Message) -> None:
        """Add message to memory."""
        message.estimate_tokens()
        self.messages.append(message)

    async def compress_memory(self) -> List[Message | SummarizedMessage]:
        """Compress current memory."""
        if not self.messages:
            return []

        compressed = await self.engine.compress(self.messages.copy())

        # Track summaries
        for item in compressed:
            if isinstance(item, SummarizedMessage):
                self.compressed_history.append(item)

        return compressed

    async def get_compressed_context(self) -> str:
        """Get current memory as compressed context."""
        compressed = await self.compress_memory()

        context_parts = []
        for item in compressed:
            if isinstance(item, SummarizedMessage):
                context_parts.append(item.summary)
            else:
                context_parts.append(item.content)

        return "\n".join(context_parts)

    def get_compression_stats(self) -> Dict[str, Any]:
        """Get compression statistics."""
        if not self.messages:
            return {}

        original_tokens = sum(m.estimate_tokens() for m in self.messages)
        summary_count = len(self.compressed_history)
        avg_compression_ratio = (
            sum(s.compression_ratio for s in self.compressed_history)
            / summary_count
            if summary_count > 0 else 0
        )

        return {
            "original_messages": len(self.messages),
            "summaries_created": summary_count,
            "original_tokens": original_tokens,
            "average_compression_ratio": avg_compression_ratio,
            "strategy": self.strategy.value,
        }

    async def clear(self) -> None:
        """Clear memory."""
        self.messages.clear()
        self.compressed_history.clear()
