# Technical Architecture & Production Design
**FrontierAtlas / GraphOne Global Intelligence Graph Ingestion Pipeline**  
*Document Version: 1.0.0 | Production Specification | Target Scale: 500,000+ Multi-Dimensional Entities*

---

## 1. Executive Summary & System Overview

FrontierAtlas is engineered to continuously ingest, normalize, and enrich multi-dimensional datasets across startups, founders, products, research papers, jobs, and news signals into a unified Intelligence Graph. 

The ingestion infrastructure operates on a **decoupled, asynchronous, event-driven microservices architecture** that seamlessly bridges high-throughput web scraping with resilient Large Language Model (LLM) extraction and deterministic entity resolution.

```
+----------------------------------------------------------------------------------------------------+
|                                    DISTRIBUTED INGESTION ARCHITECTURE                               |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|   [Target Sources]                                                                                 |
|   +-------------------+  +-------------------+  +-------------------+  +-----------------------+    |
|   | arXiv / PWC / GH  |  | Open Registries   |  | Hugging Face / PH |  | 5 AI News / 5 AI Jobs |    |
|   +---------+---------+  +---------+---------+  +---------+---------+  +-----------+-----------+    |
|             |                      |                      |                        |               |
|             v                      v                      v                        v               |
|   +--------------------------------------------------------------------------------------------+    |
|   |                      DISTRIBUTED CRAWLER CLUSTER (Asyncio / Playwright)                   |    |
|   |   - TLS Fingerprinting (JA3/JA4)               - Residential Proxy Mesh                     |    |
|   |   - Adaptive Rate Limiting                     - Distributed Bloom Filter (Freshness/Dedup) |    |
|   +----------------------------------------------+---------------------------------------------+    |
|                                                  |                                                 |
|                                                  v                                                 |
|   +--------------------------------------------------------------------------------------------+    |
|   |                           DISTRIBUTED EVENT LOG (Apache Kafka)                             |    |
|   |   Topics: raw.papers | raw.startups | raw.products | raw.news | raw.jobs                   |    |
|   +----------------------------------------------+---------------------------------------------+    |
|                                                  |                                                 |
|                                                  v                                                 |
|   +--------------------------------------------------------------------------------------------+    |
|   |                  RESILIENT MULTI-TIER LLM EXTRACTION & RESOLUTION WORKERS                  |    |
|   |   - Token-Aware Density Pruning (No 413s)      - Multi-Tier Fallback: Gemini -> Groq -> DS |    |
|   |   - Redis Distributed Token Bucket (No 429s)   - Full Jitter Exponential Backoff           |    |
|   |   - Deterministic Entity Resolution            - Seed Catalog + Jaro-Winkler Matching       |    |
|   +----------------------------------------------+---------------------------------------------+    |
|                                                  |                                                 |
|                                                  v                                                 |
|   +--------------------------------------------------------------------------------------------+    |
|   |                              MULTI-TIER STORAGE TOPOLOGY                                   |    |
|   |   [PostgreSQL / TiDB]              [Neo4j / Amazon Neptune]              [Qdrant / Milvus]     |    |
|   |   Relational Metadata Core         Entity Relationship Graph             Semantic Vector Embed |    |
|   +--------------------------------------------------------------------------------------------+    |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Scale Strategy: Ingesting 500,000+ Entities Without Manual Intervention

Scaling from 3,000 entities in evaluation to **500,000+ entities** across startups, products, and papers requires eliminating all localized bottlenecks and stateful single-points-of-failure.

### 2.1 Autonomous Discovery & Frontier Management
1. **Dynamic Frontier Crawling via Kafka & Temporal.io:**
   - Instead of static scrapers, a persistent orchestrator (Temporal.io) schedules recursive discovery workflows.
   - Discovered outbound links (e.g., links from startup profiles to product pages, arXiv papers to GitHub repos) are pushed into partitioned Kafka topics (`crawler.frontier`).
2. **Stateless Worker Autoscaling (Kubernetes HPA):**
   - Crawler nodes are deployed as containerized Kubernetes pods scaled via Horizontal Pod Autoscaler (KEDA) based on Kafka consumer lag.
   - When 500k URLs are enqueued, worker pools scale from 10 to 500 pods automatically without manual operator intervention.
3. **Partitioned Sharding & Anti-Ban Isolation:**
   - Ingestion jobs are sharded by target domain hash `Hash(domain) % NumPartitions`.
   - Each partition strictly enforces domain-specific politeness policies, concurrency caps, and proxy sticky sessions, preventing IP bans across external hosts.
4. **Self-Healing Error Escalation:**
   - Payloads failing schema validation are routed to a Dead Letter Queue (DLQ) with automated schema-drift detection. If a source layout changes, an automated LLM scraper-synthesizer proposes new extraction selectors.

---

## 3. Resilient LLM Orchestration: Managing Context (413s) & Rate Limits (429s)

Processing hundreds of thousands of documents through LLMs under strict API rate limits and token boundaries requires deterministic payload governance.

```
+----------------------------------------------------------------------------------------------------+
|                                LLM PAYLOAD & RATE-LIMIT GOVERNANCE                                 |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|    Raw HTML/Text Document                                                                          |
|              |                                                                                     |
|              v                                                                                     |
|    +-----------------------------+                                                                 |
|    |  DOM / Semantic Pruning     |  --> Strips <script>, <style>, <nav>, footers, boilerplate       |
|    |  (SmartChunker Engine)      |  --> Targets <main>, <article>, and high-entropy metadata tags  |
|    +--------------+--------------+                                                                 |
|                   |                                                                                |
|                   v (Token Count > Context Budget?)                                                |
|    +-----------------------------+                                                                 |
|    |  Adaptive Sliding Window    |  --> Slices text into bounded semantic chunks (max 8k tokens)   |
|    |  Payload Bounds Enforcement |  --> GUARANTEE: Never emits HTTP 413 Payload Too Large          |
|    +--------------+--------------+                                                                 |
|                   |                                                                                |
|                   v                                                                                |
|    +-----------------------------+                                                                 |
|    |  Redis Token Bucket Limiter |  --> Global RPM/TPM Rate Limiter across distributed workers     |
|    +--------------+--------------+                                                                 |
|                   | (Token Available?)                                                             |
|                   +-------------------------------+                                                |
|                   | Yes                           | No (429 Threat)                                |
|                   v                               v                                                |
|    +-----------------------------+   +---------------------------------------------------------+   |
|    | Multi-Tier Execution Chain  |   | Decorrelated Full Jitter Backoff                        |   |
|    | Tier 1: Gemini 2.0 Flash    |   | T_wait = Uniform(0, min(T_max, T_base * 2^attempt))    |   |
|    | Tier 2: Groq Llama 3 70B    |   +---------------------------------------------------------+   |
|    | Tier 3: DeepSeek Chat       |                                                                 |
|    +-----------------------------+                                                                 |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### 3.1 Eliminating HTTP 413 (Payload Too Large) via SmartChunker
- **Semantic Noise Elimination:** Raw web pages are 80-90% layout boilerplate. The `SmartChunker` removes all non-semantic DOM trees (`<script>`, `<style>`, `<svg>`, `<nav>`, `<footer>`) and extracts structured JSON-LD and OpenGraph metadata first.
- **Hierarchical Text Bounding:** Paragraphs are accumulated into semantic chunks strictly bounded to 8,000 tokens (32,000 characters). For documents exceeding single-turn limits, map-reduce extraction is triggered: chunk-level summaries are merged into a canonical schema.

