import signal

from agent.smart_homelab_maintenance.process_control import ProcessIdentity, kill_verified_after_term, terminate_verified, verify_identity


def test_process_identity_must_match_before_signal():
    identity = ProcessIdentity(321, 321, "old")
    signals = []
    assert not verify_identity(identity, starttime=lambda _: "new", getpgid=lambda _: 321)
    assert terminate_verified(identity, starttime=lambda _: "new", getpgid=lambda _: 321, killpg=lambda *args: signals.append(args)) == "identity_changed"
    assert signals == []


def test_term_is_rechecked_and_never_escalates_automatically():
    identity = ProcessIdentity(321, 321, "same")
    signals = []
    assert terminate_verified(identity, starttime=lambda _: "same", getpgid=lambda _: 321, killpg=lambda *args: signals.append(args)) == "term_sent_recheck_required"
    assert len(signals) == 1


def test_kill_requires_a_fresh_identity_check_after_bounded_term_wait():
    identity = ProcessIdentity(321, 321, "same")
    signals = []
    assert kill_verified_after_term(identity, starttime=lambda _: "changed", getpgid=lambda _: 321, killpg=lambda *args: signals.append(args)) == "identity_changed"
    assert signals == []
    assert kill_verified_after_term(identity, starttime=lambda _: "same", getpgid=lambda _: 321, killpg=lambda *args: signals.append(args)) == "kill_sent_recheck_required"
    assert signals == [(321, signal.SIGKILL)]
