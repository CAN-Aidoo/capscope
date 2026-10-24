"""
capscope.profiles
=================

ToolProfile tables for the four AgentDojo v1.2 suites (agentdojo 0.1.35).

Authoring rule (frozen before any evaluation, see PROTOCOL.md):
  * Written from the tool NAMES and DOCSTRINGS only. No user-task or injection-task
    prompt was consulted (one banking user prompt was seen once while checking that
    ground-truth calls exist; it was not used to choose keywords).
  * Categories are capability classes; every tool in a matched category is allowed.
  * Read/search tools are sensitivity 1 and default-allowed.
  * For tools with sensitivity >= 2, keywords are VERBS naming the action (send, pay,
    delete, ...), never the object noun (email, money, file), because object nouns
    also appear in purely read-only requests ("summarise my emails").

Two variants are evaluated:
  MANUAL: the hand-written keyword lists below.
  AUTO:   keywords derived mechanically from the tool name and the first docstring
          sentence, minus a fixed stop-list (see `auto_profiles`). Categories and
          sensitivities are identical to MANUAL; only the keywords differ.
"""

from __future__ import annotations

import re

from capscope.manifest import ToolProfile

R = "read"  # default-allowed, sensitivity 1

SEND_VERBS = ("send", "reply", "forward", "compose", "notify", "inform", "tell", "write")

MANUAL: dict[str, list[ToolProfile]] = {
    "workspace": [
        ToolProfile("send_email", "email_send", SEND_VERBS, 3),
        ToolProfile("delete_email", "email_delete", ("delete", "remove", "trash", "erase"), 3),
        *[ToolProfile(n, R, (), 1) for n in (
            "get_unread_emails", "get_sent_emails", "get_received_emails", "get_draft_emails",
            "search_emails", "search_contacts_by_name", "search_contacts_by_email", "get_current_day",
            "search_calendar_events", "get_day_calendar_events", "search_files_by_filename",
            "get_file_by_id", "list_files", "search_files")],
        ToolProfile("create_calendar_event", "calendar_write",
                    ("create", "schedule", "book", "organize", "arrange", "add", "set"), 2),
        ToolProfile("reschedule_calendar_event", "calendar_write",
                    ("reschedule", "move", "postpone", "change", "shift"), 2),
        ToolProfile("add_calendar_event_participants", "calendar_write", ("add", "invite", "include"), 2),
        ToolProfile("cancel_calendar_event", "calendar_cancel", ("cancel", "delete", "remove"), 3),
        ToolProfile("append_to_file", "file_write", ("append", "add", "write", "update", "edit"), 2),
        ToolProfile("create_file", "file_write", ("create", "write", "save", "make", "draft"), 2),
        ToolProfile("delete_file", "file_delete", ("delete", "remove", "erase", "trash"), 3),
        ToolProfile("share_file", "file_share", ("share", "grant", "give"), 3),
    ],
    "travel": [
        ToolProfile("get_user_information", "pii_read", ("personal", "profile", "passport", "information"), 2),
        *[ToolProfile(n, R, (), 1) for n in (
            "get_all_hotels_in_city", "get_hotels_prices", "get_rating_reviews_for_hotels", "get_hotels_address",
            "get_all_restaurants_in_city", "get_cuisine_type_for_restaurants", "get_restaurants_address",
            "get_rating_reviews_for_restaurants", "get_dietary_restrictions_for_all_restaurants",
            "get_contact_information_for_restaurants", "get_price_for_restaurants",
            "check_restaurant_opening_hours", "get_all_car_rental_companies_in_city", "get_car_types_available",
            "get_rating_reviews_for_car_rental", "get_car_fuel_options", "get_car_rental_address",
            "get_car_price_per_day", "search_calendar_events", "get_day_calendar_events",
            "get_flight_information")],
        ToolProfile("create_calendar_event", "calendar_write",
                    ("create", "schedule", "add", "remind", "organize", "arrange"), 2),
        ToolProfile("cancel_calendar_event", "calendar_cancel", ("cancel", "delete", "remove"), 3),
        ToolProfile("reserve_hotel", "reservation", ("reserve", "book"), 3),
        ToolProfile("reserve_car_rental", "reservation", ("reserve", "book", "rent"), 3),
        ToolProfile("reserve_restaurant", "reservation", ("reserve", "book"), 3),
        ToolProfile("send_email", "email_send", SEND_VERBS, 3),
    ],
    "banking": [
        *[ToolProfile(n, R, (), 1) for n in (
            "get_iban", "get_balance", "get_most_recent_transactions", "get_scheduled_transactions",
            "read_file")],
        ToolProfile("get_user_info", "pii_read", ("personal", "profile", "information"), 2),
        ToolProfile("send_money", "money_out", ("send", "pay", "transfer", "refund", "wire"), 3),
        ToolProfile("schedule_transaction", "money_out", ("schedule", "pay", "transfer", "set"), 3),
        ToolProfile("update_scheduled_transaction", "money_out",
                    ("update", "change", "modify", "adjust", "edit", "correct", "fix"), 3),
        ToolProfile("update_password", "account_write", ("reset", "change", "update"), 3),
        ToolProfile("update_user_info", "account_write", ("update", "change", "modify", "edit", "correct"), 3),
    ],
    "slack": [
        *[ToolProfile(n, R, (), 1) for n in (
            "get_channels", "read_channel_messages", "read_inbox", "get_users_in_channel")],
        ToolProfile("get_webpage", "web_fetch",
                    ("visit", "browse", "fetch", "website", "webpage", "url", "www",
                     "http", "https", "link"), 2),
        ToolProfile("send_direct_message", "message_send", SEND_VERBS + ("post", "announce", "dm"), 3),
        ToolProfile("send_channel_message", "message_send", SEND_VERBS + ("post", "announce", "dm"), 3),
        ToolProfile("add_user_to_channel", "membership_add", ("add", "invite", "join"), 3),
        ToolProfile("invite_user_to_slack", "membership_add", ("invite", "add", "onboard"), 3),
        ToolProfile("remove_user_from_slack", "membership_remove", ("remove", "kick", "delete"), 3),
        ToolProfile("post_webpage", "web_post", ("post", "publish", "upload"), 3),
    ],
}

# Frozen stop-list for the AUTO variant: generic words in tool names/docstrings that
# carry no capability signal.
STOP = set("""
a an the of to for in on at by with from and or is are be it its this that given
get gets return returns returned list all new current user users provided details detail
dictionary dictionaries information info id ids e g ie could within should which each
""".split())

_W = re.compile(r"[A-Za-z]+")


def _auto_keywords(name: str, doc: str) -> tuple[str, ...]:
    first = re.split(r"(?<=[.!?])\s", (doc or "").strip())[0]
    words = name.split("_") + _W.findall(first)
    out = []
    for w in words:
        w = w.lower()
        if len(w) > 2 and w not in STOP and w not in out:
            out.append(w)
    return tuple(out)


def auto_profiles(suite_name: str, suite) -> list[ToolProfile]:
    """AUTO variant: same categories/sensitivities as MANUAL, keywords derived
    mechanically from each tool's name and first docstring sentence."""
    docs = {t.name: (t.description or "") for t in suite.tools}
    return [ToolProfile(p.name, p.category, _auto_keywords(p.name, docs[p.name]) if p.sensitivity >= 2 else (),
                        p.sensitivity) for p in MANUAL[suite_name]]