### 3.2 Eliminating HTTP 429 (Too Many Requests) Across Distributed Nodes
- **Distributed Token Bucket in Redis:**
  All distributed worker pods consult a shared Redis cluster maintaining global token buckets per provider:
  $$\text{Tokens}_{\text{new}} = \min(\text{Capacity}, \text{Tokens}_{\text{current}} + \Delta t \cdot \text{RefillRate})$$
  Workers wait locally if the bucket is empty, preventing 429s before requests are even transmitted over the wire.
- **Multi-Tier Provider Failover:**
  If a provider experiences infrastructure-level rate limiting or quota exhaustion, requests failover seamlessly:
  $$\text{Tier 1: Gemini 2.0 Flash} \xrightarrow{\text{Failover}} \text{Tier 2: Groq Llama 3.3 70B} \xrightarrow{\text{Failover}} \text{Tier 3: DeepSeek Chat}$$
- **Exponential Backoff with Full Jitter:**
  When a 429 response is returned, threads back off using Full Jitter to avoid synchronized thundering herd spikes:
  $$T_{\text{sleep}} = \text{Uniform}\left(0, \min(T_{\text{max}}, T_{\text{base}} \cdot 2^{\text{attempt}})\right)$$

---

## 4. Freshness Tracking: Zero-Duplicate Distributed State Management

