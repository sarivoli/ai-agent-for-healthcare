# GEMINI.md - AI Agent Context & Multi-Session Protocol

## Workspace Overview
This repository contains the **Enterprise Healthcare Model Context Protocol (MCP) & Multi-Agent Platform**, built step-by-step as a structured hands-on curriculum.

## Multi-Session Agent Protocol

Whenever starting a new chat session or resuming work in this workspace, **YOU MUST**:

1. **Read Core Tracking Files First:**
   - [TASKS.md](file:///d:/aiagent/TASKS.md): Read to identify current module, current task status, and session history log.
   - [PROJECTS.md](file:///d:/aiagent/PROJECTS.md): Check project vision, tech stack, and feature documentation index.
   - [ARCHITECTURE.md](file:///d:/aiagent/ARCHITECTURE.md): Inspect current architectural diagram, security boundaries, and Architectural Decision Records (ADRs).
   - [SKILLS.md](file:///d:/aiagent/SKILLS.md): Review learned technical concepts (MCP, FHIR, LangGraph, PHI router, RBAC).

2. **Session Execution Rules:**
   - **Progress Tracking:** Update `TASKS.md` and the brain `task.md` whenever starting (`[/]`) or completing (`[x]`) a step.
   - **Feature Documentation:** For every completed module feature, generate or update a specification in `docs/features/`.
   - **Master Course & Demo Guide:** Update [docs/COURSE_GUIDE.md](file:///d:/aiagent/docs/COURSE_GUIDE.md) at every completed module with code snippets, concept primers, and **dual OS commands (Windows & Linux/macOS)** to maintain a complete teaching/demo guide.
   - **Architecture Updates:** If setup, dependencies, or architectural decisions deviate from original plans, immediately update `ARCHITECTURE.md` and document the ADR.
   - **Hands-On Demos:** Ensure every completed module includes a working, executable test script / demo harness that can be run to verify functionality.
   - **Beginner-Friendly Pedagogy:** Always explain *why* code is written, provide plain-language concept primers, and give exact execution instructions.


3. **Session Logging:**
   - At the end of every session, append an entry to the **Session History Log** in [TASKS.md](file:///d:/aiagent/TASKS.md) with:
     - Date & Timestamp
     - Tasks Completed
     - Deviations / Decisions Made
     - Next Steps for the Next Session

---

## Directory Map
```
d:\aiagent\
├── GEMINI.md               # Master AI agent instructions (this file)
├── PROJECTS.md             # Master project specification & feature index
├── TASKS.md                # Task list & multi-session progress log
├── SKILLS.md               # Concepts & technical skills reference guide
├── ARCHITECTURE.md         # Architecture diagrams & ADR log
├── docs/
│   └── features/           # Feature documentation generated per module
│       └── README.md
├── src/                    # Source code directory
│   ├── fhir/               # FHIR R4 schemas & normalizers
│   ├── mcp_server/         # Healthcare MCP server implementation
│   ├── agents/             # LangGraph agent nodes & graph workflows
│   ├── router/             # Dual-LLM PHI classifier & proxy router
│   ├── rules/              # Clinical rules engine & confidence scoring
│   └── security/           # OAuth 2.1 & RBAC middleware
├── scripts/                # Working milestone demo harnesses & scripts
└── tests/                  # Unit and integration test suites
```
