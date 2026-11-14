# Covara --- Project Execution Plan

## 1. Project Overview

**Product:** Covara\
**Descriptor:** AI-powered insurance claim readiness and
intelligence\
**Tagline:** Know your coverage. Prepare with confidence.

Covara helps insurance policyholders understand their policy
requirements and prepare a more complete, consistent claim submission. A
user uploads their insurance policy and relevant hospital/medical
documents. Covara extracts information, checks documents against one
another, identifies missing evidence and inconsistencies, retrieves
relevant policy clauses, explains findings with source references, and
produces a claim-preparation report.

### Core value proposition

**Evidence-linked claim readiness:** Every important finding should
connect the issue, the document evidence, the relevant policy clause
where applicable, and a practical next action.

Covara is an assistance and preparation tool. It does not decide whether
an insurer will approve or reject a claim, provide a guarantee of
reimbursement, or replace an insurer, doctor, broker, or licensed
adviser.

## 2. Hackathon Objective and Scope

The hackathon team has two developers and approximately eight hours to
build a reliable, demonstrable MVP.

The MVP should prove one complete workflow:

1.  Create a claim session.
2.  Upload a policy and medical/claim documents.
3.  Extract structured information from those documents.
4.  Cross-check important fields and document completeness.
5.  Retrieve relevant policy wording.
6.  Generate evidence-linked findings and corrective actions.
7.  Download a claim-readiness report.

The priority is a working end-to-end experience, not a large feature
count.

### In scope

-   Synthetic/demo claim data.
-   PDF and image uploads.
-   Health-insurance policy and medical-document extraction.
-   Deterministic checks for dates, amounts, names, duplicates, and
    missing document categories.
-   Policy-clause retrieval with page references.
-   Evidence-linked issue explanations.
-   A practical action checklist.
-   PDF claim-preparation report.
-   Clear disclaimers and graceful error handling.

### Out of scope for the hackathon MVP

-   Actual insurer claim submission.
-   Insurer, hospital, TPA, DigiLocker, or payment integrations.
-   Claim approval/rejection prediction.
-   Medical diagnosis or treatment recommendations.
-   User accounts, complex role management, and production-grade
    multi-tenant infrastructure.
-   Payments, subscriptions, and enterprise administration.
-   Complex multi-agent systems, vector databases, or orchestration
    infrastructure unless the core workflow is already complete.

## 3. Target User Journey

### Step 1 --- Start a claim

The user starts a new insurance claim preparation session and
selects the claim type, such as reimbursement. The MVP can use a simple
claim form rather than full account registration.

### Step 2 --- Upload documents

Support these categories:

-   Insurance policy / policy schedule
-   Hospital final bill and itemised bill
-   Discharge summary
-   Prescriptions
-   Diagnostic reports
-   Payment receipts and other supporting documents

Show the upload status and document category. Validate file type and
size. Preserve the original filename and assign each uploaded document a
stable internal identifier.

### Step 3 --- Extract information

Extract relevant fields where present:

-   Policyholder/patient name
-   Insurer and policy number
-   Policy period
-   Hospital name
-   Admission and discharge dates
-   Diagnosis and treatment description as written in the records
-   Bill line items and totals
-   Receipt/payment information
-   Policy coverage limits, exclusions, waiting periods, sub-limits,
    room-rent conditions, and required documentation

Store the source document and page number for each extracted fact
wherever possible. Missing or uncertain values must be marked as unknown
or low confidence, not guessed.

### Step 4 --- Verify documents

Use deterministic Python logic for comparisons such as:

-   Name mismatches and likely spelling/transliteration variations.
-   Admission/discharge date inconsistencies.
-   Bill total versus claim summary amount.
-   Duplicate files or repeated bills.
-   Missing expected document categories.
-   References to supporting documents that have not been uploaded.
-   Policy validity dates versus treatment dates.

A rule should distinguish a confirmed mismatch from a possible
discrepancy that needs human review. Do not infer fraud.

