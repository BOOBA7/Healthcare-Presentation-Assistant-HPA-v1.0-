# Healthcare Presentation Assistant (HPA)

## HCP User Guide

## Purpose

Healthcare Presentation Assistant (HPA) helps healthcare professionals prepare
scientific PowerPoint presentations from PDF resources they provide.

HPA supports drafting, review and export. It does not replace professional
judgement, scientific review, institutional policy or clinical decision-making.

## Before you start

Please use only PDFs you are authorised to use and documents relevant to your
presentation. Do not upload identifiable patient information. Use Patient Case
Mode only with fully de-identified or fictional cases.

## 1. Create your account and profile

1. Open the HPA link.
2. Register with a user ID and password.
3. Select your professional role.
4. Select English, French or Arabic.
5. Sign in.

Your profile helps HPA adapt its communication style. It does not replace
professional responsibility or scope clarification when required.

## 2. Create a Project

Create one Project for each independent presentation.

A Project contains its own PDF library, Resource Overview, Resource Chat,
presentation conversation, blueprint, Agenda, slides, PowerPoint export and
audit history.

Example:

```text
Depression treatment update — GP meeting
```

## 3. Choose the evidence mode

Each Project offers two evidence-context modes.

| Mode | Purpose |
|---|---|
| BM25 retrieval | Default mode. HPA selects the PDF passages most relevant to the question or generation task. |
| Direct bounded PDF context | Experimental mode. HPA uses a balanced, limited portion of the same PDFs without BM25 ranking. |

For a fair comparison, use the same PDFs, question and presentation conditions
in both modes.

## 4. Optional: Patient Case Mode

Use this mode only with fully de-identified information. HPA attempts to block
obvious identifiers such as email addresses, phone numbers, medical-record
identifiers, social-security identifiers, postal addresses and full dates in
patient-case text.

A publication date in a scientific PDF does not block a normal guideline or
article by itself. Patient Case Mode is a guardrail, not a HIPAA certification
or formal de-identification guarantee.

## 5. Use the Resources workspace

The Resources workspace is separate from the Presentation assistant. Use it to
explore your PDFs before producing slides.

### Upload PDFs

1. Open **Resources**.
2. Upload one or more readable PDF files.
3. Wait for text extraction.
4. Check the displayed title, source and page count.

### Resource Overview

Use **Generate Resource Overview** to obtain a concise synthesis of the
uploaded PDF library. It can help identify the overall idea, key themes, areas
of agreement or tension, limitations and possible presentation angles.

Use it as a discussion starter, not as a final scientific conclusion.

### Resource Chat

Use **Resource Chat** to ask questions about the uploaded PDFs.

```text
What does the guideline say about first-line treatment?

What are the limitations of these resources?

Do the two documents agree on follow-up recommendations?
```

If the resources are insufficient, HPA should request a more relevant PDF or
clarification instead of inventing an answer.

> **Note:** Resource Overview and Resource Chat are exploratory features.
> AI-generated slide citations receive stricter system validation before
> approval and PowerPoint export.

### Manage resources

You can upload or remove a PDF, attach it to the presentation, or detach it.
Only explicitly attached and user-validated PDFs can support blueprint and slide
generation.

## 6. Start the presentation workflow

Open **Presentation assistant** and describe your objective.

```text
I need a 15-minute educational presentation in French for general practitioners
about depression management, based on the attached guideline.
```

HPA may ask for the topic, audience, presentation type, duration, language,
learning objective or professional-scope clarification.

If requested, provide one clear sentence about your role and purpose.

```text
I am a medical representative with veterinary training preparing scientific
information for human healthcare professionals.
```

## 7. Validate presentation resources

Before blueprint generation:

1. Select the PDFs relevant to the presentation.
2. Review the selection.
3. Click **Validate resources and continue**.

This is a human validation step. HPA cannot validate resources for you.

## 8. Add title-slide details

You may add presenter name, professional title, organisation, event name,
venue and presentation date. These details are user-provided; HPA does not
infer them.

## 9. Review the Blueprint and Agenda

After resource validation, ask HPA to generate the blueprint. It proposes the
presentation structure, slide titles, learning objectives, key messages and
narrative sequence.

The Agenda is reviewed separately and becomes slide 2 of the exported
PowerPoint. For each blueprint item, you can approve, reject and comment, edit
directly, regenerate, or write it yourself.

## 10. Generate and review slides

After Blueprint and Agenda approval, generate the slides.

For each slide, you can approve, reject and comment, regenerate with feedback,
edit directly, mark it as user-edited, or write it yourself.

### AI-generated slides

AI-generated slides must be supported by selected and validated PDFs. HPA
verifies that:

1. the cited PDF exists in the presentation selection;
2. the cited page exists;
3. the cited excerpt is present on that page.

If evidence is insufficient for one slide, HPA pauses that slide instead of
inventing content. You can add a more relevant PDF, revise the blueprint, or
write the slide yourself.

### User-authored content

Slides and blueprint items are labelled as AI-generated, user-edited or
user-authored. A user-authored slide is created from your content without an AI
generation call.

## 11. Final approval and PowerPoint export

When all slides are reviewed:

1. Approve the final presentation.
2. Export the PowerPoint.

The export includes the title slide, Agenda as slide 2, reviewed slides, and a
final **Resources and validation** slide.

## 12. Suggested HCP test scenarios

Please test:

1. Uploading relevant PDFs.
2. Resource Overview.
3. A question clearly answered by the PDF.
4. A question not answered by the PDF.
5. Resource validation.
6. Blueprint and Agenda review.
7. Slide generation.
8. One citation and its PDF page.
9. Editing or writing one slide yourself.
10. PowerPoint export.
11. BM25 versus Direct bounded PDF context, if possible.

## 13. Feedback

Please complete the HCP evaluation form provided with HPA.

Useful feedback includes:

- Was the workflow clear?
- Were citations understandable?
- Did HPA refuse unsupported questions appropriately?
- Did the Blueprint save time?
- Were edits and approvals easy to use?
- Did the PowerPoint meet professional expectations?
- Which evidence mode did you prefer?

Thank you for helping evaluate HPA.
