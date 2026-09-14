-- ============================================================================
-- PIZZERIA DA GIGI — DATI DI PARTENZA (seed)
-- ============================================================================
-- Esegui DOPO schema.sql e funzioni.sql. Popola il database con il MENU REALE
-- (le 40 pizze già scritte in templates/menu.html, con i prezzi Grande e
-- Piccola), l'elenco ingredienti ricavato dalla composizione di ciascuna
-- pizza, e le ricette che li collegano.
--
-- Le quantità per-pizza nelle ricette e le scorte di partenza sono valori
-- ragionevoli di avvio, NON un dato scientifico — dopo qualche settimana di
-- vendite reali, aggiustale sui consumi effettivi (bastano UPDATE su
-- ingredienti/ricette, lo schema non cambia).
--
-- Nota sulla ricetta unica per formato: farina e olio non compaiono nelle
-- ricette (sono ingredienti "di base" sempre tracciati ma non specifici di
-- una pizza, come nel documento di architettura); ogni pizza usa la STESSA
-- ricetta sia in versione Grande che Piccola (vedi il commento in
-- schema.sql). Puoi rieseguire questo intero file in sicurezza: cancella e
-- ricrea gli stessi dati.
-- ============================================================================

truncate table ordini, ricette, pizze, ingredienti restart identity cascade;

-- ----------------------------------------------------------------------------
-- Ingredienti (scorta di partenza per una giornata piena + soglia di allarme)
-- ----------------------------------------------------------------------------
insert into ingredienti (nome, quantita_disponibile, quantita_iniziale, unita_misura, soglia_allarme) values
  ('Farina 00',                     9,    9,    'kg',          2),
  ('Olio extravergine',             1,    1,    'L',           0.2),
  ('Pomodoro',                      4,    4,    'kg',          1),
  ('Mozzarella fior di latte',      5,    5,    'kg',          1),
  ('Aglio',                         0.3,  0.3,  'kg',          0.05),
  ('Origano secco',                 1,    1,    'confezioni',  1),
  ('Acciughe',                      0.6,  0.6,  'kg',          0.15),
  ('Capperi',                       0.3,  0.3,  'kg',          0.1),
  ('Salsiccia',                     2,    2,    'kg',          0.4),
  ('Cipolla rossa',                 1,    1,    'kg',          0.2),
  ('Prosciutto cotto',              1.5,  1.5,  'kg',          0.3),
  ('Funghi champignon',             1.5,  1.5,  'kg',          0.3),
  ('Carciofi',                      1.2,  1.2,  'kg',          0.3),
  ('Uovo',                          24,   24,   'pezzi',       6),
  ('Olive nere',                    1,    1,    'kg',          0.2),
  ('Würstel',                       1,    1,    'kg',          0.2),
  ('Bacon',                         1,    1,    'kg',          0.2),
  ('Salame piccante',               1,    1,    'kg',          0.3),
  ('Pancetta',                      1,    1,    'kg',          0.2),
  ('Pecorino',                      0.8,  0.8,  'kg',          0.15),
  ('Peperoncino',                   0.2,  0.2,  'kg',          0.05),
  ('Ricotta',                       1,    1,    'kg',          0.2),
  ('Gorgonzola',                    1,    1,    'kg',          0.2),
  ('Grana / Parmigiano',            0.8,  0.8,  'kg',          0.15),
  ('Provola',                       1,    1,    'kg',          0.2),
  ('Pesto',                         0.5,  0.5,  'kg',          0.1),
  ('Verdure miste',                 1.5,  1.5,  'kg',          0.3),
  ('Tonno',                         0.8,  0.8,  'kg',          0.2),
  ('Funghi porcini',                0.6,  0.6,  'kg',          0.15),
  ('Speck',                         0.8,  0.8,  'kg',          0.2),
  ('Patate',                        2,    2,    'kg',          0.4),
  ('Rosmarino',                     0.2,  0.2,  'kg',          0.05),
  ('Bresaola',                      0.6,  0.6,  'kg',          0.15),
  ('Rucola',                        0.5,  0.5,  'kg',          0.1),
  ('Prosciutto crudo San Daniele',  0.6,  0.6,  'kg',          0.15),
  ('Salmone affumicato',            0.6,  0.6,  'kg',          0.15),
  ('Frutti di mare',                0.8,  0.8,  'kg',          0.2),
  ('Carne di cavallo',              0.6,  0.6,  'kg',          0.15);