Guaranteeing that signals are strictly published within 24 hours while ensuring that no article or job is processed twice across 500+ distributed crawler pods requires scalable deduplication.

### 4.1 Two-Tier Deduplication Pipeline
1. **Tier 1: In-Memory Distributed Scalable Bloom Filter (RedisBloom):**
   - Generates a composite key: $K = \text{SHA-256}(\text{CanonicalDomain} \parallel \text{NormalizedURL})$.
   - Evaluated in $O(1)$ time with a 0.01% false positive rate at 10,000,000 records, requiring less than 12MB of RAM.
   - If the Bloom filter returns `true`, the URL is immediately skipped before fetching HTML.
2. **Tier 2: Content Hash Inverted Index (Redis Hash):**
   - For articles with dynamic query parameters or URL rewrites, the crawler hashes the normalized text body:
     $$H_{\text{content}} = \text{SHA-256}(\text{Title} \parallel \text{NormalizedBodyText})$$
   - Stored in Redis with a 48-hour Sliding Time-To-Live (TTL). If the content hash exists, processing aborts, guaranteeing zero duplicate entries across distributed crawler runs.

### 4.2 Strict 24-Hour Freshness Enforcement
- **Universal Date Parsing:** Normalizes RFC 2822, ISO-8601, Unix epoch, and relative expressions (`"3 hours ago"`, `"yesterday"`).
- **Temporal Filter Boundary:**
  $$T_{\text{now}} - 24\,\text{hours} \le T_{\text{published}} \le T_{\text{now}} + 5\,\text{minutes}$$
- **Content Hash Heuristic Fallback:** For sources without metadata timestamps, a hash of the content is checked against the last-seen crawl snapshot. If unseen, it is treated as a newly surfaced signal; subsequent runs identify it as duplicate.

---

## 5. Storage Strategy & Graph Intelligence Architecture

Mapping complex venture and AI ecosystems requires a **Polyglot Persistence Strategy**, pairing relational consistency with vector search and graph intelligence.

```
                                 CANONICAL DATA INGESTION
                                            |
                +---------------------------+---------------------------+
                |                           |                           |
                v                           v                           v
     +--------------------+      +--------------------+      +--------------------+
     |   PostgreSQL /     |      |  Neo4j / Amazon    |      |  Qdrant / Milvus   |
     |   TiDB Cluster     |      |  Neptune (Graph)   |      |  (Vector DB)       |
     +--------------------+      +--------------------+      +--------------------+
     | Canonical records  |      | Entity graph       |      | Embeddings         |
     | Relational joins   |      | Multi-hop queries  |      | Semantic search    |
     | Audit & provenance |      | Influence paths    |      | Entity similarity  |
     +--------------------+      +--------------------+      +--------------------+
```

