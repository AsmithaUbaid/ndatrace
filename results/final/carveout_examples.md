# Exception/Carve-Out Failure Examples

Concrete, quotable examples backing `docs/decisions.md` ADR-011's finding: every case
in the golden/negative battery requiring reconciliation of an exception or carve-out
clause against an apparent general rule failed (4/4). Source: `data/golden/
negative_cases.json` (case selection, dev split) cross-referenced against
`data/golden_battery_pipeline_verification.json` (the real, already-completed run of
these cases against the current production pipeline - NOT T041, which never touches
these dev-split documents at all; see this script's docstring for why).

## Case 034 (doc 70, hypothesis nda-7)

**Pattern**: Misleading wording - "except as required by law" carve-out limits an apparently firm requirement

**Hypothesis**: Receiving Party may share some Confidential Information with some third-parties (including consultants, agents and professional advisors).

**Actual clause text (gold evidence spans, verbatim from the real dev-split NDA)**:
> 1. "I hereby agree as follows:"
> 2. " I will not disclose any PHI to any individual or third party, except as specifically authorized by FAU policies and procedures, and upon receiving a written authorization from the patient (unless otherwise required by applicable law), and then only on a need-to-know basis."

**Gold label**: Contradiction
**Model predicted instead**: Entailment  (agent invoked: True)

---

## Case 038 (doc 17, hypothesis nda-7)

**Pattern**: Conflicting clauses - evidence spans multiple locations, approximating one clause granting and another limiting the same right

**Hypothesis**: Receiving Party may share some Confidential Information with some third-parties (including consultants, agents and professional advisors).

**Actual clause text (gold evidence spans, verbatim from the real dev-split NDA)**:
> 1. "d. The contractor, the contractor's employees, and any subcontractor and subcontractor's employees will access the VA information, software, applications, computer systems, and hardware which VA provides, or provides access to, only to the extent necessary, and only for the purpose of performing the contract."
> 2. "The contractor will take reasonable steps to ensure that it will allow only those contractor and subcontractor employees who need to see the VA materials in order to perform the contract to do so."

**Gold label**: Contradiction
**Model predicted instead**: Entailment  (agent invoked: True)

---

## Case 039 (doc 9, hypothesis nda-5)

**Pattern**: Conflicting clauses - amendment/override language should win over an earlier, superseded clause [proxy: no keyword/structural match found in dev set; nearest available case used]

**Hypothesis**: Receiving Party may share some Confidential Information with some of Receiving Party's employees.

**Actual clause text (gold evidence spans, verbatim from the real dev-split NDA)**:
> 1. "Any individual person or organization who is identified to receive and utilize the confidential information applicable to the related Challenge, whether as an employee or representative, must be disclosed to and approved by BPS and sign this agreement prior to commencing work on or engaging in participation in the Transportation Data Challenge."

**Gold label**: Contradiction
**Model predicted instead**: Entailment  (agent invoked: True)

---

## Case 040 (doc 73, hypothesis nda-20)

**Pattern**: Conflicting clauses - a specific exception should override an apparently general requirement

**Hypothesis**: Receiving Party may retain some Confidential Information even after the return or destruction of Confidential Information.

**Actual clause text (gold evidence spans, verbatim from the real dev-split NDA)**:
> 1. "At any time, at the Disclosing Party’s request, all copies of the Confidential Information and the Confidential Materials shall be returned to the Disclosing Party within five (5) business days of such request; provided, however, that the Receiving Party shall be permitted to retain a list that contains general descriptions of the documents it has returned to the Disclosing Party to facilitate the resolution of any controversies after the Confidential Information and the Confidential Materials have been returned."

**Gold label**: Contradiction
**Model predicted instead**: NotMentioned  (agent invoked: False)

---

Found and formatted 4/4 cases.