-- ----------------------------------------------------------------------------
-- Panetti di oggi (Gigi li aggiornerà ogni mattina dalla dashboard)
-- ----------------------------------------------------------------------------
insert into panetti (data, quantita_preparati, quantita_utilizzati)
values (current_date, 40, 0)
on conflict (data) do update set quantita_preparati = excluded.quantita_preparati;

-- ----------------------------------------------------------------------------
-- Il menu — stessi numero/nome/prezzi di templates/menu.html
-- ----------------------------------------------------------------------------
insert into pizze (numero_menu, nome, descrizione, prezzo_grande, prezzo_piccola, categoria) values
  (1,  'Marinara',          'Pomodoro, aglio, origano',                                          3.50, 2.50, 'classica'),
  (2,  'Margherita',        'Pomodoro, mozzarella',                                              4.50, 3.00, 'classica'),
  (3,  'Romana',            'Pomodoro, mozzarella, acciughe, capperi',                            5.00, 3.50, 'classica'),
  (4,  'Toscana',           'Pomodoro, mozzarella, salsiccia, cipolla',                            5.00, 3.50, 'classica'),
  (5,  'Completa',          'Pomodoro, mozzarella, funghi, carciofi, prosciutto, uovo',            5.00, 3.50, 'classica'),
  (6,  'Imperiale',         'Pomodoro, mozzarella, prosciutto, funghi, carciofi, olive',           6.00, 4.00, 'gourmet'),
  (7,  'Cardinale',         'Pomodoro, mozzarella, acciughe, capperi, olive',                      6.00, 4.00, 'classica'),
  (8,  'Veneziana',         'Pomodoro, mozzarella, cipolla, acciughe',                             6.50, 4.50, 'classica'),
  (9,  'Wurstel',           'Pomodoro, mozzarella, wurstel',                                       5.00, 4.00, 'classica'),
  (10, 'Canadese',          'Pomodoro, mozzarella, bacon, cipolla',                                6.00, 4.00, 'classica'),
  (11, 'Diavola',           'Pomodoro, mozzarella, salame piccante',                               6.00, 4.00, 'piccante'),
  (12, 'Salsiccia',         'Pomodoro, mozzarella, salsiccia',                                     6.50, 4.50, 'classica'),
  (13, 'Sarda',             'Pomodoro, mozzarella, pancetta, cipolla, pecorino',                   7.00, 4.50, 'gourmet'),
  (14, 'Boscanola',         'Pomodoro, mozzarella, funghi, salsiccia',                             7.00, 5.00, 'classica'),
  (15, 'Arrabbiata',        'Pomodoro, mozzarella, salame piccante, peperoncino',                  7.00, 5.00, 'piccante'),
  (16, 'Quattro Stagioni',  'Pomodoro, mozzarella, prosciutto, funghi, carciofi, olive',           6.50, 5.00, 'gourmet'),
  (17, 'Capricciosa',       'Pomodoro, mozzarella, prosciutto, funghi, carciofi, olive, uovo',     7.00, 5.00, 'gourmet'),
  (18, 'Tucano',            'Pomodoro, mozzarella, prosciutto cotto, funghi',                      6.00, 4.00, 'classica'),
  (19, 'Calzone',           'Pomodoro, mozzarella, prosciutto, ricotta (chiusa)',                  6.50, 4.50, 'classica'),
  (20, 'Calzone Farcito',   'Pomodoro, mozzarella, prosciutto, ricotta, funghi (chiusa)',          7.00, 5.00, 'classica'),
  (21, 'Gorgonzola',        'Pomodoro, mozzarella, gorgonzola',                                    6.50, 4.50, 'gourmet'),
  (22, 'Quattro Formaggi',  'Pomodoro, mozzarella, gorgonzola, parmigiano, provola',               7.00, 5.00, 'gourmet'),
  (23, 'Pesto',             'Pomodoro, mozzarella, pesto',                                         8.50, 4.50, 'gourmet'),
  (24, 'Sassarese',         'Pomodoro, mozzarella, salsiccia, cipolla, pancetta',                  6.00, 4.00, 'classica'),
  (25, 'Greca',             'Pomodoro, mozzarella, olive, cipolla, origano',                       6.00, 4.00, 'classica'),
  (26, 'Ortolana',          'Pomodoro, mozzarella, verdure grigliate',                             7.00, 5.00, 'classica'),
  (27, 'Antunna',           'Pomodoro, mozzarella, tonno, cipolla',                                6.50, 4.50, 'classica'),
  (28, 'Porcini',           'Pomodoro, mozzarella, funghi porcini',                                7.50, 5.50, 'gourmet'),
  (29, 'Tirolese',          'Pomodoro, mozzarella, speck, cipolla',                                8.00, 6.00, 'gourmet'),
  (30, 'Patatosa',          'Pomodoro, mozzarella, patate, rosmarino',                             6.00, 4.00, 'classica'),
  (31, 'Furia',             'Pomodoro, mozzarella, salame piccante, olive, peperoncino',           7.00, 5.00, 'piccante'),
  (32, 'Bresaola',          'Pomodoro, mozzarella, bresaola, rucola, scaglie di grana',            7.00, 5.00, 'gourmet'),
  (33, 'San Daniele',       'Pomodoro, mozzarella, prosciutto crudo San Daniele, rucola',          7.00, 5.00, 'gourmet'),
  (34, 'Primavera',         'Pomodoro, mozzarella, verdure di stagione',                           8.00, 3.50, 'classica'),
  (35, 'Logudoresse',       'Pomodoro, mozzarella, salsiccia, funghi, carciofi',                   7.50, 5.50, 'classica'),
  (36, 'Salmone',           'Pomodoro, mozzarella, salmone affumicato',                            7.50, 5.50, 'gourmet'),
  (37, 'Catalana',          'Pomodoro, mozzarella, acciughe, capperi, olive, origano',             7.00, 5.50, 'classica'),
  (38, 'Carbonara',         'Pomodoro, mozzarella, uovo, pancetta, pecorino',                      7.50, 5.50, 'gourmet'),
  (39, 'Mare e Monti',      'Pomodoro, mozzarella, frutti di mare, funghi',                        8.00, 5.00, 'gourmet'),
  (40, 'Campagnola',        'Pomodoro, mozzarella, cavallo, patate al forno',                      7.50, 6.50, 'classica');

