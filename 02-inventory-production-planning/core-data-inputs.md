
# Core Data Inputs

## Purpose

The automation combines three operational data sources to generate a Finished Goods (FG) production-planning file.

The automation does not generate or modify demand.

Demand is treated as an input from Sales.

The objective is to replace the manual Excel-based process used to determine how much of each finished-good SKU should be produced based on:

- Demand
- On-hand inventory
- Inventory by location
- In-transit supply

A separate SKU Master is used as reference data to interpret SKU characteristics, market/location rules, product type, manufacturing information, and product status.

---

# 1. Demand Input

## Business Owner

Sales / Commercial team

## Source

Sales demand file / Excel

## Purpose

Provides the expected demand for each finished-good SKU by month.

## Key Principle

The Production Analyst does NOT calculate or modify demand.

Demand is an input to the production-planning process.

## Expected Granularity

SKU + market/location + month

## Example

| SKU | SKU Description | Market | Sep | Oct | Nov | Dec | Jan | Feb |
|---|---|---|---:|---:|---:|---:|---:|---:|
| CAM-001-EU | Camera EU | EU | 500 | 600 | 700 | 650 | 800 | 900 |
| CAM-001-CA | Camera Canada | CA | 300 | 350 | 400 | 450 | 500 | 550 |

## Important Characteristics

- Monthly demand horizon
- Market/location-specific demand
- New SKUs may be introduced
- Discontinued SKUs may still appear
- Product bundles/kits may have different demand structures
- Demand may contain data-quality issues

## Automation Requirement

The workflow should validate that all expected SKUs are represented and identify unexpected or missing SKU mappings without changing the underlying demand.

---

# 2. NetSuite Inventory Input

## Business Owner

Inventory / Operations

## Source

NetSuite inventory dump

## Purpose

Provides current on-hand inventory.

## Expected Granularity

SKU + location

## Example

| SKU | Location | On Hand |
|---|---|---:|
| CAM-001-EU | Europe | 1200 |
| CAM-001-CA | Canada | 450 |
| CAM-001-US | USA | 700 |

## Critical Business Issue

Inventory must NOT simply be summed across all locations.

The relevant inventory depends on the SKU's market/location rules.

For example:

- EU-specific SKU → EU inventory
- Canada-specific SKU → Canada inventory
- USA-specific SKU → USA inventory
- Global/non-market-specific SKU → business rule determines applicable inventory

The automation must therefore use the SKU Master to determine which inventory location is relevant.

## Automation Requirement

The workflow should:

1. Load the NetSuite inventory dump.
2. Standardize SKU and location fields.
3. Match each SKU to its applicable market/location rule.
4. Select the relevant inventory.
5. Flag ambiguous or unmapped SKU/location combinations for planner review.

---

# 3. In-Transit Input

## Business Owner

Logistics / Supply Chain

## Source

Manually maintained in-transit file

## Purpose

Provides supply that has already been shipped or is expected to arrive but is not yet reflected in on-hand inventory.

## Expected Granularity

SKU + destination/location + quantity

## Example

| SKU | Destination | In Transit Qty | Expected Arrival |
|---|---|---:|---|
| CAM-001-EU | EU | 500 | Sep |
| CAM-001-CA | CA | 500 | Oct |

## Current-State Reality

The source is manually maintained by Logistics.

The automation should NOT initially attempt to automate the Logistics team's process.

Instead, it should consume the maintained file as an operational input.

## Automation Requirement

The workflow should:

- Read the latest in-transit file.
- Standardize SKU and destination fields.
- Match in-transit quantities to the correct market/location.
- Include applicable in-transit supply in production calculations.
- Flag SKUs with missing or ambiguous destination information.

---

# 4. SKU Master

## Type

Reference / Master Data

## Purpose

Provides the business rules required to correctly interpret the three operational inputs.

The SKU Master prevents business logic from being hardcoded throughout the workflow.

## Expected Fields

