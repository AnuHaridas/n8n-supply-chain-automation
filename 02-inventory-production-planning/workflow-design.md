# FG Production Planning — Workflow Design

## Objective

Automatically generate the Finished Goods (FG) planning file every day using:

- Sales Demand
- NetSuite On-Hand Inventory
- In-Transit Supply
- SKU Master

The workflow calculates a six-month production requirement and surfaces exceptions for planner review.

---

## High-Level Flow

Sales Demand ───────┐
NetSuite Inventory ─┤
In-Transit ─────────┤
SKU Master ─────────┘
         ↓
   Validate Inputs
         ↓
   Normalize Data
         ↓
   Match SKU + Market + Location
         ↓
   Build 6-Month Supply Position
         ↓
   Calculate Production Requirement
         ↓
   Apply MOQ / Production Multiple
         ↓
   Apply SKU Status & Business Rules
         ↓
   Generate Exceptions
         ↓
   Generate FG Planning File
