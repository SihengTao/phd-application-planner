// phd-application-planner · parallel research workflow (v2 TEMPLATE)
// Intake config → regional discovery → per-program facts/faculty/outcomes →
// campus-anchored nearby food + blind independent verification.

export const meta = {
  name: 'phd-application-planner-research',
  description: 'Parallel, provenance-first research of doctoral programs, fitting faculty/advisors, outcomes, and nearby Chinese food',
  phases: [
    { title: 'Discover', detail: 'per-region candidate program discovery (parallel)' },
    { title: 'Research', detail: 'per-program facts ‖ faculty/advisors ‖ outcomes (parallel)' },
    { title: 'Nearby food', detail: 'verify the relevant campus anchor, then find nearby Chinese restaurants' },
    { title: 'Verify', detail: 'blind, source-first verification followed by conflict-preserving reconciliation' },
  ],
}

const cfg = args || {}
const firstIntake = cfg.first_intake || cfg.intake || {}
const getCfg = (key, fallback) => cfg[key] ?? firstIntake[key] ?? fallback
if (getCfg('intake_complete', false) !== true) {
  throw new Error('Research workflow requires a confirmed intake: pass intake_complete: true after the user reviews and confirms their requirements.')
}

const FIELD = getCfg('field', 'computational biology')
const SUBFIELDS = getCfg('subfields', '')
const rawRegions = getCfg('regions', [{ key: 'US', label: 'United States' }])
const REGIONS = Array.isArray(rawRegions) && rawRegions.length
  ? rawRegions
  : [{ key: 'US', label: 'United States' }]
const FLOOR = getCfg('stipend_floor', 35000)
const CURRENCY = getCfg('currency', 'USD')
const N_TOTAL = getCfg('n_programs', 20)
const N_FACULTY = getCfg('n_faculty_per_program', getCfg('n_pis_per_program', 10))
const FACULTY_PREFS = getCfg(
  'faculty_preferences',
  getCfg('pi_preferences', 'favor strong research/advising fit and credible current availability over fame'),
)
const RISING_WEIGHT = getCfg('rising_star_bias', 'strong')
const EXTRA = getCfg('notes', '')
const APPLICATION_CYCLE = getCfg('application_cycle', getCfg('effective_cycle', 'current published admission cycle'))
const RESEARCH_AS_OF = getCfg('research_as_of', new Date().toISOString())
const SEED = Array.isArray(getCfg('seed_programs', [])) ? getCfg('seed_programs', []) : []

const DISCIPLINE_MODES = ['lab_based', 'faculty_based', 'hybrid']
const requestedMode = getCfg('discipline_mode', null)
if (!DISCIPLINE_MODES.includes(requestedMode)) {
  throw new Error(`discipline_mode is required and must be one of: ${DISCIPLINE_MODES.join(', ')}.`)
}
const DISCIPLINE_MODE = requestedMode

const defaultRestaurantPreferences = {
  enabled: false,
  priority_cuisines: ['sichuan', 'cantonese', 'hunan'],
  spiceLevel: '🌶️🌶️🌶️',
  maxDistance: '30 minutes from the relevant campus by walking or public transit',
  pricePreference: 'any',
  minimumRating: null,
  notes: '',
}
const rawRestaurantPreferences = getCfg('food_preferences', getCfg('restaurant_preferences', null))
const normalizedRestaurantPreferences = typeof rawRestaurantPreferences === 'string'
  ? { ...defaultRestaurantPreferences, enabled: true, notes: rawRestaurantPreferences }
  : {
      ...defaultRestaurantPreferences,
      ...(rawRestaurantPreferences || {}),
      enabled: rawRestaurantPreferences == null
        ? false
        : rawRestaurantPreferences.enabled ?? true,
    }
const RESTAURANT_PREFERENCES = {
  ...normalizedRestaurantPreferences,
  priority_cuisines: normalizedRestaurantPreferences.priority_cuisines
    ?? normalizedRestaurantPreferences.cuisines
    ?? defaultRestaurantPreferences.priority_cuisines,
  maxDistance: normalizedRestaurantPreferences.max_distance
    ?? normalizedRestaurantPreferences.maxDistance
    ?? defaultRestaurantPreferences.maxDistance,
  travelModes: normalizedRestaurantPreferences.travel_modes
    ?? normalizedRestaurantPreferences.travelModes
    ?? ['walk', 'public_transit'],
  pricePreference: normalizedRestaurantPreferences.budget
    ?? normalizedRestaurantPreferences.pricePreference
    ?? defaultRestaurantPreferences.pricePreference,
  spiceLevel: normalizedRestaurantPreferences.spice
    ?? normalizedRestaurantPreferences.spiceLevel
    ?? defaultRestaurantPreferences.spiceLevel,
  dietaryNeeds: normalizedRestaurantPreferences.dietary_needs
    ?? normalizedRestaurantPreferences.dietaryNeeds
    ?? [],
}
const RESTAURANT_ENABLED = RESTAURANT_PREFERENCES.enabled !== false
const N_RESTAURANTS = getCfg('n_restaurants_per_program', 6)

const DISCIPLINE_GUIDANCE = DISCIPLINE_MODE === 'faculty_based'
  ? `This is a faculty-based humanities/social-sciences style search. Treat people as prospective
advisors/supervisors rather than assuming a lab-rotation model. Evaluate topic, theory,
methodology, language, archive/fieldwork, advising, placement, and departmental-home fit.
Do not infer that a professor is accepting students merely because their profile is online,
and do not use Scholar metrics as a substitute for intellectual or advising fit.`
  : DISCIPLINE_MODE === 'hybrid'
    ? `This is a hybrid search. Evaluate both lab/PI fit and faculty/advisor fit. Distinguish
central admissions, direct-admit, rotation, supervisor-first, and later-advisor-selection
models. Cover relevant experimental/computational facilities as well as theory, methods,
languages, archives/fieldwork, advising, and placement.`
    : `This is a lab-based search. Evaluate program membership, lab direction, methods,
wet/dry balance, lab stage/size, and evidence of current recruiting. Do not infer recruiting
from a merely active faculty or lab page.`

const FLOOR_LINE = FLOOR === 0
  ? `- Stipend threshold: 0 ${CURRENCY}/year means no positive minimum; still report the amount and use null when unknown.`
  : `- Stipend threshold: ${FLOOR} ${CURRENCY}/year; mark meetsFloor only when the converted amount is known.`