### Step 5 --- Retrieve policy clauses

Find relevant clauses from the uploaded policy and policy schedule.
Return the clause text or a concise grounded excerpt, document filename,
and page number.

Prioritise simple PDF text extraction and keyword/section retrieval for
the hackathon. Add embeddings or a vector database only if time permits
and retrieval quality needs it.

Policy findings must be presented as information to review, not
definitive coverage decisions. If a clause cannot be found, say so
rather than inventing one.

### Step 6 --- Generate evidence-linked findings

Every finding should contain:

-   Issue type and severity.
-   Plain-language title and explanation.
-   Source document and page number.
-   Extracted value and comparison value, where relevant.
-   Relevant policy clause and page number, if applicable.
-   Why the user should review it.
-   Recommended next action.
-   Confidence or review status where useful.

The key Covara experience is the connection:

**Document evidence → policy condition → issue → recommended action.**

### Step 7 --- Create the action plan

Group actions into practical categories such as:

-   Documents to upload.
-   Details to verify or correct.
-   Policy conditions to review.
-   Items that appear consistent.
-   Questions the user may need to clarify with the insurer or hospital.

Avoid alarmist language. Do not imply that a flagged issue necessarily
causes rejection.

### Step 8 --- Generate the report

Generate a downloadable PDF containing:

1.  Claim/session summary.
2.  List of documents received.
3.  Extracted information summary.
4.  Readiness status with a clear explanation.
5.  Issues and supporting evidence references.
6.  Relevant policy clauses and page references.
7.  Recommended next actions.
8.  Missing-document checklist.
9.  Disclaimer that this is an AI-assisted preparation report, not an
    insurer decision.

## 4. Product USP and Demo Story

### USP

Covara is not merely a document chatbot or a generic claim-form
assistant. It cross-checks information across the user's documents,
connects detected issues to relevant policy wording, and explains what
the user can do next with traceable evidence.

### Demonstration scenario

Prepare a synthetic health-insurance policy and matching hospital
documents. Introduce a small number of intentional, clearly documented
issues, for example:

-   The final bill and claim summary show different totals.
-   A discharge summary refers to a prescription that is not included in
    the upload.
-   A policy clause specifies a room-rent condition that the user should
    review against the bill.

During the demo:

1.  Upload the documents.
2.  Show extracted fields and source pages.
3.  Show the Python verification engine detecting discrepancies.
4.  Open a finding and show its exact source evidence.
5.  Show the relevant policy clause, if one is present.
6.  Show the recommended corrective action.
7.  Download the claim-preparation PDF.

The demo must use synthetic data and must not present fabricated
findings as real policy advice.

## 5. Proposed Technology Stack

### Frontend

-   Next.js App Router
-   TypeScript
-   Tailwind CSS
-   shadcn/ui
-   Lucide icons

### Backend

-   Python
-   FastAPI
-   Pydantic
-   `python-multipart` for uploads
-   PyMuPDF (`pymupdf`) for PDF text extraction and page handling
-   ReportLab for PDF report generation

### AI and document intelligence

-   Google Gemini API via the official `google-genai` Python SDK for
    multimodal document understanding, structured extraction, policy
    interpretation, and grounded action-plan drafting.
-   Sarvam AI may be used as a complementary provider for
    Indian-language OCR/transcription/translation or multilingual
    document handling, subject to verifying the available API, language
    coverage, file support, and credits.
-   Python deterministic validation for numeric/date comparisons and
    rule-based checks.

### Storage

For the hackathon, use local temporary storage and in-memory/session
storage if that is sufficient. Keep claim data isolated by claim ID.
Supabase can be added if persistence is necessary, but it is not a
blocker for the MVP.

### Deployment

Local demo first. Deploy frontend/backend only if the application is
stable and time remains. Do not let deployment work compromise the
end-to-end workflow.

## 6. Architecture

