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


n8n Architecture
1. Trigger

Schedule Trigger

Runs once per day
Retrieves the latest available source data
Generates/replaces the current FG planning output
2. Input Layer

Four independent input workflows/nodes:

Sales Demand
NetSuite Inventory
In-Transit
SKU Master

Keep sources separate until validation and normalization are complete.

3. Normalize

Standardize:

SKU
Market
Location
Quantity
Month
Dates
Status values

Do not change business meaning.

4. Validate

Check for:

Missing/unknown SKUs
Duplicate master records
Missing market/location
Invalid quantities
Discontinued SKUs with demand
Missing in-transit destination
Missing required arrival information

Invalid records become exceptions.

5. Combine

Use SKU Master to interpret each SKU.

Match:

Demand
↔ SKU Master
↔ Applicable Inventory
↔ Applicable In-Transit

Core planning grain:

SKU × Market × Month

6. Six-Month Planning Engine

For each SKU:

Start with applicable supply.
Apply in-transit supply in the appropriate month.
Consume supply against monthly demand.
Maintain required safety stock.
Calculate projected supply position.
Identify the month where additional production is required.
Calculate required production quantity.
Apply MOQ / production multiple.

The exact safety-stock formula will be added once confirmed.

7. Business Rules

Apply:

Discontinued SKU → no production
Discontinued SKU + demand → exception
Unknown SKU → exception
Invalid location mapping → exception
Demand below MOQ → planner review
Production quantity → applicable production multiple
Pack configuration → convert to underlying units where required
8. Output

Generate the FG Planning File.

The output contains:

SKU details
Market
Product type/category
Pack type
Manufacturer
Monthly demand
Inventory
In-transit
Safety stock
Projected supply
Production requirement
Recommended production
Exceptions
Planner comment

The output should replace the previous day's generated file rather than create uncontrolled versions.

9. Human Review

The system does NOT automatically commit production.

Planner reviews:

Exceptions
Low-demand/MOQ situations
Discontinued demand
Ambiguous inventory
Unusual recommendations

Planner comments/interventions are preserved.

Later Phases
Phase 2

Generate China and India CM files from the approved FG plan.

Phase 3

Add BOM explosion and component requirements.

Phase 4

Add smarter planning/AI capabilities where they genuinely add value.

Phase 5

Add resilience/error handling and monitoring.

Design Principle

Keep the workflow simple.

Use n8n for:

orchestration
data movement
validation
business-rule routing
file generation

Use code only where calculations become easier or clearer in code.

Do not create unnecessary nodes when one well-designed transformation can perform the job.


