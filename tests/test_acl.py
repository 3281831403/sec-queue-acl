import pytest

from bus.acl import (
    allow_publish,
    allow_subscribe,
    deadletter_ok,
    parse_topic,
    pattern_match,
    queue_batch,
    subscription_limit,
    validate_policy,
)


POLICY = {
    "subscribe": {
        "allow": {
            "team-a": ["payments.*", "public.**"],
            "team-b": ["public.**"],
        },
        "deny": {
            "team-a": ["payments.card.**"],
            "team-b": ["public.secret.*"],
        },
        "max_subscriptions": {
            "team-a": 2,
            "team-b": 1,
        },
    },
    "publish": {
        "allow": {
            "team-a": ["payments.created"],
            "team-b": ["public.*"],
        },
        "deny": {
            "team-a": ["payments.card.**"],
            "team-b": ["public.secret.*"],
        },
    },
    "deadletter": {"allow": ["dlq.payments"]},
}


def test_parse_topic_rejects_empty_segments():
    with pytest.raises(ValueError):
        parse_topic("payments..eu")
    with pytest.raises(ValueError):
        parse_topic(".payments")
    with pytest.raises(ValueError):
        parse_topic("payments.")


def test_multilevel_wildcard_does_not_collapse_to_one_level():
    assert pattern_match("payments.**", "payments.eu.west") is True
    assert pattern_match("payments.*", "payments.eu.west") is False


def test_matching_is_not_prefix_based():
    assert pattern_match("team-1.*", "team-10.eu") is False
    assert pattern_match("payments.eu", "payments.europe") is False

    exact_policy = {
        "subscribe": {
            "allow": {"team-a": ["payments.eu"]},
            "deny": {},
            "max_subscriptions": {"team-a": 2},
        }
    }
    assert allow_subscribe("team-a", "payments.europe", exact_policy) is False


def test_subscribe_deny_beats_allow():
    assert allow_subscribe("team-a", "payments.card.token", POLICY) is False
    assert allow_subscribe("team-a", "payments.cash", POLICY) is True


def test_publish_rules_are_separate_from_subscribe():
    assert allow_publish("team-a", "payments.created", POLICY) is True
    assert allow_publish("team-a", "payments.deleted", POLICY) is False

    subscribe_only_policy = {"subscribe": POLICY["subscribe"]}
    assert allow_publish("team-a", "payments.created", subscribe_only_policy) is False


def test_deadletter_is_not_readable_without_explicit_grant():
    assert deadletter_ok("team-a", "dlq.payments") is False
    assert deadletter_ok("team-a", {"name": "dlq.payments"}) is False
    assert (
        deadletter_ok(
            "team-b",
            {"name": "dlq.payments", "readers": ["team-a"]},
        )
        is False
    )


def test_subscription_limit_blocks_unbounded_subscriptions():
    assert subscription_limit("team-a", 2, POLICY) is True
    assert subscription_limit("team-a", 3, POLICY) is False
    assert subscription_limit("team-a", 10_000, POLICY) is False


def test_case_variants_cannot_bypass_deny():
    assert pattern_match("Payments.Card.**", "payments.card.token") is True
    assert allow_subscribe("team-a", "PAYMENTS.CARD.TOKEN", POLICY) is False
    assert allow_subscribe("team-a", "PAYMENTS.CASH", POLICY) is True


def test_validate_policy_flags_broad_multilevel_wildcard():
    broad_policy = {
        "subscribe": {
            "allow": {"team-a": ["**"]},
            "deny": {},
            "max_subscriptions": {"team-a": 2},
        },
        "publish": {
            "allow": {"team-a": []},
            "deny": {"team-a": []},
        },
        "deadletter": {"allow": ["dlq.payments"]},
    }
    issues = validate_policy(broad_policy)
    assert "broad_multilevel_wildcard" in issues


def test_batch_does_not_leak_previous_match():
    requests = [
        {
            "id": "first",
            "action": "subscribe",
            "principal": "team-a",
            "topic": "payments.cash",
            "count": 1,
        },
        {
            "id": "second",
            "action": "subscribe",
            "principal": "team-b",
            "topic": "payments.cash",
            "count": 1,
        },
    ]
    result = queue_batch(requests, POLICY)
    assert result["first"] is True
    assert result["second"] is False


def test_exact_topic_subscription_is_allowed():
    exact_policy = {
        "subscribe": {
            "allow": {"team-a": ["payments.eu"]},
            "deny": {},
            "max_subscriptions": {"team-a": 2},
        }
    }
    assert allow_subscribe("team-a", "payments.eu", exact_policy) is True
    assert allow_subscribe("team-a", "payments.us", exact_policy) is False


def test_single_level_wildcard_matches_exactly_one_level():
    assert pattern_match("payments.*", "payments.eu") is True
    assert pattern_match("payments.*", "payments.eu.west") is False
    assert pattern_match("payments.*", "payments") is False


def test_deny_rule_has_priority():
    deny_policy = {
        "subscribe": {
            "allow": {"team-a": ["payments.eu"]},
            "deny": {"team-a": ["payments.*"]},
            "max_subscriptions": {"team-a": 2},
        }
    }
    assert allow_subscribe("team-a", "payments.eu", deny_policy) is False
    assert allow_subscribe("team-a", "payments.us", deny_policy) is False


def test_deadletter_grant_is_explicit_and_scoped():
    queue = {"name": "dlq.payments", "readers": ["team-a"]}
    assert deadletter_ok("team-a", queue) is True
    assert deadletter_ok("team-b", queue) is False
    assert (
        deadletter_ok(
            "team-a",
            {"name": "dlq.orders", "readers": ["team-b"]},
        )
        is False
    )


def test_two_batches_are_independent_and_match_single_checks():
    requests = [
        {
            "id": "allowed",
            "action": "subscribe",
            "principal": "team-a",
            "topic": "payments.cash",
            "count": 1,
        },
        {
            "id": "denied",
            "action": "subscribe",
            "principal": "team-b",
            "topic": "payments.cash",
            "count": 1,
        },
    ]

    first_batch = queue_batch(list(requests), POLICY)
    second_batch = queue_batch(list(requests), POLICY)
    expected = {
        "allowed": allow_subscribe("team-a", "payments.cash", POLICY),
        "denied": allow_subscribe("team-b", "payments.cash", POLICY),
    }

    assert first_batch == expected
    assert second_batch == expected