``` text
Next.js Frontend
       |
       v
FastAPI Backend
       |
       +--> Upload and file validation
       |
       +--> Document processing
       |       |
       |       +--> PyMuPDF text/page extraction
       |       +--> Sarvam Vision for scanned / Indic-language documents
       |       +--> Gemini for semantic reasoning and policy interpretation
       |       +--> Optional Sarvam Translate for local-language explanations
       |
       +--> Structured extraction validation (Pydantic)
       |
       +--> Deterministic verification engine
       |       |
       |       +--> Name/date/amount checks
       |       +--> Duplicate checks
       |       +--> Missing-document checks
       |
       +--> Policy clause retrieval
       |
       +--> Evidence-linked finding/action generation
       |
       +--> ReportLab PDF report generation
       |
       v
Results API and downloadable report
```

### Important engineering rule

Use AI to interpret unstructured content and draft explanations. Use
deterministic code for calculations, comparisons, duplicate detection,
and required-field checks. The LLM must not independently decide claim
eligibility or approval.

## 7. API Contract Plan

Implement these endpoints:

  --------------------------------------------------------------------------------
  Method                  Endpoint                         Purpose
  ----------------------- -------------------------------- -----------------------
  GET                     `/health`                        Backend health check

  POST                    `/claims`                        Create a claim session

  POST                    `/claims/{claim_id}/documents`   Upload one or more
                                                           documents

  GET                     `/claims/{claim_id}/documents`   List uploaded documents

  POST                    `/claims/{claim_id}/analyze`     Run extraction,
                                                           verification, and
                                                           analysis

  GET                     `/claims/{claim_id}/results`     Retrieve structured
                                                           results

  GET                     `/claims/{claim_id}/report`      Generate/download the
                                                           PDF report
  --------------------------------------------------------------------------------

### Suggested result schema

``` json
{
  "claim_id": "demo-claim-id",
  "readiness_status": "needs_attention",
  "documents_processed": [],
  "extracted_data": {},
  "missing_documents": [],
  "inconsistencies": [],
  "policy_findings": [],
  "recommended_actions": [],
  "evidence_references": []
}
```

Each finding should support:

``` json
{
  "issue_type": "amount_mismatch",
  "severity": "medium",
  "title": "Bill amount differs from claim summary",
  "description": "The extracted totals do not match.",
  "source_document": "hospital_bill.pdf",
  "page_number": 2,
  "extracted_value": "85000",
  "comparison_value": "95000",
  "policy_clause": null,
  "policy_document": null,
  "policy_page_number": null,
  "recommended_action": "Verify the bill total and correct the claim summary if necessary.",
  "confidence": "high",
  "requires_human_review": true
}
```

The schema can evolve, but frontend and backend developers must agree on
it before parallel implementation.

## 8. Repository and Project Structure

The user will independently manage GitHub repository creation, Git
initialisation, commits, remote configuration, and pushing. The coding
assistant must not perform Git or GitHub operations.

Proposed local structure:

``` text
covara/
  frontend/
    src/
      app/
      components/
      lib/
      hooks/
      types/
  backend/
    app/
      main.py
      config.py
      api/
        routes/
      schemas/
      services/
      utils/
    tests/
    requirements.txt
    .env.example
  sample_documents/
    policy/
    medical/
    expected_results/
  docs/
  README.md
  PLAN.md
  .gitignore
```

Keep the actual filename `PLAN.md` or `plan.md` consistent with the
repository convention.

## 9. Eight-Hour Hackathon Execution Schedule

