# Echo Experience Design

## Product thesis

Echo is an AI operating workspace rather than an administrative dashboard. The interface is organized around intent, context, reasoning, and execution. CRUD APIs remain available for system integration, but the human experience no longer exposes the application as a collection of database modules.

## Experience architecture

The authenticated interface uses four coordinated layers:

1. **Application rail** — fast, keyboard-friendly movement between the most frequently used workspaces.
2. **Context rail** — the complete workspace map, record awareness, and current personal context.
3. **Adaptive canvas** — a purpose-built environment for the active domain rather than a repeated card dashboard.
4. **Echo presence** — persistent reasoning, provider, workflow, tool, memory, and background-work awareness.

The layout progressively adapts on smaller screens. The context and presence layers become controlled drawers while the central canvas remains primary.

## Design language

### Typography

Echo uses the operating system's modern UI font stack to avoid external font dependencies. Headings use tight letter spacing and moderate weight. Labels use small uppercase text only where hierarchy benefits from it.

### Color

The default dark system uses near-black neutral surfaces, warm white text, and a restrained iris accent. Status colors are muted semantic signals rather than decorative neon. A complete light mode is included and may follow the operating system.

### Spacing and grid

The design follows a four-pixel base system. Major surfaces use 16–30 pixel radii based on hierarchy. Desktop layout widths are tokenized through `--rail`, `--context`, `--presence`, and `--topbar`.

### Elevation

Elevation is communicated primarily through surface contrast, thin borders, and restrained shadows. Glass effects are limited to persistent controls such as the top bar, global composer, and modal backdrop.

### Motion

Motion communicates state changes: Echo reasoning, modal transitions, task completion, drag-and-drop, and navigation drawers. All animation is disabled or reduced under `prefers-reduced-motion`.

### Iconography

A project-owned SVG symbol library is provided in `static/icons.svg`. Icons use consistent 1.7-pixel strokes and inherit semantic color from their component.

## AI interaction model

Echo remains visible in every authenticated workspace through:

- provider readiness
- current reasoning state
- active tool and workflow records
- queued or pending work
- memory and knowledge awareness
- global command entry
- contextual suggestion prompts

Commands are persisted as real conversations and messages. When an AI provider is configured, the existing `AIExecutionService` produces the response. When no provider is configured, Echo saves the command and clearly directs the user to configuration and never fabricates provider output.

## Functional workspace routes

- `/` — adaptive home
- `/workspace/chat/`
- `/workspace/knowledge/`
- `/workspace/memory/`
- `/workspace/projects/`
- `/workspace/planner/`
- `/workspace/tasks/`
- `/workspace/analytics/`
- `/workspace/browser/`
- `/workspace/documents/`
- `/workspace/email/`
- `/workspace/calendar/`
- `/workspace/agents/`
- `/workspace/workflows/`
- `/workspace/code/`
- `/workspace/notifications/`
- `/workspace/settings/`

## Operational interactions

The workspace layer includes production-backed actions for:

- owner-scoped universal search
- record creation for supported workspaces
- task completion
- secure document upload and registration
- AI command persistence
- configured-provider AI execution
- dark, light, and system appearance modes
- keyboard command palette

## Accessibility

The interface includes semantic regions, labels, visible focus states, skip navigation, screen-reader labels, keyboard shortcuts, high-contrast adaptations, reduced-motion adaptations, and touch-safe controls. Responsive behavior preserves functional access on desktop, tablet, and mobile.
