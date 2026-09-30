"""Vertical slices: one folder per use case {router.py, service.py, schemas.py, test}.

Slices: login, refresh, logout, me, accept_invite, list_users, invite_user,
change_role, deactivate_user. Each router is re-exported by ``public.py``.
"""

from __future__ import annotations
