# Agent Orchestration

Echo has one orchestration entry point: `AgentManagerOrchestrator`. Text, voice, and workflow delegation enter this manager instead of calling independent agent stacks.

## Runtime flow

A request is persisted as a root `AgentTask`. The manager classifies the objective, creates specialist child tasks, builds a permission-scoped `AgentContext`, records structured `AgentCommunication` messages, invokes the registered agent, and persists its structured `AgentResult`. Complex objectives create a Planner child before execution. Browser operations may continue asynchronously and update the same task graph when verified execution finishes.

The task graph records the owner, conversation, project, parent task, selected agent, priority, status, progress, current operation, current tool, result, error, timestamps, cancellation request, and correlation ID. This is the status source used by the workspace rather than synthetic activity.

## Agent Registry

`AgentRegistry` is the central capability catalog. Built-in registrations include Memory, Knowledge, Planner, Browser, Computer, Documents, Projects, Tasks, Workflow, and Chat agents. A definition declares its identifier, description, capabilities, required tools, required permissions, input/output schemas, context scopes, version, availability, and handler.

Agents do not receive unrestricted state. `AgentContextBuilder` loads only context scopes declared by the selected agent. Browser/page state, computer observations, Memory, Knowledge, project state, approvals, permissions, and execution state are independently scoped.

## Agent communication

`AgentCommunication` is the structured handoff bus. Assignments, context requests, context results, handoffs, plans, and results are JSON payloads tied to one task/correlation graph. Specialists consume structured data rather than parsing another agent's prose whenever a structured representation is available.

Memory and Knowledge context requests are explicitly recorded. Browser research completion can hand verified evidence to the Knowledge and Documents agents. External research is not automatically converted into personal Memory.

## Memory and Knowledge

`MemoryAgentService` owns durable user/project memory behavior: retrieval, creation, update/correction, deletion, relevance ranking, classification, deduplication, access logging, and lifecycle cleanup. Voice memory remains approval-gated by default.

`KnowledgeAgentService` owns searchable external/user-provided knowledge. It provides owner-scoped lexical and embedding-based retrieval plus ingestion/versioning. Documents and verified research can become Knowledge; user preferences and durable personal/project decisions belong in Memory.

## Planner and projects

The Planner persists goals and plan steps with assigned agent identifiers. Research objectives are decomposed into verified browser work plus optional Knowledge ingestion and report creation. Continue/resume-project requests run a Planner child before the Project Agent and receive the scoped current project, relevant Memory, and relevant Knowledge.

## Tools and workflows

All environment capabilities remain in the central Tool Manager. Agents declare required tools but do not implement private tool registries. The Tool Manager registers an `agent.execute` bridge so workflow steps can delegate into the same Agent Manager pipeline.

Consequential actions retain their existing approval boundaries. A model-generated plan cannot self-confirm an action. Browser CAPTCHA/login/MFA blockers cannot be overridden by a normal tool payload.

## Failure and cancellation

A specialist returns structured status, result, errors, artifacts, metadata, next actions, and optional confidence. The manager persists failure rather than fabricating success. Cancellable root/child tasks propagate cancellation to linked computer-use operations. Failed environment actions can be replanned from fresh evidence where the computer-use service marks the failure as recoverable.
