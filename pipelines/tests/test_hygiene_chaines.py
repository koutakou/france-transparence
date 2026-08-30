"""Hygiène des chaînes partagée (pipelines/common.py).

Le mojibake « UTF-8 relu en cp1252 » touche au moins quatre sources
indépendantes du site (DECP, jaune budgétaire, comptes de campagne, AGORA).
Ces tests fixent le contrat de la réparation commune : elle corrige ce qui
est prouvablement cassé, et ne touche à RIEN d'autre — c'est cette seconde
moitié qui est la plus fragile, donc la plus testée ici.
"""

from pipelines.common import (
    assainir_texte,
    assainir_texte_integral,
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


# ---------------------------------------------------------------------------
# `assainir_texte_integral` — l'hygiène complète, et surtout SON ORDRE
#
# MUTATIONS TUÉES PAR CE BLOC (jouées le 30/08/2026, chacune re-vérifiée en
# réintroduisant la mutation et en exigeant que CE test-là rougisse) :
#   M1  ordre `espaces, mojibake, C1`   -> test_..._repare_le_mojibake_a_insecable
#   M2  ordre `mojibake, espaces, C1`   -> test_..._preserve_u0085
#   M3  ordre `C1, mojibake, espaces`   -> test_..._rattrape_un_c1_materialise
#   M4  point fixe réduit à UN passage  -> test_..._est_idempotente
#                                       -> et test_..._ne_regenere_aucun_controle
#   M5  `reparer_controles_cp1252` ôtée -> test_..._repare_les_controles_c1
#   M6  `or None` ajouté (comme dans `assainir_texte`) -> test_..._ne_rend_pas_none
#
# MUTATION SURVIVANTE, ASSUMÉE ET NOTÉE — parce qu'une campagne qui ne rapporte
# que ses succès ne prouve rien :
#   M7  point fixe réduit à DEUX passages -> AUCUN test ne rougit. Deux
#       applications du couple suffisent sur toute la population mesurée ; la
#       borne de 4 est une marge, pas un réglage vérifié (cf. `common.py`).
# ---------------------------------------------------------------------------


def test_assainir_texte_integral_repare_les_controles_c1():
    """La différence n° 1 avec `assainir_texte`, qui, lui, ne les répare pas."""
    assert assainir_texte_integral("LEVALLOIS AU C\x8cUR") == "LEVALLOIS AU CŒUR"
    assert assainir_texte_integral("ROSNÉENNE D\x92ACTION") == "ROSNÉENNE D’ACTION"


def test_assainir_texte_integral_ne_rend_pas_none_sur_le_vide():
    """La différence n° 2 : le vide reste du vide.

    `assainir_texte` rend `None` sur une chaîne vide après nettoyage. Ici la
    valeur part dans une colonne qui peut être `NOT NULL`, et l'ingestion est
    tout-ou-rien : un `None` inattendu gèlerait la publication de la nuit.
    """
    assert assainir_texte("   ") is None          # contre-épreuve : l'autre, si
    assert assainir_texte_integral("   ") == ""   # celle-ci, non
    assert assainir_texte_integral("\xa0  ") == ""
    # Tolérance au None et aux non-str, comme `assainir_texte`.
    assert assainir_texte_integral(None) is None
    assert assainir_texte_integral(42) == 42


def test_assainir_texte_integral_repare_le_mojibake_a_insecable():
    """MUTATION TUÉE : `normaliser_espaces` remonté en tête de la composition.

    C'est l'ordre qu'une note de qualification prescrivait le 30/08/2026. Il
    DÉTRUIT une réparation : le mojibake dont l'octet de continuation est
    l'insécable (« Ã » + U+00A0 = « à ») n'est plus réparable une fois
    l'insécable écrasée en espace ordinaire, parce que C3 20 n'est pas de
    l'UTF-8 valide. La docstring de `reparer_mojibake` le disait déjà en
    creux, en citant ce cas comme irréparable « l'insécable d'origine ayant
    déjà été normalisée en amont ».
    """
    assert assainir_texte_integral("dejÃ\xa0 enregistrée") == "dejà enregistrée"
    # … et voici, explicitement, ce que rendrait l'ordre fautif :
    ordre_fautif = reparer_controles_cp1252(
        reparer_mojibake(normaliser_espaces("dejÃ\xa0 enregistrée"))
    )
    assert ordre_fautif == "dejÃ enregistrée"
    assert ordre_fautif != assainir_texte_integral("dejÃ\xa0 enregistrée")


def test_assainir_texte_integral_preserve_u0085():
    """MUTATION TUÉE : `normaliser_espaces` placé AVANT la réparation des C1.

    U+0085 est le SEUL contrôle C1 que la classe `\\s` Unicode attrape. Laissé
    à `normaliser_espaces`, il devient une espace au lieu des points de
    suspension que cp1252 place sur cet octet. C'est le défaut inscrit sous
    `P-ASSAINIR-ORDRE-U0085` pour `assainir_texte` ; cette fonction-ci ne le
    reproduit pas.
    """
    assert assainir_texte_integral("RAPPORT\x85 ANNEXE") == "RAPPORT… ANNEXE"
    # Contre-épreuve : l'ordre de `_titre_dosleg` (espaces avant C1) le perd.
    assert reparer_controles_cp1252(
        normaliser_espaces(reparer_mojibake("RAPPORT\x85 ANNEXE"))
    ) == "RAPPORT ANNEXE"


def test_assainir_texte_integral_rattrape_un_c1_materialise():
    """MUTATION TUÉE : réparation des C1 remontée AVANT `reparer_mojibake`.

    `reparer_mojibake` MATÉRIALISE un C1 sur le motif « Â » + caractère
    typographique : un contrôle produit après le passage du remède y
    échapperait. Règle déjà posée par `_titre_dosleg` (ingest_parlement).

    Le témoin est fabriqué par ALLER-RETOUR d'encodage, jamais à la main : un
    témoin écrit à la main accuse l'instrument à sa place. Ici le pire cas est
    U+0085, parce qu'il cumule les deux pièges — matérialisé par le remède
    mojibake, puis écrasable par `normaliser_espaces`.
    """
    origine = "B\x85 test"                            # U+0085, contrôle C1
    mojibake = origine.encode("utf-8").decode("cp1252")
    assert mojibake == "BÂ… test", "prémisse : le C1 est EMPILÉ dans le mojibake"
    assert "\x85" not in mojibake, "prémisse : et il est donc INVISIBLE au prédicat Cc"
    assert assainir_texte_integral(mojibake) == "B… test"
    # Contre-épreuve : réparer les C1 en PREMIER perd la matérialisation.
    assert normaliser_espaces(
        reparer_mojibake(reparer_controles_cp1252(mojibake))
    ) == "B test"


def test_assainir_texte_integral_est_idempotente():
    """MUTATION TUÉE : point fixe du couple (mojibake, C1) réduit à UN passage.

    Un mojibake peut être écrit AVEC des contrôles C1 : « â » + U+0080 +
    U+0099 est « â€™ » dont les deux octets de continuation ont été relus en
    latin-1. Le premier passage ne le voit pas ; la réparation des C1 le
    matérialise en « â€™ » ; seul un second passage le rend « ’ ».

    🛑 CE MOTIF EST EXERCÉ, il n'est pas théorique : 46 occurrences mesurées le
    30/08/2026 dans `data/raw/boamp_ao_en_cours.json` de l'arbre SERVI. Les
    deux témoins ci-dessous en sont copiés.
    """
    assert assainir_texte_integral("Côte d\xe2\x80\x99Ivoire") == "Côte d’Ivoire"
    # Cas réels de l'export BOAMP du 30/08/2026 :
    assert assainir_texte_integral("Fort\xe2\x80\x91de\xe2\x80\x91France") == "Fort‑de‑France"
    assert assainir_texte_integral("Lot 8\xe2\x80\xaf: VRD") == "Lot 8 : VRD"
    temoins = (
        "Côte d\xe2\x80\x99Ivoire",
        "Lot 8\xe2\x80\xaf: VRD",
        "PRIXÂ\x92",
        "dejÃ\xa0 enregistrée",
        "RAPPORT\x85 ANNEXE",
        "LEVALLOIS AU C\x8cUR",
        "  Marché   public \n",
        "BÂTIMENT",
        "",
    )
    for brut in temoins:
        une = assainir_texte_integral(brut)
        assert assainir_texte_integral(une) == une, brut


def test_assainir_texte_integral_ne_touche_pas_au_texte_sain():
    """La moitié qui compte : ce qui ne doit PAS bouger."""
    for sain in (
        "Marché public de travaux",
        "BÂTIMENT",
        "CHÂTEAU",
        "Théâtre de l’Odéon",
        "Côte d’Ivoire",
        "lot n° 5",
        "SANTÉ : lot n°1",
    ):
        assert assainir_texte_integral(sain) == sain


def test_assainir_texte_integral_laisse_les_octets_sans_equivalent_cp1252():
    """Le critère d'acceptation est « plus aucun Cc de la plage cp1252
    ATTRIBUÉE », jamais « plus aucun Cc » : cinq octets n'ont aucune
    affectation en cp1252 et sortent intacts, par spécification."""
    for octet in (0x81, 0x8D, 0x8F, 0x90, 0x9D):
        assert assainir_texte_integral("A" + chr(octet) + "B") == "A" + chr(octet) + "B"


def test_assainir_texte_NE_repare_TOUJOURS_PAS_les_controles_c1():
    """CONTRE-ÉPREUVE de non-régression : ajouter `assainir_texte_integral` ne
    devait rien changer à `assainir_texte`, dont sept pipelines dépendent."""
    assert assainir_texte("LEVALLOIS AU C\x8cUR") == "LEVALLOIS AU C\x8cUR"
    assert assainir_texte_integral("LEVALLOIS AU C\x8cUR") == "LEVALLOIS AU CŒUR"


def test_assainir_texte_integral_ne_regenere_aucun_controle():
    """MUTATION TUÉE : point fixe réduit à DEUX passages.

    C'est le piège symétrique du composite, et il mord dans l'autre sens : sur
    « Â » + U+0092, le premier passage ne voit rien (U+0092 n'a pas d'encodage
    cp1252, l'aller-retour de `reparer_mojibake` échoue), la réparation des C1
    rend « Â’ », le second passage de `reparer_mojibake` en refait **un
    contrôle** U+0092 — et une hygiène s'arrêtant là RÉGÉNÉRERAIT le défaut
    qu'elle est censée supprimer. Seul le point fixe le reprend.

    Le critère est formulé juste : « plus aucun Cc DE LA PLAGE CP1252
    ATTRIBUÉE », jamais « plus aucun Cc » — les cinq octets sans affectation
    sortent intacts par spécification (test voisin).
    """
    assert assainir_texte_integral("PRIXÂ\x92") == "PRIX’"
    reparables = {chr(o) for o in range(0x80, 0xA0)} - {
        chr(o) for o in (0x81, 0x8D, 0x8F, 0x90, 0x9D)
    }
    for brut in ("PRIXÂ\x92", "Côte d\xe2\x80\x99Ivoire", "B\xc2\x85 test"):
        sortie = assainir_texte_integral(brut)
        assert not (set(sortie) & reparables), (brut, sortie)
    # … et l'instrument n'est pas muet : il voit bien un C1 réparable non traité
    assert set("PRIX\x92") & reparables
