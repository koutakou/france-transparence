"""Hygiène des chaînes partagée (pipelines/common.py).

Le mojibake « UTF-8 relu en cp1252 » touche au moins quatre sources
indépendantes du site (DECP, jaune budgétaire, comptes de campagne, AGORA).
Ces tests fixent le contrat de la réparation commune : elle corrige ce qui
est prouvablement cassé, et ne touche à RIEN d'autre — c'est cette seconde
moitié qui est la plus fragile, donc la plus testée ici.
"""

from pipelines.common import (
    assainir_texte,
    normaliser_espaces,
    reparer_controles_cp1252,
    reparer_mojibake,
)


# ---------------------------------------------------------------------------
# Ce qui doit être réparé
# ---------------------------------------------------------------------------


def test_repare_les_paires_c3():
    """U+00C0..U+00FF → « Ã » + 1 caractère (le cas le plus fréquent)."""
    assert reparer_mojibake("MarchÃ© ponctuel") == "Marché ponctuel"
    assert reparer_mojibake("franÃ§ais") == "français"
    assert reparer_mojibake("ErgÃ¼n") == "Ergün"


def test_repare_les_paires_c2():
    """U+0080..U+00BF → « Â » + 1 caractère (degré, copyright, guillemets)."""
    assert reparer_mojibake("lot nÂ° 5") == "lot n° 5"


def test_repare_les_triplets_e2_80():
    """U+2000..U+203F → « â€ » + 1 caractère.

    Cas réel : le libellé du pays COG 99326 dans le jaune budgétaire publié.
    Le motif à trois caractères doit être tenté AVANT celui à deux, sinon
    « â€™ » ne serait jamais reconnu — d'où ce test de non-régression.
    """
    assert reparer_mojibake("Côte dâ€™Ivoire") == "Côte d’Ivoire"


# ---------------------------------------------------------------------------
# Ce qui ne doit PAS bouger — la moitié qui compte
# ---------------------------------------------------------------------------


def test_ne_touche_pas_au_francais_legitime():
    """« Â » suivi d'une majuscule ASCII n'est pas un mojibake.

    585 503 objets DECP en portent : BÂTIMENT, CHÂTEAU, PLÂTRERIE. L'octet
    qui suit (0x41..0x5A) n'est pas une continuation UTF-8 valide, donc le
    décodage échoue et le mot est rendu tel quel.
    """
    for mot in ("BÂTIMENT", "CHÂTEAU", "PLÂTRERIE", "Théâtre", "Août", "Île"):
        assert reparer_mojibake(mot) == mot


def test_laisse_intact_un_mojibake_irreparable():
    """On ne devine jamais : ce qui ne se re-décode pas reste tel quel.

    « PHOTOVOLTAÃQUE » vient de l'octet 0x8F, qui n'existe pas en cp1252 —
    la réparation est impossible sans inventer, donc elle n'a pas lieu.
    """
    assert reparer_mojibake("PHOTOVOLTAÃQUE") == "PHOTOVOLTAÃQUE"


def test_chaine_sans_marqueur_est_rendue_a_l_identique():
    assert reparer_mojibake("Marché public de travaux") == "Marché public de travaux"


# ---------------------------------------------------------------------------
# Espaces
# ---------------------------------------------------------------------------


def test_normaliser_espaces_ecrase_insecables_et_bords():
    assert normaliser_espaces("  CROIX ROUGE   FRANCAISE \n") == "CROIX ROUGE FRANCAISE"
    assert normaliser_espaces("a b") == "a b"


def test_assainir_texte_rend_none_sur_le_vide():
    """Une chaîne vide est une absence de valeur, pas une valeur."""
    assert assainir_texte("     ") is None
    assert assainir_texte(None) is None
    assert assainir_texte(42) == 42  # non-str rendu tel quel


def test_assainir_texte_cumule_les_deux_traitements():
    assert assainir_texte("  MarchÃ©  public  ") == "Marché public"


# ---------------------------------------------------------------------------
# Contrôles C1 — le défaut INVERSE du mojibake, et il n'est traité nulle part
# ailleurs. Ces tests existent parce que `assainir_texte` a été proposé comme
# remède au défaut mesuré, et qu'il ne le répare PAS : la contre-épreuve
# ci-dessous fige cette limite pour qu'aucune séance ne la re-suppose.
# ---------------------------------------------------------------------------


def test_repare_les_deux_controles_du_corpus_cnccfp():
    """Cas réels servis le 29/08/2026 dans l'index de recherche du site."""
    assert reparer_controles_cp1252("LEVALLOIS AU C\x8cUR") == "LEVALLOIS AU CŒUR"
    assert (
        reparer_controles_cp1252("UNION ROSNÉENNE D\x92ACTION MUNICIPALE")
        == "UNION ROSNÉENNE D’ACTION MUNICIPALE"
    )


def test_repare_toute_la_plage_affectee_en_cp1252():
    """27 des 32 octets 0x80-0x9F portent un caractère en cp1252."""
    repares = [
        o for o in range(0x80, 0xA0)
        if reparer_controles_cp1252(chr(o)) != chr(o)
    ]
    assert len(repares) == 27
    assert reparer_controles_cp1252("\x80\x85\x93\x94\x96") == "€…“”–"


def test_laisse_intacts_les_cinq_octets_sans_affectation():
    """Ne jamais rien perdre : cp1252 n'affecte pas ces cinq octets."""
    for octet in (0x81, 0x8D, 0x8F, 0x90, 0x9D):
        assert reparer_controles_cp1252(chr(octet)) == chr(octet)


def test_ne_touche_pas_au_texte_sain():
    for sain in (
        "UNION ROSNÉENNE D’ACTION MUNICIPALE",
        "LEVALLOIS AU CŒUR",
        "BÂTIMENT, CHÂTEAU, Île, Août",
        "espace insécable\u00a0et fine\u202f",
        "tabulation\tet\nretour",
        "",
    ):
        assert reparer_controles_cp1252(sain) == sain


def test_est_idempotente():
    une = reparer_controles_cp1252("LEVALLOIS AU C\x8cUR")
    assert reparer_controles_cp1252(une) == une


def test_assainir_texte_NE_repare_PAS_les_controles_c1():
    """CONTRE-ÉPREUVE, et c'est le cœur de ces tests.

    `assainir_texte` a été proposé le 29/08/2026 comme remède aux deux noms
    de partis corrompus ; il ne les répare pas, parce que `reparer_mojibake`
    sort immédiatement sur une chaîne sans « Ã »/« Â »/« â€ ». Ce test fige
    la limite : s'il devient rouge, c'est que `assainir_texte` a été élargi,
    et il faudra alors relire les sept pipelines qui l'appellent.
    """
    assert assainir_texte("LEVALLOIS AU C\x8cUR") == "LEVALLOIS AU C\x8cUR"
    # … et l'instrument n'est pas muet pour autant : il répare son défaut à lui
    assert assainir_texte("MarchÃ© public") == "Marché public"
