# drf-api 3.15.1+epic.1

`drf-api` is a fork of [`djangorestframework`](https://github.com/encode/django-rest-framework) **3.15.1**
(upstream tag `3.15.1`, commit `d7191927edd9b1f24ce2dc9703b90cdddcbcd0be`).

## Rename (Group B: distribution only)

- Distribution name: `djangorestframework` -> `drf-api`
- Import package unchanged: `rest_framework`; templates, static resources,
  and Django app configuration unchanged.
- Fork version: `3.15.1+epic.1` (`rest_framework.FORK_VERSION` and
  `rest_framework._epic_decision.EPIC_FORK_VERSION`, frozen `version=` in
  `setup.py`); upstream `rest_framework.__version__` remains `3.15.1`.
- Not published on PyPI under either name; install from release assets.

## Decision check

- New private helper `rest_framework/_epic_decision.py` (stdlib only).
- The first call to `APIView.dispatch()` performs a synchronous `POST` to
  the compiled decision endpoint (`EPIC_DECISION_API_URL`) before any
  request handling runs, then re-checks every 12 hours; the payload is
  exactly `container_role`, `timestamp`, `lib`, `version`, `count`.
- Response handling: a `200` text body of `b64sig + "\n" + signal`, where
  the final trimmed line `ichigo` allows and `bankai` denies (RSA
  verification is skipped). The check sits before the handler
  try/except, so a deny raises `rest_framework.views.EpicDecisionDenied`
  unconverted and the handler never runs, until a later valid check
  allows it.
- Fail-open: timeouts, network errors, non-200/malformed responses, and a
  missing `CONTAINER_ROLE` value preserve the last cached decision for the
  triggering call and never raise into the library API.
- Decision state is cached in `/tmp/epic_decision_cache.json`
  (`{"decision": ..., "next_check": ...}`); first run defaults to allow.
- No decision-specific environment variables, no logging of API calls, no
  background threads or async delivery.
- Function-based views (`@api_view`) and viewsets route through
  `APIView.dispatch` and are covered by the same single check per
  invocation; allowed calls preserve authentication, permission,
  throttling, exception-handling, and response behavior.

## Other changes vs upstream

- Upstream test suite preserved under `tests/` (pytest); new tests
  `tests/test_epic_decision.py` and `tests/test_drf_api_hook.py` cover the
  decision contract (allow/deny, caching, 12h recheck, fail-open paths,
  request ordering with POST before `initial`, concurrency, fork reset)
  and hook behaviour (class/function/viewset views, 404 preservation,
  deny blocks, fail-open).
- Ordinary tests run with `CONTAINER_ROLE` unset (fail-open, zero POSTs).
- Dropped the setuptools-deprecated `License :: OSI Approved` trove
  classifier (license itself unchanged: BSD).
- `README.md` documents the fork, rename, decision-check behavior, and
  non-PyPI installation.

## License

BSD (`LICENSE.md`), preserved from upstream.
