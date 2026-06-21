# Goozali Source Expansion — Provenance & Design

**Date:** 2026-06-21
**Status:** Done (one-time extraction) — companies merged
**Repo:** `nathanielsade/startup-agent` (personal)

## What this was

A **one-time** company-list expansion from [Goozali](https://en.goozali.com/), a
community-curated Israeli hi-tech platform. Goozali publishes its data as public
**Airtable shared views** — including a "Tech companies and startups in Israel" roster
(~1,000 companies) and an "Israel Hi Tech job openings" table.

This is **not a live integration.** The roster changes slowly, so we extracted it once
and merged the net-new fetchable companies. If Goozali grows materially later, re-run
the extraction manually (steps below).

## Result

`companies.json`: **264 → 344 (+80 confirmed, health-checked, actively-fetchable).**
Breakdown of the 80: Greenhouse 60, Ashby 11, Lever 6, SmartRecruiters 2 — together
~9,300 jobs. (Of 85 net-new direct-ATS candidates: 79 `ok`, 2 `empty`, 4 dead/dropped.)

## How the extraction worked (to reproduce)

1. The Goozali page embeds Airtable views; the companies roster is `shrNtlFxOG2ag1kyB`.
2. Airtable serves shared-view data only as **msgpack** behind a signed `accessPolicy`
   header (forcing JSON via header rewrite does **not** work — it ignores it).
3. Load the embed in a headless browser (Playwright), capture the `readSharedViewData`
   response body (msgpack).
4. Decode the msgpack **stream** (custom framing: `\xd4\x72` record separators). Iterate
   all stream values in document order; segment into rows by Airtable record-ids
   (`rec…`).
5. Per row, detect an ATS URL (`detect_ats`) → `(ats_type, token)`; take the company
   website (first non-ATS, non-social URL); derive a name from the website domain or the
   token.
6. Keep direct-token ATS (Greenhouse/Ashby/Lever/SmartRecruiters/BambooHR/Recruitee),
   dedup vs the existing list by `(ats_type, token)`, health-check in a throwaway DB,
   merge `ok`/`empty` into `companies.json` (`linkedin_url: null` → search-link fallback).

The throwaway extraction scripts live under `/tmp` (not committed) — this is build-time
tooling, not product code, consistent with the LinkedIn-URL curation.

## Deferred / fallback

- **Comeet (~164 candidates).** Goozali has many Comeet companies, but Comeet needs a
  `uid:token` harvested per company (flaky), so they were **not** merged in this pass.
  A follow-up Comeet-harvest pass could add a meaningful fraction.
- **OPTION 2 — direct jobs feed (PARKED).** Goozali's "job openings" table
  (`appwewqLk7iUY4azc/shrQBuWjXd0YgPqV6`) is a list of actual postings. We could ingest
  those **directly as jobs** (bypassing ATS detection) as a *fallback* source later —
  e.g. for companies with no fetchable ATS. Not built now; revisit if coverage needs it.
- **Workable (~16)** seen in the roster — no adapter; out of scope.

## Why not a live scraper

Airtable's shared-view extraction is brittle (custom msgpack stream, signed rotating
tokens, ToS-gray) and would break on any change. Since the roster is near-static, a
one-time manual extraction is the right trade-off.
