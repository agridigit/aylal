/** F6 dictation parsing (R5). Pure, offline, text only: proposes a draft, never records anything. */
export const MAX_DICTATION_CHARS = 500;

export interface DictationParcel { id: string; name: string }
export interface DictationContext { parcels: readonly DictationParcel[]; today: string }
export interface DictationAmbiguity { field: string; candidates: string[] }
export interface DictationResult {
  understood: boolean;
  requires_confirmation: true;
  draft: Record<string, unknown>;
  ambiguous: DictationAmbiguity[];
}

const TYPE_WORDS: ReadonlyArray<readonly [string, readonly string[]]> = [
  ["phyto", ["traite", "traitement", "pulveris", "رشيت", "رش", "معالجة"]],
  ["irrigation", ["arros", "irrigu", "irrigation", "سقي", "سقيت", "سقي"]],
  ["fertilization", ["fertilis", "engrais", "فرتيليزاسيون", "سماد", "سمدت"]],
  ["pruning", ["taille", "tailler", "تقليم", "قلمت"]],
  ["harvest", ["recolt", "cueilli", "جني", "جنيت", "حصاد"]],
  ["weeding", ["desherb", "desherbe", "تعشيب"]],
];
const PRODUCT_WORDS: ReadonlyArray<readonly [string, readonly string[]]> = [
  ["cuivre", ["cuivre", "النحاس", "نحاس"]],
  ["soufre", ["soufre", "الكبريت", "كبريت"]],
];
const YESTERDAY = ["hier", "البارح", "البارحة", "امس", "أمس"];
const STOPWORDS = new Set(["du", "de", "des", "les", "le", "la", "l", "d", "ديال", "في"]);

function normalize(s: string): string {
  return s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
}

function addDays(date: string, days: number): string {
  const [y = 0, m = 1, d = 1] = date.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

function hasWord(tokens: readonly string[], words: readonly string[]): boolean {
  return tokens.some((t) =>
    words.some((w) => {
      const n = normalize(w);
      if (/^[a-z]+$/.test(n)) return n === t || (n.length >= 5 && t.startsWith(n));
      return t === n || t.endsWith(n); // Arabic clitic prefixes (ب, ل, و ...)
    }),
  );
}

function matchParcels(text: string, tokens: readonly string[], parcels: readonly DictationParcel[]): string[] {
  const padded = ` ${text} `;
  const full = parcels.filter((p) => padded.includes(` ${normalize(p.name)} `));
  if (full.length > 0) return full.map((p) => p.id);
  const sig = (name: string) => normalize(name).split(" ").filter((t) => t.length >= 4 && !STOPWORDS.has(t));
  return parcels.filter((p) => sig(p.name).some((t) => tokens.includes(t))).map((p) => p.id);
}

export function parseDictation(text: string, ctx: DictationContext): DictationResult {
  const empty: DictationResult = { understood: false, requires_confirmation: true, draft: {}, ambiguous: [] };
  if (text.length > MAX_DICTATION_CHARS) return empty;
  const norm = normalize(text);
  if (norm === "") return empty;
  const tokens = norm.split(" ");
  const type = TYPE_WORDS.find(([, words]) => hasWord(tokens, words))?.[0];
  if (!type) return empty;
  const draft: Record<string, unknown> = {
    type,
    performed_on: hasWord(tokens, YESTERDAY) ? addDays(ctx.today, -1) : ctx.today,
  };
  const ambiguous: DictationAmbiguity[] = [];
  const parcelIds = matchParcels(norm, tokens, ctx.parcels);
  if (parcelIds.length === 1) draft.parcel_ids = parcelIds;
  else ambiguous.push({ field: "parcel_ids", candidates: parcelIds });
  const product = PRODUCT_WORDS.find(([, words]) => hasWord(tokens, words))?.[0];
  if (product && type === "phyto") draft.product_query = product;
  return { understood: true, requires_confirmation: true, draft, ambiguous };
}

export interface DictationFlow {
  result: DictationResult;
  confirm(choices: Record<string, unknown>): Promise<unknown>;
  cancel(): void;
}

/** Nothing is saved until confirm() is called once with every ambiguous field resolved. */
export function startDictation(
  text: string,
  ctx: DictationContext,
  save: (draft: Record<string, unknown>) => Promise<unknown> | unknown,
): DictationFlow {
  const result = parseDictation(text, ctx);
  let closed = false;
  return {
    result,
    cancel() {
      closed = true;
    },
    async confirm(choices) {
      if (closed) throw new Error("dictation_closed");
      const draft = { ...result.draft, ...choices };
      for (const a of result.ambiguous) {
        const v = draft[a.field];
        if (v === undefined || (Array.isArray(v) && v.length === 0)) throw new Error("dictation_unresolved");
      }
      closed = true;
      return save(draft);
    },
  };
}
