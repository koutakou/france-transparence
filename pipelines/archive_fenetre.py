"""Copie vers une table d'archive les lignes qu'une fenêtre glissante DELETE.

Les tables d'archive sont NOUVELLES (`CREATE TABLE IF NOT EXISTS`). On ne
fait pas d'`ALTER` sur `votes_recents` / `votes_senat` / `jorf_textes` /
`annonces_recentes` : `CREATE TABLE IF NOT EXISTS` ne migre pas une
`france.db` persistante.

Ce module n'est pas une page `/archives`, pas un 12ᵉ onglet. Le site
continue de ne servir que la fenêtre. `INSERT OR IGNORE` : le premier
`archive_le` gagne si la même clé ressort (restauration d'une vieille
base, rejeu).
"""

from __future__ import annotations

import re
import sqlite3

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _identifiant(nom: str) -> str:
    if not _IDENT.fullmatch(nom):
        raise ValueError(f"identifiant SQL refusé : {nom!r}")
    return nom


def archiver_sortie_fenetre(
    conn: sqlite3.Connection,
    *,
    source: str,
    archive: str,
    colonnes: tuple[str, ...],
    where: str,
    params: tuple = (),
    archive_le: str,
) -> int:
    """`INSERT OR IGNORE` vers `archive` des lignes de `source` qui matchent.

    `archive` a les mêmes colonnes que `source` plus `archive_le` (date ISO
    du run qui sort la ligne). Retourne le nombre de lignes réellement
    insérées (0 si rien ne sort, ou si la clé était déjà archivée).
    """
    if not colonnes:
        raise ValueError("colonnes vide")
    if not where.strip():
        raise ValueError("where vide")
    src = _identifiant(source)
    dst = _identifiant(archive)
    cols = [_identifiant(c) for c in colonnes]
    liste = ", ".join(cols)
    sql = (
        f"INSERT OR IGNORE INTO {dst} ({liste}, archive_le) "
        f"SELECT {liste}, ? FROM {src} WHERE {where}"
    )
    cur = conn.execute(sql, (archive_le, *params))
    return cur.rowcount
