"""
Order Queue System - Async order processing with background execution.

This module provides:
- QueuedOrder: Data class for queued order items
- OrderQueue: In-memory queue with status tracking
- OrderProcessor: Background worker that processes orders

Usage:
    from mapmover.order_queue import order_queue, processor

    # Queue an order
    queue_id = order_queue.add(order_items, session_id="sess_123")

    # Check status
    status = order_queue.get_status(queue_id)

    # Start processor (called from app startup)
    await processor.start()
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """Status states for queued orders."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class QueuedOrder:
    """A single queued order with status tracking."""
    queue_id: str
    session_id: str
    items: List[Dict]
    hints: Dict

    status: OrderStatus = OrderStatus.PENDING
    progress: float = 0.0  # 0.0 to 1.0
    message: str = "Queued"
    position: int = 0

    result: Optional[Dict] = None
    error: Optional[str] = None

    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # For deduplication
    data_signature: str = ""

    def __post_init__(self):
        """Compute data signature for deduplication."""
        if not self.data_signature:
            self.data_signature = self._compute_signature()

    def _compute_signature(self) -> str:
        """Create hash signature for deduplication."""
        normalized = {
            "session_id": self.session_id,
            "items": sorted([
                {
                    "source_id": item.get("source_id"),
                    "metric": item.get("metric"),
                    "region": item.get("region"),
                    "year": item.get("year"),
                    "year_start": item.get("year_start"),
                    "year_end": item.get("year_end"),
                }
                for item in self.items
            ], key=lambda x: json.dumps(x, sort_keys=True))
        }
        return hashlib.md5(json.dumps(normalized, sort_keys=True).encode()).hexdigest()[:12]

    def to_status_dict(self) -> Dict:
        """Return status info for frontend polling."""
        return {
            "queue_id": self.queue_id,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "position": self.position,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            # Only include result when complete
            "result": self.result if self.status == OrderStatus.COMPLETE else None,
        }


class OrderQueue:
    """
    In-memory order queue with status tracking.

    Features:
    - FIFO processing
    - Deduplication (same data request returns existing queue_id)
    - Auto-cleanup of old orders
    - Position tracking
    - Session-based filtering
    """

    # Configuration
    MAX_PENDING_PER_SESSION = 10
    MAX_AGE_MINUTES = 10
    CLEANUP_INTERVAL_SECONDS = 60

    def __init__(self):
        self.orders: Dict[str, QueuedOrder] = {}
        self.processing_lock = asyncio.Lock()
        self._last_cleanup = datetime.now()

    def add(
        self,
        items: List[Dict],
        hints: Dict,
        session_id: str = "default"
    ) -> str:
        """
        Add order to queue.

        Args:
            items: Validated order items from postprocessor
            hints: Preprocessor hints for context
            session_id: Session identifier for grouping

        Returns:
            queue_id for status polling
        """
        # Check session limit
        session_pending = [
            o for o in self.orders.values()
            if o.session_id == session_id and o.status == OrderStatus.PENDING
        ]
        if len(session_pending) >= self.MAX_PENDING_PER_SESSION:
            # Cancel oldest pending order from this session
            oldest = min(session_pending, key=lambda o: o.created_at)
            self.cancel(oldest.queue_id)
            logger.info(f"Auto-cancelled oldest order {oldest.queue_id} for session {session_id}")

        # Create order
        queue_id = f"q_{uuid.uuid4().hex[:8]}"
        order = QueuedOrder(
            queue_id=queue_id,
            session_id=session_id,
            items=items,
            hints=hints,
        )

        # Check for duplicate (same data signature)
        for existing in self.orders.values():
            if (existing.data_signature == order.data_signature and
                existing.status in [OrderStatus.PENDING, OrderStatus.EXECUTING]):
                logger.info(f"Deduplicating: {queue_id} -> {existing.queue_id}")
                return existing.queue_id

        # Add to queue
        self.orders[queue_id] = order
        self._update_positions()

        logger.info(f"Queued order {queue_id} with {len(items)} items (position {order.position})")
        return queue_id

    def get(self, queue_id: str) -> Optional[QueuedOrder]:
        """Get order by queue_id."""
        return self.orders.get(queue_id)

    def get_status(self, queue_id: str) -> Optional[Dict]:
        """Get status dict for frontend polling."""
        order = self.orders.get(queue_id)
        if order:
            return order.to_status_dict()
        return None

    def belongs_to_session(self, queue_id: str, session_id: str) -> bool:
        """Check whether a queue entry belongs to the caller session."""
        order = self.orders.get(queue_id)
        if not order:
            return False
        return order.session_id == session_id

    def get_pending(self) -> List[QueuedOrder]:
        """Get all pending orders in queue order."""
        pending = [o for o in self.orders.values() if o.status == OrderStatus.PENDING]
        return sorted(pending, key=lambda o: o.created_at)

    def get_session_orders(self, session_id: str) -> List[Dict]:
        """Get all orders for a session."""
        session_orders = [
            o for o in self.orders.values()
            if o.session_id == session_id
        ]
        return [o.to_status_dict() for o in sorted(session_orders, key=lambda o: o.created_at)]

    def update_status(
        self,
        queue_id: str,
        status: OrderStatus,
        progress: float = None,
        message: str = None,
        result: Dict = None,
        error: str = None
    ):
        """Update order status."""
        order = self.orders.get(queue_id)
        if not order:
            return

        order.status = status
        if progress is not None:
            order.progress = progress
        if message is not None:
            order.message = message
        if result is not None:
            order.result = result
        if error is not None:
            order.error = error

        # Track timestamps
        if status == OrderStatus.EXECUTING and order.started_at is None:
            order.started_at = datetime.now()
        elif status in [OrderStatus.COMPLETE, OrderStatus.FAILED, OrderStatus.CANCELLED]:
            order.completed_at = datetime.now()

        # Update positions after status change
        self._update_positions()

    def cancel(self, queue_id: str) -> bool:
        """Cancel a pending order."""
        order = self.orders.get(queue_id)
        if order and order.status == OrderStatus.PENDING:
            self.update_status(
                queue_id,
                OrderStatus.CANCELLED,
                message="Cancelled by user"
            )
            return True
        return False

    def _update_positions(self):
        """Update position numbers for pending orders."""
        pending = self.get_pending()
        for i, order in enumerate(pending):
            order.position = i + 1
            order.message = f"Queued (position {order.position})" if order.position > 1 else "Next up"

    def cleanup_old(self):
        """Remove old completed/failed orders."""
        now = datetime.now()
        if (now - self._last_cleanup).total_seconds() < self.CLEANUP_INTERVAL_SECONDS:
            return

        self._last_cleanup = now
        cutoff = now - timedelta(minutes=self.MAX_AGE_MINUTES)

        to_remove = []
        for queue_id, order in self.orders.items():
            if order.status in [OrderStatus.COMPLETE, OrderStatus.FAILED, OrderStatus.CANCELLED]:
                if order.completed_at and order.completed_at < cutoff:
                    to_remove.append(queue_id)
            elif order.status == OrderStatus.PENDING:
                # Also remove very old pending orders
                if order.created_at < cutoff:
                    to_remove.append(queue_id)

        for queue_id in to_remove:
            del self.orders[queue_id]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old orders")

    def stats(self) -> Dict:
        """Get queue statistics."""
        by_status = {}
        for order in self.orders.values():
            status = order.status.value
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "total": len(self.orders),
            "by_status": by_status,
            "pending_count": len(self.get_pending()),
        }


