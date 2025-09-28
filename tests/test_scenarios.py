"""Collection of stress test scenarios per acceptance criteria."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable, Dict

from tests.stress_test import StressTest, registration_scenario, broadcast_scenario


@dataclass
class ScenarioDefinition:
    name: str
    setup: Callable[[StressTest], None]


def create_default_scenarios() -> Dict[str, ScenarioDefinition]:
    scenarios = {}

    async def registration_setup(test: StressTest):
        await registration_scenario(test, base_url="http://localhost:5000", bot_token="TEST")

    async def broadcast_setup(test: StressTest):
        await broadcast_scenario(test, admin_url="http://localhost:5000/broadcasts")

    scenarios["registration"] = ScenarioDefinition(
        name="registration",
        setup=lambda test: asyncio.create_task(registration_setup(test)),
    )
    scenarios["broadcast"] = ScenarioDefinition(
        name="broadcast",
        setup=lambda test: asyncio.create_task(broadcast_setup(test)),
    )
    return scenarios

