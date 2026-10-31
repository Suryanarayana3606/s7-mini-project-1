"""
services/llm/prompt_builder.py
"""

import json


class PromptBuilder:

    @staticmethod
    def build_recommendation_prompt(rootcause_df, provider="groq"):

        context = []

        for _, row in rootcause_df.iterrows():

            context.append({

                "Aspect": row["Aspect"],

                "Negative Reviews": int(row["Negative Reviews"]),

                "Root Causes": row["Root Causes"]

            })

        data = json.dumps(context, indent=2)

        # =====================================================
        # OLLAMA PROMPT
        # =====================================================

        if provider.lower() == "ollama":

            return f"""
You are an expert software product and application quality consultant.

Analyze the customer complaints below.

For EVERY aspect generate ONE recommendation.

Return ONLY VALID JSON.

Rules:

- No explanation
- No markdown
- No code block
- No extra text

Priority must be one of:

Critical
High
Medium
Low

Department must be one of:

Product Development
Engineering
Quality Assurance
Customer Support
Platform & DevOps
Security & Privacy

Assign teams by issue type: Product Development for workflows and feature
choices; Engineering for application logic, authentication, payments, sync,
and integrations; Quality Assurance for reproducible bugs, regressions, and
device or OS compatibility; Customer Support for help and service flows;
Platform & DevOps for uptime, latency, and infrastructure; Security & Privacy
for access control and personal-data handling.

Estimated Effort:

Low
Medium
Medium-High
High

Expected Improvement examples:

5-10%
10-20%
20-30%
30-40%

JSON Schema:

{{
    "recommendations":[
        {{
            "aspect":"",
            "priority":"",
            "department":"",
            "problem_summary":"",
            "recommendation":"",
            "business_impact":"",
            "estimated_effort":"",
            "expected_improvement":"",
            "implementation_order":1
        }}
    ],
    "executive_summary":""
}}

Customer Data:

{data}

Use software-app failure modes such as crashes, failed sign-in, slow screens,
broken notifications, sync errors, confusing navigation, and subscription
checkout problems. Recommend a concrete fix and a way to verify it.

Remember:

- Write the executive summary as 5–7 concise bullet points in plain language, one main finding per line.
- Do not write the executive summary as a paragraph.
Return ONLY VALID JSON.
"""

        # =====================================================
        # GROQ PROMPT
        # =====================================================

        return f"""
You are a Senior Software Product and Customer Experience Expert.

Your task is to analyze customer complaints and produce practical business recommendations.

=========================
DATASET
=========================

{data}

=========================
INSTRUCTIONS
=========================

For EACH aspect:

1. Understand the customer problem.

2. Determine the business severity.

3. Assign ONE Priority:

- Critical
- High
- Medium
- Low

Priority Rules

Critical

- Safety issue
- Product failure
- Large number of complaints

High

- Major usability issue
- Frequently reported

Medium

- Moderate inconvenience

Low

- Minor improvement

Department MUST be one of:

- Product Development
- Engineering
- Quality Assurance
- Customer Support
- Platform & DevOps
- Security & Privacy

Choose the team that can own the fix:

- Product Development: confusing workflows, onboarding, or feature prioritization.
- Engineering: application logic, authentication, payments, sync, or integrations.
- Quality Assurance: reproducible crashes, regressions, and device or OS compatibility.
- Customer Support: help content, support handoffs, or service response.
- Platform & DevOps: outages, latency, deployment reliability, or infrastructure.
- Security & Privacy: access control, account protection, or personal-data handling.

Recommendation Rules

DO NOT write generic recommendations.

Bad Examples

❌ Improve product quality

❌ Improve customer satisfaction

❌ Improve design

Good Examples

App crashes

→ Reproduce the crash by device and OS version, fix the failing code path, and add a regression test.

Failed sign-in

→ Trace the authentication and session-refresh flow, handle expired tokens safely, and monitor sign-in success.

Slow screens

→ Profile the slow user journey, reduce blocking network work, and track its load time after release.

Confusing onboarding

→ Remove unnecessary steps, test the revised flow with users, and measure successful setup completion.

Subscription checkout

→ Validate purchase and restore flows across supported app stores, then monitor payment completion and failure rates.

Business Impact should include:

- improved task completion and engagement
- fewer crashes, failed sessions, and support tickets
- more reliable subscriptions and payments
- improved retention and customer trust

Estimated Effort:

Low
Medium
Medium-High
High

Expected Improvement:

5-10%
10-20%
20-30%
30-40%

Return ONLY VALID JSON.

Schema:

{{
    "recommendations":[
        {{
            "aspect":"",
            "priority":"",
            "department":"",
            "problem_summary":"",
            "recommendation":"",
            "business_impact":"",
            "estimated_effort":"",
            "expected_improvement":"",
            "implementation_order":1
        }}
    ],
    "executive_summary":""
}}

Executive Summary:

Write 5–7 concise bullet points in plain language, with one main finding per point.
Put each bullet point on a new line and do not write a paragraph.

Mention:

- biggest risks
- top priorities
- departments involved
- expected business benefits

Return ONLY JSON.
"""