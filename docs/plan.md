# Open teaching extension for Blender

## 1. Product direction

Build a free, open-source Blender extension that lets teachers **create guided lessons inside Blender** and lets learners follow those lessons with instructions, visual guidance, and feedback.

The first release will prove the complete workflow with the Clubhouse LMS:

**Create or record → review → export → publish → download → learn offline → synchronize progress.**

Agreed priorities:

- Both **guided capture** and **automatic recording into editable draft steps**.
- Beginner Blender teaching first, with a mathematics lesson demonstrating subject teaching.
- Windows classroom pilot, targeting **Blender 5.2 LTS**, supported until July 2028. [Official release information](https://www.blender.org/releases/5-2/)
- Automatic checks for measurable results, learner confirmation for other steps, and existing LMS mentor review for assessed projects.
- Personal computers and shared classroom computers.
- Open tools and file format; teachers choose their tutorials’ licenses and sharing permissions.

Keep the extension in its own repository. Add the Clubhouse integration to the existing LMS through a documented adapter, allowing other platforms to integrate later.

## 2. Teacher and learner experience

### Teacher authoring

Provide one lesson editor with two entry points:

| Mode | Workflow |
|---|---|
| Guided capture | Perform a step, capture its target and expected result, then add instructions, images, hints, and completion conditions. |
| Automatic recording | Record a modelling session, then review the generated timeline and turn it into teaching steps. |

Both modes produce the same editable lesson structure: chapters containing ordered steps.

Teachers can split, merge, reorder, delete, and rewrite steps; add progressive hints; capture reference images and chapter checkpoints; and preview the lesson as a learner. Publishing requires validation and teacher review of flagged recording items.

The initial recorder covers primitives, object operations, transforms, common modifiers, basic materials, and common mesh-edit actions. Mesh edits receive visual references and manual completion by default.

Recording uses an incremental local journal, so long lessons survive Blender’s limited operator history. Unsupported or ambiguous actions become review items. Captured commands are never executed as tutorial code. Blender 5.2’s action reports and screenshot APIs support this approach. [Python API changes](https://developer.blender.org/docs/release_notes/5.2/python_api/)

### Recorder design

Based on the Milestone 1 Step 0 evidence in `docs/m1-findings.md` (Blender 5.2.2). The recorder writes two append-only journals on disk.

**Action journal.**

- **Source:** `WindowManager.reports` entries of type `OPERATOR` and `PROPERTY`. They cover confirmed tools with their final values, including typed values, and edits made in interface fields and sliders. The operator history (`WindowManager.operators`) is not used: undo clears it and it skips operators called from scripts.
- **Capture:** a persistent timer polls the reports about every 0.1 s and appends each new report with its `session_uid`, its type, its message and the poll time. Reports carry no timestamp.
- **De-duplication:** by Blender session plus `session_uid`, which keeps increasing across file loads.
- **Durability:** each entry is written to disk as it is captured, because opening a file clears the reports.
- **Safety:** report messages are evidence only. They may be parsed with `ast.parse` and `ast.literal_eval` into an operator id or property path plus values. They are never executed.

**State journal.**

- **What:** throttled snapshots of the documented property set: objects and their types, transforms and dimensions, mode, selection and active object, modifiers and their settings, and material assignments.
- **When:** after undo and redo (`undo_post`, `redo_post`), after a file load (`load_post`), and after changes flagged by message-bus subscriptions or depsgraph updates. Triggers only mark the state as changed; an idle timer takes the snapshot, never more than once per throttle interval and never inside a handler.
- **Diffs:** each snapshot is stored as a change from the previous one.

**Lifecycle.**

- **Persistence:** timers and handlers are registered as persistent, so recording continues across file loads. All of them are removed when recording stops and when the extension is disabled.
- **Pause and resume:** both are entries in the action journal.
- **Recovery:** after a crash, the journal on disk is the record; it is reopened and continued.

**Merging into draft steps (initial rules, validated in Step 4).**

1. Each supported `OPERATOR` or `PROPERTY` entry is evidence for one action. Repeated edits of the same property path with no other action between them collapse to the final value.
2. A state change that no action explains becomes a draft from the state diff. A Dimensions edit, which leaves no report, is the known case.
3. Undo and redo are matched against the state journal. Work that was undone and not redone is left out of the drafts; when the match is unclear, the step becomes a review item.
4. Reports for unsupported operators, actions from other add-ons or scripts (which Blender reports the same way as user actions), and anything that fails to parse become review items, never silent drops.
5. Cancelled tools leave no report and are correctly absent.

### Learner guidance

Provide a native sidebar for lesson controls and a collapsible instruction overlay inside the 3D viewport.

Each step can show:

- What to do and why it matters.
- Object outlines, arrows, spatial markers, and supported editor-region highlights.
- Menu/property paths and annotated images for individual Blender controls.
- Reference results, progressive hints, and completion feedback.

Use semantic targets rather than saved screen coordinates. Starter objects receive stable identifiers; newly created objects resolve through teacher-defined targets. Missing or ambiguous targets prompt selection instead of highlighting an unrelated object. Avoid persistent face or vertex indices across topology changes.

Automatic checks initially cover object existence/type, selection, mode, transforms/dimensions with tolerances, modifier settings, and material assignment. Checks evaluate results rather than requiring an exact click sequence.

Learners control advancement. Skipping leaves a required step incomplete; manual confirmation is available only where the teacher permits it. Going back changes the displayed instructions without undoing modelling work.

Recovery checkpoints open a separate working copy after offering to save current work. Starting a downloaded lesson never silently replaces an open project.

## 3. Portable packages and LMS integration

### Tutorial format and local storage

Define a documented, versioned ZIP format containing:

- A JSON manifest with tutorial/version identifiers, compatible Blender versions, author, license, learning objectives, and asset hashes.
- Chapters and steps with stable identifiers, instructions, targets, hints, and supported completion rules.
- Required images, starter projects, and optional checkpoint `.blend` files.

Tutorials contain declarative data, not executable Python. Import validates paths, file types, hashes, schema compatibility, and configured archive limits. Packaged projects open with automatic script execution disabled.

Export checks that all required resources are included. A successfully downloaded tutorial must remain usable without external images, services, or authentication.

Store packages separately from learner working files, recording journals, and progress. Pin each attempt to an immutable tutorial version; updates never replace an active attempt.

### Clubhouse publishing and launch

Reuse existing **admin and mentor** roles to upload, validate, preview, and publish packages against LMS lessons.

Learners pair Blender through a browser authorization flow. The extension receives an individual, revocable credential; it never receives the LMS password or an embedded shared service secret.

“Send to Blender” queues the published tutorial for a selected paired device. While Blender is running and online access is enabled, it checks its inbox, downloads and verifies the package, and displays **Ready to start**.

Delivery states are separate from learning states: queued, downloaded, and started. A stable request identifier makes repeated delivery harmless.

Manual download/import remains available for other LMSs and USB distribution.

### Public integration contract

Add a versioned JSON API through a PHP endpoint compatible with the current LMS hosting:

| Capability | Responsibility |
|---|---|
| Pairing and revocation | Browser approval, credential issuance/renewal, identity, and disconnection |
| Catalog and versions | Eligible lessons, immutable package metadata, and authenticated downloads |
| Launch inbox | Queue requests, retrieve deliveries, and acknowledge verified downloads |
| Attempts and progress | Create/resume version-pinned attempts and accept deduplicated progress batches |

Store tutorial versions, lesson links, device grants, launch requests, attempts, and progress events. Reuse existing enrollment and section-unlock rules on the server.

Progress events identify the attempt, step, completion method, and unique event ID. Retried or delayed events must not duplicate awards or reduce completed progress.

Route lesson completion through the existing `ProgressModel` so course totals and badges remain consistent. Tutorial checks represent learning progress; they do not approve mentor-assessed assignments.

For v1, provide **Prepare submission** and **Open LMS submission page**, reusing the existing browser submission and rubric workflow. Support packaged Blender projects through assignment-specific upload limits.

### Offline use and shared computers

Namespace learner work and pending synchronization by LMS origin and immutable member identity.

- **Personal mode:** remember pairing using Windows credential storage and resume the learner’s profile.
- **Shared-lab mode:** keep credentials in memory, show the active learner prominently, and require explicit profile selection after restart.
- Both modes support offline continuation of downloaded lessons and saved attempts.
- Synchronization requires authentication as the queue’s original owner. Another learner’s sign-in never adopts pending work.
- Signing out preserves saved work and clears active credentials; deleting a local profile is a separate action.

Shared-lab profiles prevent accidental account mixing. They do not provide filesystem privacy between people sharing one Windows login; separate Windows accounts provide that boundary.

## 4. Delivery milestones and acceptance tests

### Milestone 1 — Prove guidance and recording

Build a small Windows/Blender 5.2 prototype before the full editor.

Verify viewport instructions, object/editor guidance, workspace changes, display scaling, undo, file loading, and clean extension shutdown.

Record a 60–90-minute modelling session with at least 1,000 actions. Supported actions must produce usable draft evidence or an explicit review flag, including repeated actions, cancellation, undo/redo, and pause/resume. Earlier recordings must survive history rollover and interrupted-session recovery.

### Milestone 2 — Complete standalone authoring and playback

Deliver both authoring modes, review tools, package export/import, supported checks, checkpoint recovery, and offline resume.

Acceptance: a teacher creates and exports a lesson without coding; another computer imports it and completes it entirely offline.

### Milestone 3 — Complete the Clubhouse workflow

Deliver publishing, pairing, inbox downloads, progress synchronization, and submission preparation.

Test expired/revoked credentials, locked lessons, interrupted downloads, duplicate acknowledgements, duplicate progress events, and publication updates during existing attempts.

Test the classroom sequence explicitly: learner A works offline, learner B signs in and synchronizes, then A returns. Their projects, inboxes, and progress must remain correctly associated.

### Milestone 4 — Classroom pilot and release

Ship two example tutorials:

1. **Model a desk organiser:** basic modelling, mesh edits, modifiers, and materials.
2. **Explore volume and scale:** use dimensions and 3D objects to investigate mathematical relationships.

Validate with teachers and beginner learners on the actual lab machines. Record confusing steps, guidance failures, recording gaps, and performance issues before declaring v1 ready.

## 5. Open-source commitments and boundaries

- License extension code **GPL-3.0-or-later**. Publish the format specification, contributor documentation, tests, and build instructions.
- License bundled extension artwork CC0 and distribute example tutorial packages separately under CC BY 4.0. Teachers retain control of their own content licenses.
- Core authoring and playback require no account, paid service, or internet connection. Network access and progress transmission are explicit.
- Distribute installable extension ZIPs initially. Treat listing on Blender’s official platform as a separate review under its current requirements. [Blender Extensions terms](https://extensions.blender.org/terms-of-service/)
- V1 uses English instructions with translation-ready content fields, adjustable text, and guidance that does not rely on colour alone.
- Defer deterministic action replay, universal button highlighting, comprehensive sculpt/node recording, cloud AI authoring, live classroom control, and additional LMS adapters.
- Technical feasibility is currently based on repository and API inspection. Milestone 1 supplies the runtime evidence required for the full implementation.
