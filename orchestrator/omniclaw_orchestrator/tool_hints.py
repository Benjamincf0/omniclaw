from __future__ import annotations

from collections.abc import Iterable


def _base_tool_name(name: str) -> str:
    if "__" not in name:
        return name
    return name.split("__", 1)[1]


_TOOL_DESCRIPTION_HINTS: dict[str, str] = {
    "get_mio": (
        "Use this for inbox-style requests. If the user asks for a specific message's full"
        " contents, call this first to get message links, then call get_mio_item(link)."
    ),
    "get_mio_item": (
        "Requires a message link returned by get_mio. Use this as the follow-up step after"
        " listing MIOs."
    ),
    "get_news": (
        "Use this for the latest news list. If the user asks for the full contents of one"
        " news item, call this first to get its link, then call get_news_item(link)."
    ),
    "get_news_item": (
        "Requires a news link returned by get_news. Use this as the follow-up step after"
        " listing news items."
    ),
    "get_lea_classes": (
        "Use this first to discover per-class section URLs. The response contains"
        " classes[].sections[] entries with titles and URLs for follow-up pages like"
        " assignments, documents, grades, and announcements. For requests across classes,"
        " start here and fan out from the returned section URLs."
    ),
    "get_lea_documents": (
        "Requires a class section URL returned by get_lea_classes. Find the section for"
        " documents/videos in a class, then call this tool with that URL."
    ),
    "get_lea_assignments": (
        "Requires a class section URL returned by get_lea_classes. For requests like"
        " 'all my assignments', first call get_lea_classes, then call this tool for each"
        " relevant class section URL."
    ),
    "get_lea_assignment_content": (
        "Requires an assignment detail URL returned by get_lea_assignments, usually from"
        " the assignment's instruction_url field."
    ),
    "get_lea_grades": (
        "Requires a class section URL returned by get_lea_classes. For grade requests,"
        " first discover the class sections, then call this tool for the relevant class"
        " or classes."
    ),
    "get_lea_announcement": (
        "Requires an announcement URL returned by get_lea_classes, usually from a class"
        " section's announcements list."
    ),
}


def augment_tool_description(name: str, description: str) -> str:
    base_name = _base_tool_name(name)
    hint = _TOOL_DESCRIPTION_HINTS.get(base_name)
    if not hint:
        return description

    normalized = description.strip().rstrip(".")
    return f"{normalized}. {hint}"


def build_orchestration_system_prompt(tool_names: Iterable[str]) -> str:
    names = list(tool_names)
    if not names:
        return ""

    by_base = {_base_tool_name(name): name for name in names}
    lines = [
        "Tool-use policy:",
        "- Infer and execute prerequisite tool calls yourself when a request needs multiple steps.",
        "- Do not ask the user which intermediate tool to call when the next step can be discovered from a previous tool result.",
        "- If one tool returns links, ids, or URLs for another tool, continue the workflow automatically.",
        "- When the user asks for all items across classes or pages, fan out across the relevant follow-up URLs and then synthesize the result.",
        "- When several follow-up tool calls are independent, prefer issuing them together in the same assistant turn.",
    ]

    if "get_mio" in by_base and "get_mio_item" in by_base:
        lines.append(
            f"- MIO workflow: call {by_base['get_mio']} first, then use links from its results"
            f" with {by_base['get_mio_item']} when the user wants full message contents."
        )

    if "get_news" in by_base and "get_news_item" in by_base:
        lines.append(
            f"- News workflow: call {by_base['get_news']} first, then use returned links with"
            f" {by_base['get_news_item']} for full articles."
        )

    if "get_lea_classes" in by_base:
        lea_classes = by_base["get_lea_classes"]
        if "get_lea_assignments" in by_base:
            lines.append(
                f"- LEA assignments workflow: call {lea_classes} first. Its"
                " classes[].sections[] results contain the section URLs you need. Then call"
                f" {by_base['get_lea_assignments']} for each relevant class section. For"
                " 'all my assignments', do not stop after listing classes; continue through"
                " the assignment pages automatically."
            )
        if "get_lea_documents" in by_base:
            lines.append(
                f"- LEA documents workflow: call {lea_classes} first, then use the relevant"
                f" section URLs with {by_base['get_lea_documents']}."
            )
        if "get_lea_grades" in by_base:
            lines.append(
                f"- LEA grades workflow: call {lea_classes} first, then use the relevant"
                f" section URLs with {by_base['get_lea_grades']}."
            )
        if "get_lea_announcement" in by_base:
            lines.append(
                f"- LEA announcement workflow: call {lea_classes} first, then use"
                " announcement URLs from the class results with"
                f" {by_base['get_lea_announcement']}."
            )

    if "get_lea_assignments" in by_base and "get_lea_assignment_content" in by_base:
        lines.append(
            f"- LEA assignment detail workflow: use assignment URLs returned by"
            f" {by_base['get_lea_assignments']} with"
            f" {by_base['get_lea_assignment_content']} when the user wants the full"
            " instructions or submission details for a specific assignment."
        )

    return "\n".join(lines)
