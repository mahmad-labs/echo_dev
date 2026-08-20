# Homepage Command Center

The Echo homepage is an adaptive operating surface, not a statistics dashboard. It uses owner-scoped application records to prioritize the next meaningful action.

## Information hierarchy

1. The primary Echo command surface accepts text, voice, files, and contextual suggestions.
2. The attention lane surfaces real approvals, failed work, authentication requirements, CAPTCHA intervention, permission failures, and microphone problems.
3. Active work shows real workflow, agent, research, AI, browser, and processing states.
4. Execution and continuity surfaces show active tasks, current projects, recent conversations, and indexed documents.
5. Capability launchers provide direct access to Voice, Research, Workflows, and Knowledge.

When no urgent data exists, the homepage presents a calm starting state rather than invented metrics or demo activity.

## Universal command routing

The text composer and Voice both use `EchoCommandService`. It supports:

- task creation, listing, and completion
- daily planning from active tasks
- project creation and project continuation
- workflow execution through the existing workflow engine
- web research through the configured search provider
- document analysis after extraction and knowledge indexing
- agent assignment when an active agent is configured
- owner-scoped knowledge and approved memory retrieval
- workspace navigation
- normal AI conversation through the configured provider

Every command creates or continues a normal Chat conversation. The system never claims an external action completed unless its concrete service returned a completed result.

## File flow

The file control uploads through the authenticated document endpoint. Echo creates the existing `UploadedFile` and `Document` records, extracts supported content, creates `DocumentContent`, indexes it as a `KnowledgeDocument`, and creates bounded `DocumentSection` chunks. Processing failures remain attached to the document and surface in the attention queue.

## Performance

Homepage queries are bounded and ordered by recent relevance. Lists are limited before serialization, large document content is not loaded into the homepage, and commands only load context required for the selected operation. Long-running tasks can execute through Celery when eager mode is disabled.

## Security and accessibility

All data is owner-scoped. Actions require authentication and CSRF protection. Uploaded paths use generated storage keys and normalized filenames. The command center uses semantic headings, visible focus states, keyboard controls, live result announcements, reduced-motion support, and responsive layouts that reorder priority rather than simply shrinking the desktop grid.
