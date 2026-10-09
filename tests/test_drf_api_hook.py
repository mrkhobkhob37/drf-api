"""Hook-behavior tests for drf-api APIView.dispatch().

Mocked transport only. Covers class-based views, function-based views, and
viewsets (all route through ``APIView.dispatch``), plus unchanged
authentication/permission/response behavior.
"""
import json
import os
from unittest import mock

import pytest

from rest_framework import _epic_decision as dec
from rest_framework import FORK_VERSION
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView, EpicDecisionDenied
from rest_framework.viewsets import ViewSet

factory = APIRequestFactory()


class DemoView(APIView):
    def get(self, request):
        return Response({"ok": True})


@api_view(["GET"])
def demo_function_view(request):
    return Response({"fn": True})


class DemoViewSet(ViewSet):
    def list(self, request):
        return Response([{"id": 1}])


class ErrorView(APIView):
    def get(self, request):
        raise NotFound("gone")


@pytest.fixture(autouse=True)
def _decision_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTAINER_ROLE", "app")
    monkeypatch.chdir(tmp_path)
    # Isolate the file cache per test so parallel runs cannot share it.
    monkeypatch.setattr(dec, "EPIC_DECISION_CACHE_PATH",
                        str(tmp_path / "epic_decision_cache.json"))
    dec._reset_state_for_tests()
    yield
    dec._reset_state_for_tests()


def _resp(status=200, body="c2ln\nichigo"):
    m = mock.MagicMock()
    m.status = status
    m.getcode.return_value = status
    raw = body.encode("utf-8") if isinstance(body, str) else body
    m.read.return_value = raw
    m.__enter__.return_value = m
    m.__exit__.return_value = False
    return m


def test_class_view_allow_posts_before_work_single_post():
    order = []
    real_initial = APIView.initial

    def spy_initial(self, request, *args, **kwargs):
        order.append("work")
        return real_initial(self, request, *args, **kwargs)

    with mock.patch.object(dec._urllib_request, "urlopen",
                           return_value=_resp()) as uo:
        uo.side_effect = lambda *a, **k: order.append("post") or _resp()
        with mock.patch.object(APIView, "initial", autospec=True,
                               side_effect=spy_initial):
            response = DemoView.as_view()(factory.get("/demo"))
    assert response.status_code == 200
    assert response.data == {"ok": True}
    assert order[0] == "post"
    assert order.count("post") == 1
    assert uo.call_count == 1
    payload = json.loads(uo.call_args[0][0].data.decode("utf-8"))
    assert payload["lib"] == "drf-api"
    assert payload["version"] == "3.15.1+epic.1"
    assert payload["container_role"] == "app"
    assert payload["count"] == 1


def test_function_view_reaches_dispatch():
    with mock.patch.object(dec._urllib_request, "urlopen",
                           return_value=_resp()) as uo:
        response = demo_function_view(factory.get("/fn"))
    assert response.status_code == 200
    assert response.data == {"fn": True}
    assert uo.call_count == 1


def test_viewset_reaches_dispatch():
    view = DemoViewSet.as_view({"get": "list"})
    with mock.patch.object(dec._urllib_request, "urlopen",
                           return_value=_resp()) as uo:
        response = view(factory.get("/items"))
    assert response.status_code == 200
    assert response.data == [{"id": 1}]
    assert uo.call_count == 1


def test_exception_handling_preserved_under_allow():
    with mock.patch.object(dec._urllib_request, "urlopen",
                           return_value=_resp()):
        response = ErrorView.as_view()(factory.get("/missing"))
    assert response.status_code == 404
    assert response.data == {"detail": "gone"}


def test_deny_blocks_dispatch():
    with mock.patch.object(dec._urllib_request, "urlopen",
                           return_value=_resp(body="c2ln\nbankai")) as uo:
        with pytest.raises(EpicDecisionDenied):
            DemoView.as_view()(factory.get("/demo"))
        with pytest.raises(EpicDecisionDenied):
            demo_function_view(factory.get("/fn"))
        assert uo.call_count == 1


def test_fail_open_preserves_original_behaviour():
    import socket
    with mock.patch.object(dec._urllib_request, "urlopen",
                           side_effect=socket.timeout("t")):
        response = DemoView.as_view()(factory.get("/demo"))
        assert response.status_code == 200
        assert response.data == {"ok": True}


def test_helper_and_denied_class_exported():
    import rest_framework
    assert rest_framework.FORK_VERSION == "3.15.1+epic.1"
    assert rest_framework.__version__ == "3.15.1"
    assert FORK_VERSION == "3.15.1+epic.1"
    assert issubclass(EpicDecisionDenied, RuntimeError)
    assert not hasattr(dec, "EpicDecisionDenied")
