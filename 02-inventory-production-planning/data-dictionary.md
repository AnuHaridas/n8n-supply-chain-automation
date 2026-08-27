# Data Dictionary

## Purpose

Define the data structure used by the Finished Goods (FG) Production Planning Automation.

The automation combines four sources:

1. Sales Demand
2. NetSuite On-Hand Inventory
3. In-Transit Supply
4. SKU Master

The workflow transforms these sources into a standardized FG Planning Output.

---

# 1. Data Grain

The core planning grain is:

> SKU × Market/Location × Month

This is important because the same product family may have different SKUs for different markets, particularly where SIM cards or market-specific configurations are involved.

Inventory is additionally stored at:

> SKU × Inventory Location

In-transit is stored at:

> SKU × Destination × Expected Arrival

---

# 2. Sales Demand

## Source

Sales demand Excel file.

## Grain

One record per:

SKU × Market × Month

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| SKU | Text | Yes | Finished-good SKU |
| SKU Description | Text | No | Product description |
| Market | Text | Yes | Demand market such as EU, CA, US |
| Month | Date/Period | Yes | Demand month |
| Demand Qty | Number | Yes | Sales demand quantity |
| Source File Date | Date | No | Date the source was generated |
| Source Row ID | Text | No | Original source-row reference |

## Example

| SKU | Market | Month | Demand Qty |
|---|---|---|---:|
| CAM-EU-001 | EU | 2026-09 | 800 |
| CAM-EU-001 | EU | 2026-10 | 900 |
| CAM-CA-001 | CA | 2026-09 | 500 |

## Transformation

n8n should:

- standardize SKU formatting
- standardize market values
- standardize month format
- convert demand quantity to numeric
- preserve the original demand quantity

Demand should not be modified by the automation.

---

# 3. NetSuite On-Hand Inventory

## Source

NetSuite inventory dump.

## Grain

One record per:

SKU × Inventory Location

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| SKU | Text | Yes | Finished-good SKU |
| Inventory Location | Text | Yes | Physical/system inventory location |
| On Hand Qty | Number | Yes | Current available/on-hand quantity |
| Snapshot Date | Date | Yes | Date/time of inventory snapshot |
| Source Row ID | Text | No | Original source-row reference |

## Example

| SKU | Inventory Location | On Hand Qty |
|---|---|---:|
| CAM-EU-001 | EU DC | 1,200 |
| CAM-CA-001 | CA DC | 450 |
| CAM-US-001 | US DC | 700 |

## Transformation

n8n should:

- standardize SKU
- standardize location names
- convert quantity to numeric
- remove/flag invalid records
- use SKU Master to determine the applicable inventory location

## Important Rule

Inventory from unrelated locations must not automatically be aggregated.

Example:

EU demand should not be satisfied using Canadian inventory unless a business rule explicitly permits it.

---

# 4. In-Transit Supply

## Source

Manually maintained Logistics file.

## Grain

One record per:

SKU × Destination × Expected Arrival

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| SKU | Text | Yes | Finished-good SKU |
| Destination | Text | Yes | Intended destination/market |
| In Transit Qty | Number | Yes | Quantity currently in transit |
| Expected Arrival | Date/Month | Ideally | Expected arrival period |
| Shipment/Reference | Text | No | Shipment or logistics reference |
| Last Updated | Date | No | Last manual update |

## Example

| SKU | Destination | In Transit Qty | Expected Arrival |
|---|---|---:|---|
| CAM-EU-001 | EU | 500 | 2026-10 |
| CAM-CA-001 | CA | 500 | 2026-11 |

## Transformation

n8n should:

- standardize SKU
- standardize destination
- convert quantity to numeric
- associate supply with the appropriate planning month
- flag missing destination
- flag missing/invalid arrival timing where timing is required

---

# 5. SKU Master

## Source

Reference/master-data table.

## Grain

One record per SKU.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| SKU | Text | Yes | Unique SKU identifier |
| SKU Description | Text | No | Product description |
| Product Type | Text | Yes | Camera / Accessory |
| Market | Text | Conditional | EU / CA / US / Other |
| Location Rule | Text | Yes | Determines applicable inventory location |
| Product Category | Text | Yes | Standard / Costco Bundle / Kit Package / Other |
| Pack Type | Text | Yes | Single / Twin / 3-Pack / 4-Pack / Other |
| Units per Pack | Number | Yes | Number of underlying units |
| Product Status | Text | Yes | Active / Discontinued |
| Manufacturer | Text | Yes | Manufacturing source |
| Manufacturing Site | Text | Yes | China / India / Other |
| MOQ | Number | Yes | Minimum production quantity |
| Production Multiple | Number | Yes | Production increment |
| Effective From | Date | No | Start date of rule |
| Effective To | Date | No | End date of rule |
| Notes | Text | No | Business context |

## Example

| SKU | Type | Market | Pack | Units | Manufacturer | MOQ | Status |
|---|---|---|---|---:|---|---:|---|
| CAM-EU-001 | Camera | EU | Single | 1 | China | 500 | Active |
| CAM-CA-002 | Camera | CA | Twin | 2 | India | 500 | Active |
| KIT-AMZ-001 | Kit | US | Kit | TBD | India | 500 | Active |

---

# 6. SKU Market / Location Logic

The SKU Master acts as the reference for determining where inventory belongs to a demand record.

Example:

Demand:

