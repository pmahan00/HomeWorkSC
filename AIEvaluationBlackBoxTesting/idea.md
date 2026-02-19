# Brief description of the system overview 
## Overall diagram 






## Input Sanitization / Input Check Layer 

### Prompt & Intent Validation 
    - Classify the user intent (is the intent is to be informational, advisory or strictly restricted)
    - Reject intentions (example "gurantee returns", "override instructions")
### Prompt Injection Detection 
- Look for adversarial patterns 
    - Ignore previous instructions 
    - Reveal System Prompt 
    - Bypass Complaince 
    - DAN prompts ( Do anything prompts)
    - Block or sanitize suspicious intentions 
### PII Detection & Obfuscation
- Regex and pattern based detection for 
    - Make sure private info such as phone & Email are not exposed 
    - IBAN
    - Tax Ids to name a few 
- Obfuscate detected PII 
- Output of this block
    - Clean , policy complain structured input for the next block
    - Risk score 
    - Logged sanization actions 
### Controlled Context builder 
- Context Minimization 
    - Retrieve only whitelisted data 
    - Exclude personal identifiers
- Structured Data Formatting 
    - Convert all input to strict json schema
    - No raw text blob
- Output for this blocks
    - Structured, minimal, auditable JSON payload
    - Reduced Hallunication risk 
    - Controlled data exposure 
### LLM Inference Layer (Non Deterministic)
- Constrained prompting 
    - Investment Advice 
    - Fabrication of Financial Metrics 
- Tool calling (for added layer of constraint) for example
    - Tool : `investmentAdviceClassifier()`
    - Tool: `gdprPolicyCheck()`
-  Output of this block 
    - Structured JSON insight
    - Confidence Score
    - Declared Sources 
### Output Validation Block
- Ensure generated output meets regulatory , structural checks 
    - Strict JSON schema validation.
    - Pydantic model enforcement.
    - Reject malformed responses.
    - Reject unsupported financial claims.
    - Enforce mandatory “sources” field.
- Output of this block 
    - Validation Score
    - Compliance Status
### Risk Scoring and Decision Engine 
- Convert the cumulative scores into decision gates.
- For example if cumulative score >0.9 auto approve otherwise human intervention is needed.
### Audit and Govenance Block 
- Full tracebility and compliance 
- Logged Artifacts 
    - Prompt hash
    - Model Version
    - Input Sanitization results
    - Risk Score 
    - TimeStamps 
    - Decision tree
### Evaluation Framework 
- Golden dataset of labeled prompts 
- Measure Json validity rate, Hallucination rate, Factual Percision
- Online monitoring 
     - % Auto approved
     - % Rejected
     - Latency metrics
     - Confidence score monitoring

