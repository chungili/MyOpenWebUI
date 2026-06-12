"""
title: System Info
author: local
version: 1.0.0
description: Get current date, time, and system status.
"""

from datetime import datetime
from zoneinfo import ZoneInfo


class Tools:
    def __init__(self):
        pass

    async def get_current_datetime(self) -> str:
        """
        Get the current date and time from the system clock (Asia/Taipei timezone).
        Use this when the user asks about today's date, current time, or what day it is.
        :return: current date and time string
        """
        now = datetime.now(ZoneInfo("Asia/Taipei"))
        return now.strftime("Today is %A, %Y-%m-%d. Current time: %H:%M:%S (Asia/Taipei)")
