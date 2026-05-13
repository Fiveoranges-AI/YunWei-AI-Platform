"""Shared assistant endpoint for Free/Lite/Pro users.

Mounted at ``/api/win/assistant/chat``. Reads enterprise scope from the
server-side ``request.state.auth_context`` only; the request body is
never trusted to carry a tenant ID.

Note: callers should import ``router`` from ``yunwei_win.assistant.router``
directly. Re-exporting it from this ``__init__`` would shadow the
``router`` submodule attribute and break ``monkeypatch.setattr`` on
symbols defined inside ``router.py`` (e.g. tests stubbing
``answer_shared_assistant``).
"""