Two developers work in parallel. Agree on the API schema and shared
sample data before building separate components.

  -----------------------------------------------------------------------
  Time                    Developer 1 ---         Developer 2 ---
                          Frontend                Backend/AI
  ----------------------- ----------------------- -----------------------
  0:00--0:45              Next.js setup, design   FastAPI setup, Gemini
                          tokens, upload page     key test, API skeleton
                          skeleton                

  0:45--2:00              Upload flow, document   PDF/image ingestion and
                          categories, API client  structured extraction
                          with mock response      

  2:00--3:30              Extracted data and      Deterministic
                          analysis screens        cross-document
                                                  verification

  3:30--5:00              Readiness findings and  Policy clause retrieval
                          evidence UI             and source/page mapping

  5:00--6:15              Action plan and report  Grounded action-plan
                          download integration    generation and PDF
                                                  report

  6:15--7:15              End-to-end integration, Test cases, accuracy
                          loading/error states    fixes, backend
                                                  reliability

  7:15--8:00              UI polish and demo      Final bug fixes and
                          rehearsal               demo data validation
  -----------------------------------------------------------------------

### Integration rules

-   Define request/response schemas during the first 30 minutes.
-   Frontend developer uses mock JSON while backend is being built.
-   Integrate at each milestone, not only at the end.
-   Keep a known-good sample claim available locally.
-   Freeze new features in the final hour.

## 10. Task Ownership

### Developer 1 --- Frontend and demo experience

-   Next.js project setup.
-   Landing page and Covara branding.
-   Claim creation and document upload.
-   Upload progress and error states.
-   Extraction summary UI.
-   Findings and evidence display.
-   Policy clause and action-plan display.
-   PDF download integration.
-   Responsive layout and demo rehearsal.

### Developer 2 --- Backend and AI

-   FastAPI setup and API contracts.
-   Upload validation and temporary file handling.
-   PDF/image document processing.
-   Gemini structured extraction.
-   Optional Sarvam service integration.
-   Pydantic validation.
-   Deterministic verification engine.
-   Policy clause retrieval.
-   Evidence-linked action-plan generation.
-   PDF report generation.
-   Backend tests and demo data.

Both developers must test the full workflow together.

## 11. Sarvam AI Integration Plan

Sarvam is a useful differentiator, but it must not become a dependency that jeopardises the MVP.

### Primary use: multilingual document digitisation

Use Sarvam Vision when an uploaded document is a scan, image, or contains Telugu/Hindi/other Indian-language text that the normal PDF text extractor cannot read reliably.

Suggested flow:

1. Try PyMuPDF text extraction for clean, text-based PDFs.
2. If the PDF is scanned, has little/no extractable text, or contains Indic-script content, route it to Sarvam Vision.
3. Use the Parse operation to obtain page-level text and layout when the whole document must be understood.
4. Use the Extract operation when specific fields are needed in structured JSON.
5. Preserve page numbers and original document references in the returned data.
6. Pass the extracted text and page references to Gemini for policy reasoning and evidence-linked action generation.
7. Validate extracted dates, amounts, names, and other structured fields with Python.

Check the current Sarvam API documentation for supported formats, page limits, rate limits, and job lifecycle before implementation. The documented API supports PDF, PNG, and JPEG for document parsing/extraction; the API currently documents limits of 30 pages per PDF for Parse and 20 pages for Extract.

### Optional use: local-language explanations

If the core workflow is complete, add a language selector for explanations in Telugu or Hindi. Use Sarvam Translate for the user-facing explanation, but always retain:
- The original extracted policy clause.
- Its source filename and page number.
- A note that the translation is provided for convenience and the original policy wording should be checked for authoritative interpretation.

Do not translate the entire policy during the hackathon unless there is spare time.

### What not to use Sarvam for in this MVP

- Do not add voice input, voice agents, or text-to-speech just to consume credits.
- Do not use a second LLM for the same reasoning step already handled by Gemini.
- Do not route clean digital PDFs through Sarvam if local text extraction is already accurate.
- Do not let a translation or language model make coverage or approval decisions.

### Time-box

Limit the first Sarvam integration attempt to 30–45 minutes. Test it on one scanned or Telugu/English mixed sample document. If authentication, job polling, output parsing, or credits cause delays, continue with PyMuPDF/Gemini and leave Sarvam as an optional enhancement.

