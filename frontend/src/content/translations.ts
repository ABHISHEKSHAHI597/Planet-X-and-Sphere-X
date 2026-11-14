/**
 * Hindi and Spanish text for the home page and the five missions (optimisation.md IMP-5). English lives where it
 * always did (components/Home.tsx, content/missions.ts) and is the reviewed source: a mission's steward signs the
 * English wording (workflow.md §9.4), and a translation must say the same thing, step for step.
 * tests/content.test.ts holds every language to the same shape and the same no-measured-numbers rule.
 * TRANSLATION REVIEW: written by the team with SI assistance; a fluent speaker should read each language once
 * before release (the science terms in particular).
 */
import type { Lang } from "../lib/lang";

export interface MissionText { title: string; hook: string; look: string[] }
export interface HomeText {
  title: string; pitch: string; tryIt: string; bandsTitle: string; bandsText: string; missionsTitle: string;
  missionsHint: string; challengeTitle: string; challengeHook: string; oldEpoch: string; band: string;
  proofLink: string; creditsLink: string;
}

export const HOME_TEXT: Record<Lang, HomeText> = {
  en: {
    title: "Blink the infrared sky",
    pitch: "In 1930 Clyde Tombaugh found Pluto by flipping between two photographs of the same stars and spotting the one dot that jumped. ParallaX does the same with SPHEREx, NASA's all-sky spectral survey telescope: type a star or any RA/Dec and watch its visits play like a little video, in six infrared bands.",
    tryIt: "Try",
    bandsTitle: "One frame per visit, one band at a time",
    bandsText: "Consecutive SPHEREx exposures see different wavelengths, so blinking them would show a spectrum, not motion. ParallaX stacks each 1–3 week visit separately in every band and blinks visits of the same band, on one shared brightness scale.",
    missionsTitle: "Five targets to start with",
    missionsHint: "Each opens in the band where it shows best.",
    challengeTitle: "The challenge's coordinate",
    challengeHook: "Type an old position of a fast-moving object and see what ParallaX does with it.",
    oldEpoch: "old epoch",
    band: "Band",
    proofLink: "What we checked, and what we have not",
    creditsLink: "Data, acknowledgements and credits",
  },
  hi: {
    title: "इन्फ्रारेड आकाश को पलटकर देखिए",
    pitch: "1930 में क्लाइड टॉमबॉ ने एक ही तारों की दो तस्वीरों को बारी-बारी से देखकर वह एक बिंदु पकड़ा जो अपनी जगह से खिसक गया था, और इस तरह प्लूटो खोजा। ParallaX यही काम SPHEREx के साथ करता है, जो नासा की पूरे आकाश का सर्वे करने वाली दूरबीन है: किसी तारे का नाम या कोई भी RA/Dec लिखिए और उस जगह की तस्वीरें, छह इन्फ्रारेड बैंड में, एक छोटे वीडियो की तरह चलती देखिए।",
    tryIt: "आज़माइए",
    bandsTitle: "हर विज़िट का एक फ़्रेम, एक बार में एक बैंड",
    bandsText: "SPHEREx की लगातार ली गई तस्वीरें अलग-अलग तरंगदैर्घ्य पर होती हैं, इसलिए उन्हें सीधे पलटने पर गति नहीं, स्पेक्ट्रम दिखेगा। ParallaX हर बैंड में 1–3 हफ़्ते की हर विज़िट की तस्वीरों को अलग जोड़ता है और एक ही बैंड की विज़िटों को, चमक के एक ही पैमाने पर, पलटकर दिखाता है।",
    missionsTitle: "शुरुआत के लिए पाँच लक्ष्य",
    missionsHint: "हर लक्ष्य उस बैंड में खुलता है जिसमें वह सबसे अच्छा दिखता है।",
    challengeTitle: "चुनौती में दिया गया निर्देशांक",
    challengeHook: "तेज़ चलने वाले पिंड की पुरानी स्थिति लिखिए और देखिए कि ParallaX उसके साथ क्या करता है।",
    oldEpoch: "पुरानी स्थिति",
    band: "बैंड",
    proofLink: "हमने क्या जाँचा है, और क्या नहीं",
    creditsLink: "डेटा, आभार और श्रेय",
  },
  es: {
    title: "Parpadea el cielo infrarrojo",
    pitch: "En 1930 Clyde Tombaugh descubrió Plutón alternando dos fotografías de las mismas estrellas y fijándose en el único punto que saltaba. ParallaX hace lo mismo con SPHEREx, el telescopio de la NASA que cartografía todo el cielo en el infrarrojo: escribe una estrella o cualquier AR/Dec y mira cómo sus visitas se reproducen como un pequeño vídeo, en seis bandas infrarrojas.",
    tryIt: "Prueba",
    bandsTitle: "Un fotograma por visita, una banda cada vez",
    bandsText: "Las exposiciones consecutivas de SPHEREx ven longitudes de onda distintas, así que alternarlas mostraría un espectro, no un movimiento. ParallaX apila por separado cada visita de 1 a 3 semanas en cada banda y alterna visitas de la misma banda, con una única escala de brillo.",
    missionsTitle: "Cinco objetivos para empezar",
    missionsHint: "Cada uno se abre en la banda donde mejor se ve.",
    challengeTitle: "La coordenada del desafío",
    challengeHook: "Escribe una posición antigua de un objeto que se mueve rápido y mira qué hace ParallaX con ella.",
    oldEpoch: "época antigua",
    band: "Banda",
    proofLink: "Qué hemos comprobado y qué no",
    creditsLink: "Datos, agradecimientos y créditos",
  },
};