const WEB = `You have web access. If WebSearch/WebFetch are not already callable, FIRST call
ToolSearch with query "select:WebSearch,WebFetch" to load them, then use them. Research as of
${RESEARCH_AS_OF} for ${APPLICATION_CYCLE}. Prefer the most specific current official source:
program/department page, then school-wide policy, then a clearly identified primary source.
Third-party pages may help discovery but must not silently override a current official page.
An inaccessible page is "blocked" or "error", not "not found". If two applicable official
pages disagree, report a conflict instead of choosing one without explanation. Do not
fabricate stipends, deadlines, cohort numbers, faculty availability, outcomes, restaurant
details, or metrics. Use null for unknown numeric/boolean values, never -1.

Every substantive output section must include structured source records and collection
evidenceChecks.
Each source record needs a stable local id, exact URL/title/publisher, source type, official
flag, claimPaths, effectiveCycle, updatedAt, accessedAt, and retrievalStatus. Each entry in
evidenceChecks must link sourceIds and record one observed value, a
supported|unresolved|conflict status, conflict flag, checkedAt, and note. The workflow will
separately produce final independent-verification checks with initial, independent, and final
values; a first-pass "supported" claim is not equivalent to independently verified.`

const PROFILE = `Applicant research contract:
- Field: ${FIELD}${SUBFIELDS ? ' — subfields: ' + SUBFIELDS : ''}
- Discipline mode: ${DISCIPLINE_MODE}
- Target regions: ${REGIONS.map(r => r.label || r.key).join(', ')}
${FLOOR_LINE}
- Faculty/advisor preferences: ${FACULTY_PREFS}. Rising-star bias: ${RISING_WEIGHT}.
- Nearby Chinese food preferences: ${JSON.stringify(RESTAURANT_PREFERENCES)}
${EXTRA ? '- Other intake notes: ' + EXTRA : ''}

${DISCIPLINE_GUIDANCE}`

const NULLABLE_NUMBER = { anyOf: [{ type: 'number' }, { type: 'null' }] }
const NULLABLE_BOOLEAN = { anyOf: [{ type: 'boolean' }, { type: 'null' }] }
const NULLABLE_STRING = { anyOf: [{ type: 'string' }, { type: 'null' }] }
const CLAIM_VALUE = {
  anyOf: [{ type: 'string' }, { type: 'number' }, { type: 'boolean' }, { type: 'null' }],
  description: 'Use a scalar value; serialize complex values as concise JSON text.',
}

const SOURCE_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    id: { type: 'string' },
    url: { type: 'string' },
    title: { type: 'string' },
    publisher: { type: 'string' },
    sourceType: { type: 'string', description: 'official_program|official_institution|official_policy|official_faculty|official_lab|scholar_profile|placement_report|map_listing|restaurant_official|review_platform|other' },
    official: { type: 'boolean' },
    claimPaths: { type: 'array', items: { type: 'string' } },
    effectiveCycle: NULLABLE_STRING,
    updatedAt: NULLABLE_STRING,
    accessedAt: { type: 'string', description: 'ISO-8601 timestamp or date' },
    retrievalStatus: { type: 'string', enum: ['retrieved', 'partial', 'blocked', 'not_found', 'stale', 'error'] },
  },
  required: [
    'id', 'url', 'title', 'publisher', 'sourceType', 'official', 'claimPaths',
    'effectiveCycle', 'updatedAt', 'accessedAt', 'retrievalStatus',
  ],
}

const EVIDENCE_CHECK_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    claimPath: { type: 'string' },
    status: { type: 'string', enum: ['supported', 'unresolved', 'conflict'] },
    value: CLAIM_VALUE,
    sourceIds: { type: 'array', items: { type: 'string' } },
    checkedAt: { type: 'string', description: 'ISO-8601 timestamp or date' },
    conflict: { type: 'boolean' },
    note: { type: 'string' },
  },
  required: [
    'claimPath', 'status', 'value', 'sourceIds', 'checkedAt', 'conflict', 'note',
  ],
}

const CLAIM_CHECK_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    claimPath: { type: 'string' },
    status: { type: 'string', enum: ['confirmed', 'corrected', 'conflict', 'unresolved'] },
    initialValue: CLAIM_VALUE,
    independentValue: CLAIM_VALUE,
    finalValue: CLAIM_VALUE,
    sourceIds: { type: 'array', items: { type: 'string' } },
    checkedAt: { type: 'string', description: 'ISO-8601 timestamp or date' },
    conflict: { type: 'boolean' },
    resolution: { type: 'string' },
  },
  required: [
    'claimPath', 'status', 'initialValue', 'independentValue', 'finalValue',
    'sourceIds', 'checkedAt', 'conflict', 'resolution',
  ],
}

const ERROR_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    stage: { type: 'string' },
    code: { type: 'string' },
    message: { type: 'string' },
    url: NULLABLE_STRING,
    occurredAt: { type: 'string' },
    retryable: { type: 'boolean' },
  },
  required: ['stage', 'code', 'message', 'url', 'occurredAt', 'retryable'],
}

const CAMPUS_ANCHOR_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    name: { type: 'string' },
    address: { type: 'string' },
    sourceUrl: { type: 'string' },
  },
  required: ['name', 'address', 'sourceUrl'],
}

const DISCOVER_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    programs: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: {
          school: { type: 'string' },
          program: { type: 'string' },
          city: { type: 'string' },
          whyRelevant: { type: 'string' },
          officialProgramUrl: { type: 'string' },
          sources: { type: 'array', items: SOURCE_SCHEMA },
          evidenceChecks: { type: 'array', items: EVIDENCE_CHECK_SCHEMA },
          errors: { type: 'array', items: ERROR_SCHEMA },
        },
        required: ['school', 'program', 'sources', 'evidenceChecks', 'errors'],
      },
    },
  },
  required: ['programs'],
}

