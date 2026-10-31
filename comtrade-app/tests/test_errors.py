"""Tests of the error display: the app URL is public."""

import errors


def run_show_error(monkeypatch, is_local):
    shown = []
    monkeypatch.setattr(errors, "IS_LOCAL", is_local)
    monkeypatch.setattr(errors.st, "error", shown.append)
    errors.show_error("Report service error.", ValueError("arn:aws:iam::123456789012:role/x"))
    return shown[0]


def test_production_hides_the_details(monkeypatch):
    assert run_show_error(monkeypatch, is_local=False) == "Report service error."


def test_local_shows_the_details(monkeypatch):
    assert "123456789012" in run_show_error(monkeypatch, is_local=True)
