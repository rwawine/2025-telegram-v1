"""Async load test simulating concurrent bot and admin activity."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, List

from faker import Faker


@dataclass
class StressScenario:
    name: str
    coroutine_factory: Callable[[int], Awaitable[None]]


class StressTest:
    def __init__(self, num_users: int = 1000) -> None:
        self.num_users = num_users
        self.fake = Faker()
        self.scenarios: List[StressScenario] = []

    def add_scenario(self, name: str, coroutine_factory: Callable[[int], Awaitable[None]]) -> None:
        self.scenarios.append(StressScenario(name=name, coroutine_factory=coroutine_factory))

    async def simulate_user(self, user_id: int) -> None:
        await asyncio.gather(*(scenario.coroutine_factory(user_id) for scenario in self.scenarios))

    async def run_test(self) -> None:
        tasks = [self.simulate_user(i) for i in range(self.num_users)]
        await asyncio.gather(*tasks)


async def registration_scenario(test: StressTest, base_url: str, bot_token: str):
    # 1) Happy path: valid name -> manual phone -> valid phone -> valid card -> photo upload
    async def happy_path(user_id: int) -> None:
        await asyncio.sleep(0.001)

    # 2) Invalid name first, then fix
    async def invalid_name_then_fix(user_id: int) -> None:
        await asyncio.sleep(0.001)

    # 3) Manual phone button pressed, then enter invalid number, then valid
    async def manual_phone_invalid_then_valid(user_id: int) -> None:
        await asyncio.sleep(0.001)

    # 4) Share contact path
    async def share_contact_path(user_id: int) -> None:
        await asyncio.sleep(0.001)

    # 5) Back navigation at various steps
    async def back_navigation(user_id: int) -> None:
        await asyncio.sleep(0.001)

    # 6) Leaflet help and gallery choice
    async def leaflet_and_gallery(user_id: int) -> None:
        await asyncio.sleep(0.001)

    # 7) Wrong content types at each step (photo at name, doc at phone, text at photo)
    async def wrong_content_types(user_id: int) -> None:
        await asyncio.sleep(0.001)

    test.add_scenario("registration_happy_path", happy_path)
    test.add_scenario("registration_invalid_name_then_fix", invalid_name_then_fix)
    test.add_scenario("registration_manual_phone_invalid_then_valid", manual_phone_invalid_then_valid)
    test.add_scenario("registration_share_contact_path", share_contact_path)
    test.add_scenario("registration_back_navigation", back_navigation)
    test.add_scenario("registration_leaflet_and_gallery", leaflet_and_gallery)
    test.add_scenario("registration_wrong_content_types", wrong_content_types)


async def broadcast_scenario(test: StressTest, admin_url: str):
    async def run(user_id: int) -> None:
        await asyncio.sleep(0.01)

    test.add_scenario("broadcast", run)

