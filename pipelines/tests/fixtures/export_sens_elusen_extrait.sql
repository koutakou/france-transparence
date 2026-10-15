-- Extrait export_sens (dump PostgreSQL du Sénat, UTF-8), tables dpt et elusen.
-- data.senat.fr/data/senateurs/export_sens.zip, Last-Modified 15/10/2026 01:47 GMT.
-- Lignes réelles, copiées telles quelles : 21071F (mandat ouvert en 2023),
-- 20032T (réélu : mandat clos le 30/09/2026 puis mandat ouvert le 01/10/2026),
-- 21686H (entrant du 01/10/2026), 14133K (sortant au 30/09/2026),
-- 83008P (ancien, deux mandats clos). Table `dpt` (codes des départements
-- du Sénat) réduite aux cinq lignes que ces mandats référencent, telle quelle.

COPY dpt (dptnum, dptcod, dptlib, dptnbrsen, dptmodscrsen, dptser, regcod, dptnumtri, dptlic, dptart, dptlibtri, temvalcod, evelic, evelib, evelil, dptser2004, dptcmt, dptdatdeb, dptdatfin, dpturlcmp, syscredat, sysmajdat) FROM stdin;
973	973	Guyane	2	SM	A	51	972	Guyane	de la 	Guyane	ACTIF	Guyane	Guyane	Guyane	2	\N	1959-04-28 00:00:00	\N	\N	\N	\N
335	92	Hauts-de-Seine	7	RP	C	10	920	Hauts-de-Seine	des 	Hauts-de-Seine	ACTIF	Hauts-de-Seine	Hauts-de-Seine	Hauts-de-Seine	1	\N	1968-01-01 00:00:00	\N	http://www.cg92.fr/	\N	\N
650	65	Hautes-Pyrénées	2	SM	B	29	650	Hautes-Pyrénées	des 	Pyrénées Hautes	ACTIF	Hautes-Pyrénées	Hautes-Pyrénées	Hautes-Pyrénées	1	\N	1959-04-28 00:00:00	\N	http://www.cg65.fr/	\N	\N
120	12	Aveyron	2	SM	A	29	120	Aveyron	de l'	Aveyron	ACTIF	Aveyron	Aveyron	Aveyron	2	\N	1959-04-28 00:00:00	\N	http://www.cg12.fr/	\N	\N
140	14	Calvados	3	RP	A	25	140	Calvados	du 	Calvados	ACTIF	Calvados	Calvados	Calvados	2	\N	1959-04-28 00:00:00	\N	http://www.calvados.fr	\N	\N
\.

COPY elusen (eluid, dptnum, eludatdeb, eludatelu, eludatfin, etadebmancod, etafinmancod, temvalcod, evelic, evelib, evelil, eluanndeb, eluannfin, typmancod, senmat, eludatcum, turelucod, syscredat, sysmajdat) FROM stdin;
53297	335	2023-10-02 00:00:00	2023-09-24 00:00:00	\N	ELECTION	ACTIF	ACTIF	\N	\N	\N	\N	\N	SENAT	21071F	\N	NR	\N	\N
51850	120	2020-10-01 00:00:00	2020-09-27 00:00:00	2026-09-30 00:00:00	ELECTION	FINMAN	ANCIEN	\N	Nouveau	\N	\N	\N	\N	20032T	\N	SM1	\N	2026-09-27 13:15:39
54977	120	2026-10-01 00:00:00	2026-09-27 00:00:00	\N	REN1	ACTIF	ACTIF	\N	\N	\N	\N	\N	SENAT	20032T	\N	NR	2026-09-27 13:15:39	2026-09-27 13:15:39
55064	973	2026-10-01 00:00:00	2026-09-27 00:00:00	\N	ELECTION	ACTIF	ACTIF	\N	\N	\N	\N	\N	SENAT	21686H	\N	NR	2026-09-27 19:33:12	2026-09-27 19:33:12
14088	140	2014-10-01 00:00:00	2014-09-28 00:00:00	2020-09-30 00:00:00	ELECTION	FINMAN	ANCIEN	\N	Nouveau	\N	\N	\N	SENAT	14133K	\N	RP	2014-09-28 16:42:03	\N
51865	140	2020-10-01 00:00:00	2020-09-27 00:00:00	2026-09-30 00:00:00	REN	NONREP	ANCIEN	\N	Nouveau	\N	\N	\N	\N	14133K	\N	RP	\N	2026-09-27 10:09:18
1	650	1983-10-03 00:00:00	1983-09-25 00:00:00	1992-10-01 00:00:00	ELECTION	FINMAN	ANCIEN	\N	\N	\N	\N	\N	SENAT	83008P	\N	NR	\N	\N
2	650	1992-10-02 00:00:00	1992-09-27 00:00:00	2001-03-02 00:00:00	REN1	DECEDE	ANCIEN	\N	\N	\N	\N	2001	SENAT	83008P	\N	NR	\N	\N
\.
