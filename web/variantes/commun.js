/*
 * Culture Centro — données et utilitaires communs aux variantes de maquette.
 *
 * Toutes les variantes (web/variantes/v*.html) lisent ce même jeu de
 * démonstration afin que seule la présentation change d'une variante à
 * l'autre. Les données sont fictives. Par rapport à la maquette principale
 * (web/index.html), le jeu est enrichi de trois notions à valider avec le
 * client :
 *   - activités récurrentes (SERIES : « tous les mardis », « 3e jeudi du mois ») ;
 *   - niveaux de partenaires (tier : principal / reseau / soutien) ;
 *   - attributs pratiques (prix, gratuit, famille, vedette).
 */
window.CC = (function () {
  "use strict";

  // « Aujourd'hui » de la démo : un jeudi, pour que « ce soir » et
  // « ce week-end » aient du contenu.
  var TODAY = new Date(2026, 9, 1);

  var DISC = {
    theatre:  { label: "Théâtre",      color: "#D6435A" },
    musique:  { label: "Musique",      color: "#6C5CE7" },
    arts:     { label: "Arts visuels", color: "#159A8A" },
    festival: { label: "Festivals",    color: "#E39A2B" },
    danse:    { label: "Danse",        color: "#C24E8E" },
    litt:     { label: "Littérature",  color: "#3D7DCA" },
    humour:   { label: "Humour",       color: "#E0672F" },
    jeunesse: { label: "Jeunesse",     color: "#4CAF50" }
  };

  // Partenaires : liste de docs/partenaires.md. Les niveaux (tier) sont une
  // hypothèse de maquette à valider. x / y : position sur le plan
  // schématique de la variante 4 (0–100, non à l'échelle).
  var PARTNERS = [
    { id:"granada",   name:"Théâtre Granada",                    short:"Granada",        kind:"Salle patrimoniale",          tier:"principal", d:"theatre",  url:"https://theatregranada.com",          x:52, y:40 },
    { id:"grandesp",  name:"Le Grand-Espace",                    short:"Grand-Espace",   kind:"Théâtre · danse",             tier:"principal", d:"danse",    url:"https://legrandespace.ca",            x:40, y:58 },
    { id:"mbas",      name:"Musée des beaux-arts de Sherbrooke", short:"MBAS",           kind:"Musée",                       tier:"principal", d:"arts",     url:"https://mbas.qc.ca",                  x:62, y:27 },
    { id:"sporobole", name:"Sporobole",                          short:"Sporobole",      kind:"Centre en art actuel",        tier:"principal", d:"arts",     url:"https://sporobole.org",               x:30, y:33 },
    { id:"pbn",       name:"La Petite Boîte Noire",              short:"Petite Boîte Noire", kind:"Salle indépendante",      tier:"reseau",    d:"musique",  url:"https://lapetiteboitenoire.com",      x:56, y:52 },
    { id:"tremplin",  name:"Le Tremplin 16-30",                  short:"Tremplin",       kind:"Diffusion de la relève",      tier:"reseau",    d:"musique",  url:"https://tremplin16-30.com",           x:70, y:62 },
    { id:"map",       name:"Maison des arts de la parole",       short:"Arts de la parole", kind:"Conte · poésie",           tier:"reseau",    d:"litt",     url:"https://maisondesartsdelaparole.com", x:46, y:22 },
    { id:"cafe440",   name:"Café 440",                           short:"Café 440",       kind:"Café-spectacle",              tier:"reseau",    d:"humour",   url:"https://lecafe440sherbrooke.com",     x:64, y:46 },
    { id:"doublesigne", name:"Théâtre du Double signe",          short:"Double signe",   kind:"Théâtre de création",         tier:"reseau",    d:"theatre",  url:"https://www.doublesigne.ca",          x:24, y:52 },
    { id:"petittheatre", name:"Le Petit Théâtre de Sherbrooke",  short:"Petit Théâtre",  kind:"Jeune public",                tier:"reseau",    d:"jeunesse", url:"https://www.petittheatre.qc.ca",      x:34, y:72 },
    { id:"biblio",    name:"Bibliothèque Éva-Senécal",           short:"Éva-Senécal",    kind:"Bibliothèque",                tier:"reseau",    d:"litt",     url:"https://bibliotheques.sherbrooke.ca", x:76, y:36 },
    { id:"ccudes",    name:"Centre culturel de l'UdeS",          short:"Centre culturel UdeS", kind:"Salle Maurice-O'Bready", tier:"reseau",  d:"musique",  url:"https://www.centrecultureludes.ca",   x:90, y:84 },
    { id:"acvs",      name:"Animation Centre-Ville",             short:"ACVS",           kind:"Événements extérieurs",       tier:"soutien",   d:"festival", url:"#",                                   x:50, y:70 },
    { id:"cultureestrie", name:"Culture Estrie",                 short:"Culture Estrie", kind:"Organisme régional",          tier:"soutien",   d:"arts",     url:"https://cultureestrie.org",           x:null, y:null }
  ];

  // Événements ponctuels et de longue durée (dateEnd). venue : lieu quand
  // l'événement se tient hors les murs du partenaire.
  var EVENTS = [
    { d:"arts",     title:"Exposition « Territoires »",           p:"mbas",      date:"2026-09-20", dateEnd:"2026-11-15", time:"10 h – 17 h", prix:"12 $", vedette:true, desc:"Le paysage estrien vu par une dizaine d'artistes contemporains." },
    { d:"arts",     title:"Installations sonores",                p:"sporobole", date:"2026-09-24", dateEnd:"2026-10-10", time:"12 h – 17 h", prix:"Gratuit", desc:"Parcours immersif dans l'espace de la galerie." },
    { d:"litt",     title:"Rencontre d'autrice : Kim Thúy",       p:"biblio",    date:"2026-10-01", time:"19 h 00", prix:"Gratuit", desc:"Lecture et discussion suivies d'une séance de dédicaces." },
    { d:"musique",  title:"Soirée jazz manouche",                 p:"pbn",       date:"2026-10-01", time:"21 h 00", prix:"20 $", desc:"Trio de guitares dans l'esprit de Django Reinhardt, ambiance intime." },
    { d:"festival", title:"Festival des traditions du monde",     p:"acvs",      venue:"Parc Jacques-Cartier", date:"2026-10-02", dateEnd:"2026-10-04", time:"Dès 11 h", prix:"Gratuit", famille:true, vedette:true, desc:"Musiques, danses et cuisines d'ici et d'ailleurs, trois jours durant." },
    { d:"theatre",  title:"Les Belles-Sœurs",                     p:"granada",   date:"2026-10-03", time:"20 h 00", prix:"48 $", vedette:true, desc:"Le classique de Michel Tremblay dans une nouvelle mise en scène." },
    { d:"jeunesse", title:"Le Petit Prince",                      p:"petittheatre", date:"2026-10-04", time:"14 h 00", prix:"15 $", famille:true, desc:"Adaptation familiale, à partir de 6 ans." },
    { d:"musique",  title:"OSSH — Nuit romantique",               p:"ccudes",    date:"2026-10-05", time:"19 h 30", prix:"35 $", desc:"Brahms et Schumann sous la direction de la cheffe invitée." },
    { d:"musique",  title:"Vitrine de la relève",                 p:"tremplin",  date:"2026-10-09", time:"20 h 00", prix:"10 $", desc:"Quatre groupes émergents de la scène sherbrookoise." },
    { d:"theatre",  title:"Ceux qui restent",                     p:"doublesigne", date:"2026-10-10", time:"20 h 00", prix:"30 $", desc:"Création sur la mémoire d'un quartier ouvrier." },
    { d:"humour",   title:"Soirée d'humour de la relève",         p:"cafe440",   date:"2026-10-10", time:"21 h 00", prix:"15 $", desc:"Six humoristes, dix minutes chacun, un micro." },
    { d:"danse",    title:"Création contemporaine « Fascia »",    p:"grandesp",  date:"2026-10-15", time:"20 h 00", prix:"32 $", desc:"Cinq interprètes, une écriture chorégraphique du souffle." },
    { d:"litt",     title:"Contes à rebours",                     p:"map",       venue:"Café 440", date:"2026-10-16", time:"19 h 30", prix:"18 $", desc:"Trois conteurs remontent le temps d'une même histoire." },
    { d:"musique",  title:"Lune Rousse — lancement d'album",      p:"granada",   date:"2026-10-17", time:"20 h 00", prix:"39 $", desc:"Le groupe estrien présente son troisième disque." },
    { d:"theatre",  title:"Le Grand Cahier",                      p:"grandesp",  date:"2026-10-22", time:"20 h 00", prix:"34 $", desc:"Adaptation du roman d'Agota Kristof, deux comédiens, un cahier." },
    { d:"festival", title:"Nuit des galeries",                    p:"acvs",      venue:"Rue Wellington Nord", date:"2026-10-24", time:"18 h – 23 h", prix:"Gratuit", vedette:true, desc:"Vernissages, performances et ateliers tout au long de l'artère." },
    { d:"jeunesse", title:"Atelier de bande dessinée",            p:"biblio",    date:"2026-10-24", time:"13 h 30", prix:"Gratuit", famille:true, desc:"Pour les 8 à 12 ans, matériel fourni. Inscription requise." },
    { d:"humour",   title:"Gala d'humour de l'Estrie",            p:"granada",   date:"2026-10-30", time:"20 h 00", prix:"45 $", desc:"Les têtes d'affiche de la région réunies pour une soirée." },
    { d:"arts",     title:"Exposition « Corps numériques »",      p:"sporobole", date:"2026-11-06", dateEnd:"2026-12-19", time:"12 h – 17 h", prix:"Gratuit", desc:"Cinq artistes explorent l'image du corps à l'ère numérique." },
    { d:"musique",  title:"Chœur symphonique — Requiem de Fauré", p:"ccudes",    date:"2026-11-07", time:"19 h 30", prix:"38 $", desc:"Le Requiem porté par 80 voix et l'orchestre." },
    { d:"theatre",  title:"Les Fourberies de Scapin",             p:"grandesp",  date:"2026-11-12", time:"20 h 00", prix:"34 $", desc:"Molière joué à toute vitesse par une troupe de sept." },
    { d:"theatre",  title:"Improvisation : la grande ligue",      p:"granada",   date:"2026-11-14", time:"20 h 00", prix:"25 $", desc:"Match d'impro déjanté entre deux équipes de la région." },
    { d:"jeunesse", title:"Pierre et le loup",                    p:"petittheatre", date:"2026-11-15", time:"14 h 00", prix:"15 $", famille:true, desc:"Le conte musical de Prokofiev, raconté aux 4 ans et plus." },
    { d:"litt",     title:"Salon du conte",                       p:"map",       date:"2026-11-19", time:"19 h 30", prix:"18 $", desc:"Une soirée, cinq voix, des histoires d'ici et d'ailleurs." },
    { d:"arts",     title:"Exposition « Lumières du Nord »",      p:"mbas",      date:"2026-11-20", dateEnd:"2027-01-24", time:"10 h – 17 h", prix:"12 $", desc:"La photographie hivernale québécoise, du crépuscule aux aurores." },
    { d:"danse",    title:"Bal folk du centre-ville",             p:"tremplin",  date:"2026-11-21", time:"19 h 00", prix:"Contribution volontaire", famille:true, desc:"Initiation aux danses traditionnelles, ouvert à tous." },
    { d:"musique",  title:"Nuit électro-acoustique",              p:"pbn",       date:"2026-11-28", time:"21 h 30", prix:"18 $", desc:"Rencontre entre musiciens acoustiques et machines analogiques." },
    { d:"theatre",  title:"Un conte de Noël",                     p:"granada",   date:"2026-12-03", time:"20 h 00", prix:"42 $", famille:true, vedette:true, desc:"L'adaptation scénique du récit de Dickens, en famille." },
    { d:"musique",  title:"Concert de Noël de l'OSSH",            p:"ccudes",    date:"2026-12-05", time:"19 h 30", prix:"38 $", desc:"Les grands classiques des Fêtes par l'orchestre et ses invités." },
    { d:"danse",    title:"Casse-Noisette",                       p:"ccudes",    date:"2026-12-06", time:"14 h 00", prix:"40 $", famille:true, desc:"Le ballet de Tchaïkovski dans une version régionale." },
    { d:"festival", title:"Marché de Noël du centre-ville",       p:"acvs",      venue:"Rue Wellington Nord", date:"2026-12-11", dateEnd:"2026-12-13", time:"Dès 11 h", prix:"Gratuit", famille:true, desc:"Artisans, food trucks et musique au cœur du quartier illuminé." },
    { d:"litt",     title:"Contes d'hiver au coin du feu",        p:"biblio",    date:"2026-12-12", time:"15 h 00", prix:"Gratuit", famille:true, desc:"Heure du conte pour petits et grands, chocolat chaud offert." },
    { d:"festival", title:"Grand feu du Nouvel An",               p:"acvs",      venue:"Parc Jacques-Cartier", date:"2026-12-31", time:"22 h 00", prix:"Gratuit", desc:"Feux d'artifice et DJ pour accueillir la nouvelle année." },
    { d:"musique",  title:"Veillée trad du Jour de l'An",         p:"tremplin",  date:"2027-01-09", time:"20 h 00", prix:"12 $", desc:"Violon, podorythmie et gigue pour lancer l'année." },
    { d:"festival", title:"Sherbrooke en lumières",               p:"acvs",      venue:"Rue Wellington Nord", date:"2027-01-15", dateEnd:"2027-01-17", time:"17 h – 22 h", prix:"Gratuit", famille:true, desc:"Projections monumentales et parcours lumineux dans le centre-ville." },
    { d:"theatre",  title:"Huis clos",                            p:"doublesigne", date:"2027-01-22", time:"20 h 00", prix:"30 $", desc:"Le huis clos de Sartre, mise en scène épurée et tendue." },
    { d:"litt",     title:"Nuit de la bande dessinée",            p:"biblio",    date:"2027-01-28", time:"18 h 30", prix:"Gratuit", desc:"Rencontres d'illustrateurs et ateliers de création." },
    { d:"arts",     title:"Exposition « Matières premières »",    p:"mbas",      date:"2027-02-05", dateEnd:"2027-04-25", time:"10 h – 17 h", prix:"12 $", desc:"La sculpture contemporaine et ses matériaux bruts." }
  ];

  // Activités récurrentes. jour : 0 = dimanche … 6 = samedi.
  // nth : n-ième occurrence du jour dans le mois (sinon chaque semaine).
  var SERIES = [
    { id:"jam",    d:"musique",  title:"Jam jazz du mardi",               p:"pbn",      jour:2, time:"20 h 30", rule:"Tous les mardis",        from:"2026-09-01", to:"2027-06-29", prix:"Gratuit", desc:"Scène ouverte aux musiciens, section rythmique fournie." },
    { id:"impro",  d:"humour",   title:"Les mercredis de l'impro",        p:"tremplin", jour:3, time:"20 h 00", rule:"Tous les mercredis",     from:"2026-09-09", to:"2027-04-28", prix:"5 $",     desc:"Ligue d'improvisation amicale, le public vote." },
    { id:"chanso", d:"musique",  title:"Chansonniers du jeudi",           p:"cafe440",  jour:4, time:"21 h 00", rule:"Tous les jeudis",        from:"2026-09-03", to:"2027-06-24", prix:"Gratuit", desc:"Guitare, voix et reprises chantées en chœur." },
    { id:"slam",   d:"litt",     title:"Slam ouvert — micro libre",       p:"map",      venue:"Le Boquébière", jour:4, nth:3, time:"20 h 00", rule:"Le 3e jeudi du mois", from:"2026-09-01", to:"2027-06-30", prix:"Gratuit", desc:"Scène ouverte de poésie parlée, inscription sur place." },
    { id:"conte",  d:"jeunesse", title:"L'heure du conte",                p:"biblio",   jour:6, time:"10 h 30", rule:"Tous les samedis",       from:"2026-09-05", to:"2027-06-26", prix:"Gratuit", famille:true, desc:"Histoires et comptines pour les 3 à 6 ans." },
    { id:"visite", d:"arts",     title:"Visite commentée des expositions", p:"mbas",    jour:0, time:"14 h 00", rule:"Tous les dimanches",     from:"2026-09-06", to:"2027-06-27", prix:"Incluse avec l'entrée", famille:true, desc:"Une médiatrice présente les expositions en cours, 45 minutes." }
  ];

  EVENTS.forEach(function (e, i) { e.id = "e" + i; e.gratuit = /gratuit/i.test(e.prix || ""); });
  SERIES.forEach(function (s) { s.gratuit = /gratuit/i.test(s.prix || ""); s.serie = true; });

  // ---------- Dates ----------
  var MOIS = ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"];
  var MOIS_ABBR = ["janv.","févr.","mars","avr.","mai","juin","juil.","août","sept.","oct.","nov.","déc."];
  var JOURS = ["dimanche","lundi","mardi","mercredi","jeudi","vendredi","samedi"];
  var JOURS_ABBR = ["dim.","lun.","mar.","mer.","jeu.","ven.","sam."];
  var DAY = 86400000;

  function parseD(s) { var p = s.split("-"); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function iso(d) { return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
  function addDays(d, n) { var r = new Date(d); r.setDate(r.getDate() + n); return r; }
  function sameDay(a, b) { return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate(); }
  function startOfWeek(d) { var r = new Date(d); r.setDate(r.getDate() - ((r.getDay() + 6) % 7)); return r; } // lundi
  function diffDays(a, b) { return Math.round((b - a) / DAY); }
  function day1(n) { return n === 1 ? "1er" : String(n); }
  function dateLong(d) { return JOURS[d.getDay()] + " " + day1(d.getDate()) + " " + MOIS[d.getMonth()]; }
  function dateShort(d) { return JOURS_ABBR[d.getDay()] + " " + d.getDate() + " " + MOIS_ABBR[d.getMonth()]; }
  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

  function start(ev) { return parseD(ev.date); }
  function end(ev) { return ev.dateEnd ? parseD(ev.dateEnd) : parseD(ev.date); }
  // Longue durée : expositions et parcours de plus de 8 jours.
  function isLong(ev) { return !!ev.dateEnd && diffDays(start(ev), end(ev)) + 1 > 8; }

  function rangeLabel(ev) {
    var s = start(ev), e = end(ev);
    if (!ev.dateEnd) return dateLong(s);
    if (s <= TODAY && isLong(ev)) return "Jusqu'au " + day1(e.getDate()) + " " + MOIS[e.getMonth()];
    var sm = s.getMonth() === e.getMonth();
    return "Du " + day1(s.getDate()) + (sm ? "" : " " + MOIS_ABBR[s.getMonth()]) + " au " + e.getDate() + " " + MOIS[e.getMonth()];
  }

  // Dates d'une série entre from et to (inclus).
  function occurrences(s, from, to) {
    var out = [], a = parseD(s.from), b = parseD(s.to);
    var d = new Date(Math.max(a, from)); d.setHours(0, 0, 0, 0);
    var lim = new Date(Math.min(b, to));
    while (d.getDay() !== s.jour) d = addDays(d, 1);
    for (; d <= lim; d = addDays(d, 7)) {
      if (s.nth && Math.ceil(d.getDate() / 7) !== s.nth) continue;
      out.push(new Date(d));
    }
    return out;
  }
  function nextOccurrences(s, n, from) {
    return occurrences(s, from || TODAY, addDays(from || TODAY, 400)).slice(0, n || 1);
  }

  // Agenda à plat entre deux dates : événements qui chevauchent la fenêtre
  // + occurrences des séries. Chaque élément : { ev, date, serie, long }.
  function agenda(from, to, opts) {
    opts = opts || {};
    var items = [];
    EVENTS.forEach(function (ev) {
      if (end(ev) < from || start(ev) > to) return;
      var long = isLong(ev);
      if (long && opts.noLong) return;
      if (!long && ev.dateEnd && opts.spread) { // festival de 3 jours : une ligne par jour
        for (var d = new Date(Math.max(start(ev), from)); d <= end(ev) && d <= to; d = addDays(d, 1))
          items.push({ ev: ev, date: new Date(d), serie: false, long: false });
        return;
      }
      items.push({ ev: ev, date: long ? new Date(Math.max(start(ev), from)) : start(ev), serie: false, long: long });
    });
    if (opts.series !== false) SERIES.forEach(function (s) {
      occurrences(s, from, to).forEach(function (d) { items.push({ ev: s, date: d, serie: true, long: false }); });
    });
    items.sort(function (x, y) { return (x.date - y.date) || timeKey(x.ev) - timeKey(y.ev); });
    return items;
  }
  function timeKey(ev) { var m = /(\d{1,2}) h ?(\d{2})?/.exec(ev.time || ""); return m ? (+m[1]) * 60 + (+(m[2] || 0)) : 0; }

  function partner(id) { for (var i = 0; i < PARTNERS.length; i++) if (PARTNERS[i].id === id) return PARTNERS[i]; return null; }
  function place(ev) { var p = partner(ev.p); return ev.venue || (p ? p.name : ""); }
  function esc(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }

  // ---------- Thème clair / sombre (bouton facultatif) ----------
  function initTheme(btn) {
    var root = document.documentElement;
    try { var t = localStorage.getItem("cc-theme"); if (t) root.setAttribute("data-theme", t); } catch (e) {}
    if (!btn) return;
    btn.addEventListener("click", function () {
      var cur = root.getAttribute("data-theme");
      var dark = cur ? cur === "dark" : !!(window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches);
      var next = dark ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("cc-theme", next); } catch (e) {}
    });
  }

  // ---------- Vignettes illustrées (reprises de web/index.html) ----------
  function svgWrap(u, inner){
    return '<svg class="scene" viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
      inner +
      '<rect width="400" height="300" fill="url(#vg'+u+')"/>' +
      '<defs><radialGradient id="vg'+u+'" cx="50%" cy="40%" r="78%">' +
        '<stop offset="52%" stop-color="#000" stop-opacity="0"/>' +
        '<stop offset="100%" stop-color="#000" stop-opacity="0.36"/>' +
      '</radialGradient></defs></svg>';
  }

  var SCENES = {
    theatre: function(u){ return svgWrap(u,
      '<rect width="400" height="300" fill="#251016"/>' +
      '<rect y="158" width="400" height="142" fill="#3a1a20"/>' +
      '<ellipse cx="200" cy="52" rx="150" ry="130" fill="#f0cf8c" opacity="0.15"/>' +
      '<polygon points="200,10 118,300 282,300" fill="#f4d78f" opacity="0.13"/>' +
      '<rect y="0" width="400" height="26" fill="#5a1520"/>' +
      '<path d="M0,0 H126 C116,64 134,128 104,190 C120,244 92,300 100,300 H0 Z" fill="#7c1f2c"/>' +
      '<path d="M400,0 H274 C284,64 266,128 296,190 C280,244 308,300 300,300 H400 Z" fill="#6a1824"/>' +
      '<path d="M126,2 C118,70 134,140 108,208 C120,258 100,300 100,300" stroke="#4d1019" stroke-width="7" fill="none" opacity=".45"/>' +
      '<path d="M274,2 C282,70 266,140 292,208 C280,258 300,300 300,300" stroke="#43101a" stroke-width="7" fill="none" opacity=".45"/>'
    ); },
    musique: function(u){ return svgWrap(u,
      '<rect width="400" height="300" fill="#0d0d20"/>' +
      '<polygon points="95,0 62,300 152,300" fill="#6C5CE7" opacity=".5"/>' +
      '<polygon points="165,0 128,300 246,300" fill="#C24E8E" opacity=".42"/>' +
      '<polygon points="250,0 220,300 330,300" fill="#28B6C9" opacity=".4"/>' +
      '<polygon points="322,0 300,300 384,300" fill="#E39A2B" opacity=".32"/>' +
      '<circle cx="200" cy="26" r="64" fill="#ffffff" opacity=".07"/>' +
      '<g stroke="#05050d" stroke-width="4" stroke-linecap="round"><path d="M60,246 V212"/><path d="M132,244 V208"/><path d="M242,248 V210"/><path d="M304,244 V214"/></g>' +
      '<rect y="238" width="400" height="62" fill="#05050d"/>' +
      '<g fill="#05050d"><circle cx="34" cy="246" r="24"/><circle cx="92" cy="250" r="26"/><circle cx="150" cy="244" r="23"/><circle cx="208" cy="250" r="27"/><circle cx="268" cy="245" r="24"/><circle cx="326" cy="250" r="26"/><circle cx="380" cy="246" r="23"/></g>'
    ); },
    arts: function(u){ return svgWrap(u,
      '<rect width="400" height="300" fill="#ece5d6"/>' +
      '<rect y="212" width="400" height="88" fill="#c7b085"/>' +
      '<rect y="206" width="400" height="7" fill="#ac9068"/>' +
      '<g stroke="#d9ccb2" stroke-width="7"><rect x="34" y="66" width="72" height="94" fill="#fff"/><rect x="164" y="52" width="96" height="70" fill="#fff"/><rect x="312" y="70" width="60" height="86" fill="#fff"/></g>' +
      '<rect x="46" y="78" width="48" height="70" fill="#3d7dca"/>' +
      '<rect x="176" y="64" width="72" height="46" fill="#159A8A"/>' +
      '<rect x="324" y="82" width="36" height="62" fill="#D6435A"/>' +
      '<g fill="#2b2b34" opacity=".8"><circle cx="150" cy="176" r="12"/><path d="M136,250 C136,212 164,212 164,250 Z"/></g>'
    ); },
    festival: function(u){ return svgWrap(u,
      '<defs><linearGradient id="fs'+u+'" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F3A24B"/><stop offset=".5" stop-color="#C85F6E"/><stop offset="1" stop-color="#573A6B"/></linearGradient></defs>' +
      '<rect width="400" height="300" fill="url(#fs'+u+')"/>' +
      '<circle cx="200" cy="150" r="52" fill="#FFE0A6" opacity=".55"/>' +
      '<rect y="222" width="400" height="78" fill="#2b1e33"/>' +
      '<polygon points="52,222 104,168 156,222" fill="#2b1e33"/>' +
      '<polygon points="250,222 304,158 358,222" fill="#241a2e"/>' +
      '<path d="M0,34 Q200,74 400,34" stroke="#fff" stroke-opacity=".5" stroke-width="2" fill="none"/>' +
      '<g><polygon points="34,40 56,42 45,60" fill="#E39A2B"/><polygon points="90,48 112,50 101,68" fill="#D6435A"/><polygon points="150,52 172,54 161,72" fill="#159A8A"/><polygon points="228,52 250,54 239,72" fill="#6C5CE7"/><polygon points="292,48 314,50 303,68" fill="#E39A2B"/><polygon points="350,42 372,44 361,62" fill="#D6435A"/></g>' +
      '<g fill="#160f1c"><circle cx="40" cy="240" r="16"/><circle cx="86" cy="244" r="18"/><circle cx="140" cy="238" r="16"/><circle cx="196" cy="245" r="19"/><circle cx="256" cy="240" r="17"/><circle cx="316" cy="245" r="18"/><circle cx="372" cy="240" r="16"/></g>' +
      '<g><rect x="210" y="70" width="5" height="9" fill="#D6435A"/><rect x="140" y="104" width="5" height="9" fill="#6C5CE7"/><rect x="286" y="96" width="5" height="9" fill="#FFE9B8"/><rect x="96" y="86" width="5" height="9" fill="#159A8A"/></g>'
    ); },
    danse: function(u){ return svgWrap(u,
      '<defs><radialGradient id="dr'+u+'" cx="50%" cy="34%" r="82%"><stop offset="0" stop-color="#E58FC0"/><stop offset="1" stop-color="#571E44"/></radialGradient></defs>' +
      '<rect width="400" height="300" fill="url(#dr'+u+')"/>' +
      '<ellipse cx="200" cy="298" rx="240" ry="56" fill="#3a1430" opacity=".55"/>' +
      '<polygon points="200,0 150,300 250,300" fill="#ffffff" opacity=".12"/>' +
      '<g stroke="#ffffff" stroke-opacity=".18" stroke-width="3" fill="none" stroke-linecap="round"><path d="M118,150 C150,118 172,120 192,140"/><path d="M282,172 C256,150 234,150 220,166"/></g>' +
      '<g fill="#180a15"><circle cx="205" cy="92" r="14"/><path d="M205,106 C195,118 196,150 186,168 C179,182 166,192 146,196 C168,193 184,203 194,224 L178,272 L194,274 L214,224 C223,203 238,194 258,203 C240,187 230,166 226,146 C241,136 252,116 248,100 C242,118 224,126 210,118 Z"/></g>'
    ); },
    humour: function(u){ return svgWrap(u,
      '<rect width="400" height="300" fill="#2a1410"/>' +
      '<rect y="200" width="400" height="100" fill="#3d1d16"/>' +
      '<ellipse cx="200" cy="120" rx="150" ry="120" fill="#F58A57" opacity=".18"/>' +
      '<rect x="190" y="118" width="20" height="90" rx="4" fill="#F0A070"/>' +
      '<rect x="176" y="72" width="48" height="66" rx="24" fill="#FFD1A8"/>' +
      '<rect x="182" y="84" width="36" height="6" fill="#2a1410" opacity=".35"/><rect x="182" y="98" width="36" height="6" fill="#2a1410" opacity=".35"/>' +
      '<path d="M160,208 h80 M200,208 v22" stroke="#F0A070" stroke-width="6" stroke-linecap="round"/>' +
      '<g fill="#FFE0A6" opacity=".6"><circle cx="78" cy="70" r="5"/><circle cx="320" cy="58" r="4"/><circle cx="350" cy="130" r="6"/><circle cx="60" cy="150" r="4"/></g>' +
      '<path d="M40,250 q30,-18 60,0 t60,0 t60,0 t60,0 t60,0" stroke="#F58A57" stroke-opacity=".5" stroke-width="3" fill="none"/>'
    ); },
    jeunesse: function(u){ return svgWrap(u,
      '<defs><linearGradient id="je'+u+'" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8FD3F4"/><stop offset="1" stop-color="#E8F6DD"/></linearGradient></defs>' +
      '<rect width="400" height="300" fill="url(#je'+u+')"/>' +
      '<circle cx="330" cy="60" r="34" fill="#FFE27A"/>' +
      '<polygon points="150,60 205,120 150,205 95,120" fill="#F0728A"/>' +
      '<polygon points="150,60 205,120 150,120" fill="#FFD166" opacity=".9"/>' +
      '<polygon points="150,120 150,205 95,120" fill="#6CCB70" opacity=".9"/>' +
      '<path d="M150,205 q-10,30 10,50 t-6,45" stroke="#2E7D32" stroke-width="3" fill="none"/>' +
      '<g fill="#F0728A"><path d="M132,238 l8,-6 8,6 -8,6z"/><path d="M158,262 l8,-6 8,6 -8,6z"/></g>' +
      '<ellipse cx="200" cy="300" rx="260" ry="60" fill="#7BD37F"/>' +
      '<g fill="#fff" opacity=".85"><ellipse cx="70" cy="90" rx="30" ry="14"/><ellipse cx="92" cy="82" rx="22" ry="12"/><ellipse cx="280" cy="150" rx="26" ry="12"/></g>'
    ); },
    litt: function(u){
      var cols = ['#8a3b2e','#b6863c','#3d6b6f','#7c4a86','#a85a4a','#4a5f8a','#9c7b3a','#6b8a4a'];
      var widths = [16,22,14,20,18,15,24,17,19,16,21,15,18,22,14,20];
      function shelf(y){
        var s = '', x = 8, i = 0;
        while (x < 390){
          var w = widths[i % widths.length];
          var h = 44 - ((i * 7) % 16);
          s += '<rect x="'+x+'" y="'+(y + (48 - h))+'" width="'+(w - 2)+'" height="'+h+'" fill="'+cols[(i + y) % cols.length]+'"/>';
          x += w; i++;
        }
        return s + '<rect x="0" y="'+(y + 48)+'" width="400" height="8" fill="#5a3f28"/>';
      }
      return svgWrap(u,
        '<rect width="400" height="300" fill="#e7dcc4"/>' +
        '<ellipse cx="330" cy="40" rx="140" ry="100" fill="#ffe6a8" opacity=".5"/>' +
        shelf(30) + shelf(120) + shelf(210)
      );
    }
  };
  var uidN = 0;
  function scene(d) { var f = SCENES[d] || SCENES.arts; return f("s" + (uidN++)); }

  return {
    TODAY: TODAY, DISC: DISC, PARTNERS: PARTNERS, EVENTS: EVENTS, SERIES: SERIES,
    MOIS: MOIS, MOIS_ABBR: MOIS_ABBR, JOURS: JOURS, JOURS_ABBR: JOURS_ABBR, DAY: DAY,
    parseD: parseD, iso: iso, addDays: addDays, sameDay: sameDay, startOfWeek: startOfWeek, diffDays: diffDays,
    day1: day1, dateLong: dateLong, dateShort: dateShort, cap: cap,
    start: start, end: end, isLong: isLong, rangeLabel: rangeLabel,
    occurrences: occurrences, nextOccurrences: nextOccurrences, agenda: agenda, timeKey: timeKey,
    partner: partner, place: place, esc: esc, initTheme: initTheme, scene: scene
  };
})();