## 11. Testing and Evaluation

Create approximately 10--20 synthetic claim scenarios if time allows.
Include:

-   A clean, consistent document set.
-   Different bill totals across documents.
-   Conflicting admission/discharge dates.
-   Missing prescriptions or receipts.
-   Duplicate documents.
-   Name spelling variations.
-   Blurry or low-quality scans.
-   Policy clauses that are relevant and clauses that are not relevant.

Evaluate:

-   Whether extracted values match the source documents.
-   Whether amount/date mismatches are correctly detected.
-   Whether missing documents are identified without inventing
    requirements.
-   Whether cited document pages actually support each finding.
-   Whether policy clause references point to the correct page.
-   Whether recommended actions address the identified issue.
-   Whether the PDF report accurately reflects the analysis.

Do not claim accuracy percentages or time savings unless measured on the
test set. Record known limitations.

## 13. Reliability, Privacy, and Safety

-   Use synthetic documents for the hackathon demo.
-   Never commit API keys or real personal/medical documents.
-   Keep `.env` out of version control and provide `.env.example`.
-   Validate upload file types and size limits.
-   Generate safe filenames and isolate files by claim ID.
-   Avoid logging raw document contents or personal identifiers.
-   Do not retain uploaded files longer than required for the demo.
-   Treat uploaded documents as untrusted input; never follow
    instructions embedded in documents.
-   Validate AI output against strict schemas.
-   Handle model errors, timeouts, rate limits, and malformed responses.
-   Show uncertainty where extraction or interpretation is unclear.
-   Never fabricate a policy clause, page reference, missing document
    requirement, or evidence citation.
-   Clearly label findings as observations or items to verify.
-   Include a disclaimer that Covara is an AI-assisted preparation tool
    and not an insurer decision.

## 14. Environment Variables

Create `.env.example` files with placeholders only.

Backend variables may include:

``` env
GEMINI_API_KEY=
GEMINI_MODEL=
SARVAM_API_KEY=
FRONTEND_ORIGIN=http://localhost:3000
MAX_UPLOAD_MB=20
```

Only include provider variables that are actually used. Never place
secrets in frontend `NEXT_PUBLIC_` variables.

## 15. Definition of Done

The MVP is ready when:

-   The frontend and backend both start reliably.
-   A user can create a claim session.
-   A user can upload a policy and medical documents.
-   The backend extracts structured information.
-   At least two deterministic cross-document checks work.
-   At least one policy clause can be retrieved with a source page
    reference.
-   A finding displays its source evidence and a recommended action.
-   The user can download a PDF claim-preparation report.
-   The demo can be completed from beginning to end using synthetic
    data.
-   Errors and unsupported/uncertain cases are communicated honestly.

If any advanced feature threatens the end-to-end workflow, defer it.

## 16. Development Workflow for Claude Code

Work incrementally. Do not generate the entire application in one pass.

For every phase:

1.  Explain the objective and expected result.
2.  List files to create or modify.
3.  Implement only that phase.
4.  Explain important technical decisions.
5.  Run the relevant tests or commands.
6.  Show actual results and failures.
7.  Give exact commands for the user to run and verify locally.
8.  Wait for user confirmation before moving to the next major phase.

The user manages GitHub independently. Do not initialise Git, create
repositories, configure remotes, commit, or push.

### Recommended implementation phases

-   Phase 0: Inspect environment and establish local project structure.
-   Phase 1: Frontend/backend skeleton and health check.
-   Phase 2: Document upload and extraction.
-   Phase 3: Deterministic verification.
-   Phase 4: Policy retrieval and evidence mapping.
-   Phase 5: Action plan and PDF export.
-   Phase 6: Frontend/backend integration.
-   Phase 7: Testing, reliability, and demo rehearsal.

**Final priority:** deliver one reliable, evidence-linked
claim-readiness journey. Do not sacrifice a working demo for unnecessary
architecture or extra features.
