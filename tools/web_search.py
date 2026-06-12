"""
title: Web Search (DuckDuckGo)
author: local
version: 2.0.0
description: Search the web using DuckDuckGo and return results. Supports time range filtering.
"""

from ddgs import DDGS
from typing import Optional


class Tools:
    def __init__(self):
        pass

    async def search_web(
        self,
        query: str,
        max_results: int = 5,
        timelimit: Optional[str] = None
    ) -> str:
        """
        Search the web using DuckDuckGo and return a summary of results.
        Use this when the user asks about current events, facts, or anything requiring up-to-date information.
        :param query: search query string
        :param max_results: number of results to return (default 5)
        :param timelimit: time range filter - "d" (past day), "w" (past week), "m" (past month), "y" (past year), or None for no limit
        :return: formatted search results with titles, URLs, and snippets
        """
        timelimit_map = {
            "day": "d", "daily": "d", "today": "d", "24h": "d",
            "week": "w", "weekly": "w",
            "month": "m", "monthly": "m",
            "year": "y", "yearly": "y", "annual": "y",
            "今天": "d", "一天": "d",
            "一週": "w", "一周": "w",
            "一個月": "m", "一月": "m",
            "一年": "y",
        }
        if timelimit:
            timelimit = timelimit_map.get(timelimit.lower(), timelimit)

        try:
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results, timelimit=timelimit):
                    title = r.get("title", "")
                    href = r.get("href", "")
                    body = r.get("body", "")
                    results.append(f"**{title}**\n{href}\n{body}")

            if not results:
                return "No results found."

            labels = {"d": "past 24 hours", "w": "past week", "m": "past month", "y": "past year"}
            time_label = labels.get(timelimit, "no time limit")
            header = f"Search: '{query}' | Time range: {time_label} | {len(results)} results\n\n"
            return header + "\n\n---\n\n".join(results)

        except Exception as e:
            return f"Search error: {str(e)}"