SKU = CAM-EU-001
Market = EU

SKU Master:

Market = EU
Location Rule = EU DC

Therefore:

Use EU inventory.

If the workflow encounters:

SKU = CAM-UNKNOWN-001

and no applicable location rule exists:

→ Do not guess.

→ Create a planner exception.

---

# 7. Product Status

Product Status is controlled through the SKU Master.

Possible values:

- Active
- Discontinued

A discontinued SKU may still appear in Sales demand.

This is intentionally preserved rather than deleted.

Example:

SKU = CAM-OLD-001
Status = Discontinued
Demand = 300

Output:

Production Recommendation = 0

Exception:

"Discontinued SKU has demand"

---

# 8. Pack Configuration

Pack configuration must be represented explicitly.

Examples:

Single:
Units per Pack = 1

Twin:
Units per Pack = 2

3-Pack:
Units per Pack = 3

4-Pack:
Units per Pack = 4

Costco Bundle:
Configuration defined in SKU Master

Kit Package:
Configuration/BOM defined separately.

The original FG SKU quantity should remain intact.

Where unit-level planning is required:

Underlying Units =
FG Quantity × Units per Pack

---

# 9. Manufacturing Information

Manufacturing information is required to eventually create Contract Manufacturer-specific files.

Minimum fields:

- Manufacturer
- Manufacturing Site
- MOQ
- Production Multiple

Example:

| SKU | Manufacturing Site | MOQ | Multiple |
|---|---|---:|---:|
| CAM-001 | China | 500 | 500 |
| CAM-002 | India | 500 | 500 |

This information should be maintained as master data rather than hardcoded in n8n.

---

# 10. FG Planning Output

## Purpose

The FG output is the primary deliverable of the first automation phase.

It should preserve the familiar planning structure while being generated automatically.

## Planning Grain

SKU × Market × Month

## Core Fields

| Field | Description |
|---|---|
| SKU | Finished-good SKU |
| SKU Description | Product description |
| Market | Applicable market |
| Product Type | Camera / Accessory |
| Product Category | Standard / Bundle / Kit |
| Pack Type | Single / Twin / 3-Pack / 4-Pack |
| Manufacturer | China / India |
| Status | Active / Discontinued |
| Month | Planning month |
| Demand Qty | Sales demand |
| On Hand Qty | Applicable inventory |
| In Transit Qty | Applicable inbound supply |
| Safety Stock Qty | Calculated requirement |
| Projected Supply | Calculated supply position |
| Net Production Requirement | Calculated requirement |
| Recommended Production Qty | MOQ-adjusted recommendation |
| Exception Type | Planner exception |
| Planner Comment | Human intervention |
| Planning Status | System recommendation/review status |

---

# 11. Planning Output Example

| SKU | Market | Month | Demand | On Hand | In Transit | Safety | Net Requirement | Recommended Prod |
|---|---|---|---:|---:|---:|---:|---:|---:|
| CAM-EU-001 | EU | Sep | 800 | 1,200 | 0 | 100 | 0 | 0 |
| CAM-EU-001 | EU | Oct | 900 | Projected | 500 | 100 | Calculated | Calculated |
| CAM-EU-001 | EU | Nov | 1,000 | Projected | 0 | 100 | Calculated | Calculated |

The exact projected-inventory roll-forward calculation will be finalized during implementation.

---

# 12. Exception Fields

The FG output should support planner intervention.

## Exception Type

Possible values include:

- UNKNOWN_SKU
- MISSING_SKU_MASTER
- LOCATION_MAPPING_ERROR
- MISSING_INVENTORY
- MISSING_IN_TRANSIT_DESTINATION
- MISSING_ARRIVAL_DATE
- DISCONTINUED_WITH_DEMAND
- DEMAND_BELOW_MOQ
- UNUSUAL_PRODUCTION_QTY
- CONFLICTING_MASTER_DATA
- OTHER

## Planner Comment

Free-text field for human intervention.

Example:

"Do not produce — low Amazon demand. Review next month."

---

# 13. Data Lineage

Every generated recommendation should be traceable back to its source data.

At minimum, the system should retain:

- Source file
- Source date
- Source row/reference where practical
- Workflow execution date
- SKU
- Planning month

This allows the planner to answer:

> "Where did this production recommendation come from?"

---

# 14. Data Validation Principles

The workflow should fail visibly rather than silently producing bad planning data.

Examples:

Missing SKU
→ Exception

Unknown location
→ Exception

Duplicate master record
→ Exception

Non-numeric quantity
→ Exception

Discontinued SKU with demand
→ Exception

Missing in-transit destination
→ Exception

The objective is not merely automation.

The objective is:

> Reliable automation with visible uncertainty.

---

# 15. Source-of-Truth Hierarchy

For the first version:

Sales Demand
→ source of truth for demand

NetSuite
→ source of truth for on-hand inventory

Logistics In-Transit File
→ source of truth for in-transit supply

SKU Master
→ source of truth for SKU interpretation and planning attributes

FG Planning Engine
→ source of truth for the generated production recommendation

Planner
→ final authority for exceptions and business judgment

---

# 16. Data Model Principle

The automation should separate:

SOURCE DATA
from
REFERENCE DATA
from
CALCULATED DATA
from
HUMAN DECISIONS.

This prevents the problems experienced in the previous Excel process where data, formulas, master data, and manual overrides were mixed together.
