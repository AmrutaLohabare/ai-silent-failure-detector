# AI Silent Failure Detector - Part 4: Semantic Kernel Report

**Generated:** 2026-05-14 02:27 UTC
**Entries analysed:** 62
**Silent failures detected:** 2
**Stack:** Semantic Kernel 1.41.3 + Azure AI Search (local TF-IDF mock)

---

## [HIGH] Finding 1: Empty Success Response

**Severity:** HIGH
**Description:** 6 HTTP 200 responses with zero-byte body. Server reports success but delivers no data.

**Affected paths:**
  - /api/auth/refresh
  - /api/recommendations

### Azure RAG Context - Similar past incidents

**INC-018 - Azure API Management policy silently stripping recommendation response body**
**Azure service:** Azure API Management

**Root cause:** An Azure API Management policy update introduced a response transformation that incorrectly stripped the body for responses over 512KB. The recommendations endpoint returned HTTP 200 with Content-Length: 0. APIM logged the request as successful. The backend service was healthy. No error anywhere in the chain.

**Business impact:** All personalised recommendations blank for 8 hours. Estimated 15% drop in cross-sell revenue. No backend error, no APIM error — only the empty body was the signal.

**Detection lag:** 8 hours

**Runbook:**
  - 1
  - Check APIM policy history: Azure Portal > API Management > APIs > your-api > Policy > Revision history
  - 2
  - Revert to previous policy revision
  - 3
  - Test: az rest --method get --url https://<apim-name>.azure-api.net/api/recommendations
  - 4
  - Add body validation policy: <choose><when condition='@(context.Response.Body.As<string>().Length == 0)'>.</when></choose>.

**INC-015 - Azure AD token refresh returning empty body — managed identity misconfiguration**
**Azure service:** Azure Active Directory / Key Vault

**Root cause:** Azure Managed Identity permissions were revoked during a Key Vault policy update. The token refresh endpoint returned HTTP 200 but with an empty access token payload. Downstream API calls silently failed with 401s that were swallowed by the retry policy.

**Business impact:** 12,000 enterprise users silently de-authenticated. B2B portal inaccessible for 5 hours. SLA breach for 3 enterprise accounts.

**Detection lag:** 5 hours

**Runbook:**
  - 1
  - Check Managed Identity: az identity show --name <identity-name> --resource-group <rg>
  - 2
  - Verify Key Vault access policy: az keyvault show --name <vault-name>
  - 3
  - Re-grant permissions: az keyvault set-policy --name <vault> --object-id <identity-id> --secret-permissions get list
  - 4
  - Restart auth service: az webapp restart --name <app> --resource-group <rg>.

---

## [MED] Finding 2: Latency Spike On Success

**Severity:** MEDIUM
**Description:** 6 successful requests took >3x average (258ms). Possible silent retries.

**Affected paths:**
  - /api/checkout

### Azure RAG Context - Similar past incidents

**INC-018 - Azure API Management policy silently stripping recommendation response body**
**Azure service:** Azure API Management

**Root cause:** An Azure API Management policy update introduced a response transformation that incorrectly stripped the body for responses over 512KB. The recommendations endpoint returned HTTP 200 with Content-Length: 0. APIM logged the request as successful. The backend service was healthy. No error anywhere in the chain.

**Business impact:** All personalised recommendations blank for 8 hours. Estimated 15% drop in cross-sell revenue. No backend error, no APIM error — only the empty body was the signal.

**Detection lag:** 8 hours

**Runbook:**
  - 1
  - Check APIM policy history: Azure Portal > API Management > APIs > your-api > Policy > Revision history
  - 2
  - Revert to previous policy revision
  - 3
  - Test: az rest --method get --url https://<apim-name>.azure-api.net/api/recommendations
  - 4
  - Add body validation policy: <choose><when condition='@(context.Response.Body.As<string>().Length == 0)'>.</when></choose>.

**INC-015 - Azure AD token refresh returning empty body — managed identity misconfiguration**
**Azure service:** Azure Active Directory / Key Vault

**Root cause:** Azure Managed Identity permissions were revoked during a Key Vault policy update. The token refresh endpoint returned HTTP 200 but with an empty access token payload. Downstream API calls silently failed with 401s that were swallowed by the retry policy.

**Business impact:** 12,000 enterprise users silently de-authenticated. B2B portal inaccessible for 5 hours. SLA breach for 3 enterprise accounts.

**Detection lag:** 5 hours

**Runbook:**
  - 1
  - Check Managed Identity: az identity show --name <identity-name> --resource-group <rg>
  - 2
  - Verify Key Vault access policy: az keyvault show --name <vault-name>
  - 3
  - Re-grant permissions: az keyvault set-policy --name <vault> --object-id <identity-id> --secret-permissions get list
  - 4
  - Restart auth service: az webapp restart --name <app> --resource-group <rg>.

---

## Series Comparison

| Metric | Part 1 | Part 2 | Part 3 | Part 4 |
|---|---|---|---|---|
| Orchestration | LangChain | CrewAI | Direct Python | Semantic Kernel |
| Vector store | FAISS | TF-IDF | TF-IDF | Azure AI Search |
| Multi-agent | No | Yes (3 agents) | No | No (Planner) |
| Target stack | Any | Any | UI/visual | Azure enterprise |
| Tests | 31 | 26 | 30 | TBD |