"""Simple per-user rate limiting middleware to mitigate spam."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any, Awaitable, Callable, Deque, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery


class RateLimitMiddleware(BaseMiddleware):
    """Enhanced rate limiter with better spam protection.

    This middleware aims to reduce spam and accidental rapid clicks with
    different limits for different types of actions.
    """

    def __init__(
        self, 
        max_messages: int = 5, 
        max_callbacks: int = 3,
        window_seconds: float = 2.0,
        burst_protection: bool = True
    ) -> None:
        super().__init__()
        self.max_messages = max_messages
        self.max_callbacks = max_callbacks
        self.window = window_seconds
        self.burst_protection = burst_protection
        
        # Separate tracking for messages and callbacks
        self._message_events: Dict[int, Deque[float]] = defaultdict(
            lambda: deque(maxlen=max_messages)
        )
        self._callback_events: Dict[int, Deque[float]] = defaultdict(
            lambda: deque(maxlen=max_callbacks)
        )
        
        # Track consecutive violations for escalating penalties
        self._violations: Dict[int, int] = defaultdict(int)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None
        is_callback = False
        
        if isinstance(event, Message):
            user_id = event.from_user.id
            is_callback = False
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            is_callback = True

        if not user_id:
            return await handler(event, data)

        now = time.monotonic()
        
        # Choose appropriate bucket and limit
        if is_callback:
            bucket = self._callback_events[user_id]
            limit = self.max_callbacks
        else:
            bucket = self._message_events[user_id]
            limit = self.max_messages

        # Evict old timestamps
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()

        # Check rate limit
        if len(bucket) >= limit:
            # Escalating penalties
            violations = self._violations[user_id] + 1
            self._violations[user_id] = violations
            
            # Calculate penalty based on violations
            penalty_multiplier = min(violations, 5)  # Cap at 5x
            
            if is_callback:
                message = f"⏱️ Слишком быстро! Подождите {penalty_multiplier} сек."
                try:
                    await event.answer(message, show_alert=violations >= 3)
                except Exception:
                    pass
            else:
                if violations == 1:
                    message = "⏱️ Помедленнее, пожалуйста!"
                elif violations <= 3:
                    message = f"⏱️ Слишком быстро! Пауза {penalty_multiplier} сек."
                else:
                    message = "🚫 Превышен лимит сообщений. Большая пауза!"
                
                try:
                    await event.answer(message)
                except Exception:
                    pass
            
            return None

        # Reset violations on successful request
        if user_id in self._violations:
            self._violations[user_id] = max(0, self._violations[user_id] - 1)
        
        bucket.append(now)
        return await handler(event, data)


def setup_rate_limit_middleware(
    dispatcher, 
    *, 
    max_messages: int = 5, 
    max_callbacks: int = 3,
    window_seconds: float = 2.0
) -> None:
    """Setup enhanced rate limiting middleware with separate limits."""
    limiter = RateLimitMiddleware(
        max_messages=max_messages,
        max_callbacks=max_callbacks, 
        window_seconds=window_seconds
    )
    dispatcher.message.middleware(limiter)
    dispatcher.callback_query.middleware(limiter)