class OrderProcessor:
    """
    Background worker that processes queued orders.

    Runs as an async task, polling the queue and executing orders.
    """

    POLL_INTERVAL = 0.5  # seconds between queue checks

    def __init__(self, queue: OrderQueue):
        self.queue = queue
        self.running = False
        self.current_order: Optional[QueuedOrder] = None
        self._execute_fn: Optional[Callable] = None
        self._task: Optional[asyncio.Task] = None

    def set_executor(self, execute_fn: Callable):
        """
        Set the function to execute orders.

        Args:
            execute_fn: Async function that takes (items, hints) and returns result dict
        """
        self._execute_fn = execute_fn

    async def start(self):
        """Start the background processing loop."""
        if self.running:
            logger.warning("OrderProcessor already running")
            return

        if not self._execute_fn:
            raise RuntimeError("No executor function set. Call set_executor() first.")

        self.running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("OrderProcessor started")

    async def stop(self):
        """Stop the processor gracefully."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("OrderProcessor stopped")

    async def _process_loop(self):
        """Main processing loop."""
        while self.running:
            try:
                # Cleanup old orders periodically
                self.queue.cleanup_old()

                # Process next order
                await self._process_next()

                # Brief pause between iterations
                await asyncio.sleep(self.POLL_INTERVAL)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in process loop: {e}", exc_info=True)
                await asyncio.sleep(1)  # Back off on error

    async def _process_next(self):
        """Process the next pending order."""
        pending = self.queue.get_pending()
        if not pending:
            return

        # Get oldest pending
        order = pending[0]

        async with self.queue.processing_lock:
            self.current_order = order

            try:
                # Update to executing
                self.queue.update_status(
                    order.queue_id,
                    OrderStatus.EXECUTING,
                    progress=0.1,
                    message="Starting execution..."
                )

                # Execute the order
                logger.info(f"Executing order {order.queue_id}")
                result = await self._execute_with_progress(order)

                # Mark complete
                self.queue.update_status(
                    order.queue_id,
                    OrderStatus.COMPLETE,
                    progress=1.0,
                    message="Complete",
                    result=result
                )
                logger.info(f"Completed order {order.queue_id}")

            except Exception as e:
                logger.error(f"Order {order.queue_id} failed: {e}", exc_info=True)
                self.queue.update_status(
                    order.queue_id,
                    OrderStatus.FAILED,
                    message=f"Failed: {str(e)[:100]}",
                    error=str(e)
                )

            finally:
                self.current_order = None

    async def _execute_with_progress(self, order: QueuedOrder) -> Dict:
        """Execute order with progress updates."""
        # Update progress as we go
        self.queue.update_status(
            order.queue_id,
            OrderStatus.EXECUTING,
            progress=0.2,
            message="Loading data..."
        )

        # Call the executor function
        result = await self._execute_fn(order.items, order.hints)

        self.queue.update_status(
            order.queue_id,
            OrderStatus.EXECUTING,
            progress=0.9,
            message="Finalizing..."
        )

        return result

    def is_processing(self, queue_id: str) -> bool:
        """Check if a specific order is currently being processed."""
        return self.current_order and self.current_order.queue_id == queue_id


# Global instances
order_queue = OrderQueue()
processor = OrderProcessor(order_queue)
