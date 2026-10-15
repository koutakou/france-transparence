-- Extrait export_sens (dump PostgreSQL du Sénat, UTF-8), table elusen seulement.
-- data.senat.fr/data/senateurs/export_sens.zip, Last-Modified 15/10/2026 01:47 GMT.
-- Lignes réelles, copiées telles quelles : 21071F (mandat ouvert en 2023),
-- 20032T (réélu : mandat clos le 30/09/2026 puis mandat ouvert le 01/10/2026),
-- 21686H (entrant du 01/10/2026), 14133K (sortant au 30/09/2026),
-- 83008P (ancien, deux mandats clos).

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
