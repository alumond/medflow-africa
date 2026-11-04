# Responsible use and security

All bundled datasets, programme registers and financial figures are fictional. No real-world effectiveness, clinical approval or national-system integration is claimed. Inputs must be synthetic or appropriately anonymised operational records. Patient-like columns and unrecognised schema columns are blocked before ingestion. This is a schema guard, not a complete privacy detector; the uploader must verify anonymisation.

Hard constraints remain deterministic: known positive consumption, fresh valid balances, minimum reporting completeness, pack-size alignment, donor safety stock and plausible use before expiry. Zero consumption is unknown cover. Critical rejected balances override aggregate quality scores. Pending receipts are not assumed to arrive.

Model probabilities are advisory and have substantial synthetic-data limitations. Conservative baseline alerts remain a lower bound. Contributions describe model behaviour, not causality. False-alert, missed-event and subgroup metrics are from a time holdout, not current live outcomes. Review acceptance is an adoption measure, not accuracy ground truth. Feature mean shifts are simple investigation triggers, not validated drift tests.

Gemini uses server-only credentials and synthetic summaries. Free-tier Google processing may use content to improve products; no operational import, raw reviewer note or user-authored management note is sent. Cached AI records preserve structured input, prompt version, output and validation state. General audit logs contain identifiers and counts, not notes or raw rows.

Exports escape HTML and neutralise formula-like CSV prefixes. Uploads are bounded by file and row limits, identifiers are validated and database parameters are bound. Audit and review tables reject updates/deletes through SQLite triggers. Optimistic review versions and remote Blob compare-and-swap prevent silent concurrent overwrites. A failed remote commit returns an error rather than claiming success.

The hosted workspace cookie is a random bearer capability, not named-user authentication. Operational use needs Vercel deployment protection. Viewer/analyst/reviewer/admin roles and recoverable user identities are not implemented; external multi-user release is blocked pending those controls. HTTPS is provided by Vercel. Local service defaults to loopback.

Retention policy: 90 days; automated Blob cleanup is not configured. A storage administrator must remove expired workspaces. Clearing the browser cookie revokes that browser's access but does not delete its stored snapshot. Never describe this as a complete retention implementation.

On a safety or audit-integrity failure: disable the affected model or recommendation path, preserve versioned evidence, use the baseline or withhold recommendations, investigate, repair and add a regression test. Do not loosen thresholds to conceal a failure.
