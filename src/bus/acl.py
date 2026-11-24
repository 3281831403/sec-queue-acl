"""Queue ACL stubs for the sec-queue-acl exercise.

Every public function in this module is a stub. Implement the functions
without changing their names or signatures. Topic matching has zero
tolerance: no prefixes, no fuzzy matches, no whitespace cleanup, and no
Unicode normalization.
"""

from collections.abc import Mapping


_ASCII_WHITESPACE = " \t\n\r\v\f"
_ASCII_FOLD = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "abcdefghijklmnopqrstuvwxyz",
)


def _ascii_lower(value: str) -> str:
    """ASCII-only case folding: A-Z -> a-z, everything else untouched."""
    return value.translate(_ASCII_FOLD)


def _has_whitespace(segment: str) -> bool:
    return any(ch in segment for ch in _ASCII_WHITESPACE)


# Defect 1: topic parsing must reject empty segments (leading/trailing/
# consecutive dots) and segments containing ASCII whitespace.
def parse_topic(topic: str) -> list[str]:
    """Split a hierarchical topic into its segments.

    Contract:
    - A topic is a dot-separated string with at least one segment.
    - Every segment must be non-empty and must not contain ASCII whitespace.
    - Leading dots, trailing dots and consecutive dots are invalid and raise
      ValueError.
    - Segments are returned in their original order and with their original
      spelling. There is no trimming, case folding, escaping or Unicode
      normalization.
    - The wildcard tokens * and ** are returned as ordinary segment strings.
      Their special meaning is defined only by pattern_match.
    """
    if not isinstance(topic, str):
        raise TypeError("topic must be a string")
    segments = topic.split(".")
    for segment in segments:
        if segment == "":
            raise ValueError(f"invalid topic {topic!r}: empty segment")
        if _has_whitespace(segment):
            raise ValueError(f"invalid topic {topic!r}: whitespace in segment")
    return segments


def _parse_pattern(pattern: str) -> list[str] | None:
    """Parse a wildcard pattern.

    Same structural rules as parse_topic (non-empty, whitespace-free
    segments), but '*' and '**' are kept as ordinary segment tokens for
    pattern_match to interpret. Returns None when the pattern is malformed.
    """
    if not isinstance(pattern, str):
        return None
    segments = pattern.split(".")
    for segment in segments:
        if segment == "" or _has_whitespace(segment):
            return None
    return segments


# Defects 2, 3, 8: wildcard semantics and zero-tolerance matching.
def pattern_match(pattern: str, topic: str) -> bool:
    """Return True only when the whole pattern matches the whole topic.

    Contract:
    - A single * matches exactly one segment.
    - A ** is a multi-level wildcard. It may appear only as the final
      segment and matches one or more segments. It never matches zero
      segments.
    - Literal segments must match exactly after ASCII lower-case folding of
      both pattern and topic. No prefix match, substring match, shell glob,
      Unicode casefold, whitespace cleanup or other tolerance is allowed.
      Matching tolerance is 0.
    - A pattern with ** anywhere except the final segment is invalid and
      returns False.
    - An invalid topic, a non-string argument, or a topic containing * or **
      returns False.
    """
    if not isinstance(pattern, str) or not isinstance(topic, str):
        return False
    # Topics are concrete: any wildcard token disqualifies them.
    if "*" in topic:
        return False
    try:
        topic_segments = parse_topic(topic)
    except (TypeError, ValueError):
        return False
    pattern_segments = _parse_pattern(pattern)
    if pattern_segments is None:
        return False

    # ** is only legal as the final segment.
    if "**" in pattern_segments[:-1]:
        return False

    multilevel = pattern_segments[-1] == "**"
    literal_count = len(pattern_segments) - 1 if multilevel else len(pattern_segments)

    if multilevel:
        # ** must consume one or more segments, never zero.
        if len(topic_segments) <= literal_count:
            return False
    elif len(topic_segments) != literal_count:
        # No prefix match: segment counts must be exactly equal.
        return False

    for index in range(literal_count):
        token = pattern_segments[index]
        if token == "*":
            # Length alignment above guarantees exactly one segment.
            continue
        if _ascii_lower(token) != _ascii_lower(topic_segments[index]):
            return False
    return True


def _rule_lists(policy: dict, section: str, principal: str):
    """Fetch (deny_rules, allow_rules) for principal under one section.

    Returns None when the policy is malformed; a missing section, map,
    principal or rule list is represented by an empty list instead.
    """
    if not isinstance(policy, dict):
        return None
    block = policy.get(section)
    if block is None:
        return [], []
    if not isinstance(block, dict):
        return None

    def _rules(kind: str):
        rules = block.get(kind)
        if rules is None:
            return []
        if not isinstance(rules, dict):
            return None
        entries = rules.get(principal)
        if entries is None:
            return []
        if not isinstance(entries, list):
            return None
        return entries

    allow = _rules("allow")
    deny = _rules("deny")
    if allow is None or deny is None:
        return None
    return deny, allow