| Field | Purpose |
|---|---|
| SKU | Unique product identifier |
| SKU Description | Product description |
| Product Type | Camera / Accessory |
| Market | EU / CA / US / Other |
| Location Rule | Determines which inventory location applies |
| Product Category | Standard / Costco Bundle / Kit Package / Other |
| Pack Type | Single / Twin / 3-Pack / 4-Pack |
| Units per Pack | Conversion to underlying units |
| Manufacturer | China / India / Other |
| Manufacturing Site | Production location |
| MOQ | Minimum production quantity |
| Status | Active / Discontinued |
| Effective Date | Date the SKU rule becomes active |
| Notes | Planner/business context |

## Important Design Principle

Business rules should be maintained as data wherever practical.

The workflow should NOT contain large numbers of hardcoded SKU-specific IF statements.

Example:

Instead of:

IF SKU = "ABC123" → EU  
IF SKU = "ABC124" → Canada  
IF SKU = "ABC125" → USA

the workflow should reference:

SKU Master → Market / Location Rule

This allows new SKUs and rule changes to be handled through master data rather than rebuilding the workflow.

---

# 5. Relationship Between Inputs

The three operational inputs are combined using SKU and applicable location/market rules.

Conceptually:

Demand
+
NetSuite On-Hand Inventory
+
In-Transit Supply
+
SKU Master reference rules
↓
Finished Goods Production Planning
↓
FG Planning File

The automation should preserve the source data separately before combining it.

---

# 6. Data Ownership

| Data | Owner | Automated Initially? |
|---|---|---|
| Demand | Sales | No |
| On-Hand Inventory | NetSuite | Yes / automated extraction or file input |
| In-Transit | Logistics | No |
| SKU Master | Supply Chain / Master Data | Initially maintained reference table |
| Production Recommendation | Production Analyst / Supply Chain | Automated calculation |

---

# 7. Data Quality Checks

Before calculating production requirements, the workflow should identify:

- Missing SKU
- Unknown SKU
- Duplicate SKU records
- Missing market/location
- Invalid location mapping
- Missing demand
- Missing inventory
- Missing in-transit information
- Discontinued SKU with demand
- New SKU not present in SKU Master
- SKU with conflicting market/location rules
- Unexpected product/pack type

These should be treated as exceptions rather than silently producing potentially incorrect production quantities.

---

# 8. Scope Boundary

This automation does not initially:

- Generate demand
- Forecast demand
- Replace the Sales demand process
- Replace NetSuite
- Automate Logistics' shipment updates
- Calculate BOM/component requirements
- Create purchase orders
- Automatically send production commitments to Contract Manufacturers

These may become later stages of the solution.

The first objective is to reliably generate the Finished Goods production-planning view.

---

# 9. Target Output

The primary output is an automatically generated Finished Goods (FG) planning file.

For each SKU, the file should show the monthly demand and supply position used to determine the production requirement.

Example structure:

| SKU | SKU Desc | Metric | Sep | Oct | Nov | Dec | Jan | Feb |
|---|---|---|---:|---:|---:|---:|---:|---:|
| CAM-001-EU | Camera EU | Demand | 500 | 600 | 700 | 650 | 800 | 900 |
| CAM-001-EU | Camera EU | Inventory | 1200 | | | | | |
| CAM-001-EU | Camera EU | In Transit | 500 | 0 | 0 | 0 | 0 | 0 |
| CAM-001-EU | Camera EU | Safety | Business rule | | | | | |
| CAM-001-EU | Camera EU | Total Prod | Calculated | Calculated | Calculated | Calculated | Calculated | Calculated |

The exact production calculation rules will be defined separately in `business-rules.md`.

---

# 10. Design Principle

The automation should make the production analyst's job:

DATA → VALIDATE → CALCULATE → REVIEW EXCEPTIONS → COMMUNICATE

rather than:

OPEN 5 FILES → WAIT FOR EXCEL → DEBUG FORMULAS → VLOOKUP → CHECK LOCATIONS → COPY/PASTE → RECHECK → CHANGE FORMULAS → EMAIL PEOPLE → PANIC
