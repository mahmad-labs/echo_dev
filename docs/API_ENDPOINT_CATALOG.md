# API endpoint catalog

This catalog contains all 238 source-specified method/path pairs. The compatibility API uses the original `/api/...` paths. The generated model API is available under `/api/v1/<domain>/...`. Authentication, ownership filtering, structured errors, throttling, and correlation IDs apply unless a public status/share route is explicitly identified.

## Agent Manager

| Method | Path |
|---|---|
| `GET` | `/api/agents/` |
| `POST` | `/api/agents/` |
| `PUT` | `/api/agents/<id>/` |
| `DELETE` | `/api/agents/<id>/` |
| `GET` | `/api/agents/tasks/` |
| `POST` | `/api/agents/tasks/` |
| `GET` | `/api/agents/capabilities/` |
| `GET` | `/api/agents/groups/` |
| `POST` | `/api/agents/groups/` |
| `GET` | `/api/agents/performance/` |

## Ai Engine

| Method | Path |
|---|---|
| `GET` | `/api/ai/models/` |
| `POST` | `/api/ai/models/` |
| `PUT` | `/api/ai/models/<id>/` |
| `GET` | `/api/ai/providers/` |
| `PUT` | `/api/ai/providers/<id>/` |
| `POST` | `/api/ai/generate/` |
| `POST` | `/api/ai/stream/` |
| `GET` | `/api/ai/history/` |
| `GET` | `/api/ai/prompts/` |
| `PUT` | `/api/ai/prompts/<id>/` |
| `POST` | `/api/ai/request/` |
| `GET` | `/api/ai/analytics/` |

## Authentication

| Method | Path |
|---|---|
| `POST` | `/api/auth/register/` |
| `POST` | `/api/auth/login/` |
| `POST` | `/api/auth/logout/` |
| `POST` | `/api/auth/refresh/` |
| `POST` | `/api/auth/change-password/` |
| `POST` | `/api/auth/forgot-password/` |
| `POST` | `/api/auth/reset-password/` |
| `GET` | `/api/user/` |
| `PUT` | `/api/user/` |
| `DELETE` | `/api/user/` |
| `GET` | `/api/sessions/` |
| `DELETE` | `/api/sessions/<id>/` |
| `GET` | `/api/devices/` |
| `DELETE` | `/api/devices/<id>/` |
| `GET` | `/api/tokens/` |
| `POST` | `/api/tokens/` |
| `DELETE` | `/api/tokens/<id>/` |

## Calendar

| Method | Path |
|---|---|
| `GET` | `/api/calendar/` |
| `POST` | `/api/calendar/` |
| `PUT` | `/api/calendar/<id>/` |
| `DELETE` | `/api/calendar/<id>/` |
| `GET` | `/api/calendar/events/` |
| `POST` | `/api/calendar/events/` |
| `PUT` | `/api/calendar/events/<id>/` |
| `DELETE` | `/api/calendar/events/<id>/` |
| `GET` | `/api/calendar/availability/` |
| `PUT` | `/api/calendar/availability/` |
| `GET` | `/api/calendar/reminders/` |
| `POST` | `/api/calendar/sync/` |

## Chat

| Method | Path |
|---|---|
| `GET` | `/api/chat/conversations/` |
| `POST` | `/api/chat/conversations/` |
| `GET` | `/api/chat/conversations/<id>/` |
| `PUT` | `/api/chat/conversations/<id>/` |
| `DELETE` | `/api/chat/conversations/<id>/` |
| `GET` | `/api/chat/messages/` |
| `POST` | `/api/chat/messages/` |
| `PUT` | `/api/chat/messages/<id>/` |
| `DELETE` | `/api/chat/messages/<id>/` |
| `POST` | `/api/chat/attachments/` |
| `GET` | `/api/chat/attachments/<id>/` |
| `POST` | `/api/chat/export/` |
| `GET` | `/api/chat/share/<token>/` |
| `GET` | `/api/chat/search/` |

## Code Assistant

| Method | Path |
|---|---|
| `GET` | `/api/code/projects/` |
| `POST` | `/api/code/projects/` |
| `PUT` | `/api/code/projects/<id>/` |
| `DELETE` | `/api/code/projects/<id>/` |
| `POST` | `/api/code/analyze/` |
| `POST` | `/api/code/review/` |
| `POST` | `/api/code/generate/` |
| `POST` | `/api/code/refactor/` |
| `POST` | `/api/code/tests/` |
| `GET` | `/api/code/search/` |
| `POST` | `/api/code/documentation/` |