def _decide(section: str, principal: str, topic: str, policy: dict) -> bool:
    """Deny-first, allow-second decision for a concrete topic."""
    if not isinstance(topic, str) or "*" in topic:
        return False
    # Rejects invalid topics before any rule is consulted.
    parse_topic(topic)
    rules = _rule_lists(policy, section, principal)
    if rules is None:
        return False
    deny_rules, allow_rules = rules
    # Defect 4: deny rules are evaluated first and always win.
    for pattern in deny_rules:
        if pattern_match(pattern, topic):
            return False
    for pattern in allow_rules:
        if pattern_match(pattern, topic):
            return True
    return False


# Defect 4: subscribe honors deny rules before allow rules.
def allow_subscribe(principal: str, topic: str, policy: dict) -> bool:
    """Decide whether principal may subscribe to a concrete topic.

    Policy shape:
    policy["subscribe"]["allow"][principal] is a list of topic patterns.
    policy["subscribe"]["deny"][principal] is a list of topic patterns.
    Missing sections or a missing principal mean no rule of that kind.

    Contract:
    - The topic argument must be a concrete topic. A requested topic
      containing * or ** returns False; policy rules may still contain
      wildcards.
    - Deny rules are checked first. Any matching deny rule returns False,
      even when an allow rule also matches.
    - Allow rules are checked only after deny rules. Any matching allow rule
      returns True.
    - Matching uses pattern_match and therefore has tolerance 0 and the same
      ASCII case-fold policy everywhere.
    - An invalid topic, an invalid pattern or a malformed policy returns
      False.
    - Subscription rules never fall back to publish or dead-letter rules.
    """
    try:
        return _decide("subscribe", principal, topic, policy)
    except (TypeError, ValueError):
        return False


# Defect 5: publish is governed solely by the publish section.
def allow_publish(principal: str, topic: str, policy: dict) -> bool:
    """Decide whether principal may publish to a concrete topic.

    Policy shape:
    policy["publish"]["allow"][principal] is a list of topic patterns.
    policy["publish"]["deny"][principal] is a list of topic patterns.

    Contract:
    - Publishing is governed only by the publish section. If that section is
      missing, publishing is denied. Subscribe rules must never be reused.
    - The topic argument must be a concrete topic. A topic containing * or **
      is not a publish target and returns False.
    - Deny rules are checked first; any matching deny rule returns False.
    - An allow rule may contain wildcards, but it must match the whole
      concrete topic with tolerance 0.
    - An invalid topic, an invalid pattern or a malformed policy returns
      False.
    """
    try:
        return _decide("publish", principal, topic, policy)
    except (TypeError, ValueError):
        return False


# Defect 6: dead-letter access requires an explicit per-queue reader grant.
def deadletter_ok(principal: str, queue) -> bool:
    """Decide whether principal may read a dead-letter queue.

    Contract:
    - queue must be a mapping describing the queue: its name is in "name" and
      its explicit reader principals are in "readers".
    - Access is granted only when principal appears verbatim in readers and
      does not appear in the optional "deny_readers" list.
    - A plain queue name, a mapping without readers, a wildcard principal and
      any implicit subscription or administrator access all return False.
    - Dead-letter access is always explicitly granted per queue; no wildcard
      reader matching is performed.
    """
    if not isinstance(principal, str) or "*" in principal:
        return False
    if not isinstance(queue, Mapping):
        return False
    readers = queue.get("readers")
    if not isinstance(readers, list):
        return False
    if principal not in readers:
        return False
    denied = queue.get("deny_readers")
    if isinstance(denied, list) and principal in denied:
        return False
    return True


# Defect 7: subscription caps are mandatory and fail closed.
def subscription_limit(principal: str, count: int, policy: dict) -> bool:
    """Decide whether a subscription count stays within the configured cap.

    Contract:
    - count is the total number of subscriptions principal would have after
      this request. It must be a non-negative integer.
    - The cap is policy["subscribe"]["max_subscriptions"][principal], with a
      fallback to the "default" key when the principal has no own cap.
    - Return True only when count is less than or equal to the cap.
    - A missing cap, a negative cap, a non-integer count or any malformed
      policy fails closed and returns False. The cap is not optional.
    """
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        return False
    if not isinstance(policy, dict):
        return False
    section = policy.get("subscribe")
    if not isinstance(section, dict):
        return False
    caps = section.get("max_subscriptions")
    if not isinstance(caps, dict):
        return False
    try:
        cap = caps.get(principal, caps.get("default"))
    except TypeError:
        return False
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 0:
        return False
    return count <= cap


