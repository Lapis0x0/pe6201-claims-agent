# PE6201 A2 — Health-Insurance Claim First Response Agent

**Course:** PE6201 Emerging AI Technologies  
**Programme:** MSc Enterprise Artificial Intelligence, Nanyang Technological University  
**Assessment:** A2 — Applied AI System  
**Problem:** A — Health-Insurance Claim First Response

## Overview

This project implements a **single-agent ReAct system** for health-insurance claim first-response processing.

The agent receives a claim, dynamically retrieves the required information using tools, evaluates the claim against policy, coverage, pre-authorisation, hospital and supporting-document information, and produces one of three outcomes:

- **Approve in principle**
- **Request a specific missing document**
- **Escalate** the claim to a human assessor

The system follows a tool-using **Reason → Act → Observe → Repeat → Final** loop, with explicit guardrails around the gated decision action.

## Problem A — Health-Insurance Claim First Response

The agent works with claim, member, policy, coverage, pre-authorisation, hospital and document information to determine the appropriate first response for a health-insurance claim.

The core workflow is:

**Claim → Member & Policy → Coverage Checks → Pre-authorisation / Hospital / Documents → Approve / Request / Escalate**

The decision-letter action is simulated locally and does **not** send a real letter or modify any live insurance system.

## Team

**Team ID:** B-9  
**Section:** B

| # | Team Member |
|---|---|
| 1 | JIANG DONG |
| 2 | LIU WEIQI |
| 3 | NIU DUOER |
| 4 | SHI ZHIYUN |
| 5 | UBAIDULLA ASMITHA |
| 6 | XU LIANGJUAN |