"""Declarative WeakAura group builder: archetype x style guide x definition.

Layout:
  styles/xyrec.json           the look, as data (see style.py)
  auras/<class>/group.json    root + rows + ordered membership
  auras/<class>/defs/*.json   one semantic definition per leaf aura
  auras/<class>/lua/*.lua     real Lua bodies, re-inlined at build time

Sabimaru donor packs (data/auras/donors/) are reference material only —
they are inputs to import_donor.py, never to the build itself.
"""