def _iter_allow_patterns(policy: dict, section: str) -> list:
    block = policy.get(section)
    if not isinstance(block, dict):
        return []
    allow = block.get("allow")
    if not isinstance(allow, dict):
        return []
    patterns = []
    for entries in allow.values():
        if isinstance(entries, list):
            patterns.extend(entries)
    return patterns


def _has_broad_multilevel(patterns: list) -> bool:
    for pattern in patterns:
        if not isinstance(pattern, str):
            continue
        segments = pattern.split(".")
        if pattern == "**" or "**" in segments[:-1]:
            return True
    return False


# Defect 9: policy validation flags over-broad multilevel wildcards and
# other structural problems.
def validate_policy(policy: dict) -> list[str]:
    """Return a deterministic list of policy problem codes.

    Every problem code appears at most once. The canonical order is:
    1. broad_multilevel_wildcard
       A subscribe or publish allow pattern is exactly ** or contains ** in a
       non-final segment.
    2. missing_deadletter_allow
       policy["deadletter"]["allow"] is missing, empty, or contains **.
    3. publish_subscribe_shared
       There is no separate publish section, or its allow and deny maps are
       the same object or equal to the subscribe maps.

    A valid policy returns an empty list. The function never mutates policy.
    """
    issues: list[str] = []
    if not isinstance(policy, dict):
        return ["broad_multilevel_wildcard", "missing_deadletter_allow",
                "publish_subscribe_shared"]

    broad_patterns = (
        _iter_allow_patterns(policy, "subscribe")
        + _iter_allow_patterns(policy, "publish")
    )
    if _has_broad_multilevel(broad_patterns):
        issues.append("broad_multilevel_wildcard")

    deadletter = policy.get("deadletter")
    deadletter_allow = (
        deadletter.get("allow") if isinstance(deadletter, dict) else None
    )
    if (
        not isinstance(deadletter_allow, list)
        or not deadletter_allow
        or any(
            isinstance(pattern, str) and "**" in pattern.split(".")
            for pattern in deadletter_allow
        )
    ):
        issues.append("missing_deadletter_allow")

    subscribe = policy.get("subscribe")
    publish = policy.get("publish")
    shared = False
    if not isinstance(publish, dict):
        shared = True
    elif isinstance(subscribe, dict):
        for publish_kind, subscribe_kind in (
            ("allow", "allow"),
            ("deny", "deny"),
        ):
            publish_map = publish.get(publish_kind)
            subscribe_map = subscribe.get(subscribe_kind)
            if (
                isinstance(publish_map, dict)
                and isinstance(subscribe_map, dict)
                and (publish_map is subscribe_map or publish_map == subscribe_map)
            ):
                shared = True
                break
    if shared:
        issues.append("publish_subscribe_shared")

    return issues


# Defect 10: every batch request is evaluated independently with no shared
# match state, parsed topic or decision.
def queue_batch(requests, policy: dict) -> dict:
    """Evaluate independent ACL requests and return id-to-boolean results.

    Each request is a mapping with a unique string "id" and an "action":
    - subscribe: "principal", "topic" and optional "count". The result is
      allow_subscribe and, when count is present, subscription_limit.
    - publish: "principal" and concrete "topic". The result is
      allow_publish.
    - deadletter: "principal" and the "queue" mapping. The result is
      deadletter_ok.

    Contract:
    - Requests are evaluated independently and in input order. No match,
      parsed topic or decision may be reused across requests.
    - An unknown action or malformed request produces False for its id.
      Requests without a usable string id are skipped.
    - Every usable id appears exactly once in the returned dictionary.
    """
    results: dict[str, bool] = {}
    try:
        iterator = iter(requests)
    except TypeError:
        return results

    for request in iterator:
        if not isinstance(request, Mapping):
            continue
        request_id = request.get("id")
        if not isinstance(request_id, str) or request_id == "":
            continue

        action = request.get("action")
        try:
            if action == "subscribe":
                principal = request.get("principal")
                decision = allow_subscribe(
                    principal, request.get("topic"), policy
                )
                if decision and "count" in request:
                    decision = subscription_limit(
                        principal, request.get("count"), policy
                    )
            elif action == "publish":
                decision = allow_publish(
                    request.get("principal"), request.get("topic"), policy
                )
            elif action == "deadletter":
                decision = deadletter_ok(
                    request.get("principal"), request.get("queue")
                )
            else:
                decision = False
        except (TypeError, ValueError, KeyError, AttributeError):
            decision = False

        results[request_id] = decision

    return results