const FACTS_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    city: { type: 'string' },
    campusAnchor: CAMPUS_ANCHOR_SCHEMA,
    disciplineMode: { type: 'string', enum: DISCIPLINE_MODES },
    stipendUSD: { ...NULLABLE_NUMBER, description: `annual stipend converted to ${CURRENCY}; null if not established` },
    stipendCurrency: { type: 'string' },
    stipendLocal: NULLABLE_STRING,
    stipend_basis: NULLABLE_STRING,
    stipend_confidence: { type: 'string', enum: ['high', 'medium', 'low', 'unknown', 'conflict'] },
    stipend_foundOfficial: NULLABLE_BOOLEAN,
    stipendNotes: NULLABLE_STRING,
    meetsFloor: NULLABLE_BOOLEAN,
    cohortSize: { type: 'string' },
    degreeStructure: { type: 'string' },
    admissionsModel: { type: 'string', description: 'central|direct_admit|rotation|supervisor_first|later_advisor_selection|mixed|unknown, with explanation' },
    advisorSelection: { type: 'string' },
    applicationRoute: { type: 'string' },
    deadlineAndTests: NULLABLE_STRING,
    applicationDeadline: { ...NULLABLE_STRING, description: 'primary current-cycle deadline as YYYY-MM-DD; null if not published' },
    degreeType: { ...NULLABLE_STRING, description: 'awarded degree, e.g. PhD, DPhil, EdD, MD-PhD' },
    programUrl: { ...NULLABLE_STRING, description: 'official program home page' },
    applicationPortalUrl: { ...NULLABLE_STRING, description: 'official application portal or how-to-apply page' },
    applicationPolicy: { type: 'string', enum: ['multiple_allowed', 'single_only', 'unknown', 'conflict'] },
    applicationRestrictions: { type: 'string' },
    researchFocus: { type: 'string' },
    wetDryIntegration: { type: 'string' },
    gwasOrMechanistic: { type: 'string' },
    writingSampleRequirements: { type: 'string' },
    languageRequirements: { type: 'string' },
    methodsOrTheoryTraining: { type: 'string' },
    qualifyingOrFieldExamStructure: { type: 'string' },
    dissertationFormat: { type: 'string' },
    archiveFieldworkSupport: { type: 'string' },
    teachingRequirements: { type: 'string' },
    fitScore: { ...NULLABLE_NUMBER, description: 'fit-for-applicant 0-10; null if evidence is insufficient' },
    fitRationale: { type: 'string' },
    siblingPrograms: { type: 'string' },
    sources: { type: 'array', items: SOURCE_SCHEMA },
    evidenceChecks: { type: 'array', items: EVIDENCE_CHECK_SCHEMA },
    errors: { type: 'array', items: ERROR_SCHEMA },
  },
  required: [
    'campusAnchor', 'disciplineMode', 'stipendUSD', 'stipendCurrency',
    'stipend_foundOfficial', 'meetsFloor', 'applicationPolicy',
    'applicationRestrictions', 'fitScore', 'sources', 'evidenceChecks', 'errors',
  ],
}

const FACULTY_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    faculty: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: {
          advisor_id: { type: 'string' },
          name: { type: 'string' },
          category: { type: 'string', enum: ['rising_star', 'direction_fit', 'interesting', 'famous_but_fits'] },
          roleType: { type: 'string', enum: ['lab_pi', 'primary_advisor', 'potential_supervisor', 'program_faculty', 'committee_member', 'other'] },
          rank: { type: 'string' },
          disciplinaryHome: { type: 'string' },
          hIndex: { ...NULLABLE_NUMBER, description: 'time-stamped snapshot; null when unavailable or inappropriate' },
          citations: { ...NULLABLE_NUMBER, description: 'time-stamped snapshot; null when unavailable or inappropriate' },
          scholarUrl: { type: 'string' },
          startedApprox: NULLABLE_STRING,
          labSize: { type: 'string' },
          wetDry: { type: 'string', enum: ['dry', 'wet', 'both', 'not_applicable', 'unknown'] },
          research: { type: 'string' },
          theoreticalApproaches: { type: 'string' },
          methodologicalApproaches: { type: 'string' },
          languagesArchivesOrFieldwork: { type: 'string' },
          recentWork: { type: 'string' },
          whyFit: { type: 'string' },
          advisingFit: { type: 'string' },
          recruiting: { type: 'string' },
          contactGuidance: { type: 'string' },
          url: { type: 'string' },
          sourceIds: { type: 'array', items: { type: 'string' } },
        },
        required: ['name', 'category', 'roleType', 'whyFit', 'sourceIds'],
      },
    },
    sources: { type: 'array', items: SOURCE_SCHEMA },
    evidenceChecks: { type: 'array', items: EVIDENCE_CHECK_SCHEMA },
    errors: { type: 'array', items: ERROR_SCHEMA },
  },
  required: ['faculty', 'sources', 'evidenceChecks', 'errors'],
}

const OUTCOMES_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    careerOutcomes: { type: 'string' },
    placementTransparency: { type: 'string' },
    namedPlacements: { type: 'string' },
    admitBackgrounds: { type: 'string' },
    intlNotes: { type: 'string' },
    timeToDegree: { type: 'string' },
    teachingPreparation: { type: 'string' },
    nonAcademicCareerSupport: { type: 'string' },
    publicHumanitiesOrPolicyOpportunities: { type: 'string' },
    extraIntel: { type: 'string' },
    sources: { type: 'array', items: SOURCE_SCHEMA },
    evidenceChecks: { type: 'array', items: EVIDENCE_CHECK_SCHEMA },
    errors: { type: 'array', items: ERROR_SCHEMA },
  },
  required: ['careerOutcomes', 'sources', 'evidenceChecks', 'errors'],
}

const VERIFY_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    stipendUSD: { ...NULLABLE_NUMBER, description: `independently found annual amount in ${CURRENCY}; null if unresolved` },
    stipendCurrency: { type: 'string' },
    stipendLocal: NULLABLE_STRING,
    stipend_basis: NULLABLE_STRING,
    stipend_confidence: { type: 'string', enum: ['high', 'medium', 'low', 'unknown', 'conflict'] },
    stipend_foundOfficial: NULLABLE_BOOLEAN,
    stipendNotes: NULLABLE_STRING,
    applicationPolicy: { type: 'string', enum: ['multiple_allowed', 'single_only', 'unknown', 'conflict'] },
    applicationRestrictions: { type: 'string' },
    deadlineAndTests: NULLABLE_STRING,
    sources: { type: 'array', items: SOURCE_SCHEMA },
    evidenceChecks: { type: 'array', items: EVIDENCE_CHECK_SCHEMA },
    errors: { type: 'array', items: ERROR_SCHEMA },
  },
  required: [
    'stipendUSD', 'stipendCurrency', 'stipendLocal', 'stipend_basis',
    'stipend_confidence', 'stipend_foundOfficial', 'stipendNotes',
    'applicationPolicy', 'applicationRestrictions', 'deadlineAndTests',
    'sources', 'evidenceChecks', 'errors',
  ],
}

const NEARBY_FOOD_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    enabled: { type: 'boolean' },
    researchStatus: { type: 'string', enum: ['not_requested', 'complete', 'partial', 'failed'] },
    campusAnchor: CAMPUS_ANCHOR_SCHEMA,
    restaurants: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: {
          name: { type: 'string' },
          cuisine: { type: 'string', enum: ['sichuan', 'cantonese', 'hunan', 'other_chinese'] },
          cuisineLabel: { type: 'string', description: 'e.g. 川菜, 粤菜, 湘菜' },
          address: { type: 'string' },
          distanceFromCampus: { type: 'string' },
          distanceKm: NULLABLE_NUMBER,
          transitMode: { type: 'string' },
          priceLevel: { type: 'string' },
          rating: NULLABLE_NUMBER,
          ratingScale: NULLABLE_NUMBER,
          reviewCount: NULLABLE_NUMBER,
          operatingStatus: { type: 'string', enum: ['open', 'temporarily_closed', 'permanently_closed', 'unknown'] },
          spiceFit: { type: 'string' },
          whyRecommended: { type: 'string' },
          url: { type: 'string' },
          sourceIds: { type: 'array', items: { type: 'string' } },
        },
        required: [
          'name', 'cuisine', 'address', 'distanceFromCampus', 'rating',
          'operatingStatus', 'whyRecommended', 'sourceIds',
        ],
      },
    },
    sources: { type: 'array', items: SOURCE_SCHEMA },
    evidenceChecks: { type: 'array', items: EVIDENCE_CHECK_SCHEMA },
    errors: { type: 'array', items: ERROR_SCHEMA },
  },
  required: [
    'enabled', 'researchStatus', 'campusAnchor', 'restaurants',
    'sources', 'evidenceChecks', 'errors',
  ],
}