## Core

| Method | Path |
|---|---|
| `GET` | `/api/core/health/` |
| `GET` | `/api/core/status/` |
| `GET` | `/api/core/version/` |
| `GET` | `/api/core/config/` |
| `PUT` | `/api/core/config/` |
| `GET` | `/api/core/features/` |
| `PUT` | `/api/core/features/<id>/` |
| `GET` | `/api/core/logs/` |
| `GET` | `/api/core/audit/` |
| `POST` | `/api/core/files/` |
| `GET` | `/api/core/files/` |
| `DELETE` | `/api/core/files/<id>/` |

## Dashboard

| Method | Path |
|---|---|
| `GET` | `/api/dashboard/` |
| `GET` | `/api/dashboard/home/` |
| `POST` | `/api/dashboard/refresh/` |
| `GET` | `/api/dashboard/widgets/` |
| `POST` | `/api/dashboard/widgets/` |
| `PUT` | `/api/dashboard/widgets/<id>/` |
| `DELETE` | `/api/dashboard/widgets/<id>/` |
| `GET` | `/api/dashboard/layout/` |
| `PUT` | `/api/dashboard/layout/` |
| `POST` | `/api/dashboard/layout/reset/` |
| `GET` | `/api/dashboard/actions/` |
| `POST` | `/api/dashboard/actions/` |
| `DELETE` | `/api/dashboard/actions/<id>/` |
| `GET` | `/api/dashboard/notifications/` |
| `PUT` | `/api/dashboard/notifications/<id>/` |
| `DELETE` | `/api/dashboard/notifications/<id>/` |

## Documents

| Method | Path |
|---|---|
| `GET` | `/api/documents/` |
| `POST` | `/api/documents/` |
| `GET` | `/api/documents/<id>/` |
| `PUT` | `/api/documents/<id>/` |
| `DELETE` | `/api/documents/<id>/` |
| `POST` | `/api/documents/upload/` |
| `GET` | `/api/documents/search/` |
| `GET` | `/api/documents/<id>/preview/` |
| `POST` | `/api/documents/<id>/export/` |
| `GET` | `/api/documents/jobs/` |
| `POST` | `/api/documents/jobs/` |

## Email

| Method | Path |
|---|---|
| `GET` | `/api/email/accounts/` |
| `POST` | `/api/email/accounts/` |
| `GET` | `/api/email/messages/` |
| `GET` | `/api/email/messages/<id>/` |
| `POST` | `/api/email/drafts/` |
| `PUT` | `/api/email/drafts/<id>/` |
| `POST` | `/api/email/send/` |
| `POST` | `/api/email/sync/` |

## Internet

| Method | Path |
|---|---|
| `POST` | `/api/internet/search/` |
| `POST` | `/api/internet/news/` |
| `POST` | `/api/internet/images/` |
| `POST` | `/api/internet/videos/` |
| `POST` | `/api/internet/fetch/` |
| `GET` | `/api/internet/rss/` |
| `POST` | `/api/internet/rss/` |
| `GET` | `/api/internet/monitors/` |
| `POST` | `/api/internet/monitors/` |
| `DELETE` | `/api/internet/monitors/<id>/` |
| `GET` | `/api/internet/history/` |
| `POST` | `/api/internet/crawl/` |
| `GET` | `/api/internet/downloads/` |
| `POST` | `/api/internet/download/` |
| `GET` | `/api/internet/monitoring/` |

## Knowledge

| Method | Path |
|---|---|
| `GET` | `/api/knowledge/collections/` |
| `POST` | `/api/knowledge/collections/` |
| `PUT` | `/api/knowledge/collections/<id>/` |
| `DELETE` | `/api/knowledge/collections/<id>/` |
| `GET` | `/api/knowledge/categories/` |
| `POST` | `/api/knowledge/categories/` |
| `GET` | `/api/knowledge/documents/` |
| `POST` | `/api/knowledge/documents/` |
| `GET` | `/api/knowledge/documents/<id>/` |
| `PUT` | `/api/knowledge/documents/<id>/` |
| `DELETE` | `/api/knowledge/documents/<id>/` |
| `GET` | `/api/knowledge/search/` |
| `POST` | `/api/knowledge/import/` |
| `POST` | `/api/knowledge/export/` |
| `GET` | `/api/knowledge/versions/` |
| `POST` | `/api/knowledge/rollback/` |

## Memory

