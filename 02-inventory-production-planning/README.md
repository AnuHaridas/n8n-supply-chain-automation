# Inventory & Production Planning Automation

## Business Problem

Production planning requires bringing together multiple sources of supply and demand information to determine how much of each finished good should be produced.

In the current manual process, information may come from:

- Monthly demand
- On-hand inventory
- Inventory by location
- In-transit supply
- Product status
- New product launches
- Discontinued products
- Production constraints
- Bill of Materials (BOM)
- Contract manufacturer requirements

When these inputs are maintained across multiple spreadsheets and manual processes, planners may spend significant time validating numbers rather than making planning decisions.

## Objective

Design an n8n-based workflow that:

1. Collects the required planning inputs
2. Standardizes and validates the data
3. Determines the supply position of each SKU
4. Calculates production requirements
5. Applies production constraints such as MOQ
6. Identifies exceptions requiring human attention
7. Generates production-ready outputs for contract manufacturers
8. Supports downstream BOM/component planning

## Core Principle

The automation should reduce repetitive calculation, reconciliation, and checking.

It should **not replace the planner's judgment** where business context or commercial decisions are required.

## Project Status

Planning and architecture phase.