const now = () => new Date().toISOString()
const SHA256_CONSTANTS = [
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
  0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
  0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
  0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
  0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
  0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
  0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
  0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
  0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]
const rotateRight = (value, shift) => (value >>> shift) | (value << (32 - shift))
const sha256Hex = text => {
  const bytes = Array.from(new TextEncoder().encode(text))
  const bitLength = bytes.length * 8
  bytes.push(0x80)
  while (bytes.length % 64 !== 56) bytes.push(0)
  const highBits = Math.floor(bitLength / 0x100000000)
  const lowBits = bitLength >>> 0
  for (let shift = 24; shift >= 0; shift -= 8) bytes.push((highBits >>> shift) & 0xff)
  for (let shift = 24; shift >= 0; shift -= 8) bytes.push((lowBits >>> shift) & 0xff)

  const hash = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ]
  const words = new Array(64)
  for (let offset = 0; offset < bytes.length; offset += 64) {
    for (let index = 0; index < 16; index += 1) {
      const position = offset + index * 4
      words[index] = (
        (bytes[position] << 24)
        | (bytes[position + 1] << 16)
        | (bytes[position + 2] << 8)
        | bytes[position + 3]
      )
    }
    for (let index = 16; index < 64; index += 1) {
      const sigma0 = rotateRight(words[index - 15], 7)
        ^ rotateRight(words[index - 15], 18)
        ^ (words[index - 15] >>> 3)
      const sigma1 = rotateRight(words[index - 2], 17)
        ^ rotateRight(words[index - 2], 19)
        ^ (words[index - 2] >>> 10)
      words[index] = (words[index - 16] + sigma0 + words[index - 7] + sigma1) | 0
    }

    let [a, b, c, d, e, f, g, h] = hash
    for (let index = 0; index < 64; index += 1) {
      const sum1 = rotateRight(e, 6) ^ rotateRight(e, 11) ^ rotateRight(e, 25)
      const choose = (e & f) ^ (~e & g)
      const temp1 = (h + sum1 + choose + SHA256_CONSTANTS[index] + words[index]) | 0
      const sum0 = rotateRight(a, 2) ^ rotateRight(a, 13) ^ rotateRight(a, 22)
      const majority = (a & b) ^ (a & c) ^ (b & c)
      const temp2 = (sum0 + majority) | 0
      h = g
      g = f
      f = e
      e = (d + temp1) | 0
      d = c
      c = b
      b = a
      a = (temp1 + temp2) | 0
    }
    hash[0] = (hash[0] + a) | 0
    hash[1] = (hash[1] + b) | 0
    hash[2] = (hash[2] + c) | 0
    hash[3] = (hash[3] + d) | 0
    hash[4] = (hash[4] + e) | 0
    hash[5] = (hash[5] + f) | 0
    hash[6] = (hash[6] + g) | 0
    hash[7] = (hash[7] + h) | 0
  }
  return hash.map(value => (value >>> 0).toString(16).padStart(8, '0')).join('')
}
const stableId = (prefix, parts) => {
  const serialized = (Array.isArray(parts) ? parts : [parts])
    .map(value => String(value ?? '').trim().toLowerCase())
    .join('\u001f')
  return `${prefix}_${sha256Hex(serialized).slice(0, 16)}`
}
const makeError = (stage, code, message, url = null, retryable = true) => ({
  stage, code, message, url, occurredAt: now(), retryable,
})

const safeAgent = (prompt, options, stage) =>
  agent(prompt, options)
    .then(data => data
      ? { ok: true, data, error: null }
      : { ok: false, data: null, error: makeError(stage, 'empty_agent_result', 'The research agent returned no structured result.') })
    .catch(error => ({
      ok: false,
      data: null,
      error: makeError(stage, 'agent_error', String(error && error.message ? error.message : error)),
    }))

const normalizeClaimPath = (section, path) => {
  const value = String(path || '').replace(/^\.+/, '')
  if (!value) return section
  if (value === section || value.startsWith(`${section}.`) || value.startsWith(`${section}[`)) return value
  return `${section}.${value}`
}

const normalizeEvidence = (section, payload) => {
  if (!payload) return { sources: [], checks: [], errors: [] }
  const rawSources = Array.isArray(payload.sources) ? payload.sources : []
  const rawChecks = Array.isArray(payload.evidenceChecks)
    ? payload.evidenceChecks
    : (Array.isArray(payload.claimChecks) ? payload.claimChecks : [])
  const rawErrors = Array.isArray(payload.errors) ? payload.errors : []
  const idMap = new Map()
  const sources = rawSources.map((source, index) => {
    const oldId = String(source.id || `source-${index + 1}`)
    const id = oldId.startsWith(`${section}/`) ? oldId : `${section}/${oldId}`
    idMap.set(oldId, id)
    return {
      ...source,
      id,
      claimPaths: (source.claimPaths || []).map(path => normalizeClaimPath(section, path)),
    }
  })
  const mapSourceId = id => idMap.get(String(id)) || `${section}/${String(id)}`
  const checks = rawChecks.map(check => ({
    ...check,
    claimPath: normalizeClaimPath(section, check.claimPath),
    sourceIds: (check.sourceIds || []).map(mapSourceId),
  }))
  const errors = rawErrors.map(error => ({
    ...error,
    stage: error.stage ? `${section}:${error.stage}` : section,
  }))
  payload.sources = sources
  payload.evidenceChecks = checks
  if (Object.prototype.hasOwnProperty.call(payload, 'claimChecks')) delete payload.claimChecks
  payload.errors = errors
  if (Array.isArray(payload.faculty)) {
    payload.faculty = payload.faculty.map(person => ({
      ...person,
      sourceIds: (person.sourceIds || []).map(mapSourceId),
    }))
  }
  if (Array.isArray(payload.restaurants)) {
    payload.restaurants = payload.restaurants.map(place => ({
      ...place,
      sourceIds: (place.sourceIds || []).map(mapSourceId),
    }))
  }
  return { sources, checks, errors }
}

