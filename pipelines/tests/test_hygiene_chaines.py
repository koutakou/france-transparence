"""Hygiène des chaînes partagée (pipelines/common.py).

Le mojibake « UTF-8 relu en cp1252 » touche au moins quatre sources
indépendantes du site (DECP, jaune budgétaire, comptes de campagne, AGORA).
Ces tests fixent le contrat de la réparation commune : elle corrige ce qui
est prouvablement cassé, et ne touche à RIEN d'autre — c'est cette seconde
moitié qui est la plus fragile, donc la plus testée ici.
"""

from pipelines.common import assainir_texte, normaliser_espaces, reparer_mojibake


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
