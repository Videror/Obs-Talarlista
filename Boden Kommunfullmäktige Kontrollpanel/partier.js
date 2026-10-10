// Partilista för talarlistan.
//
// Varje rad är ett parti:
//   id    – kort och unikt, utan mellanslag (sparas tillsammans med talaren)
//   namn  – visas i rullistan i kontrollpanelen
//   ikon  – sökvägen till bilden i mappen "ikoner" (PNG, SVG eller JPG)
//
// Lägg till lokala partier genom att kopiera en rad. Ändra inte ett id
// som redan används, annars tappar sparade talare sin ikon.
window.PARTIER = [
  { id: "s",  namn: "Socialdemokraterna",  ikon: "ikoner/s.png"  },
  { id: "m",  namn: "Moderaterna",         ikon: "ikoner/m.png"  },
  { id: "sd", namn: "Sverigedemokraterna", ikon: "ikoner/sd.png" },
  { id: "c",  namn: "Centerpartiet",       ikon: "ikoner/c.png"  },
  { id: "v",  namn: "Vänsterpartiet",      ikon: "ikoner/v.png"  },
  { id: "kd", namn: "Kristdemokraterna",   ikon: "ikoner/kd.png" },
  { id: "l",  namn: "Liberalerna",         ikon: "ikoner/l.png"  },
  { id: "mp", namn: "Miljöpartiet",        ikon: "ikoner/mp.png" },
  { id: "sp", namn: "Sjukvårdspartiet",    ikon: "ikoner/sp.png" },
  { id: "ba", namn: "Bodenalternativet",        ikon: "ikoner/ba.png" }
];