-- ----------------------------------------------------------------------------
-- Ricette: quali ingredienti — e quanti — usa ciascuna pizza
-- (ricavate dalla colonna "composizione" del menu reale)
-- ----------------------------------------------------------------------------
insert into ricette (pizza_id, ingrediente_id, quantita_necessaria)
select p.id, i.id, v.qta
from (values
  ('Marinara',          'Pomodoro',                       0.07),
  ('Marinara',          'Aglio',                           0.004),
  ('Marinara',          'Origano secco',                   0.01),

  ('Margherita',        'Pomodoro',                       0.07),
  ('Margherita',        'Mozzarella fior di latte',        0.09),

  ('Romana',            'Pomodoro',                       0.07),
  ('Romana',            'Mozzarella fior di latte',        0.09),
  ('Romana',            'Acciughe',                        0.03),
  ('Romana',            'Capperi',                         0.015),

  ('Toscana',           'Pomodoro',                       0.07),
  ('Toscana',           'Mozzarella fior di latte',        0.09),
  ('Toscana',           'Salsiccia',                       0.06),
  ('Toscana',           'Cipolla rossa',                   0.03),

  ('Completa',          'Pomodoro',                       0.07),
  ('Completa',          'Mozzarella fior di latte',        0.09),
  ('Completa',          'Funghi champignon',               0.04),
  ('Completa',          'Carciofi',                        0.04),
  ('Completa',          'Prosciutto cotto',                0.05),
  ('Completa',          'Uovo',                            1),

  ('Imperiale',         'Pomodoro',                       0.07),
  ('Imperiale',         'Mozzarella fior di latte',        0.09),
  ('Imperiale',         'Prosciutto cotto',                0.05),
  ('Imperiale',         'Funghi champignon',               0.04),
  ('Imperiale',         'Carciofi',                        0.04),
  ('Imperiale',         'Olive nere',                      0.02),

  ('Cardinale',         'Pomodoro',                       0.07),
  ('Cardinale',         'Mozzarella fior di latte',        0.09),
  ('Cardinale',         'Acciughe',                        0.03),
  ('Cardinale',         'Capperi',                         0.015),
  ('Cardinale',         'Olive nere',                      0.02),

  ('Veneziana',         'Pomodoro',                       0.07),
  ('Veneziana',         'Mozzarella fior di latte',        0.09),
  ('Veneziana',         'Cipolla rossa',                   0.03),
  ('Veneziana',         'Acciughe',                        0.03),

  ('Wurstel',           'Pomodoro',                       0.07),
  ('Wurstel',           'Mozzarella fior di latte',        0.09),
  ('Wurstel',           'Würstel',                         0.06),

  ('Canadese',          'Pomodoro',                       0.07),
  ('Canadese',          'Mozzarella fior di latte',        0.09),
  ('Canadese',          'Bacon',                           0.05),
  ('Canadese',          'Cipolla rossa',                   0.03),

  ('Diavola',           'Pomodoro',                       0.07),
  ('Diavola',           'Mozzarella fior di latte',        0.09),
  ('Diavola',           'Salame piccante',                 0.05),

  ('Salsiccia',         'Pomodoro',                       0.07),
  ('Salsiccia',         'Mozzarella fior di latte',        0.09),
  ('Salsiccia',         'Salsiccia',                       0.07),

  ('Sarda',             'Pomodoro',                       0.07),
  ('Sarda',             'Mozzarella fior di latte',        0.09),
  ('Sarda',             'Pancetta',                        0.05),
  ('Sarda',             'Cipolla rossa',                   0.03),
  ('Sarda',             'Pecorino',                        0.03),

  ('Boscanola',         'Pomodoro',                       0.07),
  ('Boscanola',         'Mozzarella fior di latte',        0.09),
  ('Boscanola',         'Funghi champignon',               0.05),
  ('Boscanola',         'Salsiccia',                       0.06),

  ('Arrabbiata',        'Pomodoro',                       0.07),
  ('Arrabbiata',        'Mozzarella fior di latte',        0.09),
  ('Arrabbiata',        'Salame piccante',                 0.05),
  ('Arrabbiata',        'Peperoncino',                     0.005),

  ('Quattro Stagioni',  'Pomodoro',                       0.07),
  ('Quattro Stagioni',  'Mozzarella fior di latte',        0.09),
  ('Quattro Stagioni',  'Prosciutto cotto',                0.05),
  ('Quattro Stagioni',  'Funghi champignon',               0.04),
  ('Quattro Stagioni',  'Carciofi',                        0.04),
  ('Quattro Stagioni',  'Olive nere',                      0.02),

  ('Capricciosa',       'Pomodoro',                       0.07),
  ('Capricciosa',       'Mozzarella fior di latte',        0.09),
  ('Capricciosa',       'Prosciutto cotto',                0.05),
  ('Capricciosa',       'Funghi champignon',               0.04),
  ('Capricciosa',       'Carciofi',                        0.04),
  ('Capricciosa',       'Olive nere',                      0.02),
  ('Capricciosa',       'Uovo',                            1),

  ('Tucano',            'Pomodoro',                       0.07),
  ('Tucano',            'Mozzarella fior di latte',        0.09),
  ('Tucano',            'Prosciutto cotto',                0.06),
  ('Tucano',            'Funghi champignon',               0.04),

  ('Calzone',           'Pomodoro',                       0.07),
  ('Calzone',           'Mozzarella fior di latte',        0.09),
  ('Calzone',           'Prosciutto cotto',                0.05),
  ('Calzone',           'Ricotta',                         0.06),

  ('Calzone Farcito',   'Pomodoro',                       0.07),
  ('Calzone Farcito',   'Mozzarella fior di latte',        0.09),
  ('Calzone Farcito',   'Prosciutto cotto',                0.05),
  ('Calzone Farcito',   'Ricotta',                         0.06),
  ('Calzone Farcito',   'Funghi champignon',               0.04),

  ('Gorgonzola',        'Pomodoro',                       0.07),
  ('Gorgonzola',        'Mozzarella fior di latte',        0.09),
  ('Gorgonzola',        'Gorgonzola',                      0.06),

  ('Quattro Formaggi',  'Pomodoro',                       0.07),
  ('Quattro Formaggi',  'Mozzarella fior di latte',        0.09),
  ('Quattro Formaggi',  'Gorgonzola',                      0.04),
  ('Quattro Formaggi',  'Grana / Parmigiano',              0.03),
  ('Quattro Formaggi',  'Provola',                         0.04),

  ('Pesto',             'Pomodoro',                       0.07),
  ('Pesto',             'Mozzarella fior di latte',        0.09),
  ('Pesto',             'Pesto',                           0.03),

  ('Sassarese',         'Pomodoro',                       0.07),
  ('Sassarese',         'Mozzarella fior di latte',        0.09),
  ('Sassarese',         'Salsiccia',                       0.05),
  ('Sassarese',         'Cipolla rossa',                   0.02),
  ('Sassarese',         'Pancetta',                        0.04),

  ('Greca',             'Pomodoro',                       0.07),
  ('Greca',             'Mozzarella fior di latte',        0.09),
  ('Greca',             'Olive nere',                      0.02),
  ('Greca',             'Cipolla rossa',                   0.03),
  ('Greca',             'Origano secco',                   0.01),

  ('Ortolana',          'Pomodoro',                       0.07),
  ('Ortolana',          'Mozzarella fior di latte',        0.09),
  ('Ortolana',          'Verdure miste',                   0.12),

  ('Antunna',           'Pomodoro',                       0.07),
  ('Antunna',           'Mozzarella fior di latte',        0.09),
  ('Antunna',           'Tonno',                           0.06),
  ('Antunna',           'Cipolla rossa',                   0.03),

  ('Porcini',           'Pomodoro',                       0.07),
  ('Porcini',           'Mozzarella fior di latte',        0.09),
  ('Porcini',           'Funghi porcini',                  0.06),

  ('Tirolese',          'Pomodoro',                       0.07),
  ('Tirolese',          'Mozzarella fior di latte',        0.09),
  ('Tirolese',          'Speck',                           0.05),
  ('Tirolese',          'Cipolla rossa',                   0.03),

  ('Patatosa',          'Pomodoro',                       0.07),
  ('Patatosa',          'Mozzarella fior di latte',        0.09),
  ('Patatosa',          'Patate',                          0.10),
  ('Patatosa',          'Rosmarino',                       0.005),

  ('Furia',             'Pomodoro',                       0.07),
  ('Furia',             'Mozzarella fior di latte',        0.09),
  ('Furia',             'Salame piccante',                 0.05),
  ('Furia',             'Olive nere',                      0.02),
  ('Furia',             'Peperoncino',                     0.005),

  ('Bresaola',          'Pomodoro',                       0.07),
  ('Bresaola',          'Mozzarella fior di latte',        0.09),
  ('Bresaola',          'Bresaola',                        0.05),
  ('Bresaola',          'Rucola',                          0.02),
  ('Bresaola',          'Grana / Parmigiano',              0.02),

  ('San Daniele',       'Pomodoro',                       0.07),
  ('San Daniele',       'Mozzarella fior di latte',        0.09),
  ('San Daniele',       'Prosciutto crudo San Daniele',    0.05),
  ('San Daniele',       'Rucola',                          0.02),

  ('Primavera',         'Pomodoro',                       0.07),
  ('Primavera',         'Mozzarella fior di latte',        0.09),
  ('Primavera',         'Verdure miste',                   0.12),

  ('Logudoresse',       'Pomodoro',                       0.07),
  ('Logudoresse',       'Mozzarella fior di latte',        0.09),
  ('Logudoresse',       'Salsiccia',                       0.05),
  ('Logudoresse',       'Funghi champignon',               0.04),
  ('Logudoresse',       'Carciofi',                        0.04),

  ('Salmone',           'Pomodoro',                       0.07),
  ('Salmone',           'Mozzarella fior di latte',        0.09),
  ('Salmone',           'Salmone affumicato',              0.06),

  ('Catalana',          'Pomodoro',                       0.07),
  ('Catalana',          'Mozzarella fior di latte',        0.09),
  ('Catalana',          'Acciughe',                        0.03),
  ('Catalana',          'Capperi',                         0.015),
  ('Catalana',          'Olive nere',                      0.02),
  ('Catalana',          'Origano secco',                   0.01),

  ('Carbonara',         'Pomodoro',                       0.07),
  ('Carbonara',         'Mozzarella fior di latte',        0.09),
  ('Carbonara',         'Uovo',                            1),
  ('Carbonara',         'Pancetta',                        0.05),
  ('Carbonara',         'Pecorino',                        0.03),

  ('Mare e Monti',      'Pomodoro',                       0.07),
  ('Mare e Monti',      'Mozzarella fior di latte',        0.09),
  ('Mare e Monti',      'Frutti di mare',                  0.08),
  ('Mare e Monti',      'Funghi champignon',               0.04),

  ('Campagnola',        'Pomodoro',                       0.07),
  ('Campagnola',        'Mozzarella fior di latte',        0.09),
  ('Campagnola',        'Carne di cavallo',                0.08),
  ('Campagnola',        'Patate',                          0.10)
) as v(pizza_nome, ingrediente_nome, qta)
join pizze p on p.nome = v.pizza_nome
join ingredienti i on i.nome = v.ingrediente_nome;

-- Applica subito le regole automatiche ai dati appena inseriti.
select recalcola_disponibilita_pizze();
