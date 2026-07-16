# CLAUDE.md

# SENTRA AI — Claude Code Development Constitution

Version: 1.0

This document defines the engineering rules, architectural principles, development philosophy, and implementation standards that Claude Code MUST follow while contributing to the SENTRA platform.

This file is the authoritative guide for AI-assisted development.

If any generated code conflicts with this document, this document takes precedence.

---

# Project Mission

SENTRA is an explainable artificial intelligence platform for continuous physiological monitoring and clinical decision support.

The platform continuously acquires physiological signals, transforms them into clinically meaningful features, evaluates patient-specific baselines, applies evidence-based clinical rules, estimates confidence, prioritizes patients, explains every AI decision, and presents actionable information through an embedded touchscreen Hub.

Every contribution SHALL support this mission.

---

# Primary Goals

Claude SHALL optimize for

• Clinical Safety

• Explainability

• Reliability

• Maintainability

• Modularity

• Scalability

• Performance

Feature count is never more important than reliability.

---

# Documentation Hierarchy

Always treat documentation in this order.

```
CLAUDE.md

↓

ARCHITECTURE.md

↓

README.md

↓

Technical Documents (00-16)

↓

Source Code
```

Never contradict documentation without explicit instruction.

---

# Source of Truth

The architecture documentation is the source of truth.

Claude SHALL implement software according to the documented specifications.

Claude SHALL NOT invent undocumented architectures.

Claude SHALL NOT redesign major systems unless explicitly requested.

---

# Development Philosophy

Every subsystem shall

• Have one responsibility

• Be independently testable

• Expose documented interfaces

• Minimize coupling

• Maximize cohesion

• Be deterministic

• Produce explainable outputs

---

# Architecture Rules

The system SHALL remain layered.

```
Sensors

↓

Signal Processing

↓

Feature Extraction

↓

Baseline Engine

↓

Clinical Rules

↓

Subsystem Scores

↓

Confidence Fusion

↓

Priority Engine

↓

Explainability

↓

Embedded UI
```

No module may bypass another module.

No circular dependencies are permitted.

---

# Module Ownership

03

Sensor acquisition only.

04

Signal cleaning only.

05

Feature generation only.

06

Baseline learning only.

07

Clinical rules only.

08

Subsystem scoring only.

09

Confidence estimation only.

10

Priority generation only.

11

Explainability only.

16

Visualization only.

Modules SHALL NOT assume another module's responsibility.

---

# Explainability Requirements

Every AI output MUST be explainable.

Every prediction MUST expose

• Confidence

• Inputs

• Rules

• Evidence

• Contributing factors

Black-box outputs are prohibited.

---

# Clinical Safety

When uncertainty exists

Claude SHALL

Prefer conservative behavior.

Avoid dangerous assumptions.

Never fabricate medical values.

Never suppress uncertainty.

Clinical recommendations SHALL remain explainable.

---

# Coding Principles

Write code that is

Readable

Predictable

Modular

Strongly Typed

Well Documented

Testable

Self-Contained

Avoid clever code.

Prefer explicit code.

---

# File Organization

Maintain the repository structure.

```
docs/

backend/

frontend/

firmware/

hardware/

research/

tests/
```

Do not create unnecessary directories.

---

# Naming Standards

Classes

PascalCase

Functions

camelCase or snake_case according to language conventions.

Constants

UPPER_CASE

Variables

Descriptive names only.

Avoid abbreviations unless medically standard.

---

# API Rules

Every endpoint SHALL

Validate input.

Validate output.

Return typed responses.

Return meaningful errors.

Be versioned.

Never expose internal implementation.

---

# Database Rules

No hardcoded SQL.

Use migrations.

Validate schema changes.

Maintain referential integrity.

Never delete clinical records silently.

---

# Logging

Every critical action SHALL be logged.

Include

Timestamp

Module

Severity

Correlation ID

Operation

Error (if applicable)

Never log secrets.

Never log sensitive data insecurely.

---

# Error Handling

Errors SHALL

Fail safely.

Provide useful diagnostics.

Never crash the application.

Never expose internal stack traces to users.

Every exception SHALL be handled intentionally.

---

# Security

Always assume production.

Use

Authentication

Authorization

Encryption

Input validation

Output sanitization

Parameterized queries

Secure configuration

Never embed secrets.

Never hardcode credentials.

---

# Performance

Optimize only after correctness.

Performance targets

Priority Engine

<100 ms

Dashboard Refresh

<1 second

UI Interaction

<100 ms

Avoid premature optimization.

---

# Testing

Every module SHALL include

Unit Tests

Integration Tests

Edge Cases

Failure Cases

Regression Tests

No production code without tests.

---

# Frontend Standards

The UI SHALL be

Touch First

Embedded First

Responsive

Accessible

Explainable

Minimal

Modern

Every clinician interaction should require the fewest possible taps.

---

# AI Standards

Claude SHALL NOT

Invent algorithms.

Invent equations.

Invent physiological constants.

Invent clinical thresholds.

If research is required, request supporting evidence or reference the documented specification.

---

# Documentation

Every major class SHALL include

Purpose

Inputs

Outputs

Dependencies

Every public function SHALL include documentation.

---

# Git Workflow

Implement

↓

Test

↓

Document

↓

Review

↓

Commit

Never generate incomplete implementations intentionally.

---

# Preferred Development Order

1.

Backend Core

2.

Algorithms

3.

Database

4.

API

5.

Frontend

6.

Integration

7.

Testing

8.

Optimization

---

# Communication Style

When responding

Explain architectural decisions.

Reference affected modules.

Identify assumptions.

Highlight tradeoffs.

Do not make silent architectural changes.

---

# Forbidden Actions

Claude SHALL NOT

❌ Break module boundaries

❌ Duplicate business logic

❌ Skip validation

❌ Hide uncertainty

❌ Remove explainability

❌ Introduce circular dependencies

❌ Ignore documentation

❌ Sacrifice maintainability for brevity

---

# Success Definition

Every contribution should improve one or more of

Clinical reliability

Code quality

System modularity

Explainability

Developer experience

Maintainability

Scalability

Performance

---

# Final Directive

Claude is expected to behave as a senior software architect, systems engineer, and implementation partner for the SENTRA platform.

Every design decision, code contribution, refactor, test, and recommendation SHALL preserve the modular architecture defined within the SENTRA documentation while advancing the long-term vision of a clinically safe, explainable, scalable, and production-ready AI-powered patient monitoring platform.

When multiple implementation approaches are possible, prefer the solution that is the most maintainable, most transparent, easiest to validate, and most consistent with the documented architecture.

Quality shall always take precedence over speed.