const emptyCampusAnchor = candidate => ({
  name: `${candidate.program || candidate.school} campus`,
  address: candidate.city || '',
  sourceUrl: '',
})

const emptyFacts = candidate => ({
  city: candidate.city || '',
  campusAnchor: emptyCampusAnchor(candidate),
  disciplineMode: DISCIPLINE_MODE,
  stipendUSD: null,
  stipendCurrency: CURRENCY,
  stipend_foundOfficial: null,
  meetsFloor: null,
  applicationPolicy: 'unknown',
  applicationRestrictions: 'Research task did not return a result.',
  fitScore: null,
  sources: [],
  evidenceChecks: [],
  errors: [],
})

const emptyFaculty = () => ({ faculty: [], sources: [], evidenceChecks: [], errors: [] })
const emptyOutcomes = () => ({
  careerOutcomes: 'Research task did not return a result.',
  sources: [], evidenceChecks: [], errors: [],
})
const emptyVerification = () => ({
  stipendUSD: null,
  stipendCurrency: CURRENCY,
  stipendLocal: null,
  stipend_basis: null,
  stipend_confidence: 'unknown',
  stipend_foundOfficial: null,
  stipendNotes: null,
  applicationPolicy: 'unknown',
  applicationRestrictions: 'Independent verification did not return a result.',
  deadlineAndTests: null,
  sources: [], evidenceChecks: [], errors: [],
})
const bestKnownCampusAnchor = candidate =>
  candidate && candidate.facts && candidate.facts.campusAnchor
    ? { ...candidate.facts.campusAnchor }
    : emptyCampusAnchor(candidate)
const emptyNearbyFood = (candidate, enabled = false, researchStatus = 'not_requested') => ({
  enabled,
  researchStatus,
  campusAnchor: bestKnownCampusAnchor(candidate),
  restaurants: [],
  sources: [],
  evidenceChecks: [],
  errors: [],
})

const knownValue = value =>
  value !== null && value !== undefined && value !== '' && value !== 'unknown'

const sameValue = (left, right) => {
  if (typeof left === 'number' && typeof right === 'number') return Math.abs(left - right) < 0.01
  return left === right
}

const reconcileClaim = (
  claimPath,
  initialValue,
  independentValue,
  sourceIds,
  independentEvidence,
  conflictValue = null,
) => {
  const checkedAt = now()
  const initialKnown = knownValue(initialValue)
  const independentKnown = knownValue(independentValue)
  if (!independentEvidence) {
    return {
      claimPath, status: 'unresolved', initialValue, independentValue,
      finalValue: initialKnown
        ? initialValue
        : (conflictValue === 'conflict' ? 'unknown' : null),
      sourceIds, checkedAt, conflict: false,
      resolution: 'No independently retrieved official source supports this claim; the initial value remains provisional and the independent value was not promoted.',
    }
  }
  if (initialValue === 'conflict' || independentValue === 'conflict') {
    return {
      claimPath, status: 'conflict', initialValue, independentValue,
      finalValue: conflictValue, sourceIds, checkedAt, conflict: true,
      resolution: 'At least one research pass found conflicting applicable sources; no unsupported winner was selected.',
    }
  }
  if (initialKnown && independentKnown && sameValue(initialValue, independentValue)) {
    return {
      claimPath, status: 'confirmed', initialValue, independentValue,
      finalValue: initialValue, sourceIds, checkedAt, conflict: false,
      resolution: 'The blind independent pass confirmed the initial value.',
    }
  }
  if (!initialKnown && independentKnown) {
    return {
      claimPath, status: 'corrected', initialValue, independentValue,
      finalValue: independentValue, sourceIds, checkedAt, conflict: false,
      resolution: 'The independent pass supplied a source-backed value that was missing initially.',
    }
  }
  if (initialKnown && !independentKnown) {
    return {
      claimPath, status: 'unresolved', initialValue, independentValue,
      finalValue: initialValue, sourceIds, checkedAt, conflict: false,
      resolution: 'The initial value is retained as provisional because the independent pass could not confirm it.',
    }
  }
  if (!initialKnown && !independentKnown) {
    return {
      claimPath, status: 'unresolved', initialValue, independentValue,
      finalValue: conflictValue === 'conflict' ? 'unknown' : null,
      sourceIds, checkedAt, conflict: false,
      resolution: 'Neither pass established this value.',
    }
  }
  return {
    claimPath, status: 'conflict', initialValue, independentValue,
    finalValue: conflictValue, sourceIds, checkedAt, conflict: true,
    resolution: 'The initial and blind independent passes disagree; the conflict is preserved for review.',
  }
}

const claimTokens = tokens => (Array.isArray(tokens) ? tokens : [tokens])
  .map(token => String(token).toLowerCase())

const sourceMatchesClaim = (source, tokens) =>
  (source.claimPaths || []).some(path => {
    const normalizedPath = String(path).toLowerCase()
    return claimTokens(tokens).some(token => normalizedPath.includes(token))
  })

const sourceIdsFor = (sources, tokens) =>
  (sources || [])
    .filter(source => sourceMatchesClaim(source, tokens))
    .map(source => source.id)

const hasIndependentOfficialEvidence = (sources, tokens) =>
  (sources || []).some(source =>
    source.official === true
    && source.retrievalStatus === 'retrieved'
    && sourceMatchesClaim(source, tokens))

const overallVerificationStatus = checks => {
  if (checks.some(check => check.status === 'conflict')) return 'conflict'
  if (checks.some(check => check.status === 'unresolved')) return 'unresolved'
  if (checks.some(check => check.status === 'corrected')) return 'corrected'
  return 'confirmed'
}

const workflowErrors = []

