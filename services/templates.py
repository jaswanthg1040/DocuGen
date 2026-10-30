"""Starter templates. Application-defined data (not stored in the database)."""
from __future__ import annotations

TEMPLATES: list[dict] = [
    {
        "id": "blank", "icon": "📄", "name": "Blank Document",
        "description": "Start from scratch with an empty page.",
        "title": "", "content": "",
    },
    {
        "id": "project_report", "icon": "📊", "name": "Project Report",
        "description": "Status, progress, risks and next steps for a project.",
        "title": "Project Report",
        "content": """# Project Report

**Project name:** [Name]
**Prepared by:** [Your name]
**Date:** [Date]

## 1. Executive Summary
Briefly describe the project, its current status and the most important outcomes so far.

## 2. Objectives
- Objective one
- Objective two
- Objective three

## 3. Progress to Date
Describe the work completed, milestones reached and deliverables produced.

### Milestones
| Milestone | Owner | Due date | Status |
| --- | --- | --- | --- |
| Milestone one | [Name] | [Date] | On track |
| Milestone two | [Name] | [Date] | Not started |

## 4. Challenges and Risks
1. Risk or challenge, with its impact
2. Mitigation action taken or planned

## 5. Next Steps
- Action item, owner and due date
- Action item, owner and due date

## 6. Conclusion
Summarise the overall outlook and any decisions required.
""",
    },
    {
        "id": "meeting_minutes", "icon": "🗒️", "name": "Meeting Minutes",
        "description": "Record attendees, decisions and action items.",
        "title": "Meeting Minutes",
        "content": """# Meeting Minutes

**Meeting:** [Meeting title]
**Date and time:** [Date, time]
**Location:** [Room or video link]
**Facilitator:** [Name]

## Attendees
- Name, role
- Name, role

## Agenda
1. Opening and introductions
2. Review of previous actions
3. Main discussion topics
4. Any other business

## Discussion Summary
Summarise the key points raised for each agenda item.

## Decisions Made
- Decision one
- Decision two

## Action Items
- Task, owner, due date
- Task, owner, due date

## Next Meeting
Date, time and proposed agenda.
""",
    },
    {
        "id": "business_proposal", "icon": "💼", "name": "Business Proposal",
        "description": "Pitch a solution with scope, timeline and pricing.",
        "title": "Business Proposal",
        "content": """# Business Proposal

**Prepared for:** [Client name]
**Prepared by:** [Your company]
**Date:** [Date]

## Executive Summary
Summarise the client's need and your proposed solution in a few sentences.

## The Problem
Describe the challenge or opportunity you have identified.

## Proposed Solution
Explain what you will deliver and how it addresses the problem.

### Scope of Work
- Deliverable one
- Deliverable two
- Deliverable three

### Timeline
1. Phase one: dates and outcomes
2. Phase two: dates and outcomes
3. Phase three: dates and outcomes

## Investment
Outline pricing, payment terms and anything that is not included.

## Why Choose Us
Highlight your experience, results and differentiators.

## Next Steps
Explain how the client can accept this proposal and what happens next.
""",
    },
    {
        "id": "professional_letter", "icon": "✉️", "name": "Professional Letter",
        "description": "A formal letter with sender, recipient and closing.",
        "title": "Professional Letter",
        "content": """[Your name]
[Your address]
[City, postal code]
[Email address]

[Date]

[Recipient name]
[Recipient title]
[Organisation]
[Address]

Dear [Recipient name],

**Subject: [Brief subject line]**

Open with the purpose of your letter in one or two clear sentences.

Use the next paragraph to give the necessary details, background or supporting information.

Close by stating what action you expect or what you would like to happen next, and thank the reader for their time.

Yours sincerely,

[Your name]
[Your title]
""",
    },
    {
        "id": "study_notes", "icon": "🎓", "name": "Study Notes",
        "description": "Organised notes with key terms and review questions.",
        "title": "Study Notes",
        "content": """# Study Notes

**Subject:** [Subject]
**Topic:** [Topic]
**Date:** [Date]

## Key Concepts
- **Concept one:** short definition
- **Concept two:** short definition
- **Concept three:** short definition

## Detailed Notes
### Section 1
Write your notes here, in your own words.

### Section 2
Add examples, formulas or diagrams you want to remember.

## Important Terms
1. Term: meaning
2. Term: meaning

## Summary
Summarise the topic in three to five sentences.

## Review Questions
1. Question you should be able to answer
2. Another question to test yourself
""",
    },
    {
        "id": "resume", "icon": "👤", "name": "Resume / CV",
        "description": "A clean one-page resume layout.",
        "title": "Resume",
        "content": """# [Your Full Name]
[City, Country] | [Phone] | [Email] | [LinkedIn or portfolio]

## Professional Summary
Two or three sentences describing your experience, strengths and career goals.

## Experience
### [Job Title], [Company]
*[Start date] – [End date], [Location]*
- Achievement with a measurable result
- Responsibility or project you led
- Skill or tool you applied

### [Job Title], [Company]
*[Start date] – [End date], [Location]*
- Achievement with a measurable result
- Responsibility or project you led

## Education
### [Degree], [Institution]
*[Years attended]*
- Honours, relevant coursework or thesis

## Skills
- Technical skills
  - Skill, skill, skill
- Languages: language (level), language (level)
- Tools: tool, tool, tool

## Certifications
- Certification name, issuer, year
""",
    },
    {
        "id": "research_report", "icon": "🔬", "name": "Research Report",
        "description": "Abstract, methods, results and references.",
        "title": "Research Report",
        "content": """# Research Report

**Author:** [Your name]
**Date:** [Date]

## Abstract
Summarise the research question, method, main findings and conclusion in about 150 words.

## 1. Introduction
Introduce the topic, explain why it matters and state your research question or hypothesis.

## 2. Literature Review
Summarise relevant prior work and identify the gap your research addresses.

## 3. Methodology
Describe how the research was carried out.
- Data sources
- Tools and procedures
- Limitations of the approach

## 4. Results
Present your findings clearly and objectively.

## 5. Discussion
Interpret the results, compare them with earlier work and explain their implications.

## 6. Conclusion
Restate the main findings and suggest directions for future research.

## References
1. Author, Title, Publisher, Year
2. Author, Title, Publisher, Year
""",
    },
]


def get_template(template_id: str) -> dict | None:
    return next((t for t in TEMPLATES if t["id"] == template_id), None)