/** Keyed by mission id (content/missions.ts). English is the mission's own text and is not repeated here. */
export const MISSION_TEXT: Record<Exclude<Lang, "en">, Record<string, MissionText>> = {
  hi: {
    barnard: {
      title: "आकाश का सबसे तेज़ तारा",
      hook: "सूर्य का सबसे नज़दीकी अकेला तारा, जो आकाश में किसी भी दूसरे तारे से तेज़ खिसकता है।",
      look: [
        "विज़िटों को पलटकर देखिए: चमकीला तारा उछलता है, बाक़ी तारे अपनी जगह रहते हैं।",
        "इसके बीच का काला छेद कोई गड़बड़ी नहीं है: तारा इतना चमकीला है कि डिटेक्टर भर गया। OVERFLOW फ़्लैग परत चालू कीजिए।",
        "अनुमानित पथ (बिंदु) में लंबन भी शामिल है: विज़िटों के बीच का छोटा-सा बग़ल का खिसकाव पृथ्वी की कक्षा के कारण है।",
      ],
    },
    epsindb: {
      title: "दो भूरे बौने, एक बिंदु",
      hook: "ठंडे भूरे बौनों की एक जोड़ी, जो इतनी पास-पास है कि SPHEREx उन्हें अलग नहीं कर पाता, और जो साथ-साथ खिसक रही है।",
      look: [
        "बैंडों को छोटी से लंबी तरंगदैर्घ्य की ओर बदलिए: बिंदु की चमक बदलती है, क्योंकि इसके स्पेक्ट्रम को मीथेन और पानी आकार देते हैं।",
        "पास का एक बहुत चमकीला तारा नक़ली छाया और प्रतिबिंब छोड़ सकता है। कुछ अजीब दिखे तो पहले फ़्लैग परतें जाँचिए।",
      ],
    },
    wise0855: {
      title: "सबसे ठंडा ज्ञात भूरा बौना",
      hook: "किसी भी तारे से ठंडा, यह लगभग केवल SPHEREx की सबसे लंबी तरंगदैर्घ्यों पर चमकता है।",
      look: [
        "इस पिंड का मशहूर निर्देशांक WISE के समय की पुरानी स्थिति है। ParallaX यह बताता है और दृश्य को वहाँ ले जाता है जहाँ यह अब है।",
        "बैंड 1 की तुलना बैंड 6 से कीजिए। छोटे बैंडों में इसकी जगह पर जो दिखता है वह ठीक बग़ल में बैठा एक अलग, साधारण तारा है।",
        "अधूरी विज़िटें (केवल कुछ फ़्रेम) टाइमलाइन पर धारीदार दिखती हैं और आम तौर पर ब्लिंक से बाहर रखी जाती हैं।",
      ],
    },
    rwaur: {
      title: "बदलती धूल के पीछे एक युवा तारा",
      hook: "एक नवजात तारा जो अब भी अपनी डिस्क से पदार्थ खींच रहा है, और धूल के सामने से गुज़रने पर मंद पड़ने के लिए जाना जाता है।",
      look: [
        "यह खिसकता नहीं: इसकी जगह विज़िटों के बीच चमक में बदलाव देखिए।",
        "कुछ बैंडों में यह इतना चमकीला है कि डिटेक्टर भर जाता है; फ़्लैग परत दिखाती है कि कहाँ।",
      ],
    },
    rdra: {
      title: "साँस लेता दानव तारा",
      hook: "एक स्पंदित लाल दानव तारा जो महीनों में फूलता और मंद पड़ता है, और क्रांतिवृत्त के ध्रुव के पास होने के कारण लगभग लगातार देखा जाता है।",
      look: [
        "यहाँ समय-अक्ष अपने आप विज़िटों की जगह 14 दिन के खानों में बदल जाता है, क्योंकि SPHEREx इस हिस्से को लगभग हर समय देखता है।",
        "इसका केंद्र ज़्यादातर बैंडों में संतृप्त है; चमक के बदलाव तारे के चारों ओर एक छल्ले में नापे जाते हैं, इसलिए उन्हें सापेक्ष ही मानिए।",
      ],
    },
  },
  es: {
    barnard: {
      title: "La estrella más rápida del cielo",
      hook: "La estrella solitaria más cercana al Sol, que cruza el cielo más deprisa que ninguna otra.",
      look: [
        "Alterna las visitas: la estrella brillante salta mientras el campo se queda quieto.",
        "El agujero oscuro de su centro no es un fallo: la estrella brilla tanto que el detector se desbordó. Activa la capa de la marca OVERFLOW.",
        "La trayectoria prevista (puntos) incluye la paralaje: el pequeño paso lateral entre visitas es la órbita de la Tierra.",
      ],
    },
    epsindb: {
      title: "Dos enanas marrones, un solo punto",
      hook: "Una pareja de enanas marrones frías, demasiado juntas para que SPHEREx las separe, que se desplazan juntas.",
      look: [
        "Recorre las bandas de las longitudes de onda cortas a las largas: el punto cambia de brillo porque el metano y el agua dan forma a su espectro.",
        "Una estrella muy brillante cercana puede dejar fantasmas y reflejos. Si aparece algo raro, mira primero las capas de marcas.",
      ],
    },
    wise0855: {
      title: "La enana marrón más fría conocida",
      hook: "Más fría que cualquier estrella, brilla casi solo en las longitudes de onda más largas de SPHEREx.",
      look: [
        "La coordenada famosa de este objeto es una posición antigua, de la época de WISE. ParallaX te lo dice y lleva la vista adonde está ahora.",
        "Compara la banda 1 con la banda 6. En las bandas cortas, lo que ves en su posición es otra estrella, corriente, que está justo al lado.",
        "Las visitas parciales (solo unos pocos fotogramas) aparecen rayadas en la línea de tiempo y, por defecto, quedan fuera del parpadeo.",
      ],
    },
    rwaur: {
      title: "Una estrella joven tras polvo cambiante",
      hook: "Una estrella recién nacida que aún se alimenta de su disco, conocida por atenuarse cuando el polvo pasa por delante.",
      look: [
        "No se mueve: fíjate, en cambio, en las variaciones de brillo entre visitas.",
        "Brilla lo bastante para desbordar el detector en algunas bandas; la capa de marcas muestra dónde.",
      ],
    },
    rdra: {
      title: "Una gigante que respira",
      hook: "Una gigante roja pulsante que se hincha y se apaga a lo largo de meses, observada casi sin pausa desde cerca del polo de la eclíptica.",
      look: [
        "Aquí el eje de tiempo pasa por sí solo de visitas a intervalos de 14 días, porque SPHEREx ve esta zona casi todo el tiempo.",
        "Su centro está saturado en casi todas las bandas; los cambios de brillo se miden en un anillo alrededor de la estrella, así que tómalos como relativos.",
      ],
    },
  },
};

/** A mission's text in a language; English (or a missing translation) is the mission's own reviewed text. */
export function missionText(m: { id: string; title: string; hook: string; look: string[] }, lang: Lang): MissionText {
  return (lang !== "en" && MISSION_TEXT[lang][m.id]) || { title: m.title, hook: m.hook, look: m.look };
}