// ---------- Phase 1: Discover ----------
phase('Discover')
let candidates = SEED.map(seed => ({
  ...seed,
  program_id: seed.program_id || stableId('program', [seed.region, seed.school, seed.program]),
  discovery: {
    whyRelevant: 'User-provided seed program.',
    officialProgramUrl: '',
    sources: [],
    evidenceChecks: [],
    errors: [],
  },
}))
if (candidates.length < N_TOTAL) {
  const perRegion = Math.max(4, Math.ceil((N_TOTAL - candidates.length) / REGIONS.length) + 2)
  const found = await parallel(REGIONS.map(region => () =>
    safeAgent(
      `${WEB}\n\n${PROFILE}\n\nTASK: Find ${perRegion} strong doctoral programs in
${region.label || region.key}. Use the exact current official program identity and URL.
For ${DISCIPLINE_MODE}, prioritize programs with dense, genuinely relevant
${DISCIPLINE_MODE === 'lab_based' ? 'PI/lab' : 'faculty/advisor'} coverage. Do not reject a
program merely because its stipend is below the threshold; record that later. For every
candidate return school, exact program name, city, whyRelevant, and discovery provenance.
Use claim paths rooted at "discovery".`,
      { label: `discover:${region.key}`, phase: 'Discover', schema: DISCOVER_SCHEMA },
      `discover:${region.key}`,
    ).then(run => ({ region: region.key, run })),
  ))
  const seen = new Set(candidates.map(candidate =>
    `${candidate.school || ''}|${candidate.program || ''}`.toLowerCase()))
  for (const item of found || []) {
    if (!item || !item.run || !item.run.ok) {
      if (item && item.run && item.run.error) workflowErrors.push(item.run.error)
      continue
    }
    for (const program of item.run.data.programs || []) {
      const key = `${program.school || ''}|${program.program || ''}`.toLowerCase()
      if (!program.school || !program.program || seen.has(key)) continue
      seen.add(key)
      candidates.push({
        program_id: stableId('program', [item.region, program.school, program.program]),
        region: item.region,
        school: program.school,
        program: program.program,
        city: program.city || '',
        discovery: {
          whyRelevant: program.whyRelevant || '',
          officialProgramUrl: program.officialProgramUrl || '',
          sources: program.sources || [],
          evidenceChecks: program.evidenceChecks || program.claimChecks || [],
          errors: program.errors || [],
        },
      })
    }
  }
}
candidates = candidates.slice(0, N_TOTAL)
log(`researching ${candidates.length} programs across ${REGIONS.length} regions in ${DISCIPLINE_MODE} mode`)

