/**
 * Acknowledgements for About/Credits (P0-7; understanding.md §4.8; implementation.md §11.5).
 * `verbatim: true` = copied word for word from the archive's own page (understanding.md §4.8 quotes the
 * SPHEREx text). `verbatim: false` = the standard text as we know it, which F must re-check against the
 * source page before RC0 (workflow.md G2 "Credits/About page carries every acknowledgement").
 * tests/credits.test.ts fails the release check while any entry is unverified (see `UNVERIFIED`).
 */
export interface Credit {
  id: string;
  name: string;
  text: string;
  dois?: string[];
  url: string;
  verbatim: boolean;
  /** shown only when that capability or data source is actually used */
  when?: string;
}

export const CREDITS: Credit[] = [
  {
    id: "spherex", name: "SPHEREx (QR2, QR3) at IRSA",
    text: "This publication makes use of data products from the Spectro-Photometer for the History of the Universe, " +
      "Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion Laboratory " +
      "and the California Institute of Technology, and is funded by the National Aeronautics and Space Administration.",
    dois: ["10.26131/IRSA652", "10.26131/IRSA662"],
    url: "https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_qr.html", verbatim: true,
  },
  {
    id: "irsa", name: "NASA/IPAC Infrared Science Archive",
    text: "This research has made use of the NASA/IPAC Infrared Science Archive, which is funded by the National " +
      "Aeronautics and Space Administration and operated by the California Institute of Technology.",
    url: "https://irsa.ipac.caltech.edu/", verbatim: false,
  },
  {
    id: "gaia", name: "Gaia DR3 (ESA/DPAC)",
    // Verbatim, 2026-11-10: the acknowledgement Gaia asks DR3 users for ("If you have used Gaia DR3 data in your
    // research, please use the following acknowledgement"), from the credit and citation instructions page.
    text: "This work has made use of data from the European Space Agency (ESA) mission Gaia " +
      "(https://www.cosmos.esa.int/gaia), processed by the Gaia Data Processing and Analysis Consortium (DPAC, " +
      "https://www.cosmos.esa.int/web/gaia/dpac/consortium). Funding for the DPAC has been provided by national " +
      "institutions, in particular the institutions participating in the Gaia Multilateral Agreement.",
    url: "https://gea.esac.esa.int/archive/documentation/GDR3/Miscellaneous/sec_credit_and_citation_instructions/", verbatim: true,
  },
  {
    id: "2mass", name: "2MASS",
    text: "This publication makes use of data products from the Two Micron All Sky Survey, which is a joint project " +
      "of the University of Massachusetts and the Infrared Processing and Analysis Center/California Institute of " +
      "Technology, funded by the National Aeronautics and Space Administration and the National Science Foundation.",
    // Verbatim, 2026-11-14: the "standard acknowledgment" on IRSA's 2MASS mission page.
    url: "https://irsa.ipac.caltech.edu/Missions/2mass.html", verbatim: true,
  },
  {
    id: "wise", name: "WISE and NEOWISE",
    text: "This publication makes use of data products from the Wide-field Infrared Survey Explorer, which is a joint " +
      "project of the University of California, Los Angeles, and the Jet Propulsion Laboratory/California Institute " +
      "of Technology, funded by the National Aeronautics and Space Administration. This publication also makes use of " +
      "data products from NEOWISE, which is a project of the Jet Propulsion Laboratory/California Institute of " +
      "Technology, funded by the Planetary Science Division of the National Aeronautics and Space Administration.",
    // Verbatim, 2026-11-10: WISE All-Sky Explanatory Supplement §I.6b, "Acknowledging WISE and NEOWISE in Publications".
    url: "https://irsa.ipac.caltech.edu/data/WISE/docs/release/All-Sky/expsup/sec1_6b.html", verbatim: true,
  },
  {
    id: "simbad", name: "SIMBAD (CDS)",
    text: "This research has made use of the SIMBAD database, operated at CDS, Strasbourg, France.",
    url: "https://simbad.cds.unistra.fr/simbad/", verbatim: false,
  },
  {
    id: "aladin", name: "Aladin Lite (CDS)",
    text: "This research has made use of \"Aladin sky atlas\" developed at CDS, Strasbourg Observatory, France.",
    url: "https://aladin.cds.unistra.fr/", verbatim: false,
  },
  {
    id: "horizons", name: "JPL Horizons", when: "sso",
    text: "Horizons is provided by the Solar System Dynamics Group of the Jet Propulsion Laboratory. Ephemerides here " +
      "are computed for the SPHEREx spacecraft as observer (−163182).",
    url: "https://ssd.jpl.nasa.gov/horizons/", verbatim: true,   // first sentence verbatim (no citation text is requested)
  },
  {
    id: "skybot", name: "IMCCE SkyBoT", when: "movers",
    text: "This research has made use of IMCCE's SkyBoT VO tool (Berthier et al. 2006, ASPC 351, 367).",
    url: "https://ssp.imcce.fr/webservices/skybot/", verbatim: true,   // verified 2026-11-08
  },
  {
    id: "aavso", name: "AAVSO", when: "lightcurve",
    text: "We acknowledge with thanks the variable star observations from the AAVSO International Database " +
      "contributed by observers worldwide and used in this research.",
    url: "https://www.aavso.org/", verbatim: false,
  },
  {
    id: "catwise", name: "CatWISE2020", when: "movers",
    text: "Proper motions from the CatWISE2020 catalogue (Marocco et al. 2021, ApJS 253, 8), produced with funding from " +
      "NASA's Astrophysics Data Analysis Program.",
    url: "https://catwise.github.io/", verbatim: false,
  },
  {
    id: "unwise", name: "unWISE", when: "aladin",
    text: "unWISE / NASA/JPL-Caltech / D. Lang (Perimeter Institute). Lang 2014, AJ 147, 108; Meisner, Lang & Schlegel 2017.",
    url: "https://unwise.me/", verbatim: true,   // image attribution string verified 2026-11-08
  },
  {
    id: "templates", name: "Spectral templates", when: "spectrum",
    text: "Spectral standards from the SpeX Prism Library via SPLAT (Burgasser et al. 2017, ASInC 14, 7; original " +
      "data sources cited per template), IRTF Spectral Library spectra (Cushing et al. 2005; Rayner et al. 2009), " +
      "BT-Settl models (Allard et al. 2012) and the Pickles (1998) stellar library.",
    url: "https://github.com/aburgasser/splat", verbatim: false,
  },
  {
    id: "hips", name: "Aladin HiPS surveys", when: "aladin",
    text: "Background surveys in the sky context: 2MASS, AllWISE, unWISE, DSS2 and Pan-STARRS DR1, served as HiPS by CDS and its mirrors " +
      "(ESA ESAC, China-VO, CSIRO CASDA, STScI MAST).",
    url: "https://aladin.cds.unistra.fr/hips/list", verbatim: false,
  },
];

