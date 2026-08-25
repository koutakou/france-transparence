-- Extrait Dosleg (COPY PostgreSQL, UTF-8). Gabarit réel du dump
-- data.senat.fr/data/dosleg/dosleg.zip (Last-Modified 25/08/2026).
-- Tables scr + votsen seulement ; posvot documente le code de position.
-- Pas le zip de 16 Mo.

COPY posvot (posvotcod, posvotlib) FROM stdin;
1	pour
2	contre
3	abstention
4	non-votant
\.

COPY scr (sesann, scrnum, scrint, scrdat, scrpou, scrcon, scrvot, scrsuf, scrmaj, soslib, scrjso) FROM stdin;
2024	1	hors fenêtre glissante	2024-01-10 00:00:00	10	5	16	15	0	\N	I
2025	338	sur l'ensemble du projet de loi visant à offrir des réponses immédiates aux phénomènes troublant lordre public	2026-07-21 00:00:00	235	34	345	269	0	\N	N
2025	339	sur l'ensemble de la proposition de loi pour une montagne vivante et souveraine	2026-07-21 00:00:00	325	16	341	341	0	\N	N
2025	340	sur l'ensemble du projet de loi d'urgence pour la protection et la souveraineté agricoles	2026-07-21 00:00:00	214	111	345	325	0	\N	N
\.

COPY votsen (sesann, scrnum, senmat, posvotcod, titsencod, stavotidt, senmatdel, votsenmar) FROM stdin;
2024	1	21071F	1	0	0	\N	\N
2025	338	21071F	1	0	0	\N	\N
2025	338	19489J	2	0	0	\N	\N
2025	338	01008M	3	0	0	\N	\N
2025	338	98046X	4	0	8	\N	\N
2025	339	21071F	1	0	0	\N	\N
2025	339	19489J	1	0	0	11060J	\N
2025	339	01008M	4	0	0	\N	\N
2025	340	21071F	1	0	0	\N	\N
2025	340	19489J	2	0	0	\N	\N
2025	340	01008M	1	0	0	\N	\N
2025	340	98046X 	4	0	0	\N	\N
\.