// ---------- Phase 2+3: research, blind verification, and campus-anchored food ----------
phase('Research')
const results = await pipeline(
  candidates,
  candidate => parallel([
    () => safeAgent(
      `${WEB}\n\n${PROFILE}\n\nTASK: Build a current factual profile of "${candidate.program}"
at ${candidate.school} (${candidate.city || 'city not yet confirmed'}). Verify the relevant
program/department campus anchor, funding amount and basis, cohort/degree structure,
admissions/advisor-selection model, deadlines/tests, and whether the institution permits
multiple applications in the same cycle. Also record the tracker fields degreeType,
applicationDeadline (YYYY-MM-DD for the main current-cycle deadline), programUrl, and
applicationPortalUrl from official pages, or null. applicationPolicy MUST be exactly one of
multiple_allowed, single_only, unknown, conflict. Fill discipline-relevant fields: for
faculty_based/hybrid modes specifically research writing samples, languages, theory/methods
training, field/qualifying exams, dissertation form, archives/fieldwork support, and teaching.
Compute fitScore from this applicant's contract, not generic prestige. Use null for unknown
numbers/booleans. Use source and claim paths rooted at "facts".`,
      { label: `facts:${candidate.region}:${candidate.school}:${candidate.program}`, phase: 'Research', schema: FACTS_SCHEMA },
      `facts:${candidate.school}:${candidate.program}`,
    ),
    () => safeAgent(
      `${WEB}\n\n${PROFILE}\n\nTASK: Find up to ${N_FACULTY} people through
"${candidate.program}" at ${candidate.school} who fit this applicant. ${FACULTY_PREFS}.
First verify each person's current program affiliation; separately verify any recruiting or
advising-availability claim. For lab_based mode cover lab direction, methods, wet/dry balance,
stage and size. For faculty_based mode cover disciplinary home, intellectual/theoretical fit,
methods, languages/archives/fieldwork, recent work, advising role/model, and whether contact
before applying is appropriate; do not force lab concepts onto HSS faculty. For hybrid mode
cover both where applicable. Scholar metrics are optional snapshots and MUST be null rather
than -1 when unavailable or inappropriate. Return sourceIds for every person and claim checks
rooted at "faculty".`,
      { label: `faculty:${candidate.region}:${candidate.school}:${candidate.program}`, phase: 'Research', schema: FACULTY_SCHEMA },
      `faculty:${candidate.school}:${candidate.program}`,
    ),
    () => safeAgent(
      `${WEB}\n\n${PROFILE}\n\nTASK: Research outcomes and applicant context for
"${candidate.program}" at ${candidate.school}. Distinguish a published placement record from
anecdotes and from silence. Cover career outcomes, named placements when published, typical
admit backgrounds, international-student funding/visa context, and time to degree. For
faculty_based/hybrid modes emphasize academic placement by field, teaching preparation,
public-humanities/policy opportunities, and support for nonacademic careers. Be explicit when
the program publishes no usable data. Use source and claim paths rooted at "outcomes".`,
      { label: `outcomes:${candidate.region}:${candidate.school}:${candidate.program}`, phase: 'Research', schema: OUTCOMES_SCHEMA },
      `outcomes:${candidate.school}:${candidate.program}`,
    ),
  ]).then(([factsRun, facultyRun, outcomesRun]) => {
    const facts = factsRun.ok ? factsRun.data : emptyFacts(candidate)
    const faculty = facultyRun.ok ? facultyRun.data : emptyFaculty()
    const outcomes = outcomesRun.ok ? outcomesRun.data : emptyOutcomes()
    if (factsRun.error) facts.errors.push(factsRun.error)
    if (facultyRun.error) faculty.errors.push(facultyRun.error)
    if (outcomesRun.error) outcomes.errors.push(outcomesRun.error)
    normalizeEvidence('facts', facts)
    normalizeEvidence('faculty', faculty)
    normalizeEvidence('outcomes', outcomes)
    faculty.faculty = (faculty.faculty || []).map(person => ({
      ...person,
      advisor_id: person.advisor_id || stableId('advisor', [
        candidate.program_id,
        person.name,
      ]),
    }))
    return { ...candidate, facts, faculty, outcomes }
  }),
  record => parallel([
    () => safeAgent(
      `${WEB}\n\n${PROFILE}\n\nINDEPENDENT SOURCE-FIRST VERIFY: Research
"${record.program}" at ${record.school} from scratch. You are intentionally NOT given the
first-pass values. Do not search for confirmation of a prior answer. Independently establish
the current-cycle annual stipend in ${CURRENCY}, stipend basis, whether it is stated on an
applicable official page, the exact applicationPolicy
(multiple_allowed|single_only|unknown|conflict), the plain-language restriction, and current
deadline/test requirements. If applicable official pages disagree, return conflict/unknown
rather than selecting one silently. On each source, name every exact supported claim path
(verification.stipendUSD, verification.stipendLocal, verification.stipend_basis,
verification.stipendNotes, verification.applicationPolicy,
verification.applicationRestrictions, verification.deadlineAndTests); do not use one generic
"stipend" path as evidence for unsupported details. Use source and claim paths rooted at
"verification".`,
      { label: `verify:${record.region}:${record.school}:${record.program}`, phase: 'Verify', schema: VERIFY_SCHEMA },
      `verify:${record.school}:${record.program}`,
    ),
    () => {
      if (!RESTAURANT_ENABLED) {
        return Promise.resolve({
          ok: true,
          data: emptyNearbyFood(record),
          error: null,
        })
      }
      const anchor = record.facts && record.facts.campusAnchor
        ? record.facts.campusAnchor
        : emptyCampusAnchor(record)
      return safeAgent(
        `${WEB}\n\n${PROFILE}\n\nTASK: Find up to ${N_RESTAURANTS} genuinely nearby,
currently operating Chinese restaurants for "${record.program}" at ${record.school}.

ORDER IS MANDATORY:
1. First independently verify the relevant teaching/department campus anchor. The first pass
suggested ${JSON.stringify(anchor)}; correct it if an official school/program page indicates
another campus.
2. Only after anchoring the campus, search map/listing/restaurant/review sources for nearby
places. Prioritize Sichuan (川菜), Cantonese (粤菜), and Hunan (湘菜), especially
${RESTAURANT_PREFERENCES.spiceLevel || 'spicy'} options, subject to these intake preferences:
${JSON.stringify(RESTAURANT_PREFERENCES)}.

Do not measure from a city center or a different campus. Report distance/transit basis,
operating status, price/rating only when source-backed, and use null for unknown numeric
values. Restaurant facts are volatile: include current accessedAt and retrievalStatus.
Return enabled=true. Set researchStatus to complete when the requested search was completed,
partial when retrieval limitations leave a usable but incomplete result, or failed when no
usable campus-anchored search result could be produced.
Use source and claim paths rooted at "nearbyFood".`,
        { label: `food:${record.region}:${record.school}:${record.program}`, phase: 'Nearby food', schema: NEARBY_FOOD_SCHEMA },
        `nearbyFood:${record.school}:${record.program}`,
      )
    },
  ]).then(([verificationRun, foodRun]) => {
    const verificationPass = verificationRun.ok ? verificationRun.data : emptyVerification()
    const nearbyFood = foodRun.ok
      ? foodRun.data
      : emptyNearbyFood(record, true, 'failed')
    if (verificationRun.error) verificationPass.errors.push(verificationRun.error)
    if (foodRun.error) nearbyFood.errors.push(foodRun.error)
    nearbyFood.enabled = RESTAURANT_ENABLED
    if (!RESTAURANT_ENABLED) {
      nearbyFood.researchStatus = 'not_requested'
      nearbyFood.campusAnchor = bestKnownCampusAnchor(record)
    } else if (nearbyFood.researchStatus === 'not_requested') {
      nearbyFood.researchStatus = nearbyFood.errors.length ? 'failed' : 'partial'
    }
    const verificationEvidence = normalizeEvidence('verification', verificationPass)
    const foodEvidence = normalizeEvidence('nearbyFood', nearbyFood)
    const discoveryEvidence = normalizeEvidence('discovery', record.discovery || {
      sources: [], evidenceChecks: [], errors: [],
    })

    const factsInitial = record.facts
    const claimEvidence = tokens => ({
      sourceIds: [...new Set([
        ...sourceIdsFor(factsInitial.sources, tokens),
        ...sourceIdsFor(verificationPass.sources, tokens),
      ])],
      independent: hasIndependentOfficialEvidence(verificationPass.sources, tokens),
    })
    const stipendEvidence = claimEvidence(['stipendusd', 'stipendamount'])
    const stipendLocalEvidence = claimEvidence('stipendlocal')
    const stipendBasisEvidence = claimEvidence('stipend_basis')
    const stipendNotesEvidence = claimEvidence('stipendnotes')
    const policyEvidence = claimEvidence('applicationpolicy')
    const restrictionEvidence = claimEvidence('applicationrestriction')
    const deadlineEvidence = claimEvidence(['deadlineandtests', 'deadline'])
    const stipendCheck = reconcileClaim(
      'facts.stipendUSD',
      factsInitial.stipendUSD ?? null,
      verificationPass.stipendUSD ?? null,
      stipendEvidence.sourceIds,
      stipendEvidence.independent,
      null,
    )
    const stipendLocalCheck = reconcileClaim(
      'facts.stipendLocal',
      factsInitial.stipendLocal ?? null,
      verificationPass.stipendLocal ?? null,
      stipendLocalEvidence.sourceIds,
      stipendLocalEvidence.independent,
      'Conflicting stipend-local statements; inspect provenance.',
    )
    const stipendBasisCheck = reconcileClaim(
      'facts.stipend_basis',
      factsInitial.stipend_basis ?? null,
      verificationPass.stipend_basis ?? null,
      stipendBasisEvidence.sourceIds,
      stipendBasisEvidence.independent,
      'Conflicting stipend-basis statements; inspect provenance.',
    )
    const stipendNotesCheck = reconcileClaim(
      'facts.stipendNotes',
      factsInitial.stipendNotes ?? null,
      verificationPass.stipendNotes ?? null,
      stipendNotesEvidence.sourceIds,
      stipendNotesEvidence.independent,
      'Conflicting stipend notes; inspect provenance.',
    )
    const policyCheck = reconcileClaim(
      'facts.applicationPolicy',
      factsInitial.applicationPolicy || 'unknown',
      verificationPass.applicationPolicy || 'unknown',
      policyEvidence.sourceIds,
      policyEvidence.independent,
      'conflict',
    )
    const restrictionCheck = reconcileClaim(
      'facts.applicationRestrictions',
      factsInitial.applicationRestrictions ?? null,
      verificationPass.applicationRestrictions ?? null,
      restrictionEvidence.sourceIds,
      restrictionEvidence.independent,
      'Conflicting applicable-source findings; inspect provenance.',
    )
    const deadlineCheck = reconcileClaim(
      'facts.deadlineAndTests',
      factsInitial.deadlineAndTests ?? null,
      verificationPass.deadlineAndTests ?? null,
      deadlineEvidence.sourceIds,
      deadlineEvidence.independent,
      'Conflicting deadline/test findings; inspect provenance.',
    )
    const optionalDetailChecks = [
      stipendLocalCheck,
      stipendBasisCheck,
      stipendNotesCheck,
      restrictionCheck,
    ].filter(check => knownValue(check.initialValue) || knownValue(check.independentValue))
    const verificationChecks = [
      stipendCheck,
      policyCheck,
      deadlineCheck,
      ...optionalDetailChecks,
    ]
    const verificationStatus = overallVerificationStatus(verificationChecks)
    const factsFinal = {
      ...factsInitial,
      stipendUSD: stipendCheck.finalValue,
      stipendCurrency: CURRENCY,
      stipendLocal: stipendLocalCheck.finalValue,
      stipend_basis: stipendBasisCheck.finalValue,
      stipendNotes: stipendNotesCheck.finalValue,
      meetsFloor: typeof stipendCheck.finalValue === 'number'
        ? stipendCheck.finalValue >= FLOOR
        : null,
      applicationPolicy: policyCheck.finalValue,
      applicationRestrictions: restrictionCheck.finalValue,
      deadlineAndTests: deadlineCheck.finalValue,
      stipend_foundOfficial: stipendCheck.status === 'conflict'
        ? null
        : stipendEvidence.independent
          && (stipendCheck.status === 'confirmed' || stipendCheck.status === 'corrected')
          ? verificationPass.stipend_foundOfficial ?? factsInitial.stipend_foundOfficial
          : factsInitial.stipend_foundOfficial,
      stipend_confidence: stipendCheck.status === 'conflict'
        ? 'conflict'
        : stipendCheck.status === 'unresolved'
          ? 'low'
          : factsInitial.stipend_confidence || verificationPass.stipend_confidence || 'unknown',
      sources: [...(factsInitial.sources || []), ...(verificationPass.sources || [])],
      evidenceChecks: [
        ...(factsInitial.evidenceChecks || []),
        ...(verificationPass.evidenceChecks || []),
      ],
      claimChecks: verificationChecks,
      errors: [...(factsInitial.errors || []), ...(verificationPass.errors || [])],
    }

    const collectionEvidenceChecks = [
      ...discoveryEvidence.checks,
      ...(factsInitial.evidenceChecks || []),
      ...(record.faculty.evidenceChecks || []),
      ...(record.outcomes.evidenceChecks || []),
      ...foodEvidence.checks,
      ...verificationEvidence.checks,
    ]
    const conflicts = verificationChecks
      .filter(check => check.conflict)
      .map(check => ({
        claimPath: check.claimPath,
        initialValue: check.initialValue,
        independentValue: check.independentValue,
        sourceIds: check.sourceIds,
        status: 'open',
        resolution: check.resolution,
      }))
      .concat(collectionEvidenceChecks
        .filter(check => check.status === 'conflict' || check.conflict === true)
        .map(check => ({
          claimPath: check.claimPath,
          initialValue: check.value ?? null,
          independentValue: null,
          sourceIds: check.sourceIds || [],
          status: 'open',
          resolution: check.note || 'The evidence-collection pass reported a source conflict.',
        })))
    const allErrors = [
      ...(discoveryEvidence.errors || []),
      ...(factsFinal.errors || []),
      ...(record.faculty.errors || []),
      ...(record.outcomes.errors || []),
      ...(foodEvidence.errors || []),
    ]
    const provenance = {
      applicationCycle: APPLICATION_CYCLE,
      sources: [
        ...discoveryEvidence.sources,
        ...(factsFinal.sources || []),
        ...(record.faculty.sources || []),
        ...(record.outcomes.sources || []),
        ...foodEvidence.sources,
      ],
      evidenceChecks: collectionEvidenceChecks,
      checks: verificationChecks,
      conflicts,
      errors: allErrors,
    }
    const verification = {
      status: verificationStatus,
      checkedAt: verificationChecks[0].checkedAt,
      initial: {
        stipendUSD: factsInitial.stipendUSD ?? null,
        stipendLocal: factsInitial.stipendLocal ?? null,
        stipend_basis: factsInitial.stipend_basis ?? null,
        stipendNotes: factsInitial.stipendNotes ?? null,
        meetsFloor: factsInitial.meetsFloor ?? null,
        applicationPolicy: factsInitial.applicationPolicy || 'unknown',
        applicationRestrictions: factsInitial.applicationRestrictions ?? null,
        deadlineAndTests: factsInitial.deadlineAndTests ?? null,
      },
      independent: {
        stipendUSD: verificationPass.stipendUSD ?? null,
        stipendLocal: verificationPass.stipendLocal ?? null,
        stipend_basis: verificationPass.stipend_basis ?? null,
        stipendNotes: verificationPass.stipendNotes ?? null,
        applicationPolicy: verificationPass.applicationPolicy || 'unknown',
        applicationRestrictions: verificationPass.applicationRestrictions ?? null,
        deadlineAndTests: verificationPass.deadlineAndTests ?? null,
      },
      final: {
        stipendUSD: factsFinal.stipendUSD,
        stipendLocal: factsFinal.stipendLocal,
        stipend_basis: factsFinal.stipend_basis,
        stipendNotes: factsFinal.stipendNotes,
        meetsFloor: factsFinal.meetsFloor,
        applicationPolicy: factsFinal.applicationPolicy,
        applicationRestrictions: factsFinal.applicationRestrictions,
        deadlineAndTests: factsFinal.deadlineAndTests,
      },
      conflict: conflicts.length > 0,
      resolution: verificationChecks.map(check => `${check.claimPath}: ${check.resolution}`).join(' '),
      sources: verificationEvidence.sources,
      evidenceChecks: verificationEvidence.checks,
      claimChecks: verificationChecks,
      errors: verificationEvidence.errors,
    }
    const pis = {
      pis: record.faculty.faculty || [],
      sources: record.faculty.sources || [],
      evidenceChecks: record.faculty.evidenceChecks || [],
      errors: record.faculty.errors || [],
    }
    const hasUnresolvedCheck = provenance.checks.some(check => check.status === 'unresolved')
    const hasAnyResearchSource = factsFinal.sources.length
      || pis.sources.length
      || record.outcomes.sources.length
      || nearbyFood.sources.length
    const researchStatus = conflicts.length || verificationStatus === 'conflict'
      ? 'conflict'
      : allErrors.length
        ? (hasAnyResearchSource ? 'partial' : 'failed')
        : verificationStatus === 'unresolved'
          || hasUnresolvedCheck
          || nearbyFood.researchStatus === 'partial'
          || nearbyFood.researchStatus === 'failed'
          ? 'partial'
          : 'complete'
    provenance.researchStatus = researchStatus
    return {
      program_id: record.program_id || stableId('program', [record.region, record.school, record.program]),
      region: record.region,
      school: record.school,
      program: record.program,
      city: factsFinal.city || record.city || '',
      researchStatus,
      facts: factsFinal,
      faculty: record.faculty,
      pis,
      outcomes: record.outcomes,
      out: record.outcomes,
      nearbyFood,
      restaurants: nearbyFood.restaurants,
      verification,
      provenance,
    }
  }),
)

const completedPrograms = results || []
const workflowStatus = workflowErrors.length
  || completedPrograms.some(program => program.researchStatus !== 'complete')
  ? 'partial'
  : 'complete'

return {
  schema_version: '2.0',
  schemaVersion: '2.0',
  generatedAt: now(),
  discipline_mode: DISCIPLINE_MODE,
  disciplineMode: DISCIPLINE_MODE,
  field: FIELD,
  regions: REGIONS,
  floor: FLOOR,
  currency: CURRENCY,
  programs: completedPrograms,
  workflowStatus,
  errors: workflowErrors,
}