| Method | Path |
|---|---|
| `GET` | `/api/memory/` |
| `POST` | `/api/memory/` |
| `GET` | `/api/memory/<id>/` |
| `PUT` | `/api/memory/<id>/` |
| `DELETE` | `/api/memory/<id>/` |
| `GET` | `/api/memory/categories/` |
| `POST` | `/api/memory/categories/` |
| `GET` | `/api/memory/search/` |
| `GET` | `/api/memory/relationships/` |
| `POST` | `/api/memory/relationships/` |
| `POST` | `/api/memory/feedback/` |

## Notifications

| Method | Path |
|---|---|
| `GET` | `/api/notifications/` |
| `POST` | `/api/notifications/` |
| `PUT` | `/api/notifications/<id>/` |
| `DELETE` | `/api/notifications/<id>/` |
| `GET` | `/api/notifications/preferences/` |
| `PUT` | `/api/notifications/preferences/` |
| `GET` | `/api/notifications/templates/` |
| `GET` | `/api/notifications/digests/` |
| `GET` | `/api/notifications/delivery/` |

## Planner

| Method | Path |
|---|---|
| `GET` | `/api/planner/goals/` |
| `POST` | `/api/planner/goals/` |
| `PUT` | `/api/planner/goals/<id>/` |
| `DELETE` | `/api/planner/goals/<id>/` |
| `GET` | `/api/planner/plans/` |
| `POST` | `/api/planner/plans/` |
| `GET` | `/api/planner/plans/<id>/` |
| `PUT` | `/api/planner/steps/<id>/` |
| `POST` | `/api/planner/steps/reorder/` |
| `GET` | `/api/planner/progress/` |

## Projects

| Method | Path |
|---|---|
| `GET` | `/api/projects/workspaces/` |
| `POST` | `/api/projects/workspaces/` |
| `GET` | `/api/projects/` |
| `POST` | `/api/projects/` |
| `PUT` | `/api/projects/<id>/` |
| `DELETE` | `/api/projects/<id>/` |
| `GET` | `/api/projects/members/` |
| `POST` | `/api/projects/members/` |
| `GET` | `/api/projects/milestones/` |
| `POST` | `/api/projects/milestones/` |
| `POST` | `/api/projects/backup/` |
| `POST` | `/api/projects/restore/` |

## Tasks

| Method | Path |
|---|---|
| `GET` | `/api/tasks/` |
| `POST` | `/api/tasks/` |
| `GET` | `/api/tasks/<id>/` |
| `PUT` | `/api/tasks/<id>/` |
| `DELETE` | `/api/tasks/<id>/` |
| `POST` | `/api/tasks/subtasks/` |
| `PUT` | `/api/tasks/subtasks/<id>/` |
| `GET` | `/api/tasks/reminders/` |
| `POST` | `/api/tasks/reminders/` |
| `POST` | `/api/tasks/time/start/` |
| `POST` | `/api/tasks/time/stop/` |
| `GET` | `/api/tasks/analytics/` |

## Tool Manager

| Method | Path |
|---|---|
| `GET` | `/api/tools/` |
| `POST` | `/api/tools/` |
| `PUT` | `/api/tools/<id>/` |
| `DELETE` | `/api/tools/<id>/` |
| `POST` | `/api/tools/execute/` |
| `GET` | `/api/tools/registry/` |
| `POST` | `/api/tools/register/` |
| `GET` | `/api/tools/health/` |
| `GET` | `/api/tools/analytics/` |

## Vector Database

| Method | Path |
|---|---|
| `POST` | `/api/vector/embed/` |
| `POST` | `/api/vector/embed/batch/` |
| `POST` | `/api/vector/search/` |
| `POST` | `/api/vector/hybrid-search/` |
| `GET` | `/api/vector/index/` |
| `POST` | `/api/vector/index/` |
| `PUT` | `/api/vector/index/rebuild/` |
| `POST` | `/api/vector/documents/` |
| `DELETE` | `/api/vector/documents/<id>/` |
| `GET` | `/api/vector/namespaces/` |
| `POST` | `/api/vector/namespaces/` |

## Workflow Engine

| Method | Path |
|---|---|
| `GET` | `/api/workflows/` |
| `POST` | `/api/workflows/` |
| `PUT` | `/api/workflows/<id>/` |
| `DELETE` | `/api/workflows/<id>/` |
| `GET` | `/api/workflows/executions/` |
| `POST` | `/api/workflows/execute/` |
| `GET` | `/api/workflows/steps/` |
| `PUT` | `/api/workflows/steps/<id>/` |
| `GET` | `/api/workflows/checkpoints/` |
| `POST` | `/api/workflows/checkpoints/restore/` |