export const SOFTWARE = [
  { name: "Astropy", cite: "Astropy Collaboration 2013, 2018, 2022", url: "https://www.astropy.org/acknowledging.html" },
  { name: "reproject", cite: "Robitaille et al. (reproject, Zenodo)", url: "https://reproject.readthedocs.io/" },
  { name: "photutils", cite: "Bradley et al. (photutils, Zenodo)", url: "https://photutils.readthedocs.io/" },
  { name: "NumPy / SciPy", cite: "Harris et al. 2020; Virtanen et al. 2020", url: "https://numpy.org/citing-numpy/" },
  { name: "Aladin Lite v3", cite: "Boch & Fernique 2014; Baumann et al. 2022", url: "https://aladin.cds.unistra.fr/AladinLite/" },
  { name: "Archivo and IBM Plex Mono", cite: "Omnibus-Type; IBM. SIL Open Font License 1.1, bundled via Fontsource", url: "https://fontsource.org/" },
];

/** Space Apps 2026 asks that SI-generated code be acknowledged in the project itself (submission/2026-rules.md). */
export const SI_USE = "Use of SI (AI) tools: parts of ParallaX's code, tests and documentation were written with an SI " +
  "coding assistant (Claude Code). The idea and the scientific approach are the team's; no SI-generated images, video " +
  "or audio are used. Scientific claims rest on the evidence records listed on the proof page.";

export const UNVERIFIED = CREDITS.filter((c) => !c.verbatim).map((c) => c.id);

export const DISCLAIMER = "ParallaX is an independent NASA Space Apps Challenge 2026 project. It is not affiliated " +
  "with or endorsed by NASA, JPL, Caltech, IPAC or ESA.";