| Storage Tier | Technology | Justification & Workload |
| :--- | :--- | :--- |
| **Primary Relational Core** | **PostgreSQL / TiDB** | **ACID System of Record:** Stores structured entity tables (`startups`, `products`, `papers`, `jobs`, `news`), audit logs, schema versions, and raw provenance URLs. TiDB provides horizontal scale-out for massive volumes. |
| **Intelligence Graph Store** | **Neo4j / Amazon Neptune** | **Deep Relationship Traversal:** Models complex multidimensional graphs: `(Startup)-[:BUILDS]->(Product)`, `(Paper)-[:RELEASES_CODE]->(GitHubRepo)`, `(Founder)-[:FOUNDED]->(Startup)`, `(Startup)-[:POSTS]->(Job)`. Enables $O(1)$ relationship traversal that would choke relational SQL joins at 500k+ scale. |
| **Semantic Vector Engine** | **Qdrant / pgvector** | **High-Dimensional Discovery:** Generates 1536-dimensional embeddings for paper abstracts, product descriptions, and startup value propositions. Enables semantic deduplication, thematic clustering, and natural language search. |

---

## 6. Anti-Bot Navigation: Cloudflare & Datadome Bypass Architecture

High-value intelligence directories aggressively defend against automation. Our production scraping framework operates stealthily via multi-layered evasion:

1. **TLS Fingerprint Impersonation (JA3/JA4):**
   Standard HTTP libraries (e.g. basic Python `urllib`/`requests`) leak distinctive TLS handshakes (cipher suites, extensions, elliptic curves) instantly flagged by Cloudflare WAF. The crawler employs `curl-cffi` / specialized OpenSSL hooks to clone genuine Google Chrome 133 TLS client hellos.
2. **HTTP/2 SETTINGS Frame Emulation:**
   Cloudflare fingerprints the order of HTTP/2 headers (`:method`, `:authority`, `:scheme`, `:path`) and window frame updates. Headers are strictly generated in identical order to standard Chrome desktop binaries.
3. **Headless Browser Stealth Injections:**
   For pages gated behind Cloudflare Turnstile or Datadome challenge canvases, headless Playwright workers execute pre-rendered stealth scripts:
   - Purging `window.navigator.webdriver`.
   - Mocking `window.chrome.runtime` and realistic plugin lists.
   - Injecting subtle sub-pixel mouse movement curves and jittered viewport scrolling.
4. **Residential IP Proxy Mesh:**
   Requests route through a rotating pool of 500,000+ residential exit nodes, pinning sticky sessions by domain to emulate natural browsing sessions.

---

## 7. Deterministic Entity Resolution Framework

To map ambiguous raw scraped names (`"OpenAI"`, `"OpenAI, Inc."`, `"Open AI"`) into a single canonical node:

$$\text{Pipeline: Raw String} \xrightarrow{\text{Unicode Normalization}} \xrightarrow{\text{Legal Suffix Strip}} \xrightarrow{\text{Exact Lookup}} \xrightarrow{\text{Jaro-Winkler / Levenshtein}} \xrightarrow{\text{Canonical ID}}$$

1. **Normalization:** Strips accents, lowercases, removes legal punctuation and suffixes (`Inc`, `LLC`, `Corp`, `Technologies`, `Labs`, `AI`).
2. **Deterministic Seed Index:** Instant $O(1)$ match against curated seed directory of 50 known canonical AI startups.
3. **Fuzzy String Matching:** Calculates normalized edit distance ratio:
   $$\text{Score}(s_1, s_2) = 1.0 - \frac{\text{LevenshteinDistance}(s_1, s_2)}{\max(\text{len}(s_1), \text{len}(s_2))}$$
   Scores $\ge 0.82$ canonicalize automatically; lower confidence candidates are flagged for asynchronous human-in-the-loop audit in the `entity_mapping_